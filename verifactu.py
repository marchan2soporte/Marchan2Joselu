"""Preparación de VeriFactu: registro interno de facturación encadenado.

ESTADO: EN PREPARACIÓN. NO ES UN SISTEMA VERIFACTU.
- Genera un registro de alta por cada cuenta cobrada (factura simplificada F2)
  con la huella SHA-256 encadenada a la del registro anterior, siguiendo el
  formato de cálculo publicado por la AEAT para los registros de alta.
- NO envía nada a la AEAT, NO firma electrónicamente, NO tiene declaración
  responsable del productor ni homologación. Los tickets NO deben llevar la
  leyenda «VERI*FACTU» ni el QR tributario mientras esto no esté terminado.
- Sirve para validar datos (NIF, numeración, cuotas) y la integridad de la
  cadena antes de la integración real.
"""
import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

QR_TEST_URL = 'https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR'


def initialize(store):
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS verifactu_records(
            id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
            nif TEXT NOT NULL, invoice_number TEXT NOT NULL, issue_date TEXT NOT NULL,
            invoice_type TEXT NOT NULL DEFAULT 'F2', tax_total INTEGER NOT NULL, total INTEGER NOT NULL,
            breakdown TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL,
            generated_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'no_enviado')''')


def settings(c):
    row = c.execute("SELECT value FROM settings WHERE key='verifactu'").fetchone()
    return dict({'enabled': False}, **(json.loads(row['value']) if row else {}))


def set_enabled(store, enabled):
    with store.db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES('verifactu',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (json.dumps({'enabled': bool(enabled)}),))
    return status(store)


def amount(cents):
    sign = '-' if cents < 0 else ''
    cents = abs(cents)
    return f'{sign}{cents // 100}.{cents % 100:02d}'


def tax_breakdown(lines):
    """Base y cuota por tipo de IVA a partir de importes con IVA incluido."""
    totals = {}
    for l in lines:
        totals[l['tax']] = totals.get(l['tax'], 0) + l['qty'] * l['price']
    result = []
    for rate, gross in sorted(totals.items()):
        base = (gross * 100 + (100 + rate) // 2) // (100 + rate)
        result.append({'rate': rate, 'base': base, 'tax': gross - base, 'total': gross})
    return result


def fingerprint(nif, number, issue_date, invoice_type, tax_total, total, previous_hash, generated_at):
    text = (f'IDEmisorFactura={nif}&NumSerieFactura={number}&FechaExpedicionFactura={issue_date}'
            f'&TipoFactura={invoice_type}&CuotaTotal={amount(tax_total)}&ImporteTotal={amount(total)}'
            f'&Huella={previous_hash}&FechaHoraHusoGenRegistro={generated_at}')
    return hashlib.sha256(text.encode('utf-8')).hexdigest().upper()


def record_sale(c, order_id):
    """Llamado al cerrar (cobrar) una cuenta. No hace nada si está desactivado."""
    if not settings(c)['enabled']:
        return None
    if c.execute('SELECT 1 FROM verifactu_records WHERE order_id=?', (order_id,)).fetchone():
        return None
    company = c.execute("SELECT value FROM settings WHERE key='company'").fetchone()
    nif = (json.loads(company['value']).get('tax_id', '') if company else '').strip().upper()
    if not nif:
        return None
    order = c.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
    lines = [dict(r) for r in c.execute('SELECT qty,price,tax FROM lines WHERE order_id=?', (order_id,))]
    breakdown = tax_breakdown(lines)
    total = sum(b['total'] for b in breakdown)
    tax_total = sum(b['tax'] for b in breakdown)
    number = f"{order['series_name']}-{order['series_number']}" if order['series_name'] else f'M2-{order_id}'
    paid = datetime.fromisoformat(order['paid_at'] or datetime.now().isoformat())
    issue_date = paid.strftime('%d-%m-%Y')
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
    previous = c.execute('SELECT hash FROM verifactu_records ORDER BY id DESC LIMIT 1').fetchone()
    previous_hash = previous['hash'] if previous else ''
    digest = fingerprint(nif, number, issue_date, 'F2', tax_total, total, previous_hash, generated_at)
    c.execute('''INSERT INTO verifactu_records(order_id,nif,invoice_number,issue_date,invoice_type,tax_total,total,breakdown,previous_hash,hash,generated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (order_id, nif, number, issue_date, 'F2', tax_total, total, json.dumps(breakdown), previous_hash, digest, generated_at))
    return digest


def verify_chain(c):
    previous = ''
    for r in c.execute('SELECT * FROM verifactu_records ORDER BY id'):
        if r['previous_hash'] != previous:
            return {'ok': False, 'broken_at': r['id'], 'reason': 'El enlace con el registro anterior no coincide.'}
        expected = fingerprint(r['nif'], r['invoice_number'], r['issue_date'], r['invoice_type'], r['tax_total'], r['total'], r['previous_hash'], r['generated_at'])
        if expected != r['hash']:
            return {'ok': False, 'broken_at': r['id'], 'reason': 'La huella no corresponde a los datos del registro.'}
        previous = r['hash']
    return {'ok': True}


def qr_url(record):
    """URL de cotejo (entorno de PRUEBAS de la AEAT), solo para validar el formato."""
    return QR_TEST_URL + '?' + urlencode({'nif': record['nif'], 'numserie': record['invoice_number'],
                                          'fecha': record['issue_date'], 'importe': amount(record['total'])})


def status(store):
    with store.db() as c:
        c.execute('BEGIN')
        cfg = settings(c)
        company = c.execute("SELECT value FROM settings WHERE key='company'").fetchone()
        nif = (json.loads(company['value']).get('tax_id', '') if company else '').strip()
        records = [dict(r) for r in c.execute('SELECT * FROM verifactu_records ORDER BY id DESC LIMIT 200')]
        for r in records:
            r['breakdown'] = json.loads(r['breakdown'])
            r['qr_test_url'] = qr_url(r)
        count = c.execute('SELECT COUNT(*) FROM verifactu_records').fetchone()[0]
        return {'enabled': cfg['enabled'], 'nif': nif, 'count': count, 'chain': verify_chain(c), 'records': records,
                'pending': ['Envío a la AEAT (servicio web SOAP con certificado electrónico)', 'Firma o remisión según modalidad VERI*FACTU',
                            'Registros de anulación y subsanación', 'Facturas completas y rectificativas', 'Declaración responsable del productor del software',
                            'QR tributario y leyenda en el ticket (solo cuando todo lo anterior esté validado)']}
