"""Comandero móvil en la red local (opcional, desactivado por defecto).

El TPV abre un segundo servicio en la red local para que los móviles de los
camareros tomen comandas con su usuario y PIN. Medidas de seguridad:
- Desactivado por defecto; se activa en Administración y en el TPV al arrancar.
- Cada móvil se empareja una vez con un código de 6 cifras que muestra el TPV.
  El móvil recibe un token aleatorio; en la base de datos solo se guarda su
  huella SHA-256. Los móviles se pueden revocar.
- Bloqueo de 5 minutos tras 5 códigos de emparejamiento erróneos.
- Desde el móvil no se puede cerrar la aplicación; los permisos de cada
  usuario se aplican igual que en el TPV.
Limitación: la conexión es HTTP sin cifrar dentro de la red local. Úsalo solo
en una wifi privada con contraseña (WPA2/WPA3), nunca en la wifi de clientes.
"""
import hashlib
import json
import secrets
import socket
import threading
import time
from datetime import datetime

DEFAULT_PORT = 8790
_lock = threading.Lock()
_failures = {'count': 0, 'until': 0.0}


def initialize(store):
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS comandero_devices(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
            created TEXT NOT NULL, last_seen TEXT, revoked INTEGER NOT NULL DEFAULT 0)''')


def _settings(c):
    row = c.execute("SELECT value FROM settings WHERE key='comandero'").fetchone()
    return dict({'enabled': False, 'port': DEFAULT_PORT, 'code': '', 'allow_pay': False}, **(json.loads(row['value']) if row else {}))


def _save(c, data):
    c.execute("INSERT INTO settings(key,value) VALUES('comandero',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(data),))


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('192.0.2.1', 9))  # no se envía nada: solo elige la interfaz de salida
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return '127.0.0.1'


def status(store, running_port=None):
    with store.db() as c:
        cfg = _settings(c)
        devices = [dict(r) for r in c.execute('SELECT id,name,created,last_seen,revoked FROM comandero_devices ORDER BY revoked, id DESC')]
    ip = local_ip()
    return {'enabled': cfg['enabled'], 'port': cfg['port'], 'code': cfg['code'], 'allow_pay': cfg['allow_pay'], 'running': running_port is not None,
            'url': f'http://{ip}:{running_port or cfg["port"]}', 'devices': devices}


def configure(store, data):
    port = int(data.get('port', DEFAULT_PORT))
    if not 1024 <= port <= 65000:
        raise ValueError('Puerto entre 1024 y 65000.')
    with store.db() as c:
        cfg = _settings(c)
        cfg.update(enabled=bool(data.get('enabled')), port=port, allow_pay=data.get('allow_pay') is True)
        if cfg['enabled'] and not cfg['code']:
            cfg['code'] = f'{secrets.randbelow(10**6):06d}'
        _save(c, cfg)
    return status(store)


def new_code(store):
    with store.db() as c:
        cfg = _settings(c)
        cfg['code'] = f'{secrets.randbelow(10**6):06d}'
        _save(c, cfg)
    return status(store)


def revoke(store, device_id):
    with store.db() as c:
        c.execute('UPDATE comandero_devices SET revoked=1 WHERE id=?', (int(device_id),))
    return status(store)


def pair(store, code, name):
    with _lock:
        if time.monotonic() < _failures['until']:
            raise PermissionError('Demasiados códigos erróneos. Espera 5 minutos.')
        with store.db() as c:
            cfg = _settings(c)
            if not cfg['enabled'] or not cfg['code'] or not secrets.compare_digest(str(code or '').strip(), cfg['code']):
                _failures['count'] += 1
                if _failures['count'] >= 5:
                    _failures.update(count=0, until=time.monotonic() + 300)
                raise PermissionError('Código de emparejamiento incorrecto.')
            _failures['count'] = 0
            token = secrets.token_urlsafe(32)
            label = ' '.join(str(name or 'MÓVIL').split())[:40].upper() or 'MÓVIL'
            c.execute('INSERT INTO comandero_devices(name,token_hash,created) VALUES(?,?,?)',
                      (label, hashlib.sha256(token.encode()).hexdigest(), datetime.now().isoformat(timespec='seconds')))
    return {'device_token': token, 'name': label}


def device_ok(store, token):
    if not token or len(token) > 200:
        return False
    digest = hashlib.sha256(token.encode()).hexdigest()
    with store.db() as c:
        row = c.execute('SELECT id FROM comandero_devices WHERE token_hash=? AND revoked=0', (digest,)).fetchone()
        if row:
            c.execute('UPDATE comandero_devices SET last_seen=? WHERE id=?', (datetime.now().isoformat(timespec='seconds'), row['id']))
    return bool(row)


PAY_ACTIONS = {'pay', 'split_pay'}


def allow_pay(store):
    with store.db() as c:
        return _settings(c)['allow_pay']


def enabled_port(store):
    with store.db() as c:
        cfg = _settings(c)
    return cfg['port'] if cfg['enabled'] else None
