"""Company profile stored in the existing local settings database."""
import json
import re

FIELDS = {
    'legal_name': 160, 'trade_name': 160, 'tax_id': 32,
    'address': 240, 'city': 120, 'province': 120, 'postal_code': 20,
    'contact': 160, 'phone': 40, 'email': 254, 'website': 240,
}


def read(store):
    with store.db() as c:
        row = c.execute("SELECT value FROM settings WHERE key='company'").fetchone()
    saved = json.loads(row['value']) if row else {}
    return {key: saved.get(key, '') for key in FIELDS}


def save(store, data):
    if not isinstance(data, dict):
        raise ValueError('Datos de empresa no válidos.')
    result = {}
    for key, limit in FIELDS.items():
        value = data.get(key, '')
        if not isinstance(value, str) or len(value.strip()) > limit:
            raise ValueError('Revisa los campos: hay un valor no válido o demasiado largo.')
        result[key] = value.strip()
    if result['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+', result['email']):
        raise ValueError('Introduce un email válido.')
    with store.db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES('company',?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (json.dumps(result, ensure_ascii=False),))
    return result
