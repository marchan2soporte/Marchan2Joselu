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

PREP_TYPES = ('BARRA', 'COCINA')
DOCUMENT_TYPES = ('receipt', 'z_report')


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
                                         'print_mode': 'manual', 'profile_id': profile_id})
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
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        profile_id = int(data['profile_id'])
        if not c.execute('SELECT 1 FROM pos_profiles WHERE id=?', (profile_id,)).fetchone():
            raise ValueError('Punto de venta no encontrado.')
        c.execute('''INSERT INTO document_printer_routes(profile_id,kind,printer_name,copies,print_mode)
            VALUES(?,?,?,?,?) ON CONFLICT(profile_id,kind) DO UPDATE SET
            printer_name=excluded.printer_name,copies=excluded.copies,print_mode=excluded.print_mode''',
                  (profile_id, kind, printer, copies, mode))
    return {'ok': True}


def save_kitchen(store, data):
    name = str(data.get('name', '')).strip()
    printer = str(data.get('printer_name', '')).strip()
    preps = data.get('prep_types', [])
    centers = data.get('center_ids', [])
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
            changed = c.execute('''UPDATE kitchen_printer_routes SET name=?,printer_name=?,prep_types=?,center_ids=?
                WHERE id=? AND profile_id=?''', (name, printer, json.dumps(preps), json.dumps(centers),
                                                   int(data['id']), profile_id)).rowcount
            if not changed: raise ValueError('Ruta de cocina no encontrada.')
            identifier = int(data['id'])
        else:
            identifier = c.execute('''INSERT INTO kitchen_printer_routes
                (profile_id,name,printer_name,prep_types,center_ids) VALUES(?,?,?,?,?)''',
                (profile_id, name, printer, json.dumps(preps), json.dumps(centers))).lastrowid
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
            job = c.execute('''INSERT INTO print_jobs(created,kind,printer_name,copies,payload)
                VALUES(?,?,?,?,?)''', (datetime.now().isoformat(timespec='seconds'),
                'kitchen', route['printer_name'], 1, payload)).lastrowid
            c.execute('INSERT OR IGNORE INTO print_job_lines(line_id,route_id,job_id) VALUES(?,?,?)',
                      (line['id'], route['id'], job))


def _format_receipt(order, company, template=None):
    template = template or {}
    lines = ['MARCHAN2 · TICKET DE PRUEBA',
             template.get('header') or company.get('trade_name') or company.get('legal_name') or 'MARCHAN2',
             'NO FISCAL']
    if company.get('tax_id'): lines.append('CIF: ' + company['tax_id'])
    if company.get('address'): lines.append(company['address'])
    lines.append(f"Cuenta #{order['id']} · {order['table_name'] or 'VENTA DIRECTA'}")
    if template.get('show_time', 1): lines.append(order['paid_at'] or order['created'])
    lines.append('-' * 38)
    items = order['lines']
    if template.get('line_order') == 'Nombre': items = sorted(items, key=lambda item: item['name'])
    for line in items:
        lines.append(f"{line['qty']} x {line['name']}  {line['qty'] * line['price'] / 100:.2f} EUR")
        if template.get('show_unit_price'): lines.append(f"  {line['price'] / 100:.2f} EUR / unidad")
        if template.get('show_notes') and line['note']: lines.append('  Nota: ' + line['note'])
    lines.extend(['-' * 38, f"TOTAL {order['total'] / 100:.2f} EUR",
                  f"PENDIENTE {order['due'] / 100:.2f} EUR",
                  template.get('footer') or 'Gracias por su visita'])
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
        payload = _format_receipt(order, read_company(store), template)
        try:
            job = c.execute('''INSERT INTO print_jobs(created,kind,printer_name,copies,payload,unique_key)
                VALUES(?,?,?,?,?,?)''', (datetime.now().isoformat(timespec='seconds'),
                'receipt', route['printer_name'], route['copies'], payload, key)).lastrowid
        except __import__('sqlite3').IntegrityError:
            return {'configured': True, 'duplicate': True}
    return {'configured': True, 'job_id': job}


def enqueue_text(store, kind, text):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        route = c.execute('SELECT * FROM document_printer_routes WHERE profile_id=? AND kind=?',
                          (_profile_id(c), kind)).fetchone()
        if not route or not route['printer_name']: return {'configured': False}
        job = c.execute('''INSERT INTO print_jobs(created,kind,printer_name,copies,payload)
            VALUES(?,?,?,?,?)''', (datetime.now().isoformat(timespec='seconds'),
            kind, route['printer_name'], route['copies'], text)).lastrowid
    return {'configured': True, 'job_id': job}


def test_print(store, printer_name):
    if not isinstance(printer_name, str) or not printer_name.strip() or len(printer_name) > 255:
        raise ValueError('Selecciona una impresora de Windows.')
    return enqueue_text_to_printer(store, printer_name,
        'MARCHAN2 · PRUEBA DE IMPRESORA\nImpresión desde Administración\nNo es un documento fiscal')


def enqueue_text_to_printer(store, printer_name, text):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        job = c.execute('''INSERT INTO print_jobs(created,kind,printer_name,copies,payload)
            VALUES(?,?,?,?,?)''', (datetime.now().isoformat(timespec='seconds'),
            'test', printer_name.strip(), 1, text)).lastrowid
    return {'configured': True, 'job_id': job}


def print_text(printer_name, text, copies=1):
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
            print_text(job['printer_name'], job['payload'], job['copies'])
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
