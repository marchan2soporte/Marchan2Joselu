"""Local layouts for Marchan2's non-fiscal test receipts."""

BASES = ('80 mm', 'A4')


def initialize(store):
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS ticket_templates(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            base TEXT NOT NULL, header TEXT NOT NULL DEFAULT '', footer TEXT NOT NULL DEFAULT '',
            show_time INTEGER NOT NULL DEFAULT 1, show_user INTEGER NOT NULL DEFAULT 1,
            show_tax INTEGER NOT NULL DEFAULT 1, is_default INTEGER NOT NULL DEFAULT 0)''')


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
    for field in ('show_time', 'show_user', 'show_tax', 'is_default'):
        if not isinstance(data.get(field), bool):
            raise ValueError('Opción de impresión no válida.')
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
