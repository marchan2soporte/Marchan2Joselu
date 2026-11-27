"""Motor de impresión con diseño: una sola maqueta para la vista previa,
las impresoras térmicas (ESC/POS en RAW) y las impresoras con controlador de
Windows (GDI).

Un documento es {'marchan2_doc': 1, 'width': columnas, 'blocks': [...]} y cada
bloque es uno de:
  {'t': 'text', 'text': str, 'align': 'left'|'center'|'right', 'bold': bool, 'large': bool}
  {'t': 'pair', 'left': str, 'right': str|{'m': céntimos}, 'bold': bool, 'large': bool}
  {'t': 'sep', 'char': '-'|'='|'·'|'*'}
  {'t': 'image', 'data': 'data:image/png;base64,...'}
  {'t': 'feed', 'lines': int}
Los importes se guardan en céntimos y cada salida los escribe a su manera
(«12,35 €» en Windows, «12,35 EUR» en RAW porque CP850 no tiene el símbolo €).
"""
import base64
import json
import struct
import sys
import textwrap
import zlib

MARKER = '{"marchan2_doc"'
ALIGNS = ('left', 'center', 'right')
SEPARATORS = ('-', '=', '·', '*')


def is_doc(payload):
    return isinstance(payload, str) and payload.startswith(MARKER)


def dumps(doc):
    return json.dumps(doc, ensure_ascii=False, separators=(',', ':'))


def loads(payload):
    return json.loads(payload)


def money(cents, euro=True):
    sign = '-' if cents < 0 else ''
    cents = abs(int(cents))
    whole = f'{cents // 100:,}'.replace(',', '.')
    return f'{sign}{whole},{cents % 100:02d} ' + ('€' if euro else 'EUR')


def value(v, euro=True):
    return money(v['m'], euro) if isinstance(v, dict) else str(v)


def text_doc(text, width=48):
    """Convierte un texto plano (cocina, Z, pruebas) en documento monoespaciado."""
    blocks = []
    for line in text.replace('\r\n', '\n').split('\n'):
        if len(line) >= 10 and set(line) in ({'-'}, {'='}):
            blocks.append({'t': 'sep', 'char': line[0]})
        else:
            blocks.append({'t': 'text', 'text': line, 'align': 'left'})
    return {'marchan2_doc': 1, 'width': width, 'blocks': blocks}


# ---------- Maquetación en columnas (común a texto y RAW) ----------
def _wrap(text, width):
    if not text:
        return ['']
    return textwrap.wrap(text, width=max(1, width), break_long_words=True, break_on_hyphens=False) or ['']


def layout(doc, width=None, euro=True):
    """Devuelve líneas [(texto, align, bold, large)] ya ajustadas al ancho."""
    width = width or doc['width']
    out = []
    for b in doc['blocks']:
        large = bool(b.get('large'))
        w = width // 2 if large else width
        bold = bool(b.get('bold'))
        if b['t'] == 'text':
            for part in str(b['text']).split('\n'):
                for line in _wrap(part, w):
                    out.append((line, b.get('align', 'left'), bold, large))
        elif b['t'] == 'pair':
            right = value(b['right'], euro)
            room = max(1, w - len(right) - 1)
            parts = _wrap(str(b['left']), room)
            for line in parts[:-1]:
                out.append((line, 'left', bold, large))
            out.append((parts[-1].ljust(w - len(right)) + right, 'left', bold, large))
        elif b['t'] == 'sep':
            ch = b.get('char', '-')
            out.append(((ch if ch in SEPARATORS else '-') * width, 'left', False, False))
        elif b['t'] == 'feed':
            out.extend([('', 'left', False, False)] * int(b.get('lines', 1)))
    return out


def to_text(doc, width=None):
    width = width or doc['width']
    lines = []
    for text, align, _bold, large in layout(doc, width, euro=False):
        w = width // 2 if large else width
        if align == 'center':
            text = text.center(w).rstrip()
        elif align == 'right':
            text = text.rjust(w)
        lines.append(text)
    return '\n'.join(lines)


# ---------- PNG mínimo (logotipos) ----------
def decode_png(data_url):
    """Devuelve (ancho, alto, filas de luminancia 0-255) o None si no es un PNG soportado."""
    try:
        kind, _, encoded = data_url.partition(';base64,')
        if kind != 'data:image/png':
            return None
        raw = base64.b64decode(encoded)
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            return None
        pos, idat, palette, trns = 8, b'', None, None
        width = height = depth = ctype = interlace = None
        while pos < len(raw):
            length, kind = struct.unpack('>I4s', raw[pos:pos + 8])
            chunk = raw[pos + 8:pos + 8 + length]
            pos += 12 + length
            if kind == b'IHDR':
                width, height, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', chunk)
            elif kind == b'PLTE':
                palette = chunk
            elif kind == b'tRNS':
                trns = chunk
            elif kind == b'IDAT':
                idat += chunk
            elif kind == b'IEND':
                break
        if depth != 8 or interlace or ctype not in (0, 2, 3, 4, 6) or width * height > 4_000_000:
            return None
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
        stride = width * channels
        data = zlib.decompress(idat)
        rows, prev = [], bytearray(stride)
        for y in range(height):
            f = data[y * (stride + 1)]
            line = bytearray(data[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                if f == 1:
                    line[i] = (line[i] + a) & 255
                elif f == 2:
                    line[i] = (line[i] + b) & 255
                elif f == 3:
                    line[i] = (line[i] + ((a + b) >> 1)) & 255
                elif f == 4:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
            prev = line
            lum = bytearray(width)
            for x in range(width):
                px = line[x * channels:(x + 1) * channels]
                if ctype == 3:
                    idx = px[0]
                    r, g, bl = palette[idx * 3:idx * 3 + 3] if palette and idx * 3 + 2 < len(palette) else (0, 0, 0)
                    alpha = trns[idx] if trns and idx < len(trns) else 255
                elif ctype in (0, 4):
                    r = g = bl = px[0]
                    alpha = px[1] if ctype == 4 else 255
                else:
                    r, g, bl = px[0], px[1], px[2]
                    alpha = px[3] if ctype == 6 else 255
                y_ = (299 * r + 587 * g + 114 * bl) // 1000
                lum[x] = (y_ * alpha + 255 * (255 - alpha)) // 255
            rows.append(lum)
        return width, height, rows
    except Exception:
        return None


def _scaled(image, max_w):
    w, h, rows = image
    scale = min(1.0, max_w / w)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    return nw, nh, [bytes(rows[int(y / scale) if scale < 1 else y][int(x / scale) if scale < 1 else x] for x in range(nw)) for y in range(nh)]


# ---------- ESC/POS (RAW) ----------
def escpos(doc, columns, feed_lines=4, cut_mode='none'):
    width = min(int(doc['width']), int(columns))
    dots = 576 if columns >= 42 else 384
    out = bytearray(b'\x1b@\x1bt\x02')  # reiniciar y página de códigos CP850
    style = None
    for b in doc['blocks']:
        if b['t'] == 'image':
            img = decode_png(b['data'])
            if not img:
                continue
            w, h, rows = _scaled(img, int(dots * .6))
            bw = (w + 7) // 8
            raster = bytearray()
            for row in rows:
                for xb in range(bw):
                    byte = 0
                    for bit in range(8):
                        x = xb * 8 + bit
                        if x < w and row[x] < 128:
                            byte |= 0x80 >> bit
                    raster.append(byte)
            out += b'\x1ba\x01' + b'\x1dv0\x00' + struct.pack('<HH', bw, h) + raster + b'\n'
            style = None
            continue
        sub = {'marchan2_doc': 1, 'width': width, 'blocks': [b]}
        for text, align, bold, large in layout(sub, width, euro=False):
            wanted = (align, bold, large)
            if wanted != style:
                out += b'\x1ba' + bytes([ALIGNS.index(align)]) + b'\x1bE' + bytes([1 if bold else 0]) + b'\x1d!' + bytes([0x11 if large else 0])
                style = wanted
            out += text.rstrip().encode('cp850', errors='replace') + b'\n'
    out += b'\x1ba\x00\x1bE\x00\x1d!\x00' + b'\n' * int(feed_lines)
    if cut_mode != 'none':
        out += b'\x1d\x56' + (b'\x00' if cut_mode == 'full' else b'\x01')
    return bytes(out)


# ---------- Windows GDI ----------
def _gdi():
    import ctypes
    from ctypes import wintypes
    gdi = ctypes.WinDLL('gdi32', use_last_error=True)
    vp = ctypes.c_void_p
    gdi.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, vp]
    gdi.CreateDCW.restype = vp
    gdi.CreateCompatibleDC.argtypes = [vp]
    gdi.CreateCompatibleDC.restype = vp
    gdi.CreateDIBSection.argtypes = [vp, vp, wintypes.UINT, ctypes.POINTER(vp), vp, wintypes.DWORD]
    gdi.CreateDIBSection.restype = vp
    gdi.GetDeviceCaps.argtypes = [vp, ctypes.c_int]
    gdi.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
    gdi.CreateFontW.restype = vp
    gdi.SelectObject.argtypes = [vp, vp]
    gdi.SelectObject.restype = vp
    gdi.DeleteObject.argtypes = [vp]
    gdi.TextOutW.argtypes = [vp, ctypes.c_int, ctypes.c_int, wintypes.LPCWSTR, ctypes.c_int]
    gdi.PatBlt.argtypes = [vp, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    gdi.SetBkMode.argtypes = [vp, ctypes.c_int]
    gdi.StartDocW.argtypes = [vp, vp]
    for name in ('StartPage', 'EndPage', 'EndDoc', 'DeleteDC'):
        getattr(gdi, name).argtypes = [vp]
    gdi.StretchDIBits.argtypes = [vp] + [ctypes.c_int] * 8 + [vp, vp, wintypes.UINT, wintypes.DWORD]
    gdi.GdiFlush.argtypes = []
    return gdi


def _bitmap_header(w, h):
    import ctypes
    from ctypes import wintypes

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long), ('biHeight', ctypes.c_long),
                    ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', ctypes.c_long), ('biYPelsPerMeter', ctypes.c_long),
                    ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]
    return BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, h, 1, 24, 0, 0, 0, 0, 0, 0)


def _draw(gdi, hdc, doc, page_w, page_h, dpi, new_page=None):
    """Dibuja el documento en un contexto GDI (impresora o memoria). Devuelve la altura usada."""
    import ctypes
    width = int(doc['width'])
    margin = max(4, page_w // 40)
    cw = max(4, (page_w - 2 * margin) // width)
    cw = min(cw, max(4, dpi // 11))  # en A4 no más de ~11 caracteres por pulgada
    x0 = (page_w - cw * width) // 2
    ch = int(cw * 1.95)
    fonts = {}

    def font(bold, large):
        key = (bold, large)
        if key not in fonts:
            k = 2 if large else 1
            fonts[key] = gdi.CreateFontW(-ch * k, cw * k, 0, 0, 700 if bold else 400, 0, 0, 0, 1, 0, 0, 5, 1 | 0x30, 'Consolas')
        return fonts[key]

    gdi.SetBkMode(hdc, 1)
    y = margin

    def ensure(height):
        nonlocal y
        if new_page and y + height > page_h - margin:
            new_page()
            y = margin

    try:
        for b in doc['blocks']:
            if b['t'] == 'image':
                img = decode_png(b['data'])
                if not img:
                    continue
                target_w = int(cw * width * .55)
                w, h, rows = _scaled(img, min(target_w, 900))
                scale = max(1, target_w // max(1, w))
                dw, dh = w * scale, h * scale
                ensure(dh + ch // 2)
                stride = (w * 3 + 3) & ~3
                buf = bytearray(stride * h)
                for yy in range(h):
                    row = rows[h - 1 - yy]
                    for xx in range(w):
                        v = row[xx]
                        buf[yy * stride + xx * 3:yy * stride + xx * 3 + 3] = bytes((v, v, v))
                hdr = _bitmap_header(w, h)
                raw = (ctypes.c_char * len(buf)).from_buffer(buf)
                gdi.StretchDIBits(hdc, (page_w - dw) // 2, y, dw, dh, 0, 0, w, h, raw, ctypes.byref(hdr), 0, 0x00CC0020)
                y += dh + ch // 2
                continue
            if b['t'] == 'sep':
                ensure(ch)
                thick = max(1, cw // 6)
                mid = y + ch // 2
                if b.get('char') == '=':
                    gdi.PatBlt(hdc, x0, mid - thick * 2, cw * width, thick, 0x00000042)
                    gdi.PatBlt(hdc, x0, mid + thick, cw * width, thick, 0x00000042)
                elif b.get('char') in ('-', None):
                    gdi.PatBlt(hdc, x0, mid, cw * width, thick, 0x00000042)
                else:
                    line = (b.get('char') or '-') * width
                    gdi.SelectObject(hdc, font(False, False))
                    gdi.TextOutW(hdc, x0, y, line, len(line))
                y += ch
                continue
            sub = {'marchan2_doc': 1, 'width': width, 'blocks': [b]}
            for text, align, bold, large in layout(sub, width, euro=True):
                k = 2 if large else 1
                lh = int(ch * k * 1.12)
                ensure(lh)
                gdi.SelectObject(hdc, font(bold, large))
                text = text.rstrip()
                span = len(text) * cw * k
                x = x0 if align == 'left' else x0 + (cw * width - span) // (2 if align == 'center' else 1)
                if text:
                    gdi.TextOutW(hdc, x, y, text, len(text))
                y += lh
    finally:
        for f in fonts.values():
            gdi.DeleteObject(f)
    return y + margin


def print_gdi_doc(printer_name, doc, copies=1, title='Marchan2', output=None):
    if sys.platform != 'win32':
        raise ValueError('La impresión directa requiere Windows.')
    import ctypes
    from ctypes import wintypes
    gdi = _gdi()

    class DOCINFO(ctypes.Structure):
        _fields_ = [('cbSize', ctypes.c_int), ('lpszDocName', wintypes.LPCWSTR), ('lpszOutput', wintypes.LPCWSTR),
                    ('lpszDatatype', wintypes.LPCWSTR), ('fwType', wintypes.DWORD)]

    hdc = gdi.CreateDCW('WINSPOOL', printer_name, None, None)
    if not hdc:
        raise ValueError('Windows no pudo abrir la impresora seleccionada.')
    try:
        page_w, page_h, dpi = gdi.GetDeviceCaps(hdc, 8), gdi.GetDeviceCaps(hdc, 10), gdi.GetDeviceCaps(hdc, 88) or 203
        doc_info = DOCINFO(ctypes.sizeof(DOCINFO), title, output, None, 0)

        def new_page():
            gdi.EndPage(hdc)
            if gdi.StartPage(hdc) <= 0:
                raise ValueError('Windows no pudo continuar la impresión.')

        for _ in range(int(copies)):
            if gdi.StartDocW(hdc, ctypes.byref(doc_info)) <= 0:
                raise ValueError('Windows rechazó el trabajo de impresión.')
            try:
                if gdi.StartPage(hdc) <= 0:
                    raise ValueError('Windows no pudo iniciar la página.')
                _draw(gdi, hdc, doc, page_w, page_h, dpi, new_page)
                if gdi.EndPage(hdc) <= 0:
                    raise ValueError('Windows no pudo finalizar la página.')
            finally:
                gdi.EndDoc(hdc)
    finally:
        gdi.DeleteDC(hdc)


def render_png(doc, paper_px=None):
    """Imagen PNG (data URL) del ticket dibujado con el mismo código que imprime en Windows."""
    if sys.platform != 'win32':
        return None
    import ctypes
    gdi = _gdi()
    width = int(doc['width'])
    page_w = paper_px or (384 if width <= 32 else 576)
    page_h = 9000
    hdc = gdi.CreateCompatibleDC(None)
    bits = ctypes.c_void_p()
    hdr = _bitmap_header(page_w, -page_h)
    bmp = gdi.CreateDIBSection(hdc, ctypes.byref(hdr), 0, ctypes.byref(bits), None, 0)
    old = gdi.SelectObject(hdc, bmp)
    try:
        gdi.PatBlt(hdc, 0, 0, page_w, page_h, 0x00FF0062)
        used = min(page_h, _draw(gdi, hdc, doc, page_w, page_h, 203))
        gdi.GdiFlush()
        stride = (page_w * 3 + 3) & ~3
        data = ctypes.string_at(bits, stride * used)
    finally:
        gdi.SelectObject(hdc, old)
        gdi.DeleteObject(bmp)
        gdi.DeleteDC(hdc)
    raw = bytearray()
    for y in range(used):
        raw.append(0)
        row = data[y * stride:y * stride + page_w * 3]
        raw += row[1::3]  # canal verde como gris
    chunk = lambda k, d: struct.pack('>I', len(d)) + k + d + struct.pack('>I', zlib.crc32(k + d) & 0xffffffff)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', page_w, used, 8, 0, 0, 0, 0)) +
           chunk(b'IDAT', zlib.compress(bytes(raw), 6)) + chunk(b'IEND', b''))
    return 'data:image/png;base64,' + base64.b64encode(png).decode()


def printer_driver(printer_name, _cache={}):
    """Nombre del controlador con la API de Windows (sin PowerShell), en caché."""
    if printer_name in _cache:
        return _cache[printer_name]
    name = ''
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        spool = ctypes.WinDLL('winspool.drv', use_last_error=True)
        handle = wintypes.HANDLE()
        if spool.OpenPrinterW(ctypes.c_wchar_p(printer_name), ctypes.byref(handle), None):
            try:
                needed = wintypes.DWORD()
                spool.GetPrinterW(handle, 2, None, 0, ctypes.byref(needed))
                if needed.value:
                    buf = ctypes.create_string_buffer(needed.value)
                    if spool.GetPrinterW(handle, 2, buf, needed, ctypes.byref(needed)):
                        # PRINTER_INFO_2: pServerName, pPrinterName, pShareName, pPortName, pDriverName…
                        pointers = ctypes.cast(buf, ctypes.POINTER(ctypes.c_wchar_p))
                        name = pointers[4] or ''
            finally:
                spool.ClosePrinter(handle)
    _cache[printer_name] = name
    return name
