"""Global administrative preferences awaiting document integration."""
import json

SERIES_TYPES = ('Fra. Simp.', 'Factura', 'Dev. Simp.', 'Devolución', 'Pedido', 'Albarán')


def read(store):
    with store.db() as c:
        row = c.execute("SELECT value FROM settings WHERE key='global_config'").fetchone()
    saved = json.loads(row['value']) if row else {}
    return {'pos_series': {kind: saved.get('pos_series', {}).get(kind) for kind in SERIES_TYPES}}


def save(store, data):
    if not isinstance(data, dict) or not isinstance(data.get('pos_series'), dict):
        raise ValueError('Configuración no válida.')
    values = data['pos_series']
    if set(values) != set(SERIES_TYPES):
        raise ValueError('Faltan tipos de serie.')
    result = {}
    with store.db() as c:
        for kind in SERIES_TYPES:
            identity = values[kind]
            if identity in (None, ''):
                result[kind] = None
                continue
            try:
                identity = int(identity)
            except (TypeError, ValueError):
                raise ValueError('Selecciona una serie válida.')
            row = c.execute('SELECT type,active FROM document_series WHERE id=?', (identity,)).fetchone()
            if not row or row['type'] != kind or not row['active']:
                raise ValueError('La serie seleccionada debe estar activa y coincidir con el tipo.')
            result[kind] = identity
        payload = {'pos_series': result}
        c.execute("INSERT INTO settings(key,value) VALUES('global_config',?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (json.dumps(payload),))
    return payload
