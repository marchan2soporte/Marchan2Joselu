"""Windows printer queues and durable local printing jobs.

Only operational test receipts and kitchen slips are supported. The selected
printer must already be installed in Windows (including network printers).
"""
import ctypes
from ctypes import wintypes
from datetime import datetime
import json
import subprocess
import re
import ticket_print
import sys
import textwrap

PREP_TYPES = ('BARRA', 'COCINA')
DOCUMENT_TYPES = ('receipt', 'z_report')
PRINT_BACKENDS = ('auto', 'raw', 'gdi')
CUT_MODES = ('none', 'full', 'partial')


def initialize(store):
    with store.db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS kitchen_printer_routes(
            id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES pos_profiles(id) ON DELETE CASCADE,
            name TEXT NOT NULL, printer_name TEXT NOT NULL, prep_types TEXT NOT NULL,
            center_ids TEXT NOT NULL DEFAULT '[]', active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS document_printer_routes(
            profile_id INTEGER NOT NULL REFERENCES pos_profiles(id) ON DELETE CASCADE,
            kind TEXT NOT NULL, printer_name TEXT NOT NULL DEFAULT '', copies INTEGER NOT NULL DEFAULT 1,
            print_mode TEXT NOT NULL DEFAULT 'manual', PRIMARY KEY(profile_id,kind));
            CREATE TABLE IF NOT EXISTS print_jobs(
            id INTEGER PRIMARY KEY, created TEXT NOT NULL, kind TEXT NOT NULL,
            printer_name TEXT NOT NULL, copies INTEGER NOT NULL, payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', error TEXT NOT NULL DEFAULT '',
            unique_key TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS print_job_lines(
            line_id INTEGER NOT NULL, route_id INTEGER NOT NULL, job_id INTEGER NOT NULL,
            PRIMARY KEY(line_id,route_id));''')
        for table in ('kitchen_printer_routes', 'document_printer_routes', 'print_jobs'):
            columns = {row['name'] for row in c.execute(f'PRAGMA table_info({table})')}
            for field, definition in (('backend', "TEXT NOT NULL DEFAULT 'auto'"),
                                      ('raw_columns', 'INTEGER NOT NULL DEFAULT 48'),
                                      ('feed_lines', 'INTEGER NOT NULL DEFAULT 4'),
                                      ('cut_mode', "TEXT NOT NULL DEFAULT 'none'")):
                if field not in columns:
                    c.execute(f'ALTER TABLE {table} ADD COLUMN {field} {definition}')


def _backend(data):
    backend = data.get('backend', 'auto')
    if backend not in PRINT_BACKENDS:
        raise ValueError('Modo de impresión no válido.')
    return backend


def _raw_settings(data):
    columns = data.get('raw_columns', 48)
    feed = data.get('feed_lines', 4)
    cut = data.get('cut_mode', 'none')
    if type(columns) is not int or not 20 <= columns <= 64:
        raise ValueError('El ancho RAW debe estar entre 20 y 64 caracteres.')
    if type(feed) is not int or not 0 <= feed <= 8:
        raise ValueError('El avance debe estar entre 0 y 8 líneas.')
    if cut not in CUT_MODES:
        raise ValueError('Modo de corte no válido.')
    return columns, feed, cut


def installed_printers():
    if sys.platform != 'win32':
        return []
    script = 'Get-CimInstance Win32_Printer | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress'
    result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError('Windows no pudo enumerar las impresoras instaladas.')
    value = json.loads(result.stdout.strip() or '[]')
    return [value] if isinstance(value, str) else value


def _profile_id(c):
    row = c.execute('SELECT id FROM pos_profiles WHERE active=1 ORDER BY id LIMIT 1').fetchone()
    return row['id'] if row else None


def configuration(store, profile_id=None):
    with store.db() as c:
        profile_id = profile_id or _profile_id(c)
        kitchen = [dict(row) for row in c.execute(
            'SELECT * FROM kitchen_printer_routes WHERE profile_id=? ORDER BY id', (profile_id,))]
        for route in kitchen:
            route['prep_types'] = json.loads(route['prep_types'])
            route['center_ids'] = json.loads(route['center_ids'])
        documents = {row['kind']: dict(row) for row in c.execute(
            'SELECT * FROM document_printer_routes WHERE profile_id=?', (profile_id,))}
        for kind in DOCUMENT_TYPES:
            documents.setdefault(kind, {'kind': kind, 'printer_name': '', 'copies': 1,
                                         'print_mode': 'manual', 'backend': 'auto', 'profile_id': profile_id,
                                         'raw_columns': 48, 'feed_lines': 4, 'cut_mode': 'none'})
    return {'kitchen': kitchen, 'documents': documents, 'printers': installed_printers()}


def save_document(store, data):
    kind = data.get('kind')
    if kind not in DOCUMENT_TYPES:
        raise ValueError('Ese documento todavía no se emite desde Marchan2.')
    printer = str(data.get('printer_name', '')).strip()
    if len(printer) > 255:
        raise ValueError('Nombre de impresora demasiado largo.')
    copies = data.get('copies', 1)
    if type(copies) is not int or not 1 <= copies <= 5:
        raise ValueError('Elige entre una y cinco copias.')
    mode = data.get('print_mode', 'manual')
    if mode not in ('manual', 'always') or (kind != 'receipt' and mode != 'manual'):
        raise ValueError('Modo de impresión no válido.')
    if mode == 'always' and not printer:
        raise ValueError('Elige una impresora para imprimir automáticamente.')
    backend = _backend(data)
    raw_columns, feed_lines, cut_mode = _raw_settings(data)
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        profile_id = int(data['profile_id'])
        if not c.execute('SELECT 1 FROM pos_profiles WHERE id=?', (profile_id,)).fetchone():
            raise ValueError('Punto de venta no encontrado.')
        c.execute('''INSERT INTO document_printer_routes(profile_id,kind,printer_name,copies,print_mode,backend,
            raw_columns,feed_lines,cut_mode) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(profile_id,kind) DO UPDATE SET
            printer_name=excluded.printer_name,copies=excluded.copies,
            print_mode=excluded.print_mode,backend=excluded.backend,
            raw_columns=excluded.raw_columns,feed_lines=excluded.feed_lines,cut_mode=excluded.cut_mode''',
                  (profile_id, kind, printer, copies, mode, backend, raw_columns, feed_lines, cut_mode))
    return {'ok': True}


def save_kitchen(store, data):
    name = str(data.get('name', '')).strip()
    printer = str(data.get('printer_name', '')).strip()
    preps = data.get('prep_types', [])
    centers = data.get('center_ids', [])
    backend = _backend(data)
    raw_columns, feed_lines, cut_mode = _raw_settings(data)
    if not 1 <= len(name) <= 80 or not 1 <= len(printer) <= 255:
        raise ValueError('Indica un nombre y una impresora de Windows.')
    import kitchen
    with store.db() as c:
        valid = kitchen.prep_names(c) if c.execute("SELECT 1 FROM sqlite_master WHERE name='prep_types'").fetchone() else list(PREP_TYPES)
    if not isinstance(preps, list) or not preps or len(set(preps)) != len(preps) or any(p not in valid for p in preps):
        raise ValueError('Selecciona al menos un tipo de preparación existente.')
    if not isinstance(centers, list) or len(set(centers)) != len(centers) or any(type(i) is not int for i in centers):
        raise ValueError('Centros de venta no válidos.')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        profile_id = int(data['profile_id'])
        if not c.execute('SELECT 1 FROM pos_profiles WHERE id=?', (profile_id,)).fetchone():
            raise ValueError('Punto de venta no encontrado.')
        if any(not c.execute('SELECT 1 FROM centers WHERE id=?', (i,)).fetchone() for i in centers):
            raise ValueError('Hay un centro de venta inexistente.')
        if data.get('id'):
            changed = c.execute('''UPDATE kitchen_printer_routes SET name=?,printer_name=?,prep_types=?,center_ids=?,backend=?,
                raw_columns=?,feed_lines=?,cut_mode=? WHERE id=? AND profile_id=?''',
                (name, printer, json.dumps(preps), json.dumps(centers), backend, raw_columns, feed_lines, cut_mode,
                                                   int(data['id']), profile_id)).rowcount
            if not changed: raise ValueError('Ruta de cocina no encontrada.')
            identifier = int(data['id'])
        else:
            identifier = c.execute('''INSERT INTO kitchen_printer_routes
                (profile_id,name,printer_name,prep_types,center_ids,backend,raw_columns,feed_lines,cut_mode)
                VALUES(?,?,?,?,?,?,?,?,?)''',
                (profile_id, name, printer, json.dumps(preps), json.dumps(centers), backend,
                 raw_columns, feed_lines, cut_mode)).lastrowid
    return {'id': identifier}


def delete_kitchen(store, data):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        changed = c.execute('DELETE FROM kitchen_printer_routes WHERE id=? AND profile_id=?',
                            (int(data['id']), int(data['profile_id']))).rowcount
        if not changed: raise ValueError('Ruta de cocina no encontrada.')
    return {'ok': True}


def kitchen_doc(order, items, route_name):
    B = [{'t': 'text', 'text': route_name.upper(), 'align': 'center', 'bold': True},
         {'t': 'text', 'text': order['table_name'] or 'VENTA DIRECTA', 'align': 'center', 'bold': True, 'large': True},
         {'t': 'text', 'text': f"PEDIDO #{order['id']:04d}" + (f"  ·  {order['guests']} COMENSALES" if order.get('guests') else ''), 'align': 'center'},
         {'t': 'text', 'text': f"{order.get('user_name') or 'Sin asignar'} · " + datetime.now().strftime('%d/%m/%Y  %H:%M'), 'align': 'center'},
         {'t': 'sep', 'char': '='}]
    for course in dict.fromkeys(item['course'] for item in items):
        B.append({'t': 'text', 'text': f"[ {course.upper()} ]", 'align': 'left', 'bold': True})
        for item in (item for item in items if item['course'] == course):
            B.append({'t': 'text', 'text': f"{item['qty']} x {item['name']}", 'align': 'left', 'bold': True, 'large': True})
            if item['format'] and not item['format'].startswith('MENÚ'):
                B.append({'t': 'text', 'text': '     ' + item['format']})
            elif item['format']:
                B.append({'t': 'text', 'text': '     ' + item['format']})
            if item.get('weight_label'):
                B.append({'t': 'text', 'text': '     ' + item['weight_label']})
            for extra in item['extras']:
                B.append({'t': 'text', 'text': f"     + {extra['name']}"})
            if item['note']:
                B.append({'t': 'text', 'text': f"  >> {item['note']}", 'bold': True})
        B.append({'t': 'sep', 'char': '-'})
    B.append({'t': 'text', 'text': 'COMANDA INTERNA · SIN PRECIOS', 'align': 'center'})
    return {'marchan2_doc': 1, 'width': 48, 'blocks': B}


def _format_kitchen(order, items, route_name):
    return ticket_print.to_text(kitchen_doc(order, items, route_name))


def enqueue_kitchen(c, store, order_id, line_ids):
    if not line_ids: return
    profile_id = _profile_id(c)
    routes = [dict(row) for row in c.execute('''SELECT * FROM kitchen_printer_routes
        WHERE profile_id=? AND active=1 ORDER BY id''', (profile_id,))]
    if not routes: return
    order = store.order(c, order_id)
    center = c.execute('SELECT center_id FROM tables WHERE id=?', (order['table_id'],)).fetchone() if order['table_id'] else None
    center_id = center['center_id'] if center else None
    for route in routes:
        items = []
        for line in order['lines']:
            if line['id'] not in line_ids: continue
            if line['prep'] not in json.loads(route['prep_types']): continue
            allowed = json.loads(route['center_ids'])
            if allowed and center_id not in allowed: continue
            if c.execute('SELECT 1 FROM print_job_lines WHERE line_id=? AND route_id=?',
                         (line['id'], route['id'])).fetchone(): continue
            items.append(line)
        if items:
            payload = ticket_print.dumps(kitchen_doc(order, items, route['name']))
            job = c.execute('''INSERT INTO print_jobs(created,kind,printer_name,copies,payload,backend,
                raw_columns,feed_lines,cut_mode) VALUES(?,?,?,?,?,?,?,?,?)''',
                (datetime.now().isoformat(timespec='seconds'), 'kitchen', route['printer_name'], 1, payload,
                 route['backend'], route['raw_columns'], route['feed_lines'], route['cut_mode'])).lastrowid
            for line in items:
                c.execute('INSERT OR IGNORE INTO print_job_lines(line_id,route_id,job_id) VALUES(?,?,?)',
                          (line['id'], route['id'], job))


def template_width(template):
    base = str((template or {}).get('base', '80 mm'))
    match = re.search(r'(\d+) caracteres', base)
    if match:
        return int(match.group(1))
    return 32 if base.startswith('56 mm') else 64 if base == 'A4' else 48


def receipt_doc(order, company, template=None, categories=None):
    """Maqueta del ticket compartida por la vista previa, RAW (ESC/POS) y Windows."""
    template = template or {}
    show = lambda key, default=1: bool(template.get(key, default))
    width = template_width(template)
    sep = template.get('separator') or '-'
    halign = template.get('header_align') or 'center'
    falign = template.get('footer_align') or 'center'
    big_header = bool(template.get('header_large', 1))
    big_total = bool(template.get('total_large', 1))
    B = []
    text = lambda t, align='left', bold=False, large=False: B.append({'t': 'text', 'text': t, 'align': align, 'bold': bold, 'large': large})
    pair = lambda l, r, bold=False, large=False: B.append({'t': 'pair', 'left': l, 'right': r, 'bold': bold, 'large': large})
    line = lambda: B.append({'t': 'sep', 'char': sep})
    if template.get('header_image') and template.get('print_logo', 1):
        B.append({'t': 'image', 'data': template['header_image']})
    heading = (template.get('header') or company.get('trade_name') or company.get('legal_name') or 'MARCHAN2').splitlines()
    for i, h in enumerate(heading):
        text(h, halign, bold=True, large=big_header and i == 0)
    if company.get('tax_id'):
        text('CIF: ' + company['tax_id'], halign)
    if company.get('address'):
        text(company['address'], halign)
    line()
    text('JUSTIFICANTE DE VENTA', 'center', bold=True)
    text('DOCUMENTO DE PRUEBA · NO FISCAL', 'center')
    line()
    if order.get('series_number'):
        text(f"Referencia interna: {order.get('series_name') or ''}-{order['series_number']}")
    identity = []
    if show('show_order_id'):
        identity.append(f"Cuenta #{order['id']:04d}")
    if show('show_location'):
        identity.append(order['table_name'] or 'VENTA DIRECTA')
    if identity:
        text(' · '.join(identity), bold=True)
    stamp = (order['paid_at'] or order['created']).replace('T', ' ')
    text(stamp if show('show_time') else stamp[:10])
    if order.get('guests'):
        text(f"Comensales: {order['guests']}")
    if show('show_unpaid') and order['due'] > 0:
        text('PENDIENTE DE COBRO', 'center', bold=True)
    line()
    pair('UDS  PRODUCTO', 'IMPORTE', bold=True)
    line()
    items = list(order['lines'])
    if template.get('line_order') == 'Nombre':
        items.sort(key=lambda item: item['name'].casefold())
    if template.get('line_order') == 'Categoría' and categories:
        items.sort(key=lambda item: (categories.get(item['product_id'], '').casefold(), item['id']))
    taxes = {}
    for item in items:
        sub = item.get('menu_role') == 'item'
        pair(('   · ' if sub else f"{item['qty']} x ") + item['name'], '' if sub else {'m': item['qty'] * item['price']})
        detail = '' if sub else item['format']
        if item.get('weight_label'):
            detail += ' · ' + item['weight_label']
        if item.get('discount_label'):
            detail += ' · ' + item['discount_label']
        if item['extras']:
            detail += ' + ' + ', '.join(extra['name'] for extra in item['extras'])
        if show('show_unit_price', 0) and not sub:
            detail += f" · {item['price'] / 100:.2f} / ud.".replace('.', ',')
        if show('show_item_tax', 0) and not sub:
            detail += f" · IVA {item['tax']}%"
        if detail.strip(' ·'):
            text('    ' + detail.strip())
        if show('show_notes', 0) and item['note']:
            text('    Nota: ' + item['note'])
        taxes[item['tax']] = taxes.get(item['tax'], 0) + item['qty'] * item['price']
    line()
    pair('TOTAL' if big_total else 'TOTAL PRODUCTOS', {'m': order['total']}, bold=True, large=big_total)
    if show('show_tax'):
        for rate, gross in sorted(taxes.items()):
            base = (gross * 100 + (100 + rate) // 2) // (100 + rate)
            pair(f'  Base {rate}%  {base / 100:.2f}'.replace('.', ','), {'m': gross - base})
    if order['payments']:
        line()
    for payment in order['payments']:
        label = 'EFECTIVO' if payment['method'] == 'cash' else 'TARJETA'
        if show('show_user') and payment.get('user_name'):
            label += ' · ' + payment['user_name']
        pair(label, {'m': payment['amount']})
        if show('show_tips') and payment.get('tip'):
            pair('  Propina', {'m': payment['tip']})
        if payment['method'] == 'cash':
            pair('  Entregado', {'m': payment['tendered']})
            pair('  Cambio', {'m': payment['change_due']})
    if order['due'] > 0:
        pair('PENDIENTE', {'m': order['due']}, bold=True)
    line()
    for f in (template.get('footer') or 'Gracias por compartir mesa.\nMarchan2 · JoseluIA').splitlines():
        text(f, falign)
    if template.get('footer_image') and template.get('print_logo', 1):
        B.append({'t': 'image', 'data': template['footer_image']})
    return {'marchan2_doc': 1, 'width': width, 'blocks': B}


def _format_receipt(order, company, template=None, categories=None):
    """Texto plano equivalente (compatibilidad y pruebas)."""
    doc = receipt_doc(order, company, template, categories)
    for b in doc['blocks']:
        if b['t'] == 'pair' and b['left'] == 'UDS  PRODUCTO':
            b['left'] = 'UDS  PRODUCTO'
    return ticket_print.to_text(doc)


def active_template(c):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ticket_templates'").fetchone():
        return None
    from pos_profiles import active_options
    chosen = active_options(c).get('receipt_template_id')
    row = c.execute('SELECT * FROM ticket_templates WHERE id=?', (chosen,)).fetchone() if chosen else \
        c.execute('SELECT * FROM ticket_templates WHERE is_default=1 ORDER BY id LIMIT 1').fetchone()
    return dict(row) if row else None


def _categories(c):
    return {row['id']: row['category_name'] for row in c.execute(
        'SELECT p.id,c.name category_name FROM products p JOIN categories c ON c.id=p.category_id')}


SAMPLE_ORDER = {'id': 27, 'table_name': 'MESA 4', 'status': 'paid', 'created': '2026-11-27T13:05:00', 'paid_at': '2026-11-27T13:58:00',
                'guests': 2, 'series_number': None, 'total': 3350, 'due': 0,
                'lines': [{'id': 1, 'product_id': 0, 'qty': 2, 'name': 'CAFÉ CON LECHE', 'price': 190, 'format': 'TAZA', 'extras': [], 'tax': 10, 'note': 'SIN AZÚCAR'},
                          {'id': 2, 'product_id': 0, 'qty': 1, 'name': 'TOSTADA CON TOMATE Y JAMÓN', 'price': 450, 'format': 'MEDIA', 'extras': [{'name': 'ACEITE DE OLIVA'}], 'tax': 10, 'note': ''},
                          {'id': 3, 'product_id': 0, 'qty': 1, 'name': 'MENÚ DEL DÍA', 'price': 1450, 'format': 'COMPLETO', 'extras': [], 'tax': 10, 'note': '', 'menu_role': 'parent'},
                          {'id': 4, 'product_id': 0, 'qty': 1, 'name': 'CARRILLADA', 'price': 0, 'format': 'MENÚ · SEGUNDOS', 'extras': [], 'tax': 10, 'note': '', 'menu_role': 'item'},
                          {'id': 5, 'product_id': 0, 'qty': 1, 'name': 'COPA DE VINO BLANCO', 'price': 870, 'format': 'COPA', 'extras': [], 'tax': 21, 'note': '', 'discount_label': 'DTO 10,00 %'}],
                'payments': [{'method': 'cash', 'amount': 3350, 'tip': 150, 'tendered': 4000, 'change_due': 500, 'user_name': 'ANA'}]}


def render_preview(store, template=None, order_id=None):
    """Imagen exacta de impresión (Windows) y texto equivalente, para la vista previa."""
    from company import read as read_company
    with store.db() as c:
        if order_id is not None:
            order = store.order(c, int(order_id))
            template = active_template(c)
        else:
            order = SAMPLE_ORDER
        categories = _categories(c) if template and template.get('line_order') == 'Categoría' else {}
    doc = receipt_doc(order, read_company(store), template, categories)
    try:
        image = ticket_print.render_png(doc)
    except Exception:
        image = None
    return {'image': image, 'text': ticket_print.to_text(doc), 'width': doc['width']}


def enqueue_receipt(store, order_id, automatic=False):
    from company import read as read_company
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        profile_id = _profile_id(c)
        route = c.execute('SELECT * FROM document_printer_routes WHERE profile_id=? AND kind=?',
                          (profile_id, 'receipt')).fetchone()
        if not route or not route['printer_name'] or (automatic and route['print_mode'] != 'always'):
            return {'configured': False}
        order = store.order(c, order_id)
        if automatic and order['status'] != 'paid': return {'configured': False}
        key = f"receipt:{order_id}" if automatic else None
        template = active_template(c)
        categories = _categories(c) if template and template.get('line_order') == 'Categoría' else {}
        payload = ticket_print.dumps(receipt_doc(order, read_company(store), template, categories))
        try:
            job = c.execute('''INSERT INTO print_jobs(created,kind,printer_name,copies,payload,unique_key,backend,
                raw_columns,feed_lines,cut_mode) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (datetime.now().isoformat(timespec='seconds'), 'receipt', route['printer_name'], route['copies'],
                 payload, key, route['backend'], route['raw_columns'], route['feed_lines'], route['cut_mode'])).lastrowid
        except __import__('sqlite3').IntegrityError:
            return {'configured': True, 'duplicate': True}
    return {'configured': True, 'job_id': job}


def enqueue_text(store, kind, text):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        route = c.execute('SELECT * FROM document_printer_routes WHERE profile_id=? AND kind=?',
                          (_profile_id(c), kind)).fetchone()
        if not route or not route['printer_name']: return {'configured': False}
        job = c.execute('''INSERT INTO print_jobs(created,kind,printer_name,copies,payload,backend,
            raw_columns,feed_lines,cut_mode) VALUES(?,?,?,?,?,?,?,?,?)''',
            (datetime.now().isoformat(timespec='seconds'), kind, route['printer_name'], route['copies'],
             text, route['backend'], route['raw_columns'], route['feed_lines'], route['cut_mode'])).lastrowid
    return {'configured': True, 'job_id': job}


def test_print(store, printer_name, backend='auto', raw_columns=48, feed_lines=4, cut_mode='none'):
    if not isinstance(printer_name, str) or not printer_name.strip() or len(printer_name) > 255:
        raise ValueError('Selecciona una impresora de Windows.')
    return enqueue_text_to_printer(store, printer_name,
        'MARCHAN2 · PRUEBA DE IMPRESORA\nImpresión desde Administración\n'
        '123456789012345678901234567890123456789012345678\nFin de prueba · 80 mm / 48 columnas',
        backend, raw_columns, feed_lines, cut_mode)


def enqueue_text_to_printer(store, printer_name, text, backend='auto', raw_columns=48,
                            feed_lines=4, cut_mode='none'):
    backend = _backend({'backend': backend})
    raw_columns, feed_lines, cut_mode = _raw_settings({'raw_columns': raw_columns,
        'feed_lines': feed_lines, 'cut_mode': cut_mode})
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        job = c.execute('''INSERT INTO print_jobs(created,kind,printer_name,copies,payload,backend,
            raw_columns,feed_lines,cut_mode) VALUES(?,?,?,?,?,?,?,?,?)''',
            (datetime.now().isoformat(timespec='seconds'), 'test', printer_name.strip(), 1, text,
             backend, raw_columns, feed_lines, cut_mode)).lastrowid
    return {'configured': True, 'job_id': job}


def print_gdi(printer_name, text, copies=1):
    """Windows: fuente monoespaciada ajustada al ancho del papel, negritas, tamaños y alineación."""
    doc = ticket_print.loads(text) if ticket_print.is_doc(text) else \
        ticket_print.text_doc(text, max(32, min(64, max((len(line) for line in text.splitlines()), default=48))))
    ticket_print.print_gdi_doc(printer_name, doc, copies)


def _raw_bytes(text, raw_columns=48, feed_lines=4, cut_mode='none'):
    raw_columns, feed_lines, cut_mode = _raw_settings({'raw_columns': raw_columns,
        'feed_lines': feed_lines, 'cut_mode': cut_mode})
    # Generic / Text Only receives CP850 bytes. Keep every line inside the paper width.
    wrapper = textwrap.TextWrapper(width=raw_columns, break_long_words=True,
                                   break_on_hyphens=False, replace_whitespace=False)
    lines = []
    for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if len(line) >= 10 and set(line) in ({'-'}, {'='}):
            lines.append(line[:raw_columns])
        else:
            lines.extend(wrapper.wrap(line) or [''])
    result = ('\r\n'.join(lines) + '\r\n' + '\r\n' * feed_lines).encode('cp850', errors='replace')
    if cut_mode != 'none':
        result += b'\x1d\x56' + (b'\x00' if cut_mode == 'full' else b'\x01')
    return result


def print_raw(printer_name, text, copies=1, raw_columns=48, feed_lines=4, cut_mode='none'):
    if sys.platform != 'win32': raise ValueError('La impresión directa requiere Windows.')
    spool = ctypes.WinDLL('winspool.drv', use_last_error=True)
    spool.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    spool.OpenPrinterW.restype = wintypes.BOOL
    spool.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p]
    spool.StartDocPrinterW.restype = wintypes.DWORD
    spool.StartPagePrinter.argtypes = [wintypes.HANDLE]
    spool.StartPagePrinter.restype = wintypes.BOOL
    spool.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    spool.WritePrinter.restype = wintypes.BOOL
    spool.EndPagePrinter.argtypes = [wintypes.HANDLE]
    spool.EndPagePrinter.restype = wintypes.BOOL
    spool.EndDocPrinter.argtypes = [wintypes.HANDLE]
    spool.EndDocPrinter.restype = wintypes.BOOL
    spool.ClosePrinter.argtypes = [wintypes.HANDLE]
    spool.ClosePrinter.restype = wintypes.BOOL

    class DOCINFO1(ctypes.Structure):
        _fields_ = [('pDocName', wintypes.LPWSTR), ('pOutputFile', wintypes.LPWSTR),
                    ('pDatatype', wintypes.LPWSTR)]

    handle = wintypes.HANDLE()
    if not spool.OpenPrinterW(printer_name, ctypes.byref(handle), None):
        raise ValueError(f'Windows no pudo abrir la cola de impresión ({ctypes.get_last_error()}).')
    payload = ticket_print.escpos(ticket_print.loads(text), raw_columns, feed_lines, cut_mode) if ticket_print.is_doc(text) \
        else _raw_bytes(text, raw_columns, feed_lines, cut_mode)
    buffer = ctypes.create_string_buffer(payload)
    doc = DOCINFO1('Marchan2 · texto RAW', None, 'RAW')
    try:
        for _ in range(copies):
            if not spool.StartDocPrinterW(handle, 1, ctypes.byref(doc)):
                raise ValueError(f'Windows rechazó el trabajo RAW ({ctypes.get_last_error()}).')
            try:
                if not spool.StartPagePrinter(handle):
                    raise ValueError(f'Windows no pudo iniciar la página RAW ({ctypes.get_last_error()}).')
                try:
                    written = wintypes.DWORD()
                    if not spool.WritePrinter(handle, buffer, len(payload), ctypes.byref(written)) or written.value != len(payload):
                        raise ValueError(f'Windows no pudo enviar todo el texto RAW ({ctypes.get_last_error()}).')
                finally:
                    if not spool.EndPagePrinter(handle):
                        raise ValueError(f'Windows no pudo cerrar la página RAW ({ctypes.get_last_error()}).')
            finally:
                if not spool.EndDocPrinter(handle):
                    raise ValueError(f'Windows no pudo completar el trabajo RAW ({ctypes.get_last_error()}).')
    finally:
        spool.ClosePrinter(handle)


def _printer_driver(printer_name):
    """Controlador de la impresora con la API de Windows y en caché (antes: PowerShell, 1-3 s por impresión)."""
    try:
        return ticket_print.printer_driver(printer_name)
    except Exception:
        return ''


def print_text(printer_name, text, copies=1, backend='auto', raw_columns=48,
               feed_lines=4, cut_mode='none'):
    backend = _backend({'backend': backend})
    raw_columns, feed_lines, cut_mode = _raw_settings({'raw_columns': raw_columns,
        'feed_lines': feed_lines, 'cut_mode': cut_mode})
    if backend == 'auto':
        driver = _printer_driver(printer_name).casefold() if sys.platform == 'win32' else ''
        backend = 'raw' if 'generic' in driver and 'text' in driver else 'gdi'
    if backend == 'raw':
        print_raw(printer_name, text, copies, raw_columns, feed_lines, cut_mode)
    else:
        print_gdi(printer_name, text, copies)


def dispatch(store, job_ids=None):
    warnings = []
    with store.db() as c:
        query = "SELECT id FROM print_jobs WHERE status='pending'" if not job_ids else \
                "SELECT id FROM print_jobs WHERE status IN ('pending','error')"
        if job_ids:
            query += ' AND id IN (' + ','.join('?' for _ in job_ids) + ')'
        ids = [row['id'] for row in c.execute(query + ' ORDER BY id LIMIT 30', job_ids or ())]
    for identifier in ids:
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute("SELECT * FROM print_jobs WHERE id=? AND status IN ('pending','error')", (identifier,)).fetchone()
            if not row: continue
            c.execute("UPDATE print_jobs SET status='printing',error='' WHERE id=?", (identifier,))
            job = dict(row)
        try:
            print_text(job['printer_name'], job['payload'], job['copies'], job['backend'],
                       job['raw_columns'], job['feed_lines'], job['cut_mode'])
        except Exception as error:
            message = str(error)[:300]
            with store.db() as c:
                c.execute("UPDATE print_jobs SET status='error',error=? WHERE id=?", (message, identifier))
            warnings.append(f"Impresora {job['printer_name']}: {message}")
        else:
            with store.db() as c:
                c.execute("UPDATE print_jobs SET status='sent' WHERE id=?", (identifier,))
    return warnings


def jobs(store):
    with store.db() as c:
        return [dict(row) for row in c.execute('''SELECT id,created,kind,printer_name,status,error
            FROM print_jobs ORDER BY id DESC LIMIT 50''')]
