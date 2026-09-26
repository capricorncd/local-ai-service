"""Explicit, cancellable model download from the official repository only."""
import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import threading
from urllib.request import urlopen
from urllib.parse import quote

REPO = 'BreezeBlue/Breeze-TTS-2'

class BreezeDownload:
    def __init__(self, target):
        self.target = Path(target)
        self.state = {'status': 'idle', 'downloaded': 0, 'total': 0, 'file': '', 'error': ''}
        self.cancelled = threading.Event()
        self.task = None

    def snapshot(self):
        return dict(self.state)

    def start(self, complete):
        if self.task and not self.task.done():
            return self.snapshot()
        self.cancelled.clear()
        self.state = {'status': 'running', 'downloaded': 0, 'total': 0, 'file': '', 'error': ''}
        self.task = asyncio.create_task(self.run(complete))
        return self.snapshot()

    async def run(self, complete):
        try:
            await asyncio.to_thread(self.download)
            if self.cancelled.is_set():
                self.state['status'] = 'cancelled'
                return
            await complete(str(self.target))
            self.state['status'] = 'succeeded'
        except Exception as error:
            self.state.update(status='cancelled' if self.cancelled.is_set() else 'failed', error=str(error))

    def download(self):
        with urlopen(f'https://huggingface.co/api/models/{REPO}?blobs=true', timeout=30) as response:
            metadata = json.load(response)
        revision = metadata['sha']
        if not isinstance(revision, str) or len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
            raise ValueError('Invalid model revision')
        files = [f for f in metadata['siblings'] if f['rfilename'].endswith(('.json', '.safetensors', '.txt', '.model')) or f['rfilename'] == 'LICENSE']
        self.target.mkdir(parents=True, exist_ok=True)
        total = sum(f['size'] for f in files)
        self.state['total'] = total
        needed = sum(f['size'] for f in files if not (self.target / f['rfilename']).is_file())
        if shutil.disk_usage(self.target).free < needed + 512 * 1024 * 1024:
            raise RuntimeError('磁盘空间不足，无法下载 Breeze 模型')
        finished = 0
        for item in files:
            if self.cancelled.is_set():
                return
            name = item['rfilename']
            path = (self.target / name).resolve()
            if not path.is_relative_to(self.target.resolve()) or '\\' in name or ':' in name:
                raise ValueError('Invalid model filename')
            expected_hash = (item.get('lfs') or {}).get('sha256')
            self.state['file'] = name
            def valid():
                if not path.is_file() or path.stat().st_size != item['size']:
                    return False
                if not expected_hash:
                    return True
                with path.open('rb') as source:
                    return hashlib.file_digest(source, 'sha256').hexdigest() == expected_hash
            if not valid():
                path.parent.mkdir(parents=True, exist_ok=True)
                partial = path.with_name(path.name + '.part')
                digest = hashlib.sha256()
                received = 0
                with urlopen(f'https://huggingface.co/{REPO}/resolve/{revision}/{quote(name, safe="/")}', timeout=30) as response, partial.open('wb') as target:
                    while chunk := response.read(1024 * 1024):
                        if self.cancelled.is_set():
                            return
                        target.write(chunk)
                        digest.update(chunk)
                        received += len(chunk)
                        self.state['downloaded'] = finished + received
                if received != item['size'] or (expected_hash and digest.hexdigest() != expected_hash):
                    raise RuntimeError('下载文件校验失败：' + name)
                partial.replace(path)
            finished += item['size']
            self.state['downloaded'] = finished
        (self.target / 'download-revision.json').write_text(json.dumps({'repo': REPO, 'revision': revision}), 'utf-8')
