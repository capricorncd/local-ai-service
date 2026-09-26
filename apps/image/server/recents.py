"""Bounded operation snapshots, with shared image payloads stored only once."""
import hashlib
import json
import sqlite3
import time
import uuid

class RecentStore:
    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS recent_operations (
                    id TEXT PRIMARY KEY, created REAL, name TEXT, mode TEXT,
                    prompt TEXT, layers INTEGER, fingerprint TEXT, content TEXT);
                CREATE TABLE IF NOT EXISTS recent_assets (hash TEXT PRIMARY KEY, data TEXT);
                CREATE TABLE IF NOT EXISTS recent_links (operation TEXT, asset TEXT,
                    PRIMARY KEY(operation,asset));
            ''')

    def save(self, project):
        value = project.model_dump()
        fingerprint = hashlib.sha256(project.model_dump_json().encode()).hexdigest()
        assets = {}
        def asset(data):
            key = hashlib.sha256(data.encode()).hexdigest()
            assets[key] = data
            return key
        for layer in value['layers']:
            layer['source'] = asset(layer['source'])
        if value['mask']:
            value['mask'] = asset(value['mask'])
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            latest = db.execute('SELECT id,fingerprint FROM recent_operations ORDER BY rowid DESC LIMIT 1').fetchone()
            if latest and latest[1] == fingerprint:
                return {'id':latest[0]}
            id = uuid.uuid4().hex
            db.execute('INSERT INTO recent_operations VALUES(?,?,?,?,?,?,?,?)',
                (id,time.time(),project.name,project.mode,project.prompt,len(project.layers),fingerprint,json.dumps(value,ensure_ascii=False)))
            db.executemany('INSERT OR IGNORE INTO recent_assets VALUES(?,?)',assets.items())
            db.executemany('INSERT INTO recent_links VALUES(?,?)',((id,key) for key in assets))
            db.execute('DELETE FROM recent_operations WHERE id IN (SELECT id FROM recent_operations ORDER BY rowid DESC LIMIT -1 OFFSET 30)')
            db.execute('DELETE FROM recent_links WHERE operation NOT IN (SELECT id FROM recent_operations)')
            db.execute('DELETE FROM recent_assets WHERE hash NOT IN (SELECT asset FROM recent_links)')
            return {'id':id}

    def list(self):
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute('SELECT id,created,name,mode,prompt,layers FROM recent_operations ORDER BY rowid DESC')]

    def get(self, id):
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN')
            row = db.execute('SELECT content FROM recent_operations WHERE id=?',(id,)).fetchone()
            if row is None:
                return None
            value = json.loads(row[0])
            assets = dict(db.execute('SELECT hash,data FROM recent_assets WHERE hash IN (SELECT asset FROM recent_links WHERE operation=?)',(id,)))
            for layer in value['layers']:
                layer['source'] = assets[layer['source']]
            if value['mask']:
                value['mask'] = assets[value['mask']]
            return value
