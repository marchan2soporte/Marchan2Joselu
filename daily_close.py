"""Non-fiscal, read-only daily operations summary for the local POS."""
from collections import defaultdict
from datetime import date

import global_config
import pos_profiles


def preview(store, day=None, flags_override=None):
    day = day or date.today().isoformat()
    date.fromisoformat(day)
    flags = flags_override if flags_override is not None else global_config.read(store)['preferences']
    opening_float = (pos_profiles.active(store) or {'options': {}})['options'].get('opening_float', 0)
    with store.db() as c:
        closed = [dict(r) for r in c.execute('''SELECT o.id,o.total,o.created_by,
            COALESCE(ce.name,'VENTA DIRECTA') center,COALESCE(u.name,'SIN USUARIO') user
            FROM orders o LEFT JOIN tables t ON t.id=o.table_id
            LEFT JOIN centers ce ON ce.id=t.center_id
            LEFT JOIN users u ON u.id=o.created_by
            WHERE o.status='paid' AND substr(o.paid_at,1,10)=?''', (day,))]
        payments = [dict(r) for r in c.execute('''SELECT p.amount,p.tip,p.method,
            COALESCE(u.name,'SIN USUARIO') user FROM payments p
            LEFT JOIN users u ON u.id=p.user_id
            WHERE substr(p.created,1,10)=?''', (day,))]
        cancellations = [dict(r) for r in c.execute('''SELECT COALESCE(u.name,'SIN USUARIO') user,
            COUNT(*) count FROM line_cancellations lc LEFT JOIN users u ON u.id=lc.user_id
            WHERE substr(lc.created,1,10)=? GROUP BY user''', (day,))]
        families = [dict(r) for r in c.execute('''SELECT COALESCE(cat.parent,'SIN FAMILIA') family,
            SUM(l.qty*l.price) total FROM lines l JOIN orders o ON o.id=l.order_id
            LEFT JOIN products p ON p.id=l.product_id LEFT JOIN categories cat ON cat.id=p.category_id
            WHERE o.status='paid' AND substr(o.paid_at,1,10)=? GROUP BY family''', (day,))]
        pending = [store.order(c, r['id']) for r in c.execute("SELECT id FROM orders WHERE status='open'")]
    sections = []
    def group(key, title, items, label):
        if not flags[key]: return
        totals = defaultdict(lambda: [0, 0])
        for item in items:
            entry = totals[item[label]]
            entry[0] += 1
            entry[1] += item['total']
        sections.append({'title': title, 'columns': ['Concepto', 'Operaciones', 'Importe'],
                         'rows': [[name, *values] for name, values in sorted(totals.items())]})
    group('include_center_sales', 'Ventas por centro', closed, 'center')
    group('include_user_sales', 'Ventas por usuario', closed, 'user')
    if flags['include_user_payments']:
        totals = defaultdict(lambda: [0, 0])
        for item in payments:
            entry = totals[item['user']]
            entry[0] += 1
            entry[1] += item['amount']
        sections.append({'title': 'Cobros por usuario', 'columns': ['Usuario', 'Cobros', 'Importe'],
                         'rows': [[name, *values] for name, values in sorted(totals.items())]})
    if flags['include_cancellations']:
        sections.append({'title': 'Cancelaciones por usuario', 'columns': ['Usuario', 'Líneas'],
                         'rows': [[r['user'], r['count']] for r in cancellations]})
    if flags['include_family_sales']:
        sections.append({'title': 'Ventas por familia', 'columns': ['Familia', 'Importe'],
                         'rows': [[r['family'], r['total']] for r in families]})
    if flags['include_pending']:
        sections.append({'title': 'Cuentas pendientes ahora',
                         'columns': ['Cuenta', 'Ubicación', 'Pendiente'],
                         'rows': [[o['id'], o['table_name'] or 'VENTA DIRECTA', o['due']] for o in pending]})
    if flags['include_cash_balance']:
        cash = sum(p['amount'] for p in payments if p['method'] == 'cash')
        sections.append({'title': 'Efectivo registrado', 'columns': ['Concepto', 'Importe'],
                         'rows': [['Saldo inicial de referencia', opening_float],
                                  ['Cobros en efectivo', cash], ['Total teórico', opening_float + cash]]})
    if flags['include_tips']:
        tips = defaultdict(int)
        for payment in payments:
            tips[payment['method']] += payment['tip']
        sections.append({'title': 'Propinas por forma de pago', 'columns': ['Forma', 'Importe'],
                         'rows': [[{'cash': 'EFECTIVO', 'card': 'TARJETA'}.get(method, method), total]
                                  for method, total in sorted(tips.items())]})
    return {'day': day, 'sales': sum(o['total'] for o in closed),
            'payments': sum(p['amount'] for p in payments), 'sections': sections,
            'note': 'Resumen operativo de prueba. No cierra la caja, no verifica efectivo físico ni emite documentos fiscales.'}
