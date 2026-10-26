"""Shared local preferences for active POS behavior and future modules."""
import json

SERIES_TYPES = ('Fra. Simp.', 'Factura', 'Dev. Simp.', 'Devolución', 'Pedido', 'Albarán')
BOOL_OPTIONS = ('stock_warning', 'cancel_reason', 'consolidate_lines',
                'include_center_sales', 'include_diners', 'include_user_sales',
                'include_invites', 'include_cancellations', 'include_user_payments',
                'include_tips', 'include_returns', 'include_family_sales',
                'include_pending', 'include_cash_balance', 'automatic_close',
                'finish_preparations', 'print_daily_sales', 'web_invoicing')
CHOICES = {
    'tip_suggestion': ('Ninguna', 'Porcentaje', 'Importe fijo'),
    'service_charge_basis': ('Impuestos incluidos', 'Impuestos excluidos'),
    'scan_pay': ('Desactivado',),
    'table_order': ('Desactivado',),
    'customer_scope': ('Todos los grupos', 'Grupos seleccionados'),
    'command_template': ('Sin asignar',),
}


def defaults():
    return {**{key: key == 'consolidate_lines' for key in BOOL_OPTIONS},
            **{key: values[0] for key, values in CHOICES.items()},
            'service_charge_percent': '0', 'simplified_invoice_limit': '',
            'tip_suggestion_value': '0',
            'service_charge_tax': 'Exento'}


def read(store):
    with store.db() as c:
        row = c.execute("SELECT value FROM settings WHERE key='global_config'").fetchone()
    saved = json.loads(row['value']) if row else {}
    return {'pos_series': {kind: saved.get('pos_series', {}).get(kind) for kind in SERIES_TYPES},
            'preferences': {**defaults(), **saved.get('preferences', {})}}


def save(store, data):
    if not isinstance(data, dict) or not isinstance(data.get('pos_series'), dict):
        raise ValueError('Configuración no válida.')
    preferences = data.get('preferences', defaults())
    if not isinstance(preferences, dict) or set(preferences) != set(defaults()):
        raise ValueError('Faltan opciones de configuración.')
    for key in BOOL_OPTIONS:
        if not isinstance(preferences[key], bool):
            raise ValueError('Opción no válida: ' + key)
    for key, choices in CHOICES.items():
        if key == 'command_template':
            continue
        if preferences[key] not in choices:
            raise ValueError('Selección no válida: ' + key)
    for key in ('service_charge_percent', 'simplified_invoice_limit', 'tip_suggestion_value'):
        value = preferences[key]
        if not isinstance(value, str) or len(value) > 20:
            raise ValueError('Importe no válido.')
        if value:
            try:
                amount = float(value.replace(',', '.'))
            except ValueError:
                raise ValueError('Introduce un importe válido.')
            if not 0 <= amount <= (100 if key in ('service_charge_percent', 'tip_suggestion_value') else 100000):
                raise ValueError('Importe fuera de rango.')
    if preferences['service_charge_tax'] not in ('Exento', '0 %', '4 %', '10 %', '21 %'):
        raise ValueError('Impuesto no válido.')
    values = data['pos_series']
    if set(values) != set(SERIES_TYPES):
        raise ValueError('Faltan tipos de serie.')
    result = {}
    with store.db() as c:
        template = preferences['command_template']
        if template != 'Sin asignar':
            try:
                template_id = int(template)
            except (TypeError, ValueError):
                raise ValueError('Plantilla de comandas no válida.')
            if not c.execute('SELECT 1 FROM ticket_templates WHERE id=?', (template_id,)).fetchone():
                raise ValueError('La plantilla de comandas ya no existe.')
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
        payload = {'pos_series': result, 'preferences': preferences}
        c.execute("INSERT INTO settings(key,value) VALUES('global_config',?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (json.dumps(payload),))
    return payload
