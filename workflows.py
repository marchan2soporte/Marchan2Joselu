"""Authenticated staff workflows and transactional split payments."""
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
from datetime import datetime

COURSES=('PRIMERO','SEGUNDO','TERCEROS','BEBIDAS','POSTRES')


def password(pin,salt=None):
    if not re.fullmatch(r'[0-9]{4,8}',str(pin)):
        raise ValueError('El PIN debe tener entre 4 y 8 dígitos.')
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',str(pin).encode(),bytes.fromhex(salt),160000).hex()


class WorkflowMixin:
    def __init__(self,path):
        existed=Path(path).exists()
        super().__init__(path)
        with self.db() as c:
            version=c.execute('PRAGMA user_version').fetchone()[0]
        if version<2 and existed:
            backup=Path(path).with_name('marchan2-antes-v02-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(2)+'.db')
            with self.db() as c:
                target=sqlite3.connect(backup)
                try:c.backup(target)
                finally:target.close()
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('''CREATE TABLE IF NOT EXISTS line_cancellations(
                id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL,line_id INTEGER NOT NULL,
                name TEXT NOT NULL,qty INTEGER NOT NULL,reason TEXT NOT NULL,
                user_id INTEGER,created TEXT NOT NULL)''')
            for column, kind in [('series_id','INTEGER'),('series_number','INTEGER'),('series_name','TEXT')]:
                if column not in [r['name'] for r in c.execute('PRAGMA table_info(orders)')]:
                    c.execute(f'ALTER TABLE orders ADD COLUMN {column} {kind}')
            if c.execute('PRAGMA user_version').fetchone()[0]<2:
                c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,pin_hash TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1)')
                c.execute('CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES orders(id),amount INTEGER NOT NULL,method TEXT NOT NULL,tendered INTEGER NOT NULL,change_due INTEGER NOT NULL,created TEXT NOT NULL,user_id INTEGER REFERENCES users(id),request_id TEXT UNIQUE)')
                c.execute('CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,created TEXT NOT NULL,user_id INTEGER,action TEXT NOT NULL,order_id INTEGER)')
                for name,typ in [('created_by','INTEGER'),('parent_id','INTEGER'),('source_label',"TEXT NOT NULL DEFAULT ''")]:
                    if name not in [r['name'] for r in c.execute('PRAGMA table_info(orders)')]:
                        c.execute(f'ALTER TABLE orders ADD COLUMN {name} {typ}')
                if not c.execute('SELECT 1 FROM users').fetchone():
                    c.execute('INSERT INTO users(name,pin_hash,role) VALUES(?,?,?)',('ADMIN',password('1234'),'admin'))
                c.execute("INSERT INTO payments(order_id,amount,method,tendered,change_due,created) SELECT id,total,payment,COALESCE(tendered,total),COALESCE(change_due,0),paid_at FROM orders WHERE status='paid' AND NOT EXISTS(SELECT 1 FROM payments p WHERE p.order_id=orders.id)")
                c.execute('PRAGMA user_version=2')

    def users(self,active_only=True):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT id,name,role,active FROM users'+(' WHERE active=1' if active_only else '')+' ORDER BY name')]

    def authenticate(self,uid,pin):
        with self.db() as c:
            user=c.execute('SELECT * FROM users WHERE id=? AND active=1',(uid,)).fetchone()
        if not user:raise ValueError('Usuario o PIN incorrectos.')
        try:valid=hmac.compare_digest(user['pin_hash'],password(pin,user['pin_hash'].split(':')[0]))
        except ValueError:valid=False
        if not valid:raise ValueError('Usuario o PIN incorrectos.')
        return {k:user[k] for k in ('id','name','role','active')}

    def audit(self,c,actor,action,oid=None):
        c.execute('INSERT INTO audit(created,user_id,action,order_id) VALUES(?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),actor,action,oid))

    def order(self,c,oid):
        result=super().order(c,oid)
        result['payments']=[dict(r) for r in c.execute('SELECT p.*,u.name user_name FROM payments p LEFT JOIN users u ON u.id=p.user_id WHERE order_id=? ORDER BY p.id',(oid,))]
        result['paid']=sum(p['amount'] for p in result['payments'])
        result['due']=result['total']-result['paid']
        result['user_name']=None
        if result['created_by']:
            u=c.execute('SELECT name FROM users WHERE id=?',(result['created_by'],)).fetchone()
            if u:result['user_name']=u['name']
        if result['source_label'] and not result['table_name']:result['table_name']=result['source_label']
        return result

    def state(self):
        result=super().state()
        with self.db() as c:
            today=datetime.now().strftime('%Y-%m-%d')
            revenue=dict(c.execute("SELECT COALESCE(SUM(amount),0) revenue,COALESCE(SUM(CASE WHEN method='cash' THEN amount ELSE 0 END),0) cash,COALESCE(SUM(CASE WHEN method='card' THEN amount ELSE 0 END),0) card FROM payments WHERE substr(created,1,10)=?",(today,)).fetchone())
            result['stats'].update(revenue)
            result['payment_history']=[dict(r) for r in c.execute('SELECT p.*,u.name user_name FROM payments p LEFT JOIN users u ON u.id=p.user_id ORDER BY p.id DESC LIMIT 100')]
        return result

    def take_payment(self,c,order,data,actor,amount=None):
        from store import money
        if not order['lines']:raise ValueError('La cuenta está vacía.')
        if int(data['expected_total'])!=order['total'] or int(data.get('expected_due',order['due']))!=order['due']:
            raise ValueError('La cuenta ha cambiado. Vuelve a abrir Pagos.')
        amount=order['due'] if amount is None else amount
        if not isinstance(amount,int) or amount<0 or amount>order['due'] or (amount==0 and order['due']>0):
            raise ValueError('El importe a cobrar no es válido.')
        method=data.get('payment')
        if method not in ('cash','card'):raise ValueError('Elige efectivo o tarjeta.')
        tendered=money(data.get('tendered',0)) if method=='cash' else amount
        if tendered<amount:raise ValueError('El efectivo recibido no cubre el importe.')
        now=datetime.now().isoformat(timespec='seconds')
        c.execute('INSERT INTO payments(order_id,amount,method,tendered,change_due,created,user_id,request_id) VALUES(?,?,?,?,?,?,?,?)',
                  (order['id'],amount,method,tendered,tendered-amount,now,actor,data.get('request_id')))
        paid=order['paid']+amount
        if paid==order['total']:
            methods={r[0] for r in c.execute('SELECT method FROM payments WHERE order_id=?',(order['id'],))}
            c.execute("UPDATE orders SET status='paid',paid_at=?,payment=?,total=?,tendered=?,change_due=? WHERE id=?",(now,method if len(methods)==1 else 'mixed',order['total'],tendered,tendered-amount,order['id']))
            settings=c.execute("SELECT value FROM settings WHERE key='global_config'").fetchone()
            selected=json.loads(settings['value']).get('pos_series',{}).get('Fra. Simp.') if settings else None
            if selected:
                series=c.execute("SELECT id,name,next_number FROM document_series WHERE id=? AND type='Fra. Simp.' AND active=1",(selected,)).fetchone()
                if series:
                    c.execute('UPDATE orders SET series_id=?,series_number=?,series_name=? WHERE id=?',
                              (series['id'],series['next_number'],series['name'],order['id']))
                    c.execute('UPDATE document_series SET next_number=next_number+1 WHERE id=?',(series['id'],))
        return {'receipt':self.order(c,order['id']),'paid_now':amount,'change':tendered-amount}

    def mutate(self,action,data,actor=None):
        extended={'pay','split_pay','march','course','note','move','cancel_line','user','user_disable'}
        if action not in extended:return super().mutate(action,data,actor)
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            self.audit(c,actor,action,data.get('order_id'))
            if action in ('user','user_disable'):
                from store import title
                operator=c.execute("SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1",(actor,)).fetchone()
                if not operator:raise ValueError('Solo un administrador puede gestionar usuarios.')
                uid=data.get('id')
                current=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone() if uid else None
                if uid and not current:raise ValueError('Usuario no encontrado.')
                role=data.get('role','staff')
                active=0 if action=='user_disable' else 1
                if action=='user_disable' and uid==actor:raise ValueError('No puedes desactivar tu propia sesión.')
                if current and current['role']=='admin' and (not active or role!='admin'):
                    if c.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1 AND id<>?",(uid,)).fetchone()[0]==0:raise ValueError('Debe quedar al menos un administrador activo.')
                if action=='user_disable':c.execute('UPDATE users SET active=0 WHERE id=?',(uid,))
                else:
                    if role not in ('admin','staff'):raise ValueError('Perfil no válido.')
                    name=title(data.get('name'));pin=data.get('pin')
                    hashed=password(pin) if pin else current['pin_hash'] if current else None
                    if not hashed:raise ValueError('Indica un PIN para el nuevo usuario.')
                    if current:c.execute('UPDATE users SET name=?,pin_hash=?,role=?,active=1 WHERE id=?',(name,hashed,role,uid))
                    else:c.execute('INSERT INTO users(name,pin_hash,role) VALUES(?,?,?)',(name,hashed,role))
                return {'ok':True}
            order=self.require_open(c,data['order_id'])
            if action=='cancel_line':
                if order['paid']:raise ValueError('La cuenta tiene pagos parciales. No se puede cancelar esta línea.')
                line_id=int(data['line_id'])
                target=next((row for row in order['lines'] if row['id']==line_id),None)
                if not target:raise ValueError('La línea no pertenece a esta cuenta.')
                settings=c.execute("SELECT value FROM settings WHERE key='global_config'").fetchone()
                prefs=json.loads(settings['value']).get('preferences',{}) if settings else {}
                reason=str(data.get('reason','')).strip()
                if target['kitchen']!='new' and prefs.get('cancel_reason') and not reason:
                    raise ValueError('Indica el motivo de cancelación.')
                if len(reason)>300:raise ValueError('El motivo es demasiado largo.')
                c.execute('INSERT INTO line_cancellations(order_id,line_id,name,qty,reason,user_id,created) VALUES(?,?,?,?,?,?,?)',
                          (order['id'],line_id,target['name'],target['qty'],reason,actor,datetime.now().isoformat(timespec='seconds')))
                c.execute('DELETE FROM lines WHERE id=?',(line_id,))
                return {'ok':True}
            if action=='pay':
                return self.take_payment(c,order,data,actor,data.get('amount'))
            if action=='split_pay':
                if order['paid']:raise ValueError('Ya hay pagos por importe. Continúa cobrando el saldo pendiente.')
                if int(data['expected_total'])!=order['total']:raise ValueError('La cuenta ha cambiado. Vuelve a abrir Pagos.')
                selected=data.get('lines',[])
                if not selected:raise ValueError('Selecciona los productos que se van a cobrar.')
                wanted={int(r['id']):int(r['qty']) for r in selected}
                if len(wanted)!=len(selected):raise ValueError('Hay líneas repetidas.')
                originals={r['id']:r for r in order['lines']}
                if any(i not in originals or q<1 or q>originals[i]['qty'] for i,q in wanted.items()):raise ValueError('Revisa las cantidades seleccionadas.')
                amount=sum(originals[i]['price']*q for i,q in wanted.items())
                if amount!=int(data['expected_amount']):raise ValueError('El importe seleccionado ha cambiado.')
                if all(wanted.get(r['id'])==r['qty'] for r in order['lines']):return self.take_payment(c,order,data,actor)
                child=c.execute('INSERT INTO orders(created,created_by,parent_id,source_label) VALUES(?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),actor,order['id'],(order['center_name'] or '')+' '+(order['table_name'] or 'VENTA DIRECTA'))).lastrowid
                columns=['product_id','format_id','name','format','price','qty','tax','extras','note','prep','course','kitchen']
                for lid,qty in wanted.items():
                    line=originals[lid]
                    if qty==line['qty']:c.execute('UPDATE lines SET order_id=? WHERE id=?',(child,lid))
                    else:
                        values=[json.dumps(line[k]) if k=='extras' else qty if k=='qty' else line[k] for k in columns]
                        c.execute('INSERT INTO lines(order_id,'+','.join(columns)+') VALUES('+','.join('?' for _ in range(len(columns)+1))+')',[child]+values)
                        c.execute('UPDATE lines SET qty=qty-? WHERE id=?',(qty,lid))
                child_order=self.order(c,child)
                result=self.take_payment(c,child_order,dict(data,expected_total=amount,expected_due=amount),actor)
                result['source_order_id']=order['id']
                return result
            if action=='move':
                target=data.get('table_id')
                if target is None and not data.get('direct'):raise ValueError('Elige una mesa de destino.')
                if target is not None:
                    if not c.execute('SELECT 1 FROM tables WHERE id=?',(target,)).fetchone():raise ValueError('La mesa no existe.')
                    if c.execute("SELECT 1 FROM orders WHERE table_id=? AND status='open' AND id<>?",(target,order['id'])).fetchone():raise ValueError('La mesa destino tiene otra cuenta. Selecciona una mesa libre.')
                c.execute('UPDATE orders SET table_id=? WHERE id=?',(target,order['id']))
                return {'ok':True}
            selected=data.get('line_ids',[])
            if not selected:raise ValueError('Selecciona al menos una línea.')
            existing={r['id']:r for r in order['lines']}
            if len(set(selected))!=len(selected) or any(i not in existing for i in selected):raise ValueError('Las líneas seleccionadas no pertenecen a esta cuenta.')
            for lid in selected:
                if action=='march':
                    c.execute("UPDATE lines SET kitchen='pending' WHERE id=? AND kitchen='new'",(lid,))
                elif action=='course':
                    if data.get('course') not in COURSES:raise ValueError('Orden de preparación no válido.')
                    c.execute('UPDATE lines SET course=? WHERE id=?',(data['course'],lid))
                elif action=='note':
                    c.execute('UPDATE lines SET note=? WHERE id=?',(str(data.get('note',''))[:300],lid))
            return {'ok':True}
