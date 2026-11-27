"""Tipos de preparación editables y monitores de cocina (KDS) independientes.

- Tipos de preparación: BARRA y COCINA de serie; Administración puede crear más
  (FRÍOS, CALIENTES, POSTRES…), cambiar su color y desactivarlos si no se usan.
- Monitores: cada pantalla de cocina tiene nombre, tipos de preparación que
  muestra, disposición (izquierda, derecha o apiladas como papel pinchado),
  volumen y sonido del aviso y tiempos de alerta. Se abren desde
  http://IP:PUERTO/cocina en cualquier pantalla de la red emparejada.
"""
import json
import re
from datetime import datetime, timedelta

LAYOUTS = ('left', 'right', 'stack')
SOUNDS = ('beep', 'bell', 'double', 'off')
DEFAULT_TYPES = [('COCINA', '#e0803a'), ('BARRA', '#3b82c4')]
ADMIN_ACTIONS = {'prep_type_save', 'prep_type_delete', 'monitor_save', 'monitor_delete'}
NOW = lambda: datetime.now().isoformat(timespec='seconds')


def initialize(store):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('''CREATE TABLE IF NOT EXISTS prep_types(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, color TEXT NOT NULL DEFAULT '#0f7b5a',
            sort INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1)''')
        if not c.execute('SELECT 1 FROM prep_types').fetchone():
            for i, (name, color) in enumerate(DEFAULT_TYPES):
                c.execute('INSERT INTO prep_types(name,color,sort) VALUES(?,?,?)', (name, color, i))
            for (prep,) in c.execute('SELECT DISTINCT prep FROM products').fetchall():
                if prep and not c.execute('SELECT 1 FROM prep_types WHERE name=?', (prep,)).fetchone():
                    c.execute('INSERT INTO prep_types(name,sort) VALUES(?,99)', (prep,))
        c.execute('''CREATE TABLE IF NOT EXISTS kitchen_monitors(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, prep_types TEXT NOT NULL DEFAULT '[]',
            layout TEXT NOT NULL DEFAULT 'left', volume INTEGER NOT NULL DEFAULT 70, sound TEXT NOT NULL DEFAULT 'beep',
            warn_minutes INTEGER NOT NULL DEFAULT 10, late_minutes INTEGER NOT NULL DEFAULT 20, active INTEGER NOT NULL DEFAULT 1)''')
        if not c.execute('SELECT 1 FROM kitchen_monitors').fetchone():
            c.execute("INSERT INTO kitchen_monitors(name,prep_types) VALUES('COCINA','[\"COCINA\"]')")
            c.execute("INSERT INTO kitchen_monitors(name,prep_types) VALUES('BARRA','[\"BARRA\"]')")
        if 'sold_out' not in {r['name'] for r in c.execute('PRAGMA table_info(products)')}:
            c.execute('ALTER TABLE products ADD COLUMN sold_out INTEGER NOT NULL DEFAULT 0')


def prep_names(c, active_only=True):
    return [r['name'] for r in c.execute('SELECT name FROM prep_types' + (' WHERE active=1' if active_only else '') + ' ORDER BY sort,id')]


def prep_types(c):
    rows = [dict(r) for r in c.execute('SELECT * FROM prep_types ORDER BY sort,id')]
    for r in rows:
        r['products'] = c.execute('SELECT COUNT(*) FROM products WHERE prep=? AND active=1', (r['name'],)).fetchone()[0]
    return rows


def monitors(c):
    rows = [dict(r) for r in c.execute('SELECT * FROM kitchen_monitors ORDER BY id')]
    for r in rows:
        r['prep_types'] = json.loads(r['prep_types'])
    return rows


def monitor(c, monitor_id):
    row = c.execute('SELECT * FROM kitchen_monitors WHERE id=? AND active=1', (int(monitor_id),)).fetchone()
    if not row:
        raise ValueError('Ese monitor ya no existe. Elige otro.')
    data = dict(row)
    data['prep_types'] = json.loads(data['prep_types'])
    return data


def _name(value):
    name = ' '.join(str(value or '').split()).upper()
    if not 2 <= len(name) <= 30:
        raise ValueError('El nombre debe tener entre 2 y 30 caracteres.')
    return name


def mutate(store, action, data, actor):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        store.audit(c, actor, action)
        if action == 'prep_type_save':
            name = _name(data.get('name'))
            color = str(data.get('color') or '#0f7b5a')
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                raise ValueError('Color no válido.')
            if data.get('id'):
                old = c.execute('SELECT name FROM prep_types WHERE id=?', (int(data['id']),)).fetchone()
                if not old:
                    raise ValueError('Tipo de preparación no encontrado.')
                if old['name'] != name:
                    if c.execute('SELECT 1 FROM prep_types WHERE name=?', (name,)).fetchone():
                        raise ValueError('Ya existe un tipo con ese nombre.')
                    # Renombrar en productos, líneas abiertas, rutas de impresión y monitores.
                    c.execute('UPDATE products SET prep=? WHERE prep=?', (name, old['name']))
                    c.execute("UPDATE lines SET prep=? WHERE prep=? AND order_id IN (SELECT id FROM orders WHERE status='open')", (name, old['name']))
                    for table in ('kitchen_printer_routes', 'kitchen_monitors'):
                        if c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
                            for r in c.execute(f'SELECT id,prep_types FROM {table}').fetchall():
                                types = json.loads(r['prep_types'])
                                if old['name'] in types:
                                    c.execute(f'UPDATE {table} SET prep_types=? WHERE id=?', (json.dumps([name if t == old['name'] else t for t in types]), r['id']))
                c.execute('UPDATE prep_types SET name=?,color=?,active=1 WHERE id=?', (name, color, int(data['id'])))
                return {'id': int(data['id'])}
            if c.execute('SELECT 1 FROM prep_types WHERE name=?', (name,)).fetchone():
                raise ValueError('Ya existe un tipo con ese nombre.')
            sort = c.execute('SELECT COALESCE(MAX(sort),0)+1 FROM prep_types').fetchone()[0]
            return {'id': c.execute('INSERT INTO prep_types(name,color,sort) VALUES(?,?,?)', (name, color, sort)).lastrowid}
        if action == 'prep_type_delete':
            row = c.execute('SELECT name FROM prep_types WHERE id=?', (int(data['id']),)).fetchone()
            if not row:
                raise ValueError('Tipo de preparación no encontrado.')
            if c.execute('SELECT 1 FROM products WHERE prep=? AND active=1', (row['name'],)).fetchone():
                raise ValueError('Hay productos con este tipo. Cámbialos antes de eliminarlo.')
            if c.execute('SELECT COUNT(*) FROM prep_types WHERE active=1').fetchone()[0] <= 1:
                raise ValueError('Debe quedar al menos un tipo de preparación.')
            c.execute('DELETE FROM prep_types WHERE id=?', (int(data['id']),))
            return {'ok': True}
        if action == 'monitor_delete':
            c.execute('DELETE FROM kitchen_monitors WHERE id=?', (int(data['id']),))
            return {'ok': True}
        if action == 'monitor_save':
            return save_monitor(c, data)
    raise ValueError('Acción no disponible.')


def save_monitor(c, data, partial=False):
    current = monitor(c, data['id']) if data.get('id') else None
    get = lambda k, d: data[k] if k in data else (current[k] if current else d)
    name = _name(get('name', ''))
    types = get('prep_types', [])
    valid = prep_names(c)
    if not isinstance(types, list) or not types or any(t not in valid for t in types):
        raise ValueError('Elige al menos un tipo de preparación existente.')
    layout, sound = get('layout', 'left'), get('sound', 'beep')
    if layout not in LAYOUTS or sound not in SOUNDS:
        raise ValueError('Disposición o sonido no válidos.')
    volume, warn, late = int(get('volume', 70)), int(get('warn_minutes', 10)), int(get('late_minutes', 20))
    if not 0 <= volume <= 100 or not 1 <= warn < late <= 240:
        raise ValueError('Volumen entre 0 y 100; aviso antes que retraso (minutos).')
    values = (name, json.dumps(types), layout, volume, sound, warn, late)
    if current:
        if c.execute('SELECT 1 FROM kitchen_monitors WHERE name=? AND id<>?', (name, current['id'])).fetchone():
            raise ValueError('Ya existe un monitor con ese nombre.')
        c.execute('UPDATE kitchen_monitors SET name=?,prep_types=?,layout=?,volume=?,sound=?,warn_minutes=?,late_minutes=? WHERE id=?', values + (current['id'],))
        return {'id': current['id']}
    if c.execute('SELECT 1 FROM kitchen_monitors WHERE name=?', (name,)).fetchone():
        raise ValueError('Ya existe un monitor con ese nombre.')
    return {'id': c.execute('INSERT INTO kitchen_monitors(name,prep_types,layout,volume,sound,warn_minutes,late_minutes) VALUES(?,?,?,?,?,?,?)', values).lastrowid}


# ---------- Pantalla de cocina (sin usuario: dispositivo emparejado) ----------
def board(store, monitor_id):
    with store.db() as c:
        c.execute('BEGIN')
        m = monitor(c, monitor_id)
        types = m['prep_types']
        marks = ','.join('?' for _ in types)
        orders = {}
        for l in c.execute(f'''SELECT l.*, o.guests, o.service_type, o.table_id, COALESCE(t.name,o.source_label,'VENTA DIRECTA') table_name,
                COALESCE(u.name,'') user_name FROM lines l JOIN orders o ON o.id=l.order_id LEFT JOIN tables t ON t.id=o.table_id
                LEFT JOIN users u ON u.id=o.created_by WHERE l.kitchen='pending' AND l.prep IN ({marks}) AND o.status IN ('open','paid')
                ORDER BY l.sent_at, l.id''', types):
            l = dict(l)
            l['extras'] = json.loads(l['extras'])
            o = orders.setdefault(l['order_id'], {'id': l['order_id'], 'table_name': l['table_name'], 'guests': l['guests'],
                                                  'service_type': l['service_type'], 'user_name': l['user_name'], 'since': l['sent_at'], 'lines': []})
            o['lines'].append({k: l[k] for k in ('id', 'name', 'format', 'qty', 'course', 'note', 'extras', 'prep', 'sent_at', 'menu_role', 'weight_milli')})
            if l['sent_at'] and (not o['since'] or l['sent_at'] < o['since']):
                o['since'] = l['sent_at']
        since = (datetime.now() - timedelta(minutes=15)).isoformat(timespec='seconds')
        recent = [dict(r) for r in c.execute(f'''SELECT l.order_id, COALESCE(t.name,o.source_label,'VENTA DIRECTA') table_name, MAX(l.ready_at) ready_at, COUNT(*) n
            FROM lines l JOIN orders o ON o.id=l.order_id LEFT JOIN tables t ON t.id=o.table_id
            WHERE l.kitchen='ready' AND l.ready_at>=? AND l.prep IN ({marks}) GROUP BY l.order_id ORDER BY ready_at DESC LIMIT 8''', [since, *types])]
        colors = {r['name']: r['color'] for r in c.execute('SELECT name,color FROM prep_types')}
    return {'monitor': m, 'orders': sorted(orders.values(), key=lambda o: o['since'] or ''), 'recent': recent, 'colors': colors, 'now': NOW()}


def kds_action(store, action, data):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        m = monitor(c, data['monitor_id'])
        types = m['prep_types']
        marks = ','.join('?' for _ in types)
        if action == 'ready':
            n = c.execute(f"UPDATE lines SET kitchen='ready' WHERE order_id=? AND kitchen='pending' AND prep IN ({marks})", [int(data['order_id']), *types]).rowcount
        elif action == 'line_ready':
            n = c.execute(f"UPDATE lines SET kitchen='ready' WHERE id=? AND kitchen='pending' AND prep IN ({marks})", [int(data['line_id']), *types]).rowcount
        elif action == 'recall':
            since = (datetime.now() - timedelta(minutes=15)).isoformat(timespec='seconds')
            n = c.execute(f"UPDATE lines SET kitchen='pending', ready_at=NULL WHERE order_id=? AND kitchen='ready' AND ready_at>=? AND prep IN ({marks})",
                          [int(data['order_id']), since, *types]).rowcount
        elif action == 'settings':
            allowed = {k: data[k] for k in ('layout', 'volume', 'sound') if k in data}
            return save_monitor(c, dict(allowed, id=m['id']))
        else:
            raise ValueError('Acción de cocina no válida.')
        store.audit(c, None, 'kds_' + action, data.get('order_id'))
    return {'changed': n}


def set_sold_out(store, product_id, sold_out, actor):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute('SELECT 1 FROM products WHERE id=?', (int(product_id),)).fetchone():
            raise ValueError('Producto no encontrado.')
        c.execute('UPDATE products SET sold_out=? WHERE id=?', (1 if sold_out else 0, int(product_id)))
        store.audit(c, actor, 'sold_out')
    return {'ok': True}
