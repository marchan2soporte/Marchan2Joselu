import tempfile
import unittest
from pathlib import Path

import comandero
from store import Store


class ComanderoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s = Store(Path(self.tmp.name) / 'db.sqlite')
        comandero.initialize(self.s)
        comandero._failures.update(count=0, until=0.0)

    def test_disabled_by_default_and_pairing_requires_code(self):
        self.assertIsNone(comandero.enabled_port(self.s))
        with self.assertRaises(PermissionError):
            comandero.pair(self.s, '', 'x')
        code = comandero.configure(self.s, {'enabled': True, 'port': 8790})['code']
        self.assertRegex(code, r'^\d{6}$')
        self.assertEqual(comandero.enabled_port(self.s), 8790)
        token = comandero.pair(self.s, code, 'móvil de ana')['device_token']
        self.assertTrue(comandero.device_ok(self.s, token))
        self.assertFalse(comandero.device_ok(self.s, token + 'x'))
        self.assertFalse(comandero.device_ok(self.s, ''))
        with self.s.db() as c:
            stored = c.execute('SELECT token_hash FROM comandero_devices').fetchone()['token_hash']
        self.assertNotEqual(stored, token)
        device = comandero.status(self.s)['devices'][0]
        comandero.revoke(self.s, device['id'])
        self.assertFalse(comandero.device_ok(self.s, token))

    def test_lockout_after_five_wrong_codes_and_new_code(self):
        code = comandero.configure(self.s, {'enabled': True, 'port': 8790})['code']
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            with self.assertRaises(PermissionError):
                comandero.pair(self.s, wrong, 'x')
        with self.assertRaisesRegex(PermissionError, 'Espera'):
            comandero.pair(self.s, code, 'x')
        comandero._failures.update(count=0, until=0.0)
        new = comandero.new_code(self.s)['code']
        if new != code:
            with self.assertRaises(PermissionError):
                comandero.pair(self.s, code, 'x')
        self.assertIn('device_token', comandero.pair(self.s, new, 'x'))
        with self.assertRaises(ValueError):
            comandero.configure(self.s, {'enabled': True, 'port': 80})


if __name__ == '__main__':
    unittest.main()
