"""PNG iTXt metadata without pixel re-encoding. Python standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import zlib

SIGNATURE = b'\x89PNG\r\n\x1a\n'
KEY = 'ImageAssetMetadata'
OWNED = {KEY, 'Description', 'GenerationPrompt'}


def chunks(data):
    if not data.startswith(SIGNATURE):
        raise ValueError('Only PNG is supported; do not rename another format to .png')
    pos = 8
    while pos < len(data):
        if pos + 12 > len(data):
            raise ValueError('Truncated PNG')
        n = struct.unpack('>I', data[pos:pos+4])[0]
        end = pos + 12 + n
        if end > len(data):
            raise ValueError('Truncated PNG chunk')
        typ = data[pos+4:pos+8]
        payload = data[pos+8:pos+8+n]
        crc = struct.unpack('>I', data[pos+8+n:end])[0]
        if zlib.crc32(typ + payload) & 0xffffffff != crc:
            raise ValueError('PNG CRC mismatch')
        yield typ, payload, data[pos:end]
        pos = end
        if typ == b'IEND':
            if pos != len(data):
                raise ValueError('Unexpected data after IEND; refuse to discard it')
            return
    raise ValueError('Missing IEND')


def text_chunk(typ, payload):
    if typ not in (b'iTXt', b'tEXt', b'zTXt'):
        return None
    key, rest = payload.split(b'\x00', 1)
    key = key.decode('latin1')
    if typ == b'tEXt':
        return key, rest.decode('latin1')
    if typ == b'zTXt':
        return key, zlib.decompress(rest[1:]).decode('latin1')
    flag, method = rest[0], rest[1]
    language, translated, text = rest[2:].split(b'\x00', 2)
    if flag:
        if method != 0:
            raise ValueError('Unsupported PNG text compression')
        text = zlib.decompress(text)
    return key, text.decode('utf8')


def itxt(key, value):
    payload = key.encode('latin1') + b'\x00\x00\x00\x00\x00' + value.encode('utf8')
    typ = b'iTXt'
    return struct.pack('>I', len(payload)) + typ + payload + struct.pack('>I', zlib.crc32(typ+payload) & 0xffffffff)


def image_digest(data):
    # All critical pixel chunks plus color, alpha and animation chunks.
    names = {b'IHDR', b'PLTE', b'IDAT', b'IEND', b'tRNS', b'iCCP', b'gAMA', b'cHRM', b'sRGB', b'acTL', b'fcTL', b'fdAT'}
    return hashlib.sha256(b''.join(raw for typ, _, raw in chunks(data) if typ in names)).hexdigest()


def read(path):
    texts = {}
    for typ, payload, _ in chunks(Path(path).read_bytes()):
        pair = text_chunk(typ, payload)
        if pair:
            texts[pair[0]] = pair[1]
    return json.loads(texts[KEY]) if KEY in texts else None


def validate(record):
    if record.get('schema_version') != 1:
        raise ValueError('schema_version must be 1')
    for field in ('asset_name', 'asset_type', 'generation_prompt_source', 'generation_mode'):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError('Missing field: '+field)
    if record['asset_type'] not in ('character','scene','prop','reference_sheet','image'):
        raise ValueError('Unknown asset_type')
    status = record.get('generation_prompt_status')
    prompt = record.get('generation_prompt')
    if status == 'exact':
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError('Exact status requires the exact prompt')
    elif status == 'unavailable':
        if prompt is not None:
            raise ValueError('Unavailable original prompt must be null')
    else:
        raise ValueError('Invalid prompt status')
    if not isinstance(record.get('reference_images'), list):
        raise ValueError('reference_images must be an array')
    if record['asset_type'] != 'image':
        if not record.get('setting_description') or not isinstance(record.get('consistency_constraints'), list):
            raise ValueError('Reference sheets require description and constraints')


def write(path, record, backup_dir):
    validate(record)
    path = Path(path).resolve()
    old = path.read_bytes()
    previous = read(path)
    if previous is None:
        for typ, payload, _ in chunks(old):
            if typ in (b'iTXt',b'tEXt',b'zTXt') and payload.split(b'\x00',1)[0].decode('latin1') in OWNED:
                raise ValueError('Existing metadata key collision; refuse to overwrite unrelated metadata')
    elif previous.get('generation_prompt') != record.get('generation_prompt'):
        record = dict(record)
        history = list(previous.get('generation_history',[]))
        history.append({k:v for k,v in previous.items() if k.startswith('generation_') and k != 'generation_history'})
        record['generation_history'] = history
    before = image_digest(old)
    canonical = json.dumps(record, ensure_ascii=False, separators=(',', ':'))
    if len(canonical.encode('utf8')) > 2_000_000:
        raise ValueError('Metadata exceeds 2MB limit')
    values = {KEY: canonical, 'Description': record.get('setting_description', ''),
              'GenerationPrompt': record.get('generation_prompt') or '[UNAVAILABLE] ' + record['generation_prompt_source']}
    parts = [SIGNATURE]
    for typ, payload, raw in chunks(old):
        if typ in (b'iTXt', b'tEXt', b'zTXt'):
            key = payload.split(b'\x00', 1)[0].decode('latin1')
            if key in OWNED:
                continue
        if typ == b'IEND':
            parts.extend(itxt(k, v) for k, v in values.items())
        parts.append(raw)
    new = b''.join(parts)
    if image_digest(new) != before:
        raise ValueError('Pixel-data digest changed')
    # Every unrelated chunk must survive byte-for-byte and in order.
    def retained(data):
        return [raw for t, p, raw in chunks(data) if not (t in (b'iTXt', b'tEXt', b'zTXt') and p.split(b'\x00',1)[0].decode('latin1') in OWNED)]
    if retained(old) != retained(new):
        raise ValueError('Unrelated chunks changed')
    if new == old:
        return {'path':str(path), 'status':'unchanged', 'pixel_data_sha256':before}
    backup_dir = Path(backup_dir).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / (hashlib.sha256(old).hexdigest() + '.png')
    if not backup.exists():
        shutil.copy2(path, backup)
    elif hashlib.sha256(backup.read_bytes()).digest() != hashlib.sha256(old).digest():
        raise ValueError('Backup hash mismatch')
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.metadata-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(new)
            f.flush()
            os.fsync(f.fileno())
        if read(tmp) != record:
            raise ValueError('Metadata read-back mismatch')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return {'path':str(path), 'status':'updated', 'backup':str(backup), 'pixel_data_sha256':before}


def subject(record, subject_number, picture_number):
    validate(record)
    if record['asset_type'] != 'character':
        raise ValueError('Subject template is for a single character; read other assets as scene/prop data')
    if subject_number < 1 or picture_number < 1:
        raise ValueError('Subject and Picture numbers must be positive')
    text = f'<Subject {subject_number}> 是 <Picture {picture_number}> 中的' + record['setting_description']
    constraints = record.get('consistency_constraints', [])
    if constraints:
        text += '\n一致性要求：' + '；'.join(constraints) + '。'
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('read','write','subject'):
        p = sub.add_parser(name)
        p.add_argument('image')
        if name == 'write':
            p.add_argument('--metadata', required=True)
            p.add_argument('--backup-dir', required=True)
        if name == 'subject':
            p.add_argument('--subject', type=int, default=1)
            p.add_argument('--picture', type=int, default=1)
    args = parser.parse_args()
    if args.command == 'write':
        record = json.loads(Path(args.metadata).read_text(encoding='utf-8-sig'))
        print(json.dumps(write(args.image, record, args.backup_dir), ensure_ascii=False))
    else:
        record = read(args.image)
        if args.command == 'subject':
            if record is None:
                raise ValueError('Image has no ImageAssetMetadata')
            print(subject(record, args.subject, args.picture))
        else:
            print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
