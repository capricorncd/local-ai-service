from asset_references import sync_asset_references
import shutil
import sqlite3
from contextlib import closing
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException
from domain import Project, Chapter, Episode


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


class Store:
    def __init__(self, home):
        self.home = Path(home).resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.database = self.home / 'story.sqlite3'
        with closing(self.connect()) as db, db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, directory TEXT UNIQUE NOT NULL, document TEXT, name_key TEXT UNIQUE)')
            db.execute('CREATE TABLE IF NOT EXISTS history (project_id TEXT NOT NULL, revision INTEGER NOT NULL, reason TEXT NOT NULL, document TEXT NOT NULL, PRIMARY KEY(project_id, revision))')
            registry = self.home / 'projects.json'
            if registry.exists():
                for id, directory in json.loads(registry.read_text('utf-8')).items():
                    db.execute('INSERT OR IGNORE INTO projects (id, directory, document) VALUES (?, ?, NULL)', (id, str(Path(directory).resolve())))
        for id in self.roots:
            with closing(self.connect()) as db:
                row = db.execute('SELECT document FROM projects WHERE id=?', (id,)).fetchone()
            if row[0] is None:
                try: self.load(id)
                except HTTPException: pass

    def connect(self):
        return sqlite3.connect(self.database, timeout=30)

    @property
    def roots(self):
        with closing(self.connect()) as db:
            return dict(db.execute('SELECT id, directory FROM projects'))

    def root(self, id):
        with closing(self.connect()) as db:
            row = db.execute('SELECT directory FROM projects WHERE id=?', (id,)).fetchone()
        if row is None: raise HTTPException(404, '项目不存在')
        return Path(row[0])

    def _import_legacy(self, db, root, project):
        for path in sorted((root / 'history').glob('*.json')):
            snapshot = json.loads(path.read_text('utf-8'))
            old = Project.model_validate(snapshot['project'])
            db.execute('INSERT OR IGNORE INTO history VALUES (?, ?, ?, ?)',
                       (project.id, old.revision, snapshot['reason'], old.model_dump_json()))
        db.execute('INSERT INTO projects VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET document=excluded.document, name_key=excluded.name_key',
                   (project.id, str(root), project.model_dump_json(), project.name.strip().casefold()))

    def load(self, id):
        with self.lock, closing(self.connect()) as db, db:
            row = db.execute('SELECT directory, document FROM projects WHERE id=?', (id,)).fetchone()
            if row is None: raise HTTPException(404, '项目不存在')
            if row[1] is not None: return Project.model_validate_json(row[1])
            try:
                project = Project.model_validate_json((Path(row[0]) / 'story.json').read_text('utf-8'))
                if project.id != id: raise ValueError('项目 ID 不匹配')
                self._import_legacy(db, Path(row[0]), project)
                return project
            except (OSError, ValueError) as e:
                raise HTTPException(409, f'无法读取旧项目：{e}')

    def register(self, directory='', name=None, default_directory=''):
        project = Project(name=name.strip() or '未命名', chapters=[Chapter(episodes=[Episode()])]) if name is not None else None
        if project is not None and not name.strip(): project.name = project.id
        if not directory.strip():
            if project is None: raise HTTPException(422, '请选择要打开的项目目录')
            directory = str((Path(default_directory).expanduser() if default_directory else self.home / 'projects') / self.folder_name(project.name))
        root = Path(directory).expanduser()
        if not root.is_absolute(): raise HTTPException(422, '请选择绝对目录路径')
        root = root.resolve()
        with self.lock, closing(self.connect()) as db, db:
            if project is not None: self.check_name(db, project)
            existing = db.execute('SELECT id FROM projects WHERE directory=?', (str(root),)).fetchone()
            if existing:
                if name is not None: raise HTTPException(409, '目录已有项目，请使用打开项目')
                return self.load(existing[0])
            if project is None:
                try: project = Project.model_validate_json((root / 'story.json').read_text('utf-8'))
                except (OSError, ValueError) as e: raise HTTPException(422, f'目录中没有有效的 story.json：{e}')
                if db.execute('SELECT id FROM projects WHERE id=?', (project.id,)).fetchone():
                    raise HTTPException(409, '同 ID 项目已从其他目录打开；请使用原目录')
                self._import_legacy(db, root, project)
            else:
                if (root / 'story.json').exists(): raise HTTPException(409, '目录已有项目，请使用打开项目')
                project.updated = datetime.now(timezone.utc).isoformat()
                db.execute('INSERT INTO projects VALUES (?, ?, ?, ?)', (project.id, str(root), project.model_dump_json(), project.name.strip().casefold()))
            (root / 'media').mkdir(parents=True, exist_ok=True)
            return project

    @staticmethod
    def folder_name(name):
        folder = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', name).strip().rstrip('. ')
        if not folder or folder.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *[f'COM{i}' for i in range(1,10)], *[f'LPT{i}' for i in range(1,10)]}:
            folder = '_' + folder
        return folder

    @staticmethod
    def check_name(db, project):
        row = db.execute('SELECT id FROM projects WHERE name_key=? AND id<>?', (project.name.strip().casefold(), project.id)).fetchone()
        if row: raise HTTPException(409, '项目名称已存在，请使用其他名称')

    def save(self, id, project, reason='自动保存'):
        with self.lock, closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT document, directory FROM projects WHERE id=?', (id,)).fetchone()
            if row is None: raise HTTPException(404, '项目不存在')
            old = Project.model_validate_json(row[0])
            if project.id != id or project.revision != old.revision:
                raise HTTPException(409, '项目已在其他窗口修改，请保留当前草稿后重新打开项目')
            project = project.model_copy(deep=True)
            sync_asset_references(project, old)
            project.name = project.name.strip() or project.id
            if project.model_dump(exclude={'revision', 'updated'}) == old.model_dump(exclude={'revision', 'updated'}):
                return old
            for relative in [v for a in project.assets for v in (a.image,a.voice)] + [v for c in project.chapters for e in c.episodes for s in e.shots for v in (s.image,s.audio)]:
                if relative: self.media(id,relative)
            db.execute('INSERT INTO history VALUES (?, ?, ?, ?)', (id, old.revision, reason, old.model_dump_json()))
            project = project.model_copy(deep=True)
            project.revision += 1
            project.updated = datetime.now(timezone.utc).isoformat()
            project.name = project.name.strip() or project.id
            self.check_name(db, project)
            root = Path(row[1]).resolve()
            target = root.parent / self.folder_name(project.name) if project.name != old.name else root
            target = target.resolve()
            if target.parent != root.parent: raise HTTPException(422, '无效项目目录')
            moved = False
            if target != root:
                if target.exists(): raise HTTPException(409, '目标项目目录已存在，未覆盖，请换一个名称')
                if root.exists():
                    shutil.move(str(root), str(target))
                    moved = True
            try:
                db.execute('UPDATE projects SET document=?, directory=?, name_key=? WHERE id=?',
                           (project.model_dump_json(), str(target), project.name.casefold(), id))
                db.commit()
            except Exception:
                if moved: shutil.move(str(target), str(root))
                raise
            return project

    def media(self, id, relative):
        if not re.fullmatch(r'media/[a-f0-9]{32}\.(png|jpg|jpeg|webp|wav|mp3|ogg|flac|m4a)', relative):
            raise HTTPException(422, '无效素材路径')
        root = self.root(id).resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root / 'media') or not path.is_file():
            raise HTTPException(404, '素材不存在')
        return path

    def history(self, id, revision):
        if not re.fullmatch(r'\d{8}', revision): raise HTTPException(404, '版本不存在')
        with closing(self.connect()) as db:
            row = db.execute('SELECT reason, document FROM history WHERE project_id=? AND revision=?', (id, int(revision))).fetchone()
        if row is None: raise HTTPException(404, '版本不存在')
        return {'reason': row[0], 'project': json.loads(row[1])}

    def versions(self, id):
        self.root(id)
        with closing(self.connect()) as db:
            rows = db.execute('SELECT revision, reason, document FROM history WHERE project_id=? ORDER BY revision DESC', (id,)).fetchall()
        return [{'id': f'{revision:08}', 'revision': revision, 'reason': reason,
                 'updated': json.loads(document)['updated'], 'name': json.loads(document)['name']}
                for revision, reason, document in rows]
