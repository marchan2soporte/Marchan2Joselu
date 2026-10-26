"""Windows printer queues and durable local printing jobs.

Only operational test receipts and kitchen slips are supported. The selected
printer must already be installed in Windows (including network printers).
"""
import ctypes
from ctypes import wintypes
from datetime import datetime
import json
import subprocess
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
    if not isinstance(preps, list) or not preps or len(set(preps)) != len(preps) or any(p not in PREP_TYPES for p in preps):
        raise ValueError('Selecciona BARRA, COCINA o ambas.')
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


def _format_kitchen(order, line, route_name):
    return '\n'.join(['MARCHAN2 · COMANDA DE PRUEBA', route_name,
        f"Mesa: {order['table_name'] or 'VENTA DIRECTA'}   Cuenta: #{order['id']}",
        f"Preparación: {line['prep']}   {line['course']}", '-' * 32,
        f"{line['qty']} x {line['name']}", line['format'],
        *[f"+ {extra['name']}" for extra in line['extras']],
        *([f"Nota: {line['note']}"] if line['note'] else []), '-' * 32,
        datetime.now().strftime('%d/%m/%Y %H:%M')])


def enqueue_kitchen(c, store, order_id, line_ids):
    if not line_ids: return
    profile_id = _profile_id(c)
    routes = [dict(row) for row in c.execute('''SELECT * FROM kitchen_printer_routes
        WHERE profile_id=? AND active=1 ORDER BY id''', (profile_id,))]
    if not routes: return
    order = store.order(c, order_id)
    center = c.execute('SELECT center_id FROM tables WHERE id=?', (order['table_id'],)).fetchone() if order['table_id'] else None
    center_id = center['center_id'] if center else None
    for line in order['lines']:
        if line['id'] not in line_ids: continue
        for route in routes:
            if line['prep'] not in json.loads(route['prep_types']): continue
            allowed = json.loads(route['center_ids'])
            if allowed and center_id not in allowed: continue
            if c.execute('SELECT 1 FROM print_job_lines WHERE line_id=? AND route_id=?',
                         (line['id'], route['id'])).fetchone(): continue
            payload = _format_kitchen(order, line, route['name'])
            job = c.execute('''INSERT INTO print_jobs(created,kind,printer_name,copies,payload,backend,
                raw_columns,feed_lines,cut_mode) VALUES(?,?,?,?,?,?,?,?,?)''',
                (datetime.now().isoformat(timespec='seconds'), 'kitchen', route['printer_name'], 1, payload,
                 route['backend'], route['raw_columns'], route['feed_lines'], route['cut_mode'])).lastrowid
            c.execute('INSERT OR IGNORE INTO print_job_lines(line_id,route_id,job_id) VALUES(?,?,?)',
                      (line['id'], route['id'], job))


def _format_receipt(order, company, template=None, categories=None):
    """Text equivalent of the shared browser preview for text-only queues."""
    template = template or {}
    show = lambda key, default=1: bool(template.get(key, default))
    width = 32 if str(template.get('base', '')).startswith('56 mm') else 48
    separator = '-' * width
    amount = lambda cents: f'{cents / 100:.2f} EUR'
    lines = (template.get('header') or company.get('trade_name') or
             company.get('legal_name') or 'MARCHAN2').splitlines()
    if company.get('tax_id'): lines.append('CIF: ' + company['tax_id'])
    if company.get('address'): lines.append(company['address'])
    lines.append('DEMOSTRACIÓN · NO FISCAL')
    if order.get('series_number'):
        lines.append(f"Referencia interna: {order.get('series_name') or ''}-{order['series_number']}")
    identity = []
    if show('show_order_id'): identity.append(f"Cuenta #{order['id']:04d}")
    if show('show_location'): identity.append(order['table_name'] or 'VENTA DIRECTA')
    if identity: lines.append(' · '.join(identity))
    date = order['paid_at'] or order['created']
    lines.append(date if show('show_time') else date[:10])
    if show('show_unpaid') and order['due'] > 0: lines.append('PENDIENTE DE COBRO')
    lines.append(separator)
    items = list(order['lines'])
    if template.get('line_order') == 'Nombre':
        items.sort(key=lambda item: item['name'].casefold())
    if template.get('line_order') == 'Categoría' and categories:
        items.sort(key=lambda item: (categories.get(item['product_id'], '').casefold(), item['id']))
    taxes = {}
    for item in items:
        lines.append(f"{item['qty']} x {item['name']}  {amount(item['qty'] * item['price'])}")
        detail = item['format']
        if item['extras']: detail += ' + ' + ', '.join(extra['name'] for extra in item['extras'])
        if show('show_unit_price', 0): detail += f" · {amount(item['price'])} / ud."
        if show('show_item_tax', 0): detail += f" · IVA {item['tax']}%"
        lines.append('  ' + detail)
        if show('show_notes', 0) and item['note']: lines.append('  Nota: ' + item['note'])
        taxes[item['tax']] = taxes.get(item['tax'], 0) + item['qty'] * item['price']
    lines.extend([separator, f"TOTAL PRODUCTOS  {amount(order['total'])}"])
    if show('show_tax'):
        for rate, gross in taxes.items():
            tax = gross - int(gross / (1 + rate / 100) + 0.5)
            lines.append(f"IVA {rate}% incluido  {amount(tax)}")
    lines.append(separator)
    for payment in order['payments']:
        label = 'EFECTIVO' if payment['method'] == 'cash' else 'TARJETA'
        if show('show_user') and payment.get('user_name'): label += ' · ' + payment['user_name']
        lines.append(f"{label}  {amount(payment['amount'])}")
        if show('show_tips') and payment.get('tip'):
            lines.append(f"Propina  {amount(payment['tip'])}")
        if payment['method'] == 'cash':
            lines.append(f"Recibido {amount(payment['tendered'])} · Cambio {amount(payment['change_due'])}")
    lines.extend([f"PENDIENTE  {amount(order['due'])}", separator])
    lines.extend((template.get('footer') or 'Gracias por compartir mesa.\nMarchan2 · JoseluIA').splitlines())
    return '\n'.join(lines)


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
        template = None
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ticket_templates'").fetchone():
            from pos_profiles import active_options
            chosen = active_options(c).get('receipt_template_id')
            row = c.execute('SELECT * FROM ticket_templates WHERE id=?', (chosen,)).fetchone() if chosen else \
                  c.execute('SELECT * FROM ticket_templates WHERE is_default=1 ORDER BY id LIMIT 1').fetchone()
            template = dict(row) if row else None
        categories = {}
        if template and template.get('line_order') == 'Categoría':
            categories = {row['id']: row['category_name'] for row in c.execute('''SELECT p.id,c.name category_name
                FROM products p JOIN categories c ON c.id=p.category_id''')}
        payload = _format_receipt(order, read_company(store), template, categories)
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
    if sys.platform != 'win32': raise ValueError('La impresión directa requiere Windows.')
    gdi = ctypes.WinDLL('gdi32', use_last_error=True)
    gdi.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p]
    gdi.CreateDCW.restype = ctypes.c_void_p
    gdi.StartDocW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi.StartPage.argtypes = [ctypes.c_void_p]
    gdi.EndPage.argtypes = [ctypes.c_void_p]
    gdi.EndDoc.argtypes = [ctypes.c_void_p]
    gdi.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi.TextOutW.argtypes = [ctypes.c_void_p, wintypes.INT, wintypes.INT, wintypes.LPCWSTR, wintypes.INT]
    hdc = gdi.CreateDCW('WINSPOOL', printer_name, None, None)
    if not hdc: raise ValueError('Windows no pudo abrir la impresora seleccionada.')
    class DOCINFO(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.INT), ('lpszDocName', wintypes.LPCWSTR),
                    ('lpszOutput', wintypes.LPCWSTR), ('lpszDatatype', wintypes.LPCWSTR),
                    ('fwType', wintypes.DWORD)]
    doc = DOCINFO(ctypes.sizeof(DOCINFO), 'Marchan2 · impresión de prueba', None, None, 0)
    lines = text.splitlines()
    try:
        for _ in range(copies):
            if gdi.StartDocW(hdc, ctypes.byref(doc)) <= 0: raise ValueError('Windows rechazó el trabajo de impresión.')
            try:
                if gdi.StartPage(hdc) <= 0: raise ValueError('Windows no pudo iniciar la página.')
                y = 100
                for line in lines:
                    if y > 2900:
                        gdi.EndPage(hdc)
                        if gdi.StartPage(hdc) <= 0: raise ValueError('Windows no pudo continuar la impresión.')
                        y = 100
                    if not gdi.TextOutW(hdc, 100, y, line, len(line)):
                        raise ValueError('Windows no pudo dibujar el documento en la impresora.')
                    y += 38
                if gdi.EndPage(hdc) <= 0:
                    raise ValueError('Windows no pudo finalizar la página.')
            finally:
                if gdi.EndDoc(hdc) <= 0:
                    raise ValueError('Windows no pudo completar el trabajo de impresión.')
    finally:
        gdi.DeleteDC(hdc)


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
    payload = _raw_bytes(text, raw_columns, feed_lines, cut_mode)
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
    script = ('Get-CimInstance Win32_Printer | Where-Object { $_.Name -eq ' +
              "'" + printer_name.replace("'", "''") + "'" +
              ' } | Select-Object -ExpandProperty DriverName')
    try:
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                                capture_output=True, text=True, timeout=10,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        return result.stdout.strip() if result.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
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
