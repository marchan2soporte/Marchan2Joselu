"""Administrative document-series configuration, not yet used for issuing documents."""

TYPES = ('Fra. Simp.', 'Factura', 'Albarán', 'Dev. Simp.', 'Devolución',
         'Pedido', 'Ped. Proveedor', 'Alb. Proveedor', 'Fra. Proveedor')


def initialize(store):
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS document_series(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            type TEXT NOT NULL, next_number INTEGER NOT NULL CHECK(next_number BETWEEN 1 AND 999999999),
            active INTEGER NOT NULL DEFAULT 1)''')


def list_all(store):
    with store.db() as c:
        return [dict(row) for row in c.execute(
            'SELECT id,name,type,next_number,active FROM document_series ORDER BY id')]


def save(store, data):
    if not isinstance(data, dict):
        raise ValueError('Datos de serie no válidos.')
    name = data.get('name', '')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40:
        raise ValueError('El nombre debe tener entre 1 y 40 caracteres.')
    kind = data.get('type')
    if kind not in TYPES:
        raise ValueError('Elige un tipo de serie válido.')
    try:
        number = int(data.get('next_number'))
    except (TypeError, ValueError):
        raise ValueError('Introduce un número siguiente válido.')
    if str(data.get('next_number')) != str(number) or not 1 <= number <= 999999999:
        raise ValueError('El número siguiente debe estar entre 1 y 999999999.')
    active = data.get('active', True)
    if not isinstance(active, bool):
        raise ValueError('Estado de la serie no válido.')
    identity = data.get('id')
    with store.db() as c:
        if identity is None:
            identity = c.execute(
                'INSERT INTO document_series(name,type,next_number,active) VALUES(?,?,?,?)',
                (name.strip(), kind, number, int(active))).lastrowid
        else:
            try:
                identity = int(identity)
            except (TypeError, ValueError):
                raise ValueError('Serie no válida.')
            if not c.execute('SELECT 1 FROM document_series WHERE id=?', (identity,)).fetchone():
                raise ValueError('La serie ya no existe.')
            c.execute('UPDATE document_series SET name=?,type=?,next_number=?,active=? WHERE id=?',
                      (name.strip(), kind, number, int(active), identity))
    return {'id': identity}


def delete(store, data):
    try:
        identity = int(data['id'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('Serie no válida.')
    with store.db() as c:
        if not c.execute('DELETE FROM document_series WHERE id=?', (identity,)).rowcount:
            raise ValueError('La serie ya no existe.')
    return {'ok': True}
