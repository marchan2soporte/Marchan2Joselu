import tempfile
import unittest
from pathlib import Path

import permissions
from store import Store


class PermissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'permissions.db')

    def test_existing_users_keep_access_and_profile_changes_apply_now(self):
        self.store.mutate('user', {'name': 'ANA', 'pin': '4567', 'role': 'staff'}, 1)
        ana = next(user for user in self.store.users() if user['name'] == 'ANA')
        permissions.require(self.store, ana['id'], 'ticket_pay')
        profile = permissions.save(self.store, {'name': 'Solo sala',
            'permissions': ['ticket_open', 'ticket_add']})['id']
        self.store.mutate('user', {'id': ana['id'], 'name': 'ANA', 'role': 'staff',
                                  'profile_id': profile}, 1)
        permissions.require(self.store, ana['id'], 'ticket_add')
        with self.assertRaises(PermissionError):
            permissions.require(self.store, ana['id'], 'ticket_pay')
        permissions.save(self.store, {'id': profile, 'name': 'Sala y caja',
            'permissions': ['ticket_open', 'ticket_add', 'ticket_pay']})
        permissions.require(self.store, ana['id'], 'ticket_pay')
        with self.assertRaises(ValueError):
            permissions.delete(self.store, {'id': profile})

    def test_invalid_or_admin_profile_cannot_remove_recovery_access(self):
        catalog = permissions.list_all(self.store)
        admin = next(p for p in catalog['profiles'] if p['name'] == 'Administrador')
        with self.assertRaises(ValueError):
            permissions.save(self.store, {'id': admin['id'], 'name': 'Administrador',
                'permissions': []})
        with self.assertRaises(ValueError):
            permissions.save(self.store, {'name': 'Falso', 'permissions': ['unknown']})
        with self.assertRaises(ValueError):
            self.store.mutate('user', {'name': 'BOB', 'pin': '1234', 'role': 'staff',
                'profile_id': admin['id']}, 1)


if __name__ == '__main__': unittest.main()
