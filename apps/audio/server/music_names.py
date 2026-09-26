from datetime import datetime
import re


def song_titles(title, count):
    title = title.strip()
    if not title:
        prefix = datetime.now().strftime('%Y%m%d-%H%M%S')
        return [f'{prefix}_{i + 1}' for i in range(count)]
    return [title if count == 1 else f'{title}_{i + 1}' for i in range(count)]


def song_filename(title):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title).strip().rstrip('. ')
    if not name or re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', name):
        name = '_' + name
    return name[:140]
