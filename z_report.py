"""Read-only operational Z preview using transactions already stored by the TPV."""
from datetime import date

import daily_close
import pos_profiles

FLAG_MAP = {'sales_by_user': 'include_user_sales',
            'sales_by_center': 'include_center_sales',
            'cancellations': 'include_cancellations',
            'tips': 'include_tips',
            'pending': 'include_pending',
            'cash_balance': 'include_cash_balance',
            'sales_by_family': 'include_family_sales'}


def preview(store, day=None):
    day = day or date.today().isoformat()
    settings = pos_profiles.active(store)
    enabled = settings['options']['z_options']
    flags = {field: False for field in FLAG_MAP.values()}
    flags['include_user_payments'] = False
    for key, field in FLAG_MAP.items():
        flags[field] = enabled[key]
    report = daily_close.preview(store, day, flags)
    if enabled['payments_by_method']:
        with store.db() as c:
            rows = [dict(row) for row in c.execute('''SELECT method,COUNT(*) operations,
                COALESCE(SUM(amount),0) total FROM payments
                WHERE substr(created,1,10)=? GROUP BY method ORDER BY method''', (day,))]
        report['sections'].append({'title': 'Cobros por forma de pago',
            'columns': ['Forma', 'Operaciones', 'Importe'],
            'rows': [[{'cash': 'EFECTIVO', 'card': 'TARJETA'}.get(row['method'], row['method']),
                      row['operations'], row['total']] for row in rows]})
    report['profile'] = settings['name']
    report['kind'] = 'z_preview'
    report['note'] = ('Informe Z operativo de prueba. No ejecuta un cierre de caja, '
                      'no verifica efectivo físico ni genera un documento fiscal.')
    return report
