"""Per-user POS profiles. Permissions are checked by the local HTTP service."""
import json

CATALOG = {
    'ticket_open': 'Ticket: Ver abiertos y crear',
    'ticket_add': 'Ticket: Añadir líneas',
    'ticket_quantity': 'Ticket: Cambiar cantidad de una línea',
    'ticket_note': 'Ticket: Añadir notas a una línea',
    'ticket_course': 'Ticket: Cambiar orden de preparación',
    'ticket_cancel': 'Ticket: Borrar una línea',
    'ticket_cancel_prepared': 'Ticket: Cancelar línea preparada',
    'ticket_send': 'Ticket: Enviar preparación a cocina',
    'ticket_march': 'Ticket: Marchar línea',
    'ticket_move': 'Ticket: Mover',
    'ticket_pay': 'Ticket: Cobrar y añadir pagos',
    'ticket_print': 'Ticket: Imprimir',
    'kitchen_view': 'Pedidos: Mostrar preparaciones',
    'kitchen_ready': 'Pedido: Marcar como preparado',
    'z_view': 'TPV: Ver resumen Z anterior (compatibilidad)',
    'z_print': 'Caja: Imprimir informes X y Z',
    'daily_view': 'TPV: Ver resumen diario',
    'print_retry': 'Impresión: Reintentar trabajo',
}
NEW_CASH_RIGHTS={'ticket_void':'Ticket: Cancelar cuenta completa',
    'cash_open':'Caja: Abrir jornada','cash_view':'Caja: Ver X, arqueos y cierres',
    'cash_move':'Caja: Registrar ingresos, gastos y retiradas','cash_close':'Caja: Cerrar jornada'}
PREVIOUS_ALL=set(CATALOG)
CATALOG.update(NEW_CASH_RIGHTS)
PREVIOUS_PRICING_ALL=set(CATALOG)
NEW_PRICING_RIGHTS={'ticket_discount':'Ticket: Aplicar o quitar descuentos de línea','ticket_weight':'Ticket: Cambiar peso de una porción'}
CATALOG.update(NEW_PRICING_RIGHTS)
ALL = list(CATALOG)
WAITER = [key for key in ALL if key not in
          ('ticket_cancel_prepared', 'ticket_pay', 'z_view', 'z_print', 'print_retry',*NEW_CASH_RIGHTS,*NEW_PRICING_RIGHTS)]
ACTION = {'open': 'ticket_open', 'close_empty': 'ticket_open', 'add': 'ticket_add',
          'quantity': 'ticket_quantity', 'note': 'ticket_note', 'course': 'ticket_course',
          'cancel_line': 'ticket_cancel', 'send': 'ticket_send', 'march': 'ticket_march',
          'move': 'ticket_move', 'pay': 'ticket_pay', 'split_pay': 'ticket_pay',
          'ready': 'kitchen_ready','cancel_ticket':'ticket_void'}


def initialize(store):
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS user_profiles(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, permissions TEXT NOT NULL,
            protected INTEGER NOT NULL DEFAULT 0)''')
        if 'profile_id' not in [row['name'] for row in c.execute('PRAGMA table_info(users)')]:
            c.execute('ALTER TABLE users ADD COLUMN profile_id INTEGER REFERENCES user_profiles(id)')
        for name, rights in [('Administrador', ALL), ('Encargado', ALL), ('Camarero', WAITER)]:
            c.execute('INSERT OR IGNORE INTO user_profiles(name,permissions,protected) VALUES(?,?,1)',
                      (name, json.dumps(rights)))
        marker=c.execute("SELECT value FROM settings WHERE key='cash_permissions_v022'").fetchone()
        if not marker:
            manager=c.execute("SELECT id,permissions FROM user_profiles WHERE name='Encargado' AND protected=1").fetchone()
            if manager and set(json.loads(manager['permissions']))==PREVIOUS_ALL:
                c.execute('UPDATE user_profiles SET permissions=? WHERE id=?',(json.dumps(ALL),manager['id']))
            c.execute("INSERT INTO settings(key,value) VALUES('cash_permissions_v022','1')")
        if not c.execute("SELECT 1 FROM settings WHERE key='pricing_permissions_v022'").fetchone():
            manager=c.execute("SELECT id,permissions FROM user_profiles WHERE name='Encargado' AND protected=1").fetchone()
            if manager and set(json.loads(manager['permissions']))==PREVIOUS_PRICING_ALL:
                c.execute('UPDATE user_profiles SET permissions=? WHERE id=?',(json.dumps(ALL),manager['id']))
            c.execute("INSERT INTO settings(key,value) VALUES('pricing_permissions_v022','1')")
        admin_id = c.execute("SELECT id FROM user_profiles WHERE name='Administrador'").fetchone()[0]
        manager_id = c.execute("SELECT id FROM user_profiles WHERE name='Encargado'").fetchone()[0]
        c.execute('UPDATE users SET profile_id=CASE WHEN role=? THEN ? ELSE ? END WHERE profile_id IS NULL',
                  ('admin', admin_id, manager_id))


def list_all(store):
    with store.db() as c:
        profiles = [dict(row) for row in c.execute('SELECT * FROM user_profiles ORDER BY id')]
        for profile in profiles:
            profile['permissions'] = json.loads(profile['permissions'])
            profile['users'] = c.execute('SELECT COUNT(*) FROM users WHERE profile_id=? AND active=1',
                                         (profile['id'],)).fetchone()[0]
        return {'catalog': CATALOG, 'profiles': profiles}


def rights(c, user_id):
    row = c.execute('''SELECT u.role,p.permissions FROM users u LEFT JOIN user_profiles p
        ON p.id=u.profile_id WHERE u.id=? AND u.active=1''', (user_id,)).fetchone()
    if not row: return []
    if row['role'] == 'admin': return ALL
    return json.loads(row['permissions']) if row['permissions'] else []


def require(store, user_id, permission):
    with store.db() as c:
        if permission not in rights(c, user_id):
            raise PermissionError('Tu perfil no permite esta operación en el TPV.')


def save(store, data):
    name = str(data.get('name', '')).strip()
    if not 2 <= len(name) <= 80: raise ValueError('El nombre debe tener entre 2 y 80 caracteres.')
    selected = data.get('permissions', [])
    if not isinstance(selected, list) or len(selected) != len(set(selected)) or any(p not in CATALOG for p in selected):
        raise ValueError('Hay permisos no disponibles en Marchan2.')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        identifier = data.get('id')
        if identifier:
            row = c.execute('SELECT * FROM user_profiles WHERE id=?', (identifier,)).fetchone()
            if not row: raise ValueError('Perfil no encontrado.')
            if row['name'] == 'Administrador': raise ValueError('El perfil Administrador no se puede limitar.')
            if row['protected'] and name != row['name']:
                raise ValueError('El nombre de este perfil inicial no se puede cambiar.')
            c.execute('UPDATE user_profiles SET name=?,permissions=? WHERE id=?',
                      (name, json.dumps(selected), identifier))
        else:
            identifier = c.execute('INSERT INTO user_profiles(name,permissions) VALUES(?,?)',
                                   (name, json.dumps(selected))).lastrowid
    return {'id': identifier}


def delete(store, data):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT protected FROM user_profiles WHERE id=?', (data['id'],)).fetchone()
        if not row: raise ValueError('Perfil no encontrado.')
        if row['protected']: raise ValueError('Los perfiles iniciales no se pueden eliminar.')
        if c.execute('SELECT 1 FROM users WHERE profile_id=?', (data['id'],)).fetchone():
            raise ValueError('Este perfil está asignado a usuarios.')
        c.execute('DELETE FROM user_profiles WHERE id=?', (data['id'],))
    return {'ok': True}
