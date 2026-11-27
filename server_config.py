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
            cfg.read(path(folder), encoding='utf-8-sig')  # admite el BOM que añade el Bloc de notas
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


# ---------- Servidor en segundo plano ----------
def session_file(folder):
    return Path(folder) / 'session-servidor.json'


def running(folder, timeout=1.0):
    """Datos del servidor en marcha ({'url','lan_port','pid'}) o None si no responde."""
    import json
    import urllib.request
    try:
        info = json.loads(session_file(folder).read_text(encoding='utf-8'))
        with urllib.request.urlopen(info['url'] + '/api/server_ping', timeout=timeout) as response:
            if json.loads(response.read()).get('ok'):
                return info
    except Exception:
        return None
    return None


def background_command(folder):
    import sys
    exe = Path(sys.executable)
    if getattr(sys, 'frozen', False):
        target = exe.with_name('Marchan2_Servidor.exe')
        if not target.exists():
            return None
        command = [str(target)]
    else:
        pythonw = exe.with_name('pythonw.exe')
        command = [str(pythonw if pythonw.exists() else exe), str(Path(__file__).with_name('servidor.py'))]
    return command + ['--segundo-plano', '--data', str(folder)]


def start_background(folder, wait=0.0):
    """Arranca Marchan2 Servidor oculto si no está en marcha. Devuelve sus datos o None."""
    import subprocess
    import sys
    import time
    info = running(folder)
    if info:
        return info
    ensure(folder)
    command = background_command(folder)
    if not command:
        return None
    flags = 0
    if sys.platform == 'win32':
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(command, creationflags=flags | 0x01000000, close_fds=True,  # CREATE_BREAKAWAY_FROM_JOB
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        try:
            subprocess.Popen(command, creationflags=flags, close_fds=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return None
    end = time.monotonic() + wait
    while time.monotonic() < end:
        time.sleep(0.25)
        info = running(folder)
        if info:
            return info
    return None
