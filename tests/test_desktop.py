import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import desktop


class FakeServer:
    def __init__(self):
        self.served = False

    def serve_forever(self):
        self.served = True

    def shutdown(self):
        pass


class DesktopTests(unittest.TestCase):
    def test_without_webview_falls_back_without_serving(self):
        server = FakeServer()
        with mock.patch.dict(sys.modules, {'webview': None}):
            self.assertFalse(desktop.available())
            self.assertFalse(desktop.run(server, 'http://127.0.0.1:1', 'Marchan2', Path('.')))
        self.assertFalse(server.served)

    def test_bridge_close_destroys_window(self):
        bridge = desktop.Bridge()
        self.assertTrue(bridge.close())
        destroyed = threading.Event()
        bridge._window = mock.Mock(destroy=destroyed.set)
        self.assertTrue(bridge.close())
        self.assertTrue(destroyed.wait(2))


if __name__ == '__main__':
    unittest.main()
