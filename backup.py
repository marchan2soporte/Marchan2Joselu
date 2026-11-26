"""Copias de seguridad de la base de datos local.

Copia diaria automática al abrir la aplicación (si no hay una de las últimas
24 horas), copia al cerrar la jornada y copias manuales. Se usa la API de copia
en caliente de SQLite, así que no hace falta cerrar el TPV para copiar.
Restaurar guarda antes una copia de seguridad del estado actual.
"""
import json
import re
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

NAME = re.compile(r'^marchan2-(\d{8}-\d{6})(?:-(\d+))?-([a-z]+)\.db$')
REASONS = {'diaria': 'Automática diaria', 'cierre': 'Cierre de jornada', 'manual': 'Manual', 'restaurar': 'Antes de restaurar'}
DEFAULTS = {'folder': '', 'keep': 30}
_lock = threading.Lock()


def config(store):
    with store.db() as c:
        row = c.execute("SELECT value FROM settings WHERE key='backup_config'").fetchone()
    data = dict(DEFAULTS, **(json.loads(row['value']) if row else {}))
    data['effective_folder'] = str(folder(store, data))
    return data


def folder(store, data=None):
    data = data or config(store)
    return Path(data['folder']) if data.get('folder') else Path(store.path).parent / 'copias'


def save_config(store, data):
    target = str(data.get('folder') or '').strip()
    keep = int(data.get('keep', 30))
    if not 3 <= keep <= 365:
        raise ValueError('Conserva entre 3 y 365 copias.')
    if target:
        path = Path(target)
        if not path.is_absolute():
            raise ValueError('Indica una carpeta completa, por ejemplo D:\\CopiasMarchan2.')
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / '.marchan2-prueba'
            probe.write_text('ok', encoding='utf8')
            probe.unlink()
        except OSError as error:
            raise ValueError(f'No se puede escribir en esa carpeta: {error.strerror or error}.')
    with store.db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES('backup_config',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (json.dumps({'folder': target, 'keep': keep}),))
    return config(store)


def listing(store):
    path = folder(store)
    items = []
    if path.exists():
        for f in path.iterdir():
            m = NAME.match(f.name)
            if m:
                items.append({'name': f.name, 'created': datetime.strptime(m.group(1), '%Y%m%d-%H%M%S').isoformat(),
                              'reason': REASONS.get(m.group(3), m.group(3)), 'size': f.stat().st_size, 'seq': int(m.group(2) or 0)})
    return sorted(items, key=lambda i: (i['created'], i['seq']), reverse=True)


def create(store, reason='manual'):
    if reason not in REASONS:
        raise ValueError('Motivo de copia no válido.')
    with _lock:
        path = folder(store)
        path.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        target = path / f'marchan2-{stamp}-{reason}.db'
        n = 1
        while target.exists():
            target = path / f'marchan2-{stamp}-{n}-{reason}.db'
            n += 1
        source = sqlite3.connect(store.path, timeout=10)
        dest = sqlite3.connect(target)
        try:
            source.backup(dest)
        finally:
            dest.close()
            source.close()
        _prune(store)
        return {'name': target.name, 'folder': str(path)}


def _prune(store):
    keep = config(store)['keep']
    for item in listing(store)[keep:]:
        try:
            (folder(store) / item['name']).unlink()
        except OSError:
            pass


def automatic(store):
    """Daily copy if the newest one is older than 24 hours. Never raises."""
    try:
        latest = listing(store)
        if not latest or datetime.fromisoformat(latest[0]['created']) < datetime.now() - timedelta(hours=24):
            return create(store, 'diaria')
    except Exception:
        return None
    return None


def restore(store, name):
    if not NAME.match(str(name)):
        raise ValueError('Copia no válida.')
    source_path = folder(store) / name
    if not source_path.exists():
        raise ValueError('La copia ya no existe.')
    check = sqlite3.connect(source_path)
    try:
        if check.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('La copia está dañada; no se ha restaurado.')
        if not check.execute("SELECT 1 FROM sqlite_master WHERE name='orders'").fetchone():
            raise ValueError('El archivo no es una copia de Marchan2.')
    finally:
        check.close()
    safety = create(store, 'restaurar')
    with _lock:
        src = sqlite3.connect(source_path)
        live = sqlite3.connect(store.path, timeout=30)
        try:
            src.backup(live)
        finally:
            live.close()
            src.close()
    return {'restored': name, 'safety_copy': safety['name']}


def start_scheduler(store, stop_event):
    """Check every hour so a TPV left open for days still gets daily copies."""
    def loop():
        automatic(store)
        while not stop_event.wait(3600):
            automatic(store)
    threading.Thread(target=loop, daemon=True).start()
