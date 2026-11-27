"""Hospitality features inspired by market POS (Ágora, Numier, Qamarero).

Diners per account, customers (CRM), service type (table, bar, take away,
delivery), invitations, whole-ticket discounts, merging accounts, allergens,
favourite products, staff time clock and a table floor plan. Amounts remain
integer euro cents. Nothing here is fiscal: tickets stay non-fiscal.
"""
import json
import re
from collections import defaultdict
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation

# The 14 allergens of Regulation (EU) 1169/2011, Annex II.
ALLERGENS = {
    'gluten': 'Gluten', 'crustaceos': 'Crustáceos', 'huevo': 'Huevo', 'pescado': 'Pescado',
    'cacahuete': 'Cacahuete', 'soja': 'Soja', 'lacteos': 'Lácteos', 'frutos_cascara': 'Frutos de cáscara',
    'apio': 'Apio', 'mostaza': 'Mostaza', 'sesamo': 'Sésamo', 'sulfitos': 'Sulfitos',
    'altramuces': 'Altramuces', 'moluscos': 'Moluscos',
}
SERVICE_TYPES = {'mesa': 'Mesa', 'barra': 'Barra', 'llevar': 'Para llevar', 'domicilio': 'Domicilio'}
TPV_ACTIONS = {'order_guests', 'order_customer', 'order_service', 'ticket_discount', 'invite',
               'merge', 'clock', 'customer_save', 'bill_request'}
ADMIN_ACTIONS = {'customer_save', 'customer_delete', 'product_extra', 'table_layout', 'prep_notes_save'}
DEFAULT_PREP_NOTES = ['SIN CEBOLLA', 'SIN SAL', 'SIN GLUTEN', 'POCO HECHO', 'AL PUNTO', 'MUY HECHO', 'PARA COMPARTIR',
                      'SALSA APARTE', 'SIN HIELO', 'CON HIELO', 'URGENTE', 'PARA LLEVAR']


def prep_notes(c):
    row = c.execute("SELECT value FROM settings WHERE key='prep_notes'").fetchone()
    return json.loads(row['value']) if row else list(DEFAULT_PREP_NOTES)
from permissions import NEW_HOSPITALITY_RIGHTS as RIGHTS
NOW = lambda: datetime.now().isoformat(timespec='seconds')


def initialize(store):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('''CREATE TABLE IF NOT EXISTS customers(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '', tax_id TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '', allergens TEXT NOT NULL DEFAULT '[]', vip INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS time_clock(
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL CHECK(kind IN ('in','out')), created TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS invitations(
            id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, line_id INTEGER NOT NULL, name TEXT NOT NULL,
            qty INTEGER NOT NULL, amount INTEGER NOT NULL, reason TEXT NOT NULL, user_id INTEGER, created TEXT NOT NULL)''')
        add = lambda table, columns: [c.execute(f'ALTER TABLE {table} ADD COLUMN {n} {k}') for n, k in columns.items()
                                      if n not in {r['name'] for r in c.execute(f'PRAGMA table_info({table})')}]
        add('orders', {'guests': 'INTEGER', 'customer_id': 'INTEGER REFERENCES customers(id)',
                       'service_type': "TEXT NOT NULL DEFAULT ''", 'delivery_address': "TEXT NOT NULL DEFAULT ''",
                       'merged_into': 'INTEGER', 'bill_requested_at': 'TEXT'})
        add('products', {'allergens': "TEXT NOT NULL DEFAULT '[]'", 'favorite': 'INTEGER NOT NULL DEFAULT 0'})
        add('tables', {'pos_x': 'INTEGER', 'pos_y': 'INTEGER', 'shape': "TEXT NOT NULL DEFAULT 'square'",
                       'seats': 'INTEGER NOT NULL DEFAULT 4'})
        # New rights go to the full profiles; Camarero keeps its explicit list.
        if not c.execute("SELECT 1 FROM settings WHERE key='hospitality_rights_v023'").fetchone():
            for row in c.execute("SELECT id,name,permissions FROM user_profiles WHERE name IN ('Administrador','Encargado')").fetchall():
                rights = json.loads(row['permissions'])
                rights += [r for r in RIGHTS if r not in rights]
                c.execute('UPDATE user_profiles SET permissions=? WHERE id=?', (json.dumps(rights), row['id']))
            c.execute("INSERT INTO settings(key,value) VALUES('hospitality_rights_v023','1')")


def text(value, limit, label):
    value = ' '.join(str(value or '').split())
    if len(value) > limit:
        raise ValueError(f'{label}: máximo {limit} caracteres.')
    return value


def allergen_list(values):
    if not isinstance(values, list) or any(v not in ALLERGENS for v in values):
        raise ValueError('Alérgeno no válido.')
    return sorted(set(values))


def customer_row(row):
    result = dict(row)
    result['allergens'] = json.loads(result['allergens'])
    return result


def customers(c, include_inactive=False):
    rows = c.execute('''SELECT cu.*, (SELECT COUNT(*) FROM orders o WHERE o.customer_id=cu.id AND o.status='paid') visits,
        (SELECT COALESCE(SUM(total),0) FROM orders o WHERE o.customer_id=cu.id AND o.status='paid') spent,
        (SELECT MAX(paid_at) FROM orders o WHERE o.customer_id=cu.id AND o.status='paid') last_visit
        FROM customers cu''' + ('' if include_inactive else ' WHERE active=1') + ' ORDER BY vip DESC, name')
    return [customer_row(r) for r in rows]


def clock_status(c, user_id):
    row = c.execute('SELECT kind, created FROM time_clock WHERE user_id=? ORDER BY id DESC LIMIT 1', (user_id,)).fetchone()
    return {'working': bool(row and row['kind'] == 'in'), 'since': row['created'] if row else None}


def extend_state(store, data, user_id):
    """Add hospitality data to /api/state."""
    with store.db() as c:
        data['allergens'] = ALLERGENS
        data['service_types'] = SERVICE_TYPES
        data['customers'] = customers(c)
        data['clock'] = clock_status(c, user_id)
        data['prep_notes'] = prep_notes(c)
        extra = {r['id']: r for r in c.execute('SELECT id, allergens, favorite FROM products')}
        for p in data.get('products', []):
            p['allergens'] = json.loads(extra[p['id']]['allergens']) if p['id'] in extra else []
            p['favorite'] = bool(extra[p['id']]['favorite']) if p['id'] in extra else False
        layout = {r['id']: dict(r) for r in c.execute('SELECT id, pos_x, pos_y, shape, seats FROM tables')}
        for t in data.get('tables', []):
            t.update({k: v for k, v in layout.get(t['id'], {}).items() if k != 'id'})
        names = {cu['id']: cu['name'] for cu in data['customers']}
        for o in data.get('orders', []):
            o['customer_name'] = names.get(o.get('customer_id'))
            o['minutes_open'] = minutes_since(o.get('created'))
        data['best_sellers'] = [r[0] for r in c.execute(
            "SELECT l.product_id FROM lines l JOIN orders o ON o.id=l.order_id WHERE o.status='paid' AND o.paid_at>=? "
            "GROUP BY l.product_id ORDER BY SUM(l.qty) DESC LIMIT 12", ((date.today() - timedelta(days=30)).isoformat(),))]
    return data


def minutes_since(stamp):
    try:
        return max(0, int((datetime.now() - datetime.fromisoformat(stamp)).total_seconds() // 60))
    except (TypeError, ValueError):
        return None


def mutate(store, action, data, actor, app):
    import permissions
    allowed = TPV_ACTIONS if app == 'tpv' else ADMIN_ACTIONS
    if action not in allowed:
        raise PermissionError('Esta operación pertenece a la otra aplicación.')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        rights = permissions.rights(c, actor)
        store.audit(c, actor, action, data.get('order_id'))

        def need(right):
            if right not in rights:
                raise PermissionError('Tu perfil no permite esta operación en el TPV.')

        if action == 'clock':
            kind = data.get('kind')
            if kind not in ('in', 'out'):
                raise ValueError('Fichaje no válido.')
            current = clock_status(c, actor)
            if (kind == 'in') == current['working']:
                raise ValueError('Ya has fichado la entrada.' if kind == 'in' else 'No tienes una entrada abierta.')
            c.execute('INSERT INTO time_clock(user_id, kind, created) VALUES(?,?,?)', (actor, kind, NOW()))
            return clock_status(c, actor)

        if action in ('customer_save', 'customer_delete'):
            if app == 'tpv':
                need('customer_manage')
            if action == 'customer_delete':
                c.execute('UPDATE customers SET active=0 WHERE id=?', (int(data['id']),))
                return {'ok': True}
            name = text(data.get('name'), 120, 'Nombre').upper()
            if not name:
                raise ValueError('El nombre del cliente es obligatorio.')
            email = text(data.get('email'), 120, 'Email')
            if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
                raise ValueError('El email no es válido.')
            values = (name, text(data.get('phone'), 30, 'Teléfono'), email, text(data.get('tax_id'), 20, 'NIF').upper(),
                      text(data.get('address'), 200, 'Dirección'), str(data.get('notes') or '')[:500],
                      json.dumps(allergen_list(data.get('allergens', []))), int(bool(data.get('vip'))))
            cid = data.get('id')
            if cid:
                if not c.execute('SELECT 1 FROM customers WHERE id=?', (cid,)).fetchone():
                    raise ValueError('Cliente no encontrado.')
                c.execute('UPDATE customers SET name=?,phone=?,email=?,tax_id=?,address=?,notes=?,allergens=?,vip=?,active=1 WHERE id=?', values + (cid,))
            else:
                cid = c.execute('INSERT INTO customers(name,phone,email,tax_id,address,notes,allergens,vip,created) VALUES(?,?,?,?,?,?,?,?,?)', values + (NOW(),)).lastrowid
            return {'customer_id': cid}

        if action == 'prep_notes_save':
            notes = data.get('notes')
            if not isinstance(notes, list) or len(notes) > 40:
                raise ValueError('Hasta 40 notas rápidas.')
            clean = []
            for n in notes:
                n = text(n, 40, 'Nota').upper()
                if n and n not in clean:
                    clean.append(n)
            c.execute("INSERT INTO settings(key,value) VALUES('prep_notes',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(clean),))
            return {'notes': clean}

        if action == 'product_extra':
            pid = int(data['product_id'])
            if not c.execute('SELECT 1 FROM products WHERE id=?', (pid,)).fetchone():
                raise ValueError('Producto no encontrado.')
            c.execute('UPDATE products SET allergens=?, favorite=? WHERE id=?',
                      (json.dumps(allergen_list(data.get('allergens', []))), int(bool(data.get('favorite'))), pid))
            return {'ok': True}

        if action == 'table_layout':
            items = data.get('tables', [])
            if not isinstance(items, list) or len(items) > 1000:
                raise ValueError('Plano no válido.')
            for item in items:
                x, y, seats = int(item['x']), int(item['y']), int(item.get('seats', 4))
                shape = item.get('shape', 'square')
                if not (0 <= x <= 100 and 0 <= y <= 100) or shape not in ('square', 'round', 'long') or not 1 <= seats <= 30:
                    raise ValueError('Revisa la posición, forma y plazas de las mesas.')
                c.execute('UPDATE tables SET pos_x=?, pos_y=?, shape=?, seats=? WHERE id=?', (x, y, shape, seats, int(item['id'])))
            return {'ok': True}

        # Remaining actions work on an open account during an open shift.
        import cash_register
        cash_register.require_open(c)
        order = store.require_open(c, data['order_id'])

        if action == 'order_guests':
            need('ticket_open')
            guests = int(data.get('guests') or 0)
            if not 0 <= guests <= 500:
                raise ValueError('Comensales entre 0 y 500.')
            c.execute('UPDATE orders SET guests=? WHERE id=?', (guests or None, order['id']))
            return {'ok': True}

        if action == 'bill_request':
            need('ticket_open')
            c.execute('UPDATE orders SET bill_requested_at=? WHERE id=?', (NOW() if data.get('requested') else None, order['id']))
            return {'ok': True}

        if action == 'order_customer':
            need('ticket_open')
            cid = data.get('customer_id')
            if cid is not None and not c.execute('SELECT 1 FROM customers WHERE id=? AND active=1', (cid,)).fetchone():
                raise ValueError('Cliente no encontrado.')
            c.execute('UPDATE orders SET customer_id=? WHERE id=?', (cid, order['id']))
            return {'ok': True}

        if action == 'order_service':
            need('ticket_open')
            kind = data.get('service_type', '')
            if kind not in SERVICE_TYPES:
                raise ValueError('Tipo de servicio no válido.')
            address = text(data.get('address'), 200, 'Dirección')
            if kind == 'domicilio' and not address:
                raise ValueError('Indica la dirección de entrega.')
            c.execute('UPDATE orders SET service_type=?, delivery_address=? WHERE id=?', (kind, address, order['id']))
            if not order['table_id'] and kind != 'mesa':
                c.execute('UPDATE orders SET source_label=? WHERE id=?', (SERVICE_TYPES[kind].upper() + f" #{order['id']}", order['id']))
            return {'ok': True}

        if action in ('ticket_discount', 'invite'):
            import line_pricing
            if order['payments']:
                raise ValueError('La cuenta ya tiene pagos. No se pueden cambiar sus precios.')
            if not order['lines']:
                raise ValueError('La cuenta está vacía.')
            if action == 'invite':
                need('ticket_invite')
                reason = text(data.get('reason'), 200, 'Motivo')
                if not reason:
                    raise ValueError('Indica el motivo de la invitación.')
                ids = data.get('line_ids') or [l['id'] for l in order['lines']]
                kind, value = 'invite', 10000
            else:
                need('ticket_discount')
                kind = data.get('kind')
                if kind == 'clear':
                    value = 0
                elif kind == 'percent':
                    try:
                        number = Decimal(str(data.get('value')).replace(',', '.'))
                        if not number.is_finite() or not 0 < number <= 100 or number * 100 != (number * 100).to_integral_value():
                            raise ValueError('El porcentaje debe estar entre 0,01 y 100.')
                    except InvalidOperation:
                        raise ValueError('Porcentaje no válido.')
                    value = int(number * 100)
                else:
                    raise ValueError('Tipo de descuento no válido.')
                ids = [l['id'] for l in order['lines']]
            lines = {l['id']: l for l in order['lines']}
            if any(i not in lines for i in ids):
                raise ValueError('Las líneas no pertenecen a esta cuenta.')
            for lid in ids:
                line = lines[lid]
                base = line['base_price'] if line['base_price'] is not None else line['price']
                if action == 'ticket_discount' and line['discount_kind'] == 'invite':
                    continue
                new_kind = None if kind == 'clear' else kind
                price = line_pricing.net_price(base, new_kind, value)
                c.execute('UPDATE lines SET base_price=?, price=?, discount_kind=?, discount_value=?, pricing_revision=pricing_revision+1 WHERE id=?',
                          (base, price, new_kind, value if new_kind else 0, lid))
                if action == 'invite':
                    c.execute('INSERT INTO invitations(order_id,line_id,name,qty,amount,reason,user_id,created) VALUES(?,?,?,?,?,?,?,?)',
                              (order['id'], lid, line['name'], line['qty'], base * line['qty'], reason, actor, NOW()))
            return {'ok': True}

        if action == 'merge':
            need('ticket_merge')
            source = store.require_open(c, int(data['source_order_id']))
            if source['id'] == order['id']:
                raise ValueError('Elige otra cuenta para unir.')
            if source['payments'] or order['payments']:
                raise ValueError('No se pueden unir cuentas con pagos registrados.')
            c.execute('UPDATE lines SET order_id=? WHERE order_id=?', (order['id'], source['id']))
            c.execute("UPDATE orders SET status='void', merged_into=?, table_id=NULL WHERE id=?", (order['id'], source['id']))
            if source.get('guests'):
                c.execute('UPDATE orders SET guests=COALESCE(guests,0)+? WHERE id=?', (source['guests'], order['id']))
            return {'ok': True, 'order_id': order['id']}
    raise ValueError('Acción no disponible.')


# ---------- Reports ----------
REPORTS = {'Invitaciones', 'Alérgenos por producto', 'Comensales por centro de venta', 'Cancelaciones por usuario',
           'Ventas a cliente', 'Productos vendidos a cada cliente', 'Control horario', 'Descuentos por usuario y tipo'}


def report(store, name, start, end):
    from analytics import bounds
    a, b = bounds(start, end)
    with store.db() as c:
        c.execute('BEGIN')
        if name == 'Invitaciones':
            cols = [['Fecha', 'text'], ['Cuenta', 'text'], ['Producto', 'text'], ['Uds.', 'number'], ['Usuario', 'text'], ['Motivo', 'text'], ['Importe invitado', 'money']]
            rows = [list(r) for r in c.execute("SELECT i.created,i.order_id,i.name,i.qty,COALESCE(u.name,''),i.reason,i.amount FROM invitations i LEFT JOIN users u ON u.id=i.user_id WHERE i.created>=? AND i.created<? ORDER BY i.id", (a, b))]
            return dict(columns=cols, rows=rows, note='Importe a precio de carta de lo invitado. No es una venta ni un cobro.')
        if name == 'Alérgenos por producto':
            cols = [['Producto', 'text'], ['Categoría', 'text'], ['Alérgenos', 'text']]
            rows = [[r['name'], r['category'], ', '.join(ALLERGENS[x] for x in json.loads(r['allergens'])) or 'Sin alérgenos declarados']
                    for r in c.execute('SELECT p.name,ca.name category,p.allergens FROM products p JOIN categories ca ON ca.id=p.category_id WHERE p.active=1 ORDER BY p.name')]
            return dict(columns=cols, rows=rows, note='Declaración interna configurada en Administración → Productos. Revísala con tus fichas técnicas.')
        if name == 'Comensales por centro de venta':
            cols = [['Centro', 'text'], ['Cuentas', 'number'], ['Comensales', 'number'], ['Venta', 'money'], ['Media por comensal', 'money']]
            rows = []
            for r in c.execute("SELECT COALESCE(ce.name,'VENTA DIRECTA') center,COUNT(*) n,COALESCE(SUM(o.guests),0) g,COALESCE(SUM(o.total),0) t FROM orders o LEFT JOIN tables tb ON tb.id=o.table_id LEFT JOIN centers ce ON ce.id=tb.center_id WHERE o.status='paid' AND o.paid_at>=? AND o.paid_at<? GROUP BY center ORDER BY t DESC", (a, b)):
                rows.append([r['center'], r['n'], r['g'], r['t'], (r['t'] // r['g']) if r['g'] else 0])
            return dict(columns=cols, rows=rows, note='Solo cuentan los comensales indicados al abrir o editar la cuenta.')
        if name == 'Cancelaciones por usuario':
            cols = [['Usuario', 'text'], ['Líneas canceladas', 'number'], ['Unidades', 'number']]
            rows = [list(r) for r in c.execute("SELECT COALESCE(u.name,'ANTERIOR'),COUNT(*),SUM(l.qty) FROM line_cancellations l LEFT JOIN users u ON u.id=l.user_id WHERE l.created>=? AND l.created<? GROUP BY l.user_id ORDER BY 2 DESC", (a, b))]
            return dict(columns=cols, rows=rows, note='Líneas borradas de cuentas abiertas. Las cuentas canceladas completas figuran en el historial de caja.')
        if name == 'Descuentos por usuario y tipo':
            totals = defaultdict(lambda: [0, 0])
            for r in c.execute("SELECT COALESCE(u.name,'ANTERIOR') user,after_data FROM line_pricing_changes p LEFT JOIN users u ON u.id=p.user_id WHERE p.created>=? AND p.created<?", (a, b)):
                kind = json.loads(r['after_data']).get('discount_kind') or 'retirado'
                totals[(r['user'], kind)][0] += 1
            for r in c.execute("SELECT COALESCE(u.name,'ANTERIOR') user,COUNT(*) n,SUM(amount) amount FROM invitations i LEFT JOIN users u ON u.id=i.user_id WHERE i.created>=? AND i.created<? GROUP BY i.user_id", (a, b)):
                totals[(r['user'], 'invitación')] = [r['n'], r['amount']]
            labels = {'percent': 'Porcentaje', 'amount': 'Importe por unidad', 'retirado': 'Descuento retirado', 'invitación': 'Invitación', 'invite': 'Invitación'}
            cols = [['Usuario', 'text'], ['Tipo', 'text'], ['Operaciones', 'number'], ['Importe invitado', 'money']]
            rows = [[u, labels.get(k, k), v[0], v[1]] for (u, k), v in sorted(totals.items())]
            return dict(columns=cols, rows=rows, note='Descuentos de línea registrados y las invitaciones. Los descuentos de ticket entero se registran en la auditoría.')
        if name in ('Ventas a cliente', 'Productos vendidos a cada cliente'):
            if name == 'Ventas a cliente':
                cols = [['Cliente', 'text'], ['Teléfono', 'text'], ['Cuentas', 'number'], ['Venta', 'money']]
                rows = [list(r) for r in c.execute("SELECT cu.name,cu.phone,COUNT(*),SUM(o.total) FROM orders o JOIN customers cu ON cu.id=o.customer_id WHERE o.status='paid' AND o.paid_at>=? AND o.paid_at<? GROUP BY cu.id ORDER BY 4 DESC", (a, b))]
            else:
                cols = [['Cliente', 'text'], ['Producto', 'text'], ['Unidades', 'number'], ['Importe', 'money']]
                rows = [list(r) for r in c.execute("SELECT cu.name,l.name,SUM(l.qty),SUM(l.qty*l.price) FROM lines l JOIN orders o ON o.id=l.order_id JOIN customers cu ON cu.id=o.customer_id WHERE o.status='paid' AND o.paid_at>=? AND o.paid_at<? GROUP BY cu.id,l.name ORDER BY cu.name,4 DESC", (a, b))]
            return dict(columns=cols, rows=rows, note='Cuentas cerradas con cliente asignado. No son facturas.')
        if name == 'Control horario':
            cols = [['Usuario', 'text'], ['Entrada', 'text'], ['Salida', 'text'], ['Horas', 'text']]
            rows = []
            open_in = {}
            for r in c.execute('SELECT t.user_id,u.name,t.kind,t.created FROM time_clock t JOIN users u ON u.id=t.user_id WHERE t.created>=? AND t.created<? ORDER BY t.id', (a, b)):
                if r['kind'] == 'in':
                    open_in[r['user_id']] = (r['name'], r['created'])
                elif r['user_id'] in open_in:
                    who, since = open_in.pop(r['user_id'])
                    rows.append([who, since, r['created'], hours(since, r['created'])])
            for who, since in open_in.values():
                rows.append([who, since, 'Sin salida', hours(since, NOW()) + ' (en curso)'])
            return dict(columns=cols, rows=rows, note='Registro interno de entrada y salida desde el TPV. Consérvalo según la normativa de registro de jornada.')
    raise ValueError('Informe desconocido.')


def hours(a, b):
    minutes = int((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() // 60)
    return f'{minutes // 60} h {minutes % 60:02d} min'
