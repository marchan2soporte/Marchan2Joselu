"""server.cfg: configuración de red al estilo de Ágora.

En el equipo principal se ejecuta «Marchan2_Servidor.exe», que crea y lee
server.cfg en la carpeta de datos (%LOCALAPPDATA%\\Marchan2\\server.cfg) y sirve
por la red el comandero móvil, los monitores de cocina y los TPV de otros
equipos. En los demás equipos basta con indicar en su server.cfg la dirección
del servidor en [cliente] servidor = IP:PUERTO.
"""
import configparser
from pathlib import Path

DEFAULT_PORT = 8790
TEMPLATE = """; Marchan2 · configuración del servidor (similar a server.cfg de Ágora)
; Guarda este archivo y reinicia Marchan2 Servidor para aplicar los cambios.

[servidor]
; Puerto de red para móviles (comandero), monitores de cocina y otros TPV.
puerto = {port}
; 0.0.0.0 = escuchar en todas las redes del equipo. Para limitarlo, pon la IP local.
escuchar = 0.0.0.0
; Nombre que verán los dispositivos.
nombre = MARCHAN2

[cliente]
; SOLO en los demás equipos de la red: dirección del servidor, por ejemplo 192.168.1.10:8790.
; Déjalo vacío en el equipo que hace de servidor.
servidor =
"""


def path(folder):
    return Path(folder) / 'server.cfg'


def exists(folder):
    return path(folder).exists()


def ensure(folder, port=DEFAULT_PORT):
    target = path(folder)
    if not target.exists():
        target.write_text(TEMPLATE.format(port=port), encoding='utf-8')
    return target


def read(folder):
    cfg = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    if exists(folder):
        try:
            cfg.read(path(folder), encoding='utf-8')
        except configparser.Error:
            pass
    port = cfg.getint('servidor', 'puerto', fallback=DEFAULT_PORT) if cfg.has_section('servidor') else DEFAULT_PORT
    if not 1024 <= port <= 65000:
        port = DEFAULT_PORT
    return {'port': port,
            'listen': (cfg.get('servidor', 'escuchar', fallback='0.0.0.0') or '0.0.0.0').strip(),
            'name': (cfg.get('servidor', 'nombre', fallback='MARCHAN2') or 'MARCHAN2').strip(),
            'client_target': (cfg.get('cliente', 'servidor', fallback='') or '').strip()}


def client_url(folder):
    target = read(folder)['client_target'] if exists(folder) else ''
    if not target:
        return None
    if not target.startswith('http'):
        target = 'http://' + target
    if target.count(':') < 2:
        target += f':{DEFAULT_PORT}'
    return target.rstrip('/')


def network_port(folder, args, legacy_port):
    """Puerto de red que debe abrir este proceso (o None)."""
    if getattr(args, 'servidor', False):
        return read(folder)['port']
    if args.app == 'tpv' and not exists(folder):
        return legacy_port  # compatibilidad: comandero integrado en el TPV si no hay servidor
    return None


def listen_host(folder, args):
    if getattr(args, 'lan_host', '0.0.0.0') != '0.0.0.0':
        return args.lan_host  # pruebas
    return read(folder)['listen'] if exists(folder) else '0.0.0.0'


def summary(folder):
    if not exists(folder):
        return {'mode': 'local', 'config': None}
    cfg = read(folder)
    return {'mode': 'cliente' if cfg['client_target'] else 'servidor', 'config': str(path(folder)), 'port': cfg['port'],
            'name': cfg['name'], 'client_target': cfg['client_target']}
