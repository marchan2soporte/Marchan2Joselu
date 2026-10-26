"""Local layouts for Marchan2's non-fiscal test receipts."""
import base64
import binascii

BASES = ('80 mm', '56 mm · 32 caracteres', '80 mm · 42 caracteres',
         '80 mm · 48 caracteres', '80 mm · 56 caracteres',
         '80 mm · 64 caracteres', '80 mm · 48 caracteres + precio unitario', 'A4')
LINE_ORDERS = ('Por defecto', 'Nombre', 'Categoría')
PRINT_OPTIONS = {'show_unpaid': 1, 'show_notes': 0, 'show_location': 1,
                 'show_order_id': 1, 'show_tips': 1, 'show_unit_price': 0,
                 'show_item_tax': 0}


def initialize(store):
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS ticket_templates(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            base TEXT NOT NULL, header TEXT NOT NULL DEFAULT '', footer TEXT NOT NULL DEFAULT '',
            show_time INTEGER NOT NULL DEFAULT 1, show_user INTEGER NOT NULL DEFAULT 1,
            show_tax INTEGER NOT NULL DEFAULT 1, is_default INTEGER NOT NULL DEFAULT 0)''')
        columns = {row['name'] for row in c.execute('PRAGMA table_info(ticket_templates)')}
        for key, default in PRINT_OPTIONS.items():
            if key not in columns:
                c.execute(f'ALTER TABLE ticket_templates ADD COLUMN {key} INTEGER NOT NULL DEFAULT {default}')
        if 'line_order' not in columns:
            c.execute("ALTER TABLE ticket_templates ADD COLUMN line_order TEXT NOT NULL DEFAULT 'Por defecto'")
        for field in ('header_image', 'footer_image'):
            if field not in columns:
                c.execute(f"ALTER TABLE ticket_templates ADD COLUMN {field} TEXT NOT NULL DEFAULT ''")


def list_all(store):
    with store.db() as c:
        return [dict(row) for row in c.execute('SELECT * FROM ticket_templates ORDER BY id')]


def current(store):
    with store.db() as c:
        row = c.execute('SELECT * FROM ticket_templates WHERE is_default=1 ORDER BY id LIMIT 1').fetchone()
        return dict(row) if row else None


def save(store, data):
    if not isinstance(data, dict):
        raise ValueError('Plantilla no válida.')
    name = data.get('name', '')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError('El nombre debe tener entre 1 y 80 caracteres.')
    if data.get('base') not in BASES:
        raise ValueError('Elige un formato válido.')
    for field in ('header', 'footer'):
        if not isinstance(data.get(field), str) or len(data[field]) > 500:
            raise ValueError('Cabecera y pie admiten hasta 500 caracteres.')
    images = {}
    for field in ('header_image', 'footer_image'):
        value = data.get(field, '')
        if not isinstance(value, str):
            raise ValueError('Imagen no válida.')
        if value:
            kind, marker, encoded = value.partition(';base64,')
            if not marker or kind not in ('data:image/png', 'data:image/jpeg'):
                raise ValueError('La imagen debe ser PNG o JPEG.')
            try:
                image = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError('Imagen no válida.')
            if len(image) > 180_000 or len(image) < 8:
                raise ValueError('La imagen debe ocupar menos de 180 KB.')
            if kind == 'data:image/png' and not image.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Archivo PNG no válido.')
            if kind == 'data:image/jpeg' and not image.startswith(b'\xff\xd8\xff'):
                raise ValueError('Archivo JPEG no válido.')
        images[field] = value
    for field in ('show_time', 'show_user', 'show_tax', 'is_default'):
        if not isinstance(data.get(field), bool):
            raise ValueError('Opción de impresión no válida.')
    for field in PRINT_OPTIONS:
        if field in data and not isinstance(data[field], bool):
            raise ValueError('Opción de impresión no válida.')
    line_order = data.get('line_order', 'Por defecto')
    if line_order not in LINE_ORDERS:
        raise ValueError('Orden de líneas no válido.')
    values = (name.strip(), data['base'], data['header'].strip(), data['footer'].strip(),
              int(data['show_time']), int(data['show_user']), int(data['show_tax']))
    identity = data.get('id')
    with store.db() as c:
        if identity is None:
            identity = c.execute('''INSERT INTO ticket_templates
                (name,base,header,footer,show_time,show_user,show_tax)
                VALUES(?,?,?,?,?,?,?)''', values).lastrowid
        else:
            try:
                identity = int(identity)
            except (TypeError, ValueError):
                raise ValueError('Plantilla no válida.')
            if not c.execute('SELECT 1 FROM ticket_templates WHERE id=?', (identity,)).fetchone():
                raise ValueError('La plantilla ya no existe.')
            c.execute('''UPDATE ticket_templates SET name=?,base=?,header=?,footer=?,
                show_time=?,show_user=?,show_tax=? WHERE id=?''', values + (identity,))
        if data['is_default']:
            c.execute('UPDATE ticket_templates SET is_default=0 WHERE id<>?', (identity,))
            c.execute('UPDATE ticket_templates SET is_default=1 WHERE id=?', (identity,))
        else:
            c.execute('UPDATE ticket_templates SET is_default=0 WHERE id=?', (identity,))
        c.execute('UPDATE ticket_templates SET line_order=?,' +
                  ','.join(f'{field}=?' for field in PRINT_OPTIONS) + ' WHERE id=?',
                  (line_order, *(int(data.get(field, bool(default)))
                                 for field, default in PRINT_OPTIONS.items()), identity))
        c.execute('UPDATE ticket_templates SET header_image=?,footer_image=? WHERE id=?',
                  (images['header_image'], images['footer_image'], identity))
    return {'id': identity}


def delete(store, data):
    try:
        identity = int(data['id'])
    except (KeyError, ValueError, TypeError):
        raise ValueError('Plantilla no válida.')
    with store.db() as c:
        if not c.execute('DELETE FROM ticket_templates WHERE id=?', (identity,)).rowcount:
            raise ValueError('La plantilla ya no existe.')
    return {'ok': True}
