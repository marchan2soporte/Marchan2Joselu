"""Marchan2 local prototype. Monetary amounts are integer euro cents."""
import sqlite3
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from contextlib import contextmanager


def money(value):
    try:
        amount = Decimal(str(value).replace(',', '.'))
        if not amount.is_finite() or amount < 0 or amount > 100000:
            raise ValueError('El precio debe estar entre 0 y 100.000 €.')
        return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError):
        raise ValueError('Introduce un importe válido.')


def title(value):
    result = ' '.join(str(value or '').split()).upper()
    if not result or len(result) > 120:
        raise ValueError('El nombre es obligatorio y admite hasta 120 caracteres.')
    return result


class LegacyStore:
    def __init__(self, path):
        self.path = str(path)
        with self.db() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,parent TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,name TEXT NOT NULL,category_id INTEGER NOT NULL REFERENCES categories(id),tax INTEGER NOT NULL DEFAULT 10,prep TEXT NOT NULL DEFAULT 'COCINA',course TEXT NOT NULL DEFAULT 'PRIMERO',addon_group TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS formats(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),name TEXT NOT NULL,price INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS extras(id INTEGER PRIMARY KEY,group_name TEXT NOT NULL,name TEXT NOT NULL,price INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS centers(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS tables(id INTEGER PRIMARY KEY,center_id INTEGER NOT NULL REFERENCES centers(id),name TEXT NOT NULL,UNIQUE(center_id,name));
            CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY,table_id INTEGER REFERENCES tables(id),status TEXT NOT NULL DEFAULT 'open',created TEXT NOT NULL,paid_at TEXT,payment TEXT,total INTEGER,tendered INTEGER,change_due INTEGER);
            CREATE UNIQUE INDEX IF NOT EXISTS one_open_table ON orders(table_id) WHERE status='open' AND table_id IS NOT NULL;
            CREATE TABLE IF NOT EXISTS lines(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES orders(id),product_id INTEGER NOT NULL,format_id INTEGER NOT NULL,name TEXT NOT NULL,format TEXT NOT NULL,price INTEGER NOT NULL,qty INTEGER NOT NULL,tax INTEGER NOT NULL,extras TEXT NOT NULL DEFAULT '[]',note TEXT NOT NULL DEFAULT '',prep TEXT NOT NULL,course TEXT NOT NULL,kitchen TEXT NOT NULL DEFAULT 'new');
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            ''')
            c.execute('BEGIN IMMEDIATE')
            if not c.execute("SELECT 1 FROM settings WHERE key='initialized'").fetchone():
                self.seed(c)

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            with c:
                yield c
        finally:
            c.close()

    def seed(self, c):
        c.execute("INSERT INTO settings VALUES('initialized','1')")
        c.execute("INSERT INTO settings VALUES('business','MARCHAN2 · DEMOSTRACIÓN')")
        cats = [('ENTRANTES','COMIDAS'),('BRASA Y COCINA','COMIDAS'),('POSTRES','COMIDAS'),('CAFÉS','BEBIDAS'),('REFRESCOS','BEBIDAS'),('VINOS','BEBIDAS'),('COMBINADOS','BEBIDAS')]
        for name, parent in cats:
            c.execute('INSERT INTO categories(name,parent) VALUES(?,?)',(name,parent))
        demo = [
            ('ENSALADILLA',1,[('TAPA',4.5),('PLATO',8.5)],''),('JAMÓN',1,[('PLATO',20)],''),
            ('CROQUETAS',1,[('RACIÓN',6.5),('UNIDAD',2.2)],''),('PAN Y PICOS',1,[('SERVICIO',1.8)],'TIPO PAN'),
            ('TOMATE AL CARBÓN',2,[('PLATO',8)],''),('CARRILLADA',2,[('PLATO',14)],''),('PAVÍA',2,[('PLATO',8.5)],''),
            ('TORTILLA',2,[('CLÁSICA',6.5),('CON WHISKY',7.5)],''),('FLAN DE CAFÉ',3,[('UNIDAD',3.5)],''),('TARTA DE LA ABUELA',3,[('PORCIÓN',3.5)],''),
            ('CAFÉ CON LECHE',4,[('TAZA',1.9)],''),('ESPRESSO',4,[('TAZA',1.9)],''),
            ('COCA COLA',5,[('BOTELLA',2)],''),('COCA COLA ZERO',5,[('BOTELLA',2)],''),('AGUA',5,[('500 ML',2.2),('1,5 L',2.4)],''),
            ('MANZANILLA SOLEAR',6,[('COPA',3),('BOTELLA',11.5)],''),('BLANCO DE ALBARIZA',6,[('COPA',3.8),('BOTELLA',14)],''),
            ('JHONNY NEGRO',7,[('COPA',9),('BOTELLA',120)],'REFRESCOS')]
        for name, cat, formats, group in demo:
            parent = cats[cat-1][1]
            p = c.execute('INSERT INTO products(name,category_id,prep,course,addon_group) VALUES(?,?,?,?,?)',
                          (name,cat,'BARRA' if parent=='BEBIDAS' else 'COCINA','BEBIDAS' if parent=='BEBIDAS' else 'POSTRES' if cat==3 else 'PRIMERO',group)).lastrowid
            for fmt, price in formats:
                c.execute('INSERT INTO formats(product_id,name,price) VALUES(?,?,?)',(p,fmt,money(price)))
        for group, name, price in [('REFRESCOS','COCA COLA',0),('REFRESCOS','COCA COLA ZERO',0),('REFRESCOS','FANTA NARANJA',0),('REFRESCOS','RED BULL',100),('TIPO PAN','PAN BLANCO',0),('TIPO PAN','PAN INTEGRAL',0)]:
            c.execute('INSERT INTO extras(group_name,name,price) VALUES(?,?,?)',(group,name,price))
        for name, prefix, count in [('SALA','M',10),('TERRAZA','T',6),('BARRA','B',5)]:
            center = c.execute('INSERT INTO centers(name) VALUES(?)',(name,)).lastrowid
            for i in range(1,count+1):
                c.execute('INSERT INTO tables(center_id,name) VALUES(?,?)',(center,prefix+str(i)))

    def state(self):
        with self.db() as c:
            products = [dict(r) for r in c.execute('SELECT * FROM products WHERE active=1 ORDER BY name')]
            for p in products:
                p['formats'] = [dict(r) for r in c.execute('SELECT * FROM formats WHERE product_id=? AND active=1 ORDER BY id',(p['id'],))]
            tables = [dict(r) for r in c.execute('SELECT * FROM tables ORDER BY id')]
            orders = [self.order(c,r['id']) for r in c.execute("SELECT id FROM orders WHERE status='open' ORDER BY id")]
            history = [dict(r) for r in c.execute("SELECT o.*,t.name table_name FROM orders o LEFT JOIN tables t ON t.id=o.table_id WHERE status='paid' ORDER BY id DESC LIMIT 100")]
            today = datetime.now().strftime('%Y-%m-%d')
            stats = dict(c.execute("SELECT COUNT(*) tickets,COALESCE(SUM(total),0) revenue,COALESCE(SUM(CASE WHEN payment='cash' THEN total ELSE 0 END),0) cash,COALESCE(SUM(CASE WHEN payment='card' THEN total ELSE 0 END),0) card FROM orders WHERE status='paid' AND substr(paid_at,1,10)=?",(today,)).fetchone())
            return dict(products=products,categories=[dict(r) for r in c.execute('SELECT * FROM categories ORDER BY parent,name')],
                        extras=[dict(r) for r in c.execute('SELECT * FROM extras')],centers=[dict(r) for r in c.execute('SELECT * FROM centers')],tables=tables,orders=orders,history=history,stats=stats)

    def order(self,c,oid):
        row = c.execute('SELECT o.*,t.name table_name,ce.name center_name FROM orders o LEFT JOIN tables t ON t.id=o.table_id LEFT JOIN centers ce ON ce.id=t.center_id WHERE o.id=?',(oid,)).fetchone()
        if not row: raise ValueError('La cuenta no existe.')
        order = dict(row)
        order['lines'] = [dict(r) for r in c.execute('SELECT * FROM lines WHERE order_id=? ORDER BY id',(oid,))]
        for line in order['lines']:
            line['extras'] = json.loads(line['extras'])
        order['total'] = sum(r['qty']*r['price'] for r in order['lines'])
        return order

    def require_open(self,c,oid):
        order=self.order(c,oid)
        if order['status']!='open':raise ValueError('Esta cuenta ya está cerrada.')
        return order

    def mutate(self, action, data, actor=None):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            self.audit(c,actor,action,data.get('order_id'))
            if action in ('open','add','quantity','send','close_empty'):
                import cash_register
                active_session=cash_register.require_open(c)
            if action=='open':
                table=data.get('table_id')
                if table is None and not data.get('direct'):
                    raise ValueError('Selecciona una mesa o pulsa Venta directa.')
                if table is not None:
                    if not c.execute('SELECT 1 FROM tables WHERE id=?',(table,)).fetchone():raise ValueError('La mesa no existe.')
                    existing=c.execute("SELECT id FROM orders WHERE table_id=? AND status='open'",(table,)).fetchone()
                    if existing:return {'order_id':existing['id']}
                oid=c.execute('INSERT INTO orders(table_id,created,created_by,cash_session_id) VALUES(?,?,?,?)',(table,datetime.now().isoformat(timespec='seconds'),actor,active_session['id'])).lastrowid
                return {'order_id':oid}
            if action=='add':
                from pos_profiles import active_options
                auto_prepare=active_options(c)['auto_prepare']
                self.require_open(c,data['order_id'])
                row=c.execute('SELECT f.*,p.name product_name,p.tax,p.prep,p.course,p.addon_group,p.weighed FROM formats f JOIN products p ON p.id=f.product_id WHERE f.id=? AND f.active=1 AND p.active=1',(data['format_id'],)).fetchone()
                if not row:raise ValueError('El formato ya no está disponible.')
                qty=int(data.get('qty',1))
                if qty<1 or qty>100:raise ValueError('Cantidad entre 1 y 100.')
                grams=None
                if row['weighed']:
                    import line_pricing
                    if qty!=1:raise ValueError('Cada porción pesada se añade por separado.')
                    grams=line_pricing.weight(data.get('weight'))
                ids=data.get('extras',[])
                if len(ids)!=len(set(ids)) or len(ids)>(10 if 'BOTELLA' in row['name'] else 1):raise ValueError('Revisa la cantidad de añadidos.')
                extras=[]
                for eid in ids:
                    e=c.execute('SELECT * FROM extras WHERE id=? AND group_name=?',(eid,row['addon_group'])).fetchone()
                    if not e or not row['addon_group']:raise ValueError('Ese añadido no pertenece al producto.')
                    extras.append(dict(e))
                price=((row['price']*grams+500)//1000 if grams is not None else row['price'])+sum(e['price'] for e in extras)
                note=str(data.get('note',''))[:300];extra_json=json.dumps(extras)
                settings_row=c.execute("SELECT value FROM settings WHERE key='global_config'").fetchone()
                preferences=json.loads(settings_row['value']).get('preferences',{}) if settings_row else {}
                consolidate=preferences.get('consolidate_lines',True)
                same=c.execute("SELECT id,qty FROM lines WHERE order_id=? AND format_id=? AND price=? AND tax=? AND extras=? AND note=? AND course=? AND kitchen='new' AND weight_milli IS NULL AND discount_kind IS NULL ORDER BY id DESC LIMIT 1",
                               (data['order_id'],row['id'],price,row['tax'],extra_json,note,row['course'])).fetchone() if consolidate and not auto_prepare and grams is None else None
                if same and same['qty']+qty<=100:
                    c.execute('UPDATE lines SET qty=qty+? WHERE id=?',(qty,same['id']))
                    return {'line_id':same['id']}
                lid=c.execute('INSERT INTO lines(order_id,product_id,format_id,name,format,price,qty,tax,extras,note,prep,course,kitchen,base_price,reference_price,is_weighed,weight_milli) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                          (data['order_id'],row['product_id'],row['id'],row['product_name'],row['name'],price,qty,row['tax'],extra_json,note,row['prep'],row['course'],'pending' if auto_prepare else 'new',price,row['price'],int(bool(row['weighed'])),grams)).lastrowid
                if auto_prepare:
                    from printing import enqueue_kitchen
                    enqueue_kitchen(c,self,data['order_id'],[lid])
                return {'line_id':lid}
            elif action=='quantity':
                row=c.execute('SELECT * FROM lines WHERE id=?',(data['line_id'],)).fetchone()
                if not row:raise ValueError('La línea no existe.')
                order=self.require_open(c,row['order_id'])
                if order['paid']:raise ValueError('La cuenta tiene pagos parciales. No se pueden retirar productos.')
                if row['kitchen']!='new':raise ValueError('La línea ya se envió a preparación. Esta versión no permite anular comandas enviadas.')
                qty=row['qty']+int(data['delta']) if 'delta' in data else int(data['qty'])
                if qty<0 or qty>100:raise ValueError('Cantidad entre 0 y 100.')
                if row['is_weighed'] and qty!=1:raise ValueError('Cambia el peso de esta porción o cancela la línea completa.')
                if qty==0:c.execute('DELETE FROM lines WHERE id=?',(row['id'],))
                else:c.execute('UPDATE lines SET qty=? WHERE id=?',(qty,row['id']))
            elif action=='send':
                order=self.require_open(c,data['order_id'])
                if not order['lines']:raise ValueError('Añade productos antes de enviar.')
                newly_sent=[line['id'] for line in order['lines'] if line['kitchen']=='new']
                c.execute("UPDATE lines SET kitchen='pending' WHERE order_id=? AND kitchen='new'",(data['order_id'],))
                from printing import enqueue_kitchen
                enqueue_kitchen(c,self,data['order_id'],newly_sent)
            elif action=='ready':
                c.execute("UPDATE lines SET kitchen='ready' WHERE order_id=? AND prep=? AND kitchen='pending'",(data['order_id'],data['prep']))
            elif action=='pay':
                order=self.require_open(c,data['order_id'])
                if not order['lines']:raise ValueError('No puedes cobrar una cuenta vacía.')
                expected=int(data['expected_total'])
                if expected!=order['total']:raise ValueError('La cuenta ha cambiado. Revisa el total antes de cobrar.')
                method=data.get('payment')
                if method not in ('cash','card'):raise ValueError('Forma de pago no válida.')
                tendered=money(data.get('tendered',0)) if method=='cash' else order['total']
                if tendered<order['total']:raise ValueError('El efectivo recibido no cubre el total.')
                c.execute("UPDATE orders SET status='paid',paid_at=?,payment=?,total=?,tendered=?,change_due=? WHERE id=?",(datetime.now().isoformat(timespec='seconds'),method,order['total'],tendered,tendered-order['total'],order['id']))
                return {'receipt':self.order(c,order['id'])}
            elif action=='close_empty':
                order=self.require_open(c,data['order_id'])
                if order['lines']:raise ValueError('La cuenta contiene productos.')
                c.execute("UPDATE orders SET status='void' WHERE id=?",(order['id'],))
            elif action=='product':
                name=title(data.get('name'));cat=int(data['category_id'])
                if not c.execute('SELECT 1 FROM categories WHERE id=?',(cat,)).fetchone():raise ValueError('Selecciona una categoría.')
                tax=int(data.get('tax',10));prep=data.get('prep','COCINA');course=data.get('course','PRIMERO');group=data.get('addon_group','')
                if tax not in (0,4,10,21):raise ValueError('Selecciona un IVA válido.')
                if prep not in ('BARRA','COCINA') or course not in ('PRIMERO','SEGUNDO','TERCEROS','BEBIDAS','POSTRES'):raise ValueError('Preparación no válida.')
                if group and not c.execute('SELECT 1 FROM extras WHERE group_name=?',(group,)).fetchone():raise ValueError('El grupo de añadidos no existe.')
                existing_weight=c.execute('SELECT weighed FROM products WHERE id=?',(data.get('id'),)).fetchone()
                weighed=data.get('weighed',bool(existing_weight[0]) if existing_weight else False)
                if type(weighed) is not bool:raise ValueError('Venta por peso no válida.')
                formats=data.get('formats',[])
                if not formats or len(formats)>20:raise ValueError('Añade entre 1 y 20 formatos de venta.')
                formats=[(title(f['name']),money(f['price'])) for f in formats]
                if len({f[0] for f in formats})!=len(formats):raise ValueError('Los formatos no pueden repetirse.')
                pid=data.get('id')
                if c.execute('SELECT 1 FROM products WHERE name=? AND active=1 AND id<>?',(name,pid or 0)).fetchone():raise ValueError('Ya existe ese producto. Edítalo desde la carta.')
                if pid:
                    if not c.execute('SELECT 1 FROM products WHERE id=?',(pid,)).fetchone():raise ValueError('Producto no encontrado.')
                    c.execute('UPDATE products SET name=?,category_id=?,tax=?,prep=?,course=?,addon_group=? WHERE id=?',(name,cat,tax,prep,course,group,pid))
                    c.execute('UPDATE formats SET active=0 WHERE product_id=?',(pid,))
                else:pid=c.execute('INSERT INTO products(name,category_id,tax,prep,course,addon_group) VALUES(?,?,?,?,?,?)',(name,cat,tax,prep,course,group)).lastrowid
                c.execute('UPDATE products SET weighed=? WHERE id=?',(int(weighed),pid))
                for fmt,price in formats:c.execute('INSERT INTO formats(product_id,name,price) VALUES(?,?,?)',(pid,fmt,price))
                return {'product_id':pid}
            elif action=='category':
                c.execute('INSERT INTO categories(name,parent) VALUES(?,?)',(title(data.get('name')),title(data.get('parent'))))
            elif action=='center':
                name=title(data.get('name'));prefix=title(data.get('prefix'))
                start=int(data.get('start',1));end=int(data.get('end',10))
                if start<0 or end<start or end-start>199:raise ValueError('El rango debe contener entre 1 y 200 mesas.')
                cid=c.execute('INSERT INTO centers(name) VALUES(?)',(name,)).lastrowid
                for n in range(start,end+1):c.execute('INSERT INTO tables(center_id,name) VALUES(?,?)',(cid,prefix+str(n)))
            else:raise ValueError('Acción no disponible.')
        return {'ok':True}

    def preparation(self):
        with self.db() as c:
            ids=[r[0] for r in c.execute("SELECT DISTINCT order_id FROM lines WHERE kitchen='pending'")]
            return [self.order(c,oid) for oid in ids]

    def receipt(self, oid):
        with self.db() as c:return self.order(c,oid)


from workflows import WorkflowMixin


class Store(WorkflowMixin,LegacyStore):
    pass
