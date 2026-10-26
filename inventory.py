"""Administrative identity and manual goods ledger, independent of POS recipes."""
from datetime import datetime
from decimal import Decimal,InvalidOperation

def initialize(store):
 with store.db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,tax_id TEXT NOT NULL DEFAULT '',contact TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS stock_items(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,unit TEXT NOT NULL DEFAULT 'UD');
CREATE TABLE IF NOT EXISTS stock_moves(id INTEGER PRIMARY KEY,item_id INTEGER NOT NULL REFERENCES stock_items(id),supplier_id INTEGER REFERENCES suppliers(id),qty INTEGER NOT NULL,cost INTEGER NOT NULL,total INTEGER NOT NULL,kind TEXT NOT NULL,reference TEXT NOT NULL DEFAULT '',created TEXT NOT NULL,user_id INTEGER REFERENCES users(id),request_id TEXT NOT NULL UNIQUE);''')
  if 'minimum' not in [r['name'] for r in c.execute('PRAGMA table_info(stock_items)')]:
   c.execute('ALTER TABLE stock_items ADD COLUMN minimum INTEGER NOT NULL DEFAULT 0')

def quantity(value):
 try:
  n=Decimal(str(value).replace(',','.'))
  if not n.is_finite() or n<=0 or n>100000 or n*1000!=(n*1000).to_integral_value():raise ValueError('Cantidad positiva con hasta tres decimales.')
  return int(n*1000)
 except InvalidOperation:raise ValueError('Cantidad no válida.')

def state(store):
 with store.db() as c:
  c.execute('BEGIN')
  suppliers=[dict(r) for r in c.execute('SELECT * FROM suppliers ORDER BY name')]
  items=[dict(r) for r in c.execute('SELECT i.*,COALESCE(SUM(m.qty),0) balance FROM stock_items i LEFT JOIN stock_moves m ON m.item_id=i.id GROUP BY i.id ORDER BY i.name')]
  moves=[dict(r) for r in c.execute("SELECT m.*,i.name,i.unit,COALESCE(s.name,'') supplier FROM stock_moves m JOIN stock_items i ON i.id=m.item_id LEFT JOIN suppliers s ON s.id=m.supplier_id ORDER BY m.id DESC LIMIT 200")]
 return dict(suppliers=suppliers,items=items,moves=moves)

def mutate(store,action,data,actor):
 from store import title,money
 with store.db() as c:
  c.execute('BEGIN IMMEDIATE')
  if action=='supplier':
   name=title(data.get('name'));tax_id=str(data.get('tax_id',''))[:40];contact=str(data.get('contact',''))[:200]
   if data.get('id'):
    if not c.execute('SELECT 1 FROM suppliers WHERE id=?',(data['id'],)).fetchone():raise ValueError('Proveedor inexistente.')
    c.execute('UPDATE suppliers SET name=?,tax_id=?,contact=? WHERE id=?',(name,tax_id,contact,data['id']))
   else:c.execute('INSERT INTO suppliers(name,tax_id,contact) VALUES(?,?,?)',(name,tax_id,contact))
  elif action=='stock_item':
   minimum=0 if not data.get('minimum') else quantity(data['minimum'])
   name=title(data.get('name'));unit=title(data.get('unit','UD'))
   if data.get('id'):
    if not c.execute('SELECT 1 FROM stock_items WHERE id=?',(data['id'],)).fetchone():raise ValueError('Artículo inexistente.')
    c.execute('UPDATE stock_items SET name=?,unit=?,minimum=? WHERE id=?',(name,unit,minimum,data['id']))
   else:c.execute('INSERT INTO stock_items(name,unit,minimum) VALUES(?,?,?)',(name,unit,minimum))
  elif action=='stock_move':
   kind=data.get('kind');item=int(data['item_id']);qty=quantity(data.get('qty'));request=str(data.get('request_id',''))
   if not request or len(request)>100:raise ValueError('Falta el identificador de operación.')
   if kind not in ('receipt','waste','out'):raise ValueError('Tipo de movimiento no válido.')
   if not c.execute('SELECT 1 FROM stock_items WHERE id=?',(item,)).fetchone():raise ValueError('Artículo inexistente.')
   supplier=int(data['supplier_id']) if data.get('supplier_id') else None
   if kind=='receipt' and not c.execute('SELECT 1 FROM suppliers WHERE id=?',(supplier,)).fetchone():raise ValueError('Selecciona un proveedor.')
   cost=money(data.get('cost',0));total=(cost*qty+500)//1000
   if kind!='receipt':
    balance=c.execute('SELECT COALESCE(SUM(qty),0) FROM stock_moves WHERE item_id=?',(item,)).fetchone()[0]
    if qty>balance:raise ValueError('La salida supera las existencias registradas.')
    previous=c.execute("SELECT cost FROM stock_moves WHERE item_id=? AND kind='receipt' ORDER BY id DESC LIMIT 1",(item,)).fetchone()
    cost=previous[0] if previous else 0;qty=-qty;total=-((cost*(-qty)+500)//1000);supplier=None
   c.execute('INSERT INTO stock_moves(item_id,supplier_id,qty,cost,total,kind,reference,created,user_id,request_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(item,supplier,qty,cost,total,kind,str(data.get('reference',''))[:160],datetime.now().isoformat(timespec='seconds'),actor,request))
  else:raise ValueError('Operación desconocida.')
  store.audit(c,actor,action)
 return {'ok':True}

def report(store,name,start,end):
 from analytics import bounds
 a,b=bounds(start,end)
 with store.db() as c:
  c.execute('BEGIN')
  rows=[dict(r) for r in c.execute("SELECT m.*,i.name,i.unit,COALESCE(s.name,'SIN PROVEEDOR') supplier FROM stock_moves m JOIN stock_items i ON i.id=m.item_id LEFT JOIN suppliers s ON s.id=m.supplier_id WHERE m.created>=? AND m.created<? ORDER BY m.created,m.id",(a,b))]
  cols=[['Fecha','text'],['Artículo','text'],['Proveedor','text'],['Cantidad','number'],['Unidad','text'],['Coste unitario','money'],['Importe','money'],['Referencia','text']]
  note='Registro manual de mercancías. Importes de adquisición introducidos por el usuario. No se descuentan recetas ni ventas del TPV automáticamente.'
  if name in ('Stock por producto','Análisis de stocks'):
   cols=[['Artículo','text'],['Unidad','text'],['Existencia','number']]
   output=[list(r)[:2]+[r[2]/1000] for r in c.execute('SELECT i.name,i.unit,COALESCE(SUM(m.qty),0) FROM stock_items i LEFT JOIN stock_moves m ON m.item_id=i.id AND m.created<? GROUP BY i.id ORDER BY i.name',(b,))]
   note+=' Saldo acumulado hasta la fecha final, incluidas entradas anteriores al inicio.'
  elif name in ('Compras por proveedor','Análisis de compras'):
   groups={}
   for r in rows:
    if r['kind']=='receipt':groups[r['supplier']]=groups.get(r['supplier'],0)+r['total']
   cols=[['Proveedor','text'],['Compras registradas','money']];output=[[k,v] for k,v in groups.items()]
  else:
   if name in ('Entradas detalladas por proveedor','Precios de compra','Histórico de compras'):rows=[r for r in rows if r['kind']=='receipt']
   if name=='Valoración de mermas':rows=[r for r in rows if r['kind']=='waste'];note+=' Mermas valoradas al coste de la última recepción disponible en el momento de registrarlas.'
   output=[[r['created'],r['name'],r['supplier'],r['qty']/1000,r['unit'],r['cost'],r['total'],r['reference']] for r in rows]
 return dict(id=name,name=name,available=True,columns=cols,rows=output,note=note,start=start,end=end)


def valuation(store,cutoff):
 with store.db() as c:
  total=0
  for item in c.execute('SELECT id FROM stock_items'):
   qty=c.execute('SELECT COALESCE(SUM(qty),0) FROM stock_moves WHERE item_id=? AND created<?',(item[0],cutoff)).fetchone()[0]
   cost=c.execute("SELECT cost FROM stock_moves WHERE item_id=? AND kind='receipt' AND created<? ORDER BY created DESC,id DESC LIMIT 1",(item[0],cutoff)).fetchone()
   if cost:total+=(qty*cost[0]+500)//1000
 return total
