"""Read-only business reporting, based on closed accounts and dated payment entries."""
from datetime import date,datetime,timedelta
from collections import defaultdict
from decimal import Decimal,ROUND_HALF_UP

REPORT_GROUPS={
'Visión del negocio':['Análisis de ventas','Análisis de compras','Análisis de stocks'],
'Locales':['Ventas por local','Comensales por local y periodo de servicio','Operaciones por local y periodo de servicio','Formatos de venta por local','Productos por local'],
'Evolución':['Evolución de ventas','Comparativa interanual','Resumen de impuestos','Invitaciones','Reservas','Documento 347','Estado de TicketBAI'],
'Carta y rentabilidad':['Grupos mayores','Familias y productos','Categorías y productos','Productos en menús','Márgenes por familias','Márgenes por categorías','Promociones y productos','Alérgenos por producto','Histórico de ventas','Rentabilidad de la carta','Top 50 formatos','Top 50 productos','Ventas diarias'],
'Equipo':['Rendimiento de usuarios','Usuarios por periodo de servicio','Productos por usuario','Descuentos por usuario y producto','Descuentos por usuario y tipo','Cancelaciones por usuario'],
'Espacios':['Centros de venta','Ventas por ubicación','Productos por centro de venta','Comensales por centro de venta','Operaciones por centro de venta'],
'Cobros y caja':['Formas de pago','Tarifas','Movimientos de caja','Cobros pendientes','Propinas por formas de pago'],
'Servicios':['Productos por periodo de servicio','Centros de venta por periodo de servicio','Comensales por periodo de servicio','Operaciones por periodo de servicio'],
'Clientes':['Ventas a cliente','Facturas por cliente','Impuestos por cliente','Productos vendidos a cada cliente'],
'Almacén':['Entradas detalladas por proveedor','Compras por proveedor','Precios de compra','Compras y ventas por producto','Stock por producto','Facturas de proveedor','Histórico de compras','Movimientos por producto','Pagos pendientes','Pedidos por recibir','Valoración de mermas'],
'Cocina':['Tiempos de preparación'],
'Diarios':['Diario de facturas','Diario de albaranes','Diario de pedidos','Diario de cierres de caja','Diario de ventas']}
LIVE={'Análisis de ventas','Evolución de ventas','Comparativa interanual','Resumen de impuestos','Familias y productos','Categorías y productos','Histórico de ventas','Top 50 formatos','Top 50 productos','Ventas diarias','Rendimiento de usuarios','Productos por usuario','Centros de venta','Ventas por ubicación','Productos por centro de venta','Operaciones por centro de venta','Formas de pago','Cobros pendientes','Diario de ventas'}
INVENTORY_REPORTS={'Análisis de compras','Análisis de stocks','Entradas detalladas por proveedor','Compras por proveedor','Precios de compra','Stock por producto','Histórico de compras','Movimientos por producto','Valoración de mermas'}
LIVE.update(INVENTORY_REPORTS)
LIVE.update({'Movimientos de caja','Diario de cierres de caja'})
DEPENDENCIES={'Visión del negocio':'compras, existencias y costes de adquisición','Locales':'locales y periodos de servicio vinculados a cada operación','Evolución':'reservas, invitaciones o integración fiscal, según el informe','Carta y rentabilidad':'costes históricos, menús, promociones o alérgenos vinculados a los productos','Equipo':'descuentos, cancelaciones y periodos de servicio','Espacios':'número de comensales registrado en cada cuenta','Cobros y caja':'tarifas, movimientos de caja y propinas','Servicios':'periodos de servicio vinculados a cada operación','Clientes':'clientes vinculados a ventas y documentos','Almacén':'recepciones, compras y movimientos de existencias','Cocina':'marcas de tiempo de envío y finalización de cada línea','Diarios':'documentos y cierres de caja'}

def report_catalog():
 return [dict(id=name,group=group,name=name,available=name in LIVE,reason='' if name in LIVE else 'Requiere '+DEPENDENCIES[group]+'. Este módulo todavía no registra esos datos.') for group,names in REPORT_GROUPS.items() for name in names]

def bounds(start,end):
 a=date.fromisoformat(start);b=date.fromisoformat(end)
 if b<a or (b-a).days>3660:raise ValueError('Selecciona un periodo válido de hasta diez años.')
 return a.isoformat(),(b+timedelta(days=1)).isoformat()

def records(store,start,end):
 a,b=bounds(start,end)
 with store.db() as c:
  c.execute('BEGIN')
  orders=[dict(r) for r in c.execute("SELECT o.*,COALESCE(t.name,o.source_label,'VENTA DIRECTA') location,COALESCE(ce.name,'VENTA DIRECTA') center,COALESCE(u.name,'ANTERIOR') user FROM orders o LEFT JOIN tables t ON t.id=o.table_id LEFT JOIN centers ce ON ce.id=t.center_id LEFT JOIN users u ON u.id=o.created_by WHERE o.status='paid' AND o.paid_at>=? AND o.paid_at<?",(a,b))]
  payments=[dict(r) for r in c.execute('SELECT p.*,COALESCE(u.name,\'ANTERIOR\') user FROM payments p LEFT JOIN users u ON u.id=p.user_id WHERE p.created>=? AND p.created<?',(a,b))]
  lines=[dict(r) for r in c.execute("SELECT l.*,o.paid_at,COALESCE(ce.name,'VENTA DIRECTA') center,COALESCE(u.name,'ANTERIOR') user,COALESCE(ca.name,'SIN CATEGORÍA') category,COALESCE(ca.parent,'SIN FAMILIA') family FROM lines l JOIN orders o ON o.id=l.order_id LEFT JOIN products p ON p.id=l.product_id LEFT JOIN categories ca ON ca.id=p.category_id LEFT JOIN tables t ON t.id=o.table_id LEFT JOIN centers ce ON ce.id=t.center_id LEFT JOIN users u ON u.id=o.created_by WHERE o.status='paid' AND o.paid_at>=? AND o.paid_at<?",(a,b))]
 return orders,payments,lines

def dashboard(store,today=None):
 today=today or date.today();starts=[today,today-timedelta(days=today.weekday()),today.replace(day=1),today.replace(month=1,day=1)]
 cards=[]
 for name,start in zip(['Hoy','Esta semana','Este mes','Este año'],starts):
  orders,payments,_=records(store,start.isoformat(),today.isoformat())
  cards.append(dict(name=name,start=start.isoformat(),end=today.isoformat(),sales=sum(o['total'] or 0 for o in orders),collected=sum(p['amount'] for p in payments),tickets=len(orders)))
 with store.db() as c:
  c.execute('BEGIN')
  tables=c.execute('SELECT COUNT(*) FROM tables').fetchone()[0]
  occupied=c.execute("SELECT COUNT(DISTINCT table_id) FROM orders WHERE status='open'").fetchone()[0]
  pending=c.execute("SELECT COALESCE(SUM((SELECT COALESCE(SUM(qty*price),0) FROM lines WHERE order_id=o.id)-(SELECT COALESCE(SUM(amount),0) FROM payments WHERE order_id=o.id)),0) FROM orders o WHERE status='open'").fetchone()[0]
 import inventory
 stock=dict(current=inventory.valuation(store,(today+timedelta(days=1)).isoformat()),month=inventory.valuation(store,today.replace(day=1).isoformat()),year=inventory.valuation(store,today.replace(month=1,day=1).isoformat()))
 return dict(cards=cards,tables=tables,occupied=occupied,pending=pending,stock=stock,guests=None,generated=datetime.now().isoformat(timespec='seconds'))

def report(store,name,start,end):
 entry=next((r for r in report_catalog() if r['id']==name),None)
 if not entry:raise ValueError('Informe desconocido.')
 if not entry['available']:return dict(**entry,columns=[],rows=[],note=entry['reason'])
 if name in INVENTORY_REPORTS:
  import inventory
  return inventory.report(store,name,start,end)
 if name in ('Movimientos de caja','Diario de cierres de caja'):
  import cash_register
  return cash_register.analytics_report(store,name,start,end)
 orders,payments,lines=records(store,start,end)
 cols=[];rows=[];note='Ventas de cuentas cerradas, con IVA incluido, por fecha de cierre. No incluye cuentas abiertas. Las cuentas divididas cerradas cuentan por separado.'
 if name in ('Análisis de ventas','Histórico de ventas','Diario de ventas'):
  cols=[['Cuenta','text'],['Fecha','text'],['Centro','text'],['Ubicación','text'],['Usuario','text'],['Venta','money']]
  rows=[[o['id'],o['paid_at'],o['center'],o['location'] or 'VENTA DIRECTA',o['user'],o['total']] for o in orders]
 elif name in ('Evolución de ventas','Ventas diarias','Comparativa interanual'):
  totals=defaultdict(int)
  for o in orders:totals[o['paid_at'][:10]]+=o['total'] or 0
  a=date.fromisoformat(start);b=date.fromisoformat(end)
  cols=[['Fecha','text'],['Venta','money']]
  for n in range((b-a).days+1):
   d=a+timedelta(days=n);rows.append([d.isoformat(),totals[d.isoformat()]])
  if name=='Comparativa interanual':
   def last(d):return d.replace(year=d.year-1,day=min(d.day,28) if d.month==2 else d.day)
   previous=records(store,last(a).isoformat(),last(b).isoformat())[0];old=defaultdict(int)
   for o in previous:old[o['paid_at'][:10]]+=o['total'] or 0
   cols.extend([['Fecha año anterior','text'],['Venta año anterior','money']])
   for r in rows:
    d=last(date.fromisoformat(r[0])).isoformat();r.extend([d,old[d]])
   note+=' El 29 de febrero se compara con el 28 de febrero del año anterior.'
 elif name=='Formas de pago':
  cols=[['Forma de pago','text'],['Operaciones','number'],['Cobrado','money']];groups=defaultdict(lambda:[0,0])
  for p in payments:g=groups[p['method']];g[0]+=1;g[1]+=p['amount']
  rows=[['EFECTIVO' if k=='cash' else 'TARJETA',*v] for k,v in groups.items()];note='Cobros por fecha del pago. Incluye pagos parciales de cuentas abiertas; no equivale a las ventas cerradas.'
 elif name=='Cobros pendientes':
  cols=[['Cuenta','text'],['Ubicación','text'],['Total','money'],['Cobrado','money'],['Pendiente','money']]
  with store.db() as c:
   c.execute('BEGIN')
   for r in c.execute("SELECT id FROM orders WHERE status='open'"):
    o=store.order(c,r['id']);rows.append([o['id'],o['table_name'] or 'VENTA DIRECTA',o['total'],o['paid'],o['due']])
  note='Estado actual de todas las cuentas abiertas. No se limita al intervalo de fechas.'
 elif name=='Resumen de impuestos':
  cols=[['IVA %','number'],['Base','money'],['IVA incluido','money'],['Total','money']];groups=defaultdict(int)
  for l in lines:groups[l['tax']]+=l['qty']*l['price']
  for tax,gross in groups.items():
   base=int((Decimal(gross)/(1+Decimal(tax)/100)).quantize(Decimal('1'),rounding=ROUND_HALF_UP));rows.append([tax,base,gross-base,gross])
  note+=' Desglose orientativo, redondeado por tipo. No es una declaración ni documento fiscal.'
 elif name in ('Centros de venta','Ventas por ubicación','Operaciones por centro de venta','Rendimiento de usuarios'):
  field='user' if name=='Rendimiento de usuarios' else 'location' if name=='Ventas por ubicación' else 'center'
  groups=defaultdict(lambda:[0,0]);cols=[['Usuario' if field=='user' else 'Ubicación' if field=='location' else 'Centro','text'],['Cuentas cerradas','number'],['Venta','money'],['Cuenta media','money']]
  for o in orders:g=groups[o[field] or 'VENTA DIRECTA'];g[0]+=1;g[1]+=o['total'] or 0
  rows=[[k,*v,round(v[1]/v[0])] for k,v in groups.items()]
 else:
  fields={'Familias y productos':['family','name'],'Categorías y productos':['category','name'],'Productos por usuario':['user','name'],'Productos por centro de venta':['center','name'],'Top 50 formatos':['name','format'],'Top 50 productos':['name']}[name]
  labels={'family':'Familia','category':'Categoría','user':'Usuario','center':'Centro','name':'Producto','format':'Formato'}
  cols=[[labels[f],'text'] for f in fields]+[['Unidades','number'],['Venta','money']];groups=defaultdict(lambda:[0,0])
  for l in lines:g=groups[tuple(l[f] for f in fields)];g[0]+=l['qty'];g[1]+=l['qty']*l['price']
  rows=[[*k,*v] for k,v in sorted(groups.items(),key=lambda kv:kv[1][1],reverse=True)]
  if name.startswith('Top 50'):rows=rows[:50]
  note+=' Agrupación según la categoría y familia actuales; usuario que abrió la cuenta.'
 return dict(**entry,columns=cols,rows=rows,note=note,start=start,end=end)
