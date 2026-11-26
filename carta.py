"""Carta avanzada: tarifas y happy hour, menús, escandallos y tiempos de cocina.

- Tarifas: reglas de precio por centro de venta, días, franja horaria y
  categorías. Se aplica una sola regla (la de mayor prioridad) al añadir la línea.
- Menús: un producto con secciones (primero, segundo, bebida…). Al venderlo se
  crea la línea del menú con su precio y una línea a 0 € por cada plato elegido,
  que va a cocina por su orden de preparación.
- Escandallos: ingredientes del almacén por producto o formato. Al cerrar la
  cuenta se descuentan automáticamente; también dan coste y margen.
- Tiempos de cocina: hora de envío y de «listo» de cada línea (triggers SQLite).
Los importes siguen en céntimos enteros y las cantidades de almacén en milésimas.
"""
import json
import re
from collections import defaultdict
from datetime import datetime

NOW = lambda: datetime.now().isoformat(timespec='seconds')
COURSES = ('PRIMERO', 'SEGUNDO', 'TERCEROS', 'BEBIDAS', 'POSTRES')
ADMIN_ACTIONS = {'tariff_save', 'tariff_delete', 'menu_save', 'recipe_save'}
TPV_ACTIONS = {'add_menu'}


def initialize(store):
    import inventory
    inventory.initialize(store)
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('''CREATE TABLE IF NOT EXISTS tariffs(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, percent INTEGER NOT NULL,
            centers TEXT NOT NULL DEFAULT '[]', days TEXT NOT NULL DEFAULT '[]',
            start_time TEXT NOT NULL DEFAULT '', end_time TEXT NOT NULL DEFAULT '',
            categories TEXT NOT NULL DEFAULT '[]', priority INTEGER NOT NULL DEFAULT 10,
            active INTEGER NOT NULL DEFAULT 1)''')
        c.execute('''CREATE TABLE IF NOT EXISTS recipes(
            id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id),
            format_id INTEGER REFERENCES formats(id), item_id INTEGER NOT NULL REFERENCES stock_items(id),
            qty INTEGER NOT NULL CHECK(qty>0))''')
        add = lambda table, columns: [c.execute(f'ALTER TABLE {table} ADD COLUMN {n} {k}') for n, k in columns.items()
                                      if n not in {r['name'] for r in c.execute(f'PRAGMA table_info({table})')}]
        add('lines', {'tariff': "TEXT NOT NULL DEFAULT ''", 'menu_role': 'TEXT', 'menu_parent_id': 'INTEGER',
                      'sent_at': 'TEXT', 'ready_at': 'TEXT'})
        add('products', {'menu_sections': "TEXT NOT NULL DEFAULT '[]'"})
        add('orders', {'stock_consumed': 'INTEGER NOT NULL DEFAULT 0'})
        c.execute('''CREATE TRIGGER IF NOT EXISTS line_sent_insert AFTER INSERT ON lines WHEN NEW.kitchen='pending'
            BEGIN UPDATE lines SET sent_at=strftime('%Y-%m-%dT%H:%M:%S','now','localtime') WHERE id=NEW.id; END''')
        c.execute('''CREATE TRIGGER IF NOT EXISTS line_sent_update AFTER UPDATE OF kitchen ON lines
            WHEN NEW.kitchen='pending' AND OLD.kitchen='new'
            BEGIN UPDATE lines SET sent_at=strftime('%Y-%m-%dT%H:%M:%S','now','localtime') WHERE id=NEW.id; END''')
        c.execute('''CREATE TRIGGER IF NOT EXISTS line_ready_update AFTER UPDATE OF kitchen ON lines
            WHEN NEW.kitchen='ready' AND OLD.kitchen='pending'
            BEGIN UPDATE lines SET ready_at=strftime('%Y-%m-%dT%H:%M:%S','now','localtime') WHERE id=NEW.id; END''')


# ---------- Tarifas ----------
def _json_ids(value, label):
    if not isinstance(value, list) or any(type(v) is not int for v in value):
        raise ValueError(f'{label} no válidos.')
    return sorted(set(value))


def _time(value):
    value = str(value or '').strip()
    if value and not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', value):
        raise ValueError('Hora no válida. Usa el formato HH:MM.')
    return value


def tariffs(c):
    rows = [dict(r) for r in c.execute('SELECT * FROM tariffs ORDER BY priority, id')]
    for r in rows:
        for key in ('centers', 'days', 'categories'):
            r[key] = json.loads(r[key])
        r['active'] = bool(r['active'])
    return rows


def matching_tariff(c, order_id, category_id, when=None):
    when = when or datetime.now()
    row = c.execute('SELECT t.center_id FROM orders o LEFT JOIN tables t ON t.id=o.table_id WHERE o.id=?', (order_id,)).fetchone()
    center = row['center_id'] if row else None
    hhmm = when.strftime('%H:%M')
    for t in tariffs(c):
        if not t['active']:
            continue
        if t['centers'] and center not in t['centers']:
            continue
        if t['days'] and when.weekday() not in t['days']:
            continue
        if t['categories'] and category_id not in t['categories']:
            continue
        start, end = t['start_time'], t['end_time']
        if start and end:
            inside = start <= hhmm < end if start < end else (hhmm >= start or hhmm < end)
            if not inside:
                continue
        return t
    return None


def apply_tariff(c, order_id, category_id, price, when=None):
    t = matching_tariff(c, order_id, category_id, when)
    if not t or not t['percent']:
        return price, ''
    return max(0, (price * (10000 + t['percent']) + 5000) // 10000), t['name']


# ---------- Menús ----------
def menu_sections(c, product_id):
    row = c.execute('SELECT menu_sections FROM products WHERE id=?', (product_id,)).fetchone()
    return json.loads(row['menu_sections']) if row else []


def add_menu(store, c, data, actor):
    import cash_register
    from pos_profiles import active_options
    cash_register.require_open(c)
    store.require_open(c, data['order_id'])
    row = c.execute('SELECT f.*,p.name product_name,p.tax,p.category_id,p.menu_sections FROM formats f JOIN products p ON p.id=f.product_id WHERE f.id=? AND f.active=1 AND p.active=1', (data['format_id'],)).fetchone()
    if not row:
        raise ValueError('El menú ya no está disponible.')
    sections = json.loads(row['menu_sections'])
    if not sections:
        raise ValueError('Este producto no es un menú.')
    choices = data.get('choices')
    if not isinstance(choices, list) or len(choices) != len(sections):
        raise ValueError('Elige un plato de cada apartado del menú.')
    auto_prepare = active_options(c)['auto_prepare']
    price, tariff = apply_tariff(c, data['order_id'], row['category_id'], row['price'])
    parent = c.execute('''INSERT INTO lines(order_id,product_id,format_id,name,format,price,qty,tax,extras,note,prep,course,kitchen,
        base_price,reference_price,tariff,menu_role) VALUES(?,?,?,?,?,?,1,?,?,?,?,?,?,?,?,?,'parent')''',
                       (data['order_id'], row['product_id'], row['id'], row['product_name'], row['name'], price, row['tax'], '[]',
                        str(data.get('note', ''))[:300], 'MENÚ', 'PRIMERO', 'ready', price, row['price'], tariff)).lastrowid
    created = []
    for section, choice in zip(sections, choices):
        if choice not in section['options']:
            raise ValueError(f"El plato elegido no pertenece a {section['name']}.")
        p = c.execute('SELECT p.*,(SELECT id FROM formats WHERE product_id=p.id AND active=1 ORDER BY id LIMIT 1) format_id, (SELECT name FROM formats WHERE product_id=p.id AND active=1 ORDER BY id LIMIT 1) format_name FROM products p WHERE p.id=? AND p.active=1', (choice,)).fetchone()
        if not p or not p['format_id']:
            raise ValueError('Un plato del menú ya no está disponible.')
        lid = c.execute('''INSERT INTO lines(order_id,product_id,format_id,name,format,price,qty,tax,extras,note,prep,course,kitchen,
            base_price,reference_price,menu_role,menu_parent_id) VALUES(?,?,?,?,?,0,1,?,?,?,?,?,?,0,0,'item',?)''',
                        (data['order_id'], p['id'], p['format_id'], p['name'], 'MENÚ · ' + section['name'], row['tax'], '[]', '',
                         p['prep'], section.get('course') or p['course'], 'pending' if auto_prepare else 'new', parent)).lastrowid
        created.append(lid)
    if auto_prepare:
        from printing import enqueue_kitchen
        enqueue_kitchen(c, store, data['order_id'], created)
    return {'line_id': parent}


def guard_line(c, line_id, action):
    """Menu lines are added and removed as a whole."""
    row = c.execute('SELECT menu_role FROM lines WHERE id=?', (line_id,)).fetchone()
    if not row or not row['menu_role']:
        return
    if row['menu_role'] == 'item':
        raise ValueError('Este plato forma parte de un menú. Cancela la línea del menú completo.')
    if action == 'quantity':
        raise ValueError('Los menús se añaden de uno en uno. Cancela la línea para quitarlo.')


def menu_children(c, line_id):
    return [dict(r) for r in c.execute('SELECT * FROM lines WHERE menu_parent_id=?', (line_id,))]


# ---------- Escandallos ----------
def last_cost(c, item_id):
    row = c.execute("SELECT cost FROM stock_moves WHERE item_id=? AND kind='receipt' ORDER BY id DESC LIMIT 1", (item_id,)).fetchone()
    return row['cost'] if row else 0


def recipes(c):
    rows = [dict(r) for r in c.execute('SELECT r.*,i.name item_name,i.unit FROM recipes r JOIN stock_items i ON i.id=r.item_id ORDER BY r.product_id,r.id')]
    for r in rows:
        r['cost'] = (r['qty'] * last_cost(c, r['item_id']) + 500) // 1000
    return rows


def format_cost(c, product_id, format_id):
    rows = c.execute('SELECT * FROM recipes WHERE product_id=? AND format_id=?', (product_id, format_id)).fetchall() or \
        c.execute('SELECT * FROM recipes WHERE product_id=? AND format_id IS NULL', (product_id,)).fetchall()
    if not rows:
        return None
    return sum((r['qty'] * last_cost(c, r['item_id']) + 500) // 1000 for r in rows)


def consume(c, order_id, actor):
    """Descuenta del almacén los ingredientes de una cuenta cerrada (una sola vez)."""
    order = c.execute('SELECT stock_consumed FROM orders WHERE id=?', (order_id,)).fetchone()
    if not order or order['stock_consumed']:
        return 0
    moves = 0
    for line in c.execute("SELECT * FROM lines WHERE order_id=? AND COALESCE(menu_role,'')<>'parent'", (order_id,)).fetchall():
        rows = c.execute('SELECT * FROM recipes WHERE product_id=? AND format_id=?', (line['product_id'], line['format_id'])).fetchall() or \
            c.execute('SELECT * FROM recipes WHERE product_id=? AND format_id IS NULL', (line['product_id'],)).fetchall()
        for r in rows:
            qty = r['qty'] * line['qty']
            cost = last_cost(c, r['item_id'])
            c.execute('''INSERT INTO stock_moves(item_id,supplier_id,qty,cost,total,kind,reference,created,user_id,request_id)
                VALUES(?,NULL,?,?,?,'sale',?,?,?,?)''', (r['item_id'], -qty, cost, -((cost * qty + 500) // 1000),
                                                       f'VENTA CUENTA #{order_id} · {line["name"]}', NOW(), actor,
                                                       f'sale-{order_id}-{line["id"]}-{r["id"]}'))
            moves += 1
    c.execute('UPDATE orders SET stock_consumed=1 WHERE id=?', (order_id,))
    return moves


# ---------- Estado y acciones ----------
def extend_state(store, data):
    with store.db() as c:
        data['tariffs'] = tariffs(c)
        sections = {r['id']: json.loads(r['menu_sections']) for r in c.execute('SELECT id, menu_sections FROM products')}
        costs = {}
        for p in data.get('products', []):
            p['menu_sections'] = sections.get(p['id'], [])
            for f in p['formats']:
                f['cost'] = format_cost(c, p['id'], f['id'])
                costs[f['id']] = f['cost']
        data['active_tariff'] = None
        now = matching_tariff_for_any(c)
        if now:
            data['active_tariff'] = {'name': now['name'], 'percent': now['percent']}
        data['recipes'] = recipes(c)
        data['stock_items'] = [dict(r) for r in c.execute('SELECT id,name,unit FROM stock_items ORDER BY name')]
    return data


def matching_tariff_for_any(c):
    """Tarifa horaria activa ahora mismo sin filtros de centro ni categoría (para el aviso del TPV)."""
    now = datetime.now()
    hhmm = now.strftime('%H:%M')
    for t in tariffs(c):
        if not t['active'] or not (t['start_time'] and t['end_time']):
            continue
        if t['days'] and now.weekday() not in t['days']:
            continue
        s, e = t['start_time'], t['end_time']
        if (s <= hhmm < e) if s < e else (hhmm >= s or hhmm < e):
            return t
    return None


def mutate(store, action, data, actor, app):
    allowed = ADMIN_ACTIONS if app == 'admin' else TPV_ACTIONS
    if action not in allowed:
        raise PermissionError('Esta operación pertenece a la otra aplicación.')
    import permissions
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        store.audit(c, actor, action, data.get('order_id'))
        if action == 'add_menu':
            if 'ticket_add' not in permissions.rights(c, actor):
                raise PermissionError('Tu perfil no permite añadir productos.')
            return add_menu(store, c, data, actor)
        if action == 'tariff_delete':
            c.execute('DELETE FROM tariffs WHERE id=?', (int(data['id']),))
            return {'ok': True}
        if action == 'tariff_save':
            name = ' '.join(str(data.get('name') or '').split()).upper()
            if not 2 <= len(name) <= 60:
                raise ValueError('El nombre de la tarifa debe tener entre 2 y 60 caracteres.')
            try:
                percent = round(float(str(data.get('percent')).replace(',', '.')) * 100)
            except ValueError:
                raise ValueError('Porcentaje no válido.')
            if not -10000 <= percent <= 10000 or percent == 0:
                raise ValueError('El ajuste debe estar entre −100 % y +100 % y no ser 0.')
            days = _json_ids(data.get('days', []), 'Días')
            if any(d < 0 or d > 6 for d in days):
                raise ValueError('Días no válidos.')
            start, end = _time(data.get('start_time')), _time(data.get('end_time'))
            if bool(start) != bool(end) or (start and start == end):
                raise ValueError('Indica hora de inicio y de fin distintas, o ninguna.')
            centers = _json_ids(data.get('centers', []), 'Centros')
            categories = _json_ids(data.get('categories', []), 'Categorías')
            priority = int(data.get('priority', 10))
            values = (name, percent, json.dumps(centers), json.dumps(days), start, end, json.dumps(categories), priority, int(bool(data.get('active', True))))
            if data.get('id'):
                c.execute('UPDATE tariffs SET name=?,percent=?,centers=?,days=?,start_time=?,end_time=?,categories=?,priority=?,active=? WHERE id=?', values + (int(data['id']),))
                return {'id': int(data['id'])}
            return {'id': c.execute('INSERT INTO tariffs(name,percent,centers,days,start_time,end_time,categories,priority,active) VALUES(?,?,?,?,?,?,?,?,?)', values).lastrowid}
        if action == 'menu_save':
            pid = int(data['product_id'])
            if not c.execute('SELECT 1 FROM products WHERE id=?', (pid,)).fetchone():
                raise ValueError('Producto no encontrado.')
            sections = data.get('sections', [])
            if not isinstance(sections, list) or len(sections) > 8:
                raise ValueError('Un menú admite hasta 8 apartados.')
            clean = []
            for s in sections:
                name = ' '.join(str(s.get('name') or '').split()).upper()
                options = _json_ids(s.get('options', []), 'Platos')
                course = s.get('course') or 'PRIMERO'
                if not name or not options or course not in COURSES:
                    raise ValueError('Cada apartado necesita nombre, orden de preparación y al menos un plato.')
                if pid in options:
                    raise ValueError('Un menú no puede incluirse a sí mismo.')
                for o in options:
                    if not c.execute("SELECT 1 FROM products WHERE id=? AND active=1 AND menu_sections='[]'", (o,)).fetchone():
                        raise ValueError('Los platos deben ser productos activos que no sean menús.')
                clean.append({'name': name, 'course': course, 'options': options})
            c.execute('UPDATE products SET menu_sections=? WHERE id=?', (json.dumps(clean), pid))
            return {'ok': True}
        if action == 'recipe_save':
            pid = int(data['product_id'])
            fid = data.get('format_id')
            if not c.execute('SELECT 1 FROM products WHERE id=?', (pid,)).fetchone():
                raise ValueError('Producto no encontrado.')
            if fid is not None and not c.execute('SELECT 1 FROM formats WHERE id=? AND product_id=?', (fid, pid)).fetchone():
                raise ValueError('Formato no válido.')
            items = data.get('items', [])
            if not isinstance(items, list) or len(items) > 40:
                raise ValueError('Escandallo no válido.')
            import inventory
            if fid is None:
                c.execute('DELETE FROM recipes WHERE product_id=? AND format_id IS NULL', (pid,))
            else:
                c.execute('DELETE FROM recipes WHERE product_id=? AND format_id=?', (pid, fid))
            for item in items:
                if not c.execute('SELECT 1 FROM stock_items WHERE id=?', (int(item['item_id']),)).fetchone():
                    raise ValueError('Ingrediente no encontrado en el almacén.')
                c.execute('INSERT INTO recipes(product_id,format_id,item_id,qty) VALUES(?,?,?,?)', (pid, fid, int(item['item_id']), inventory.quantity(item['qty'])))
            return {'ok': True}
    raise ValueError('Acción no disponible.')


# ---------- Informes ----------
REPORTS = {'Tarifas', 'Productos en menús', 'Rentabilidad de la carta', 'Márgenes por categorías', 'Márgenes por familias', 'Tiempos de preparación'}


def net(amount, tax):
    return (amount * 100 + (100 + tax) // 2) // (100 + tax)


def report(store, name, start, end):
    from analytics import bounds
    a, b = bounds(start, end)
    with store.db() as c:
        c.execute('BEGIN')
        if name == 'Tarifas':
            cols = [['Tarifa', 'text'], ['Líneas', 'number'], ['Unidades', 'number'], ['Venta', 'money'], ['Venta a precio base', 'money'], ['Diferencia', 'money']]
            rows = [[r[0] or 'PRECIO BASE', r[1], r[2], r[3], r[4], r[3] - r[4]] for r in c.execute(
                "SELECT l.tariff,COUNT(*),SUM(l.qty),SUM(l.qty*l.price),SUM(l.qty*COALESCE(l.reference_price,l.price)) FROM lines l JOIN orders o ON o.id=l.order_id WHERE o.status='paid' AND o.paid_at>=? AND o.paid_at<? AND COALESCE(l.menu_role,'')<>'item' GROUP BY l.tariff ORDER BY 4 DESC", (a, b))]
            return dict(columns=cols, rows=rows, note='Ventas cerradas agrupadas por la tarifa aplicada al añadir cada línea. El precio base es el de la carta, antes de tarifas y descuentos.')
        if name == 'Productos en menús':
            cols = [['Menú', 'text'], ['Apartado', 'text'], ['Plato', 'text'], ['Veces elegido', 'number']]
            rows = [list(r) for r in c.execute(
                "SELECT p.name,substr(l.format,8),l.name,SUM(l.qty) FROM lines l JOIN lines p ON p.id=l.menu_parent_id JOIN orders o ON o.id=l.order_id WHERE l.menu_role='item' AND o.status='paid' AND o.paid_at>=? AND o.paid_at<? GROUP BY p.name,l.format,l.name ORDER BY p.name,l.format,4 DESC", (a, b))]
            return dict(columns=cols, rows=rows, note='Platos elegidos dentro de los menús de cuentas cerradas.')
        if name == 'Rentabilidad de la carta':
            cols = [['Producto', 'text'], ['Formato', 'text'], ['PVP', 'money'], ['Precio sin IVA', 'money'], ['Coste escandallo', 'money'], ['Margen', 'money'], ['Margen %', 'text']]
            rows = []
            for r in c.execute('SELECT p.id,p.name,p.tax,f.id fid,f.name fname,f.price FROM products p JOIN formats f ON f.product_id=p.id WHERE p.active=1 AND f.active=1 ORDER BY p.name,f.id').fetchall():
                cost = format_cost(c, r['id'], r['fid'])
                if cost is None:
                    continue
                base = net(r['price'], r['tax'])
                rows.append([r['name'], r['fname'], r['price'], base, cost, base - cost, f'{(base - cost) * 100 / base:.1f} %' if base else '—'])
            return dict(columns=cols, rows=rows, note='Solo productos con escandallo. Coste según el último precio de compra de cada ingrediente. Margen sobre el precio sin IVA.')
        if name in ('Márgenes por categorías', 'Márgenes por familias'):
            group = 'ca.name' if name == 'Márgenes por categorías' else 'ca.parent'
            totals = defaultdict(lambda: [0, 0, 0])
            for r in c.execute(f"SELECT {group} g,l.product_id,l.format_id,l.qty,l.price,l.tax FROM lines l JOIN orders o ON o.id=l.order_id JOIN products p ON p.id=l.product_id JOIN categories ca ON ca.id=p.category_id WHERE o.status='paid' AND o.paid_at>=? AND o.paid_at<? AND COALESCE(l.menu_role,'')<>'item'", (a, b)):
                cost = format_cost(c, r['product_id'], r['format_id'])
                t = totals[r['g']]
                t[0] += net(r['qty'] * r['price'], r['tax'])
                if cost is not None:
                    t[1] += cost * r['qty']
                    t[2] += net(r['qty'] * r['price'], r['tax'])
            cols = [['Grupo', 'text'], ['Venta sin IVA', 'money'], ['Venta con escandallo', 'money'], ['Coste', 'money'], ['Margen', 'money'], ['Margen %', 'text']]
            rows = [[g, v[0], v[2], v[1], v[2] - v[1], f'{(v[2] - v[1]) * 100 / v[2]:.1f} %' if v[2] else '—'] for g, v in sorted(totals.items())]
            return dict(columns=cols, rows=rows, note='El margen solo considera las ventas de productos con escandallo. Coste con el último precio de compra.')
        if name == 'Tiempos de preparación':
            cols = [['Producto', 'text'], ['Preparación', 'text'], ['Unidades', 'number'], ['Tiempo medio', 'text'], ['Tiempo máximo', 'text']]
            rows = []
            for r in c.execute("SELECT l.name,l.prep,SUM(l.qty) n,AVG((julianday(l.ready_at)-julianday(l.sent_at))*1440) avg_m,MAX((julianday(l.ready_at)-julianday(l.sent_at))*1440) max_m FROM lines l WHERE l.sent_at>=? AND l.sent_at<? AND l.ready_at IS NOT NULL GROUP BY l.name,l.prep ORDER BY avg_m DESC", (a, b)):
                rows.append([r['name'], r['prep'], r['n'], f"{r['avg_m']:.1f} min", f"{r['max_m']:.1f} min"])
            return dict(columns=cols, rows=rows, note='Desde el envío a preparación hasta que la cocina o la barra marca la comanda como lista.')
    raise ValueError('Informe desconocido.')
