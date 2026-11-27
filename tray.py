"""Icono de Marchan2 Servidor en el área de notificación (junto a la hora).

Permanece mientras el servidor está en marcha. Menú:
- Abrir estado del servidor (también con doble clic)
- Abrir server.cfg
- Detener servidor
"""
import os
import subprocess
import sys
import threading
from pathlib import Path


def viewer_command(folder):
    exe = Path(sys.executable)
    if getattr(sys, 'frozen', False):
        return [str(exe.with_name('Marchan2_Servidor.exe')), '--data', str(folder)]
    pythonw = exe.with_name('pythonw.exe')
    return [str(pythonw if pythonw.exists() else exe), str(Path(__file__).with_name('servidor.py')), '--data', str(folder)]


def run(folder, icon_path, label, cfg_path, stop_server, server_thread):
    """Muestra el icono y bloquea hasta que el servidor se detiene. False si no hay bandeja disponible."""
    try:
        import pystray
        from PIL import Image
    except Exception:
        return False
    try:
        image = Image.open(icon_path).convert('RGBA').resize((64, 64))
    except Exception:
        image = Image.new('RGBA', (64, 64), (15, 123, 90, 255))

    def open_status(icon=None, item=None):
        try:
            subprocess.Popen(viewer_command(folder), close_fds=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def open_cfg(icon=None, item=None):
        try:
            os.startfile(str(cfg_path))
        except OSError:
            pass

    def stop(icon, item=None):
        stop_server()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: 'Marchan2 Servidor · ' + label(), None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Abrir estado del servidor', open_status, default=True),
        pystray.MenuItem('Abrir server.cfg', open_cfg),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Detener servidor', stop))
    icon = pystray.Icon('marchan2-servidor', image, 'Marchan2 Servidor · ' + label(), menu)

    def watch():
        server_thread.join()  # si se detiene desde la ventana de estado, quitar el icono
        icon.stop()

    threading.Thread(target=watch, daemon=True).start()
    try:
        icon.run()
    except Exception:
        return False
    return True
