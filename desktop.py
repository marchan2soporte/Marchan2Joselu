"""Native desktop window for Marchan2.

Opens the local interface inside its own Windows window (Edge WebView2 through
pywebview) instead of a browser tab. Closing the window stops the local server,
so no process is left running in the background. If pywebview or WebView2 is not
available, the caller falls back to the default browser.
"""
import os
import sys
import threading
import traceback
from pathlib import Path


def unblock_bundle():
    """Remove the Windows «downloaded from Internet» mark from the bundled files.

    When the portable ZIP is downloaded and extracted with the Explorer, every
    file inherits a Zone.Identifier stream. .NET then refuses to load the
    pythonnet assemblies used by the native window and the app silently fell
    back to the browser. Removing the mark from our own bundle fixes it.
    """
    root = getattr(sys, '_MEIPASS', None)
    if not root or os.name != 'nt':
        return 0
    removed = 0
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if not name.lower().endswith(('.dll', '.pyd', '.exe', '.json', '.js', '.manifest')):
                continue
            try:
                os.remove(os.path.join(folder, name) + ':Zone.Identifier')
                removed += 1
            except OSError:
                pass
    exe = Path(sys.executable)
    for target in [exe, *exe.parent.glob('*.exe')]:
        try:
            os.remove(str(target) + ':Zone.Identifier')
            removed += 1
        except OSError:
            pass
    return removed


def _log(log, message):
    if not log:
        return
    try:
        with open(log, 'a', encoding='utf8') as handle:
            handle.write(message.rstrip() + chr(10))
    except OSError:
        pass


class Bridge:
    """Functions the interface may call through window.pywebview.api."""

    def __init__(self):
        self._window = None

    def close(self):
        if self._window:
            threading.Thread(target=self._window.destroy, daemon=True).start()
        return True

    def toggle_fullscreen(self):
        if self._window:
            self._window.toggle_fullscreen()
        return True

    def is_desktop(self):
        return True


def available():
    try:
        import webview  # noqa: F401
    except Exception:
        return False
    return True


def run(server, url, title, storage, fullscreen=False, log=None):
    """Serve in the background and block until the window is closed.

    Returns False without serving when no native window can be created.
    """
    unblock_bundle()
    try:
        import webview
    except Exception:
        _log(log, 'No se pudo cargar la ventana de escritorio: ' + traceback.format_exc())
        return False
    bridge = Bridge()
    try:
        window = webview.create_window(
            title, url, js_api=bridge,
            width=1366, height=820, min_size=(1024, 680),
            maximized=True, fullscreen=fullscreen,
            background_color='#0E1A1C', text_select=True,
        )
    except Exception:
        _log(log, 'No se pudo crear la ventana: ' + traceback.format_exc())
        return False
    bridge._window = window
    closed = threading.Event()
    window.events.closed += closed.set

    def serve():
        server.serve_forever()
        # The «Cerrar aplicación» button stops the server: close the window too.
        if not closed.is_set():
            try:
                window.destroy()
            except Exception:
                pass

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        Path(storage).mkdir(parents=True, exist_ok=True)
        webview.start(private_mode=False, storage_path=str(storage))
    except Exception:
        _log(log, 'La ventana de escritorio falló al abrirse: ' + traceback.format_exc())
        closed.set()
        server.shutdown()
        return False
    closed.set()
    server.shutdown()
    return True


def open_remote(url, title, storage, fullscreen=False, log=None):
    """Equipo cliente: ventana con el TPV de otro equipo (server.cfg → [cliente] servidor)."""
    unblock_bundle()
    try:
        import webview
        webview.create_window(title, url, width=1366, height=820, min_size=(1024, 680), maximized=True,
                              fullscreen=fullscreen, background_color='#0E1A1C', text_select=True)
        Path(storage).mkdir(parents=True, exist_ok=True)
        webview.start(private_mode=False, storage_path=str(storage))
        return True
    except Exception:
        _log(log, 'No se pudo abrir la ventana del servidor remoto: ' + traceback.format_exc())
        return False


def message(title, text):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)
    except Exception:
        print(title + ': ' + text)
