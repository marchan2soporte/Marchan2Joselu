"""Line discounts and weighed portions. Settled amounts remain integer cents."""
import json
from datetime import datetime
from decimal import Decimal,InvalidOperation


def initialize(store):
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS line_pricing_changes(
            id INTEGER PRIMARY KEY,line_id INTEGER NOT NULL,order_id INTEGER NOT NULL,
            user_id INTEGER,created TEXT NOT NULL,before_data TEXT NOT NULL,
            after_data TEXT NOT NULL,request_id TEXT NOT NULL UNIQUE)''')
        c.execute('BEGIN IMMEDIATE')
        if 'weighed' not in [r['name'] for r in c.execute('PRAGMA table_info(products)')]:
            c.execute('ALTER TABLE products ADD COLUMN weighed INTEGER NOT NULL DEFAULT 0')
        columns={'base_price':'INTEGER','reference_price':'INTEGER','is_weighed':'INTEGER NOT NULL DEFAULT 0',
                 'weight_milli':'INTEGER','discount_kind':'TEXT','discount_value':'INTEGER NOT NULL DEFAULT 0',
                 'pricing_revision':'INTEGER NOT NULL DEFAULT 0'}
        existing={r['name'] for r in c.execute('PRAGMA table_info(lines)')}
        for name,kind in columns.items():
            if name not in existing:c.execute('ALTER TABLE lines ADD COLUMN '+name+' '+kind)
        c.execute('UPDATE lines SET base_price=price WHERE base_price IS NULL')


def weight(value):
    try:
        n=Decimal(str(value).replace(',','.'))
        if not n.is_finite() or not Decimal('.001')<=n<=1000 or n*1000!=(n*1000).to_integral_value():raise ValueError('Introduce un peso entre 0,001 y 1.000 kg, con hasta tres decimales.')
        return int(n*1000)
    except InvalidOperation:raise ValueError('Peso no válido.')


def net_price(base,kind,value):
    if kind=='percent':return (base*(10000-value)+5000)//10000
    if kind=='amount':
        if value>base:raise ValueError('El descuento no puede superar el precio de una unidad.')
        return base-value
    return base


def labels(line):
    line['weight_label']=(f"{line['weight_milli']/1000:.3f} KG".replace('.',',')) if line.get('weight_milli') else ''
    kind=line.get('discount_kind');value=line.get('discount_value',0)
    line['discount_label']=('DTO '+f'{value/100:.2f}'.replace('.',',')+' %') if kind=='percent' else ('DTO '+f'{value/100:.2f}'.replace('.',',')+' € / UD') if kind=='amount' else ''


def mutate(store,action,data,actor):
    from store import money
    import cash_register,permissions
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if ('ticket_weight' if action=='line_weight' else 'ticket_discount') not in permissions.rights(c,actor):raise PermissionError('Tu perfil no permite cambiar el precio o peso de esta línea.')
        cash_register.require_open(c)
        request=data.get('request_id')
        if not isinstance(request,str) or not 8<=len(request)<=120:raise ValueError('Falta el identificador de operación.')
        old=c.execute('SELECT line_id FROM line_pricing_changes WHERE request_id=?',(request,)).fetchone()
        if old:return {'line_id':old['line_id'],'duplicate':True}
        row=c.execute('SELECT * FROM lines WHERE id=?',(data.get('line_id'),)).fetchone()
        if not row:raise ValueError('Selecciona una línea existente.')
        line=dict(row);order=store.require_open(c,line['order_id'])
        if order['payments']:raise ValueError('La cuenta ya tiene pagos. No se puede cambiar su precio o peso.')
        if data.get('expected_revision')!=line['pricing_revision'] or data.get('expected_price')!=line['price'] or data.get('expected_qty')!=line['qty']:raise ValueError('La línea ha cambiado. Selecciónala de nuevo antes de aplicar el cálculo.')
        before=dict(line);base=line['base_price'] if line['base_price'] is not None else line['price']
        if action=='line_weight':
            if not line['is_weighed']:raise ValueError('Este producto no está configurado para vender por peso.')
            if line['kitchen']!='new':raise ValueError('El peso no puede cambiar después de enviar a preparación.')
            grams=weight(data.get('value'))
            extras=sum(e['price'] for e in json.loads(line['extras']))
            base=(line['reference_price']*grams+500)//1000+extras
            line['weight_milli']=grams
        else:
            kind=data.get('kind');value=data.get('value')
            if kind=='percent':
                try:
                    number=Decimal(str(value).replace(',','.'))
                    if not number.is_finite() or not 0<=number<=100 or number*100!=(number*100).to_integral_value():raise ValueError('El porcentaje debe estar entre 0 y 100, con hasta dos decimales.')
                    amount=int(number*100)
                except InvalidOperation:raise ValueError('Porcentaje no válido.')
            elif kind=='amount':amount=money(value)
            elif kind=='clear':amount=0
            else:raise ValueError('Tipo de descuento no válido.')
            line['discount_kind']=kind if amount else None;line['discount_value']=amount
        price=net_price(base,line['discount_kind'],line['discount_value'])
        c.execute('UPDATE lines SET base_price=?,price=?,weight_milli=?,discount_kind=?,discount_value=?,pricing_revision=pricing_revision+1 WHERE id=?',(base,price,line['weight_milli'],line['discount_kind'],line['discount_value'],line['id']))
        after=dict(c.execute('SELECT * FROM lines WHERE id=?',(line['id'],)).fetchone())
        c.execute('INSERT INTO line_pricing_changes(line_id,order_id,user_id,created,before_data,after_data,request_id) VALUES(?,?,?,?,?,?,?)',(line['id'],order['id'],actor,datetime.now().isoformat(timespec='seconds'),json.dumps(before),json.dumps(after),request))
        store.audit(c,actor,action,order['id'])
    return {'line_id':line['id']}
