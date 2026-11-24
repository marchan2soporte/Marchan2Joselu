"""Native desktop window for Marchan2.

Opens the local interface inside its own Windows window (Edge WebView2 through
pywebview) instead of a browser tab. Closing the window stops the local server,
so no process is left running in the background. If pywebview or WebView2 is not
available, the caller falls back to the default browser.
"""
import threading
from pathlib import Path


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


def run(server, url, title, storage, fullscreen=False):
    """Serve in the background and block until the window is closed.

    Returns False without serving when no native window can be created.
    """
    try:
        import webview
    except Exception:
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
        closed.set()
        server.shutdown()
        return False
    closed.set()
    server.shutdown()
    return True
