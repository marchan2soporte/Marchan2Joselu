"""Configuration of the active local point of sale."""
import json

DEFAULT = {'allow_pay': True, 'auto_prepare': False, 'search_mode': 'categories',
           'show_last_sale': False, 'receipt_template_id': None,
           'opening_float': 0, 'network_printer': '', 'scale_port': ''}


def initialize(store):
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS pos_profiles(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            group_name TEXT NOT NULL DEFAULT '', options TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 0)''')
        if not c.execute('SELECT 1 FROM pos_profiles').fetchone():
            c.execute('INSERT INTO pos_profiles(name,group_name,options,active) VALUES(?,?,?,1)',
                      ('TPV principal', 'TPV', json.dumps(DEFAULT)))


def _decode(row):
    if not row:
        return None
    value = dict(row)
    value['options'] = {**DEFAULT, **json.loads(value.pop('options'))}
    value['active'] = bool(value['active'])
    return value


def list_all(store):
    with store.db() as c:
        return [_decode(row) for row in c.execute('SELECT * FROM pos_profiles ORDER BY id')]


def active(store):
    with store.db() as c:
        return _decode(c.execute('SELECT * FROM pos_profiles WHERE active=1 ORDER BY id LIMIT 1').fetchone())


def active_options(c):
    row = c.execute('SELECT options FROM pos_profiles WHERE active=1 ORDER BY id LIMIT 1').fetchone()
    return {**DEFAULT, **json.loads(row['options'])} if row else DEFAULT.copy()


def save(store, data):
    name = str(data.get('name', '')).strip()
    group = str(data.get('group_name', '')).strip()
    if not 1 <= len(name) <= 80 or len(group) > 80:
        raise ValueError('Revisa el nombre y el grupo del punto de venta.')
    raw = data.get('options')
    if not isinstance(raw, dict) or set(raw) - set(DEFAULT):
        raise ValueError('Opciones de punto de venta no válidas.')
    opts = {**DEFAULT, **raw}
    for field in ('allow_pay', 'auto_prepare', 'show_last_sale'):
        if type(opts[field]) is not bool:
            raise ValueError('Opción de punto de venta no válida.')
    if opts['search_mode'] not in ('categories', 'search'):
        raise ValueError('Modo de búsqueda no válido.')
    if type(opts['opening_float']) is not int or not 0 <= opts['opening_float'] <= 10000000:
        raise ValueError('Saldo inicial no válido.')
    for field, limit in (('network_printer', 255), ('scale_port', 30)):
        if not isinstance(opts[field], str) or len(opts[field]) > limit:
            raise ValueError('Configuración de dispositivo no válida.')
    if opts['scale_port'] and not __import__('re').fullmatch(r'COM[1-9][0-9]*', opts['scale_port'].upper()):
        raise ValueError('El puerto de balanza debe ser COM1, COM2, etc.')
    template = opts['receipt_template_id']
    if template is not None and (type(template) is not int or template < 1):
        raise ValueError('Plantilla de ticket no válida.')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if template and not c.execute('SELECT 1 FROM ticket_templates WHERE id=?', (template,)).fetchone():
            raise ValueError('La plantilla seleccionada ya no existe.')
        if data.get('id'):
            if not c.execute('SELECT 1 FROM pos_profiles WHERE id=?', (data['id'],)).fetchone():
                raise ValueError('El punto de venta ya no existe.')
            c.execute('UPDATE pos_profiles SET name=?,group_name=?,options=? WHERE id=?',
                      (name, group, json.dumps(opts), data['id']))
            identifier = data['id']
        else:
            identifier = c.execute('INSERT INTO pos_profiles(name,group_name,options) VALUES(?,?,?)',
                                   (name, group, json.dumps(opts))).lastrowid
        return {'id': identifier}


def activate(store, data):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute('SELECT 1 FROM pos_profiles WHERE id=?', (data.get('id'),)).fetchone():
            raise ValueError('El punto de venta ya no existe.')
        c.execute('UPDATE pos_profiles SET active=0')
        c.execute('UPDATE pos_profiles SET active=1 WHERE id=?', (data['id'],))
    return {'ok': True}


def delete(store, data):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT active FROM pos_profiles WHERE id=?', (data.get('id'),)).fetchone()
        if not row:
            raise ValueError('El punto de venta ya no existe.')
        if row['active']:
            raise ValueError('Activa otro punto de venta antes de borrar este.')
        c.execute('DELETE FROM pos_profiles WHERE id=?', (data['id'],))
    return {'ok': True}
