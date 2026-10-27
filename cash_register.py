"""Operational cash sessions. Money is integer cents; closed Z snapshots are immutable."""
import json
from datetime import datetime,date

DENOMINATIONS=(50000,20000,10000,5000,2000,1000,500,200,100,50,20,10,5,2,1)

def initialize(store):
    with store.db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS cash_sessions(
            id INTEGER PRIMARY KEY,business_day TEXT NOT NULL,opened TEXT NOT NULL,
            opened_by INTEGER REFERENCES users(id),opening INTEGER NOT NULL CHECK(opening>=0),
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
            revision INTEGER NOT NULL DEFAULT 0,closed TEXT,closed_by INTEGER REFERENCES users(id),
            snapshot TEXT,open_request TEXT NOT NULL UNIQUE,close_request TEXT UNIQUE);
        CREATE UNIQUE INDEX IF NOT EXISTS one_open_cash_session ON cash_sessions(status) WHERE status='open';
        CREATE TABLE IF NOT EXISTS cash_movements(
            id INTEGER PRIMARY KEY,session_id INTEGER NOT NULL REFERENCES cash_sessions(id),
            kind TEXT NOT NULL CHECK(kind IN ('income','expense','withdrawal')),
            amount INTEGER NOT NULL CHECK(amount>0),reason TEXT NOT NULL,
            created TEXT NOT NULL,user_id INTEGER REFERENCES users(id),request_id TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS ticket_cancellations(
            id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
            session_id INTEGER NOT NULL REFERENCES cash_sessions(id),total INTEGER NOT NULL,
            reason TEXT NOT NULL,created TEXT NOT NULL,user_id INTEGER REFERENCES users(id),snapshot TEXT NOT NULL);
        ''')
        c.execute('BEGIN IMMEDIATE')
        for table in ('orders','payments'):
            if 'cash_session_id' not in [r['name'] for r in c.execute('PRAGMA table_info('+table+')')]:
                c.execute('ALTER TABLE '+table+' ADD COLUMN cash_session_id INTEGER REFERENCES cash_sessions(id)')
        c.execute('CREATE INDEX IF NOT EXISTS payments_cash_session ON payments(cash_session_id)')


def require_open(c):
    row=c.execute("SELECT * FROM cash_sessions WHERE status='open'").fetchone()
    if not row:raise ValueError('Abre la jornada e indica el dinero inicial antes de vender.')
    return dict(row)


def status(store):
    with store.db() as c:
        row=c.execute("SELECT id,business_day,opened,status FROM cash_sessions WHERE status='open'").fetchone()
        return dict(row) if row else None


def _actor(c,actor,permission):
    import permissions
    if permission not in permissions.rights(c,actor):raise PermissionError('Tu perfil no permite esta operación de caja.')


def _request(data):
    key=data.get('request_id')
    if not isinstance(key,str) or not 8<=len(key)<=120:raise ValueError('Falta el identificador de operación. Vuelve a abrir la pantalla.')
    return key


def _session(c,identifier=None):
    row=c.execute('SELECT * FROM cash_sessions WHERE id=?',(identifier,)).fetchone() if identifier else c.execute("SELECT * FROM cash_sessions WHERE status='open'").fetchone()
    if not row:raise ValueError('No hay una jornada para consultar.')
    return dict(row)


def _snapshot(c,session):
    sid=session['id']
    pay=[dict(r) for r in c.execute("SELECT p.*,COALESCE(u.name,'ANTERIOR') user_name FROM payments p LEFT JOIN users u ON u.id=p.user_id WHERE p.cash_session_id=? ORDER BY p.id",(sid,))]
    moves=[dict(r) for r in c.execute("SELECT m.*,COALESCE(u.name,'ANTERIOR') user_name FROM cash_movements m LEFT JOIN users u ON u.id=m.user_id WHERE m.session_id=? ORDER BY m.id",(sid,))]
    sales=c.execute("SELECT COUNT(*) tickets,COALESCE(SUM(total),0) total FROM orders WHERE cash_session_id=? AND status='paid'",(sid,)).fetchone()
    cash=sum(p['amount'] for p in pay if p['method']=='cash')
    cash_tips=sum(p['tip'] for p in pay if p['method']=='cash')
    card=sum(p['amount'] for p in pay if p['method']=='card')
    card_tips=sum(p['tip'] for p in pay if p['method']=='card')
    incoming=sum(m['amount'] for m in moves if m['kind']=='income')
    expenses=sum(m['amount'] for m in moves if m['kind']=='expense')
    withdrawn=sum(m['amount'] for m in moves if m['kind']=='withdrawal')
    cancellations=[dict(r) for r in c.execute('SELECT order_id,total,reason,created FROM ticket_cancellations WHERE session_id=?',(sid,))]
    users={}
    for p in pay:
        key=p['user_name'];users[key]=users.get(key,0)+p['amount']+p['tip']
    opened_user=c.execute('SELECT name FROM users WHERE id=?',(session['opened_by'],)).fetchone()
    pending=c.execute("SELECT COUNT(*) FROM orders WHERE status='open' AND EXISTS(SELECT 1 FROM lines WHERE order_id=orders.id)").fetchone()[0]
    from pos_profiles import active_options
    enabled=active_options(c)['z_options'];sections=[]
    groups=[('sales_by_center','Ventas por centro',"SELECT COALESCE(ce.name,'VENTA DIRECTA'),SUM(o.total) FROM orders o LEFT JOIN tables t ON t.id=o.table_id LEFT JOIN centers ce ON ce.id=t.center_id WHERE o.status='paid' AND o.cash_session_id=? GROUP BY ce.id"),
            ('sales_by_user','Ventas por usuario',"SELECT COALESCE(u.name,'ANTERIOR'),SUM(o.total) FROM orders o LEFT JOIN users u ON u.id=o.created_by WHERE o.status='paid' AND o.cash_session_id=? GROUP BY o.created_by"),
            ('sales_by_family','Ventas por familia',"SELECT COALESCE(ca.parent,'SIN FAMILIA'),SUM(l.qty*l.price) FROM lines l JOIN orders o ON o.id=l.order_id LEFT JOIN products p ON p.id=l.product_id LEFT JOIN categories ca ON ca.id=p.category_id WHERE o.status='paid' AND o.cash_session_id=? GROUP BY ca.parent")]
    for flag,label,query in groups:
        if enabled[flag]:sections.append(dict(title=label,rows=[list(r) for r in c.execute(query,(sid,))]))
    if enabled['payments_by_method']:sections.append(dict(title='Cobros por forma de pago (con propinas)',rows=[['EFECTIVO',cash+cash_tips],['TARJETA',card+card_tips]]))
    if enabled['tips']:sections.append(dict(title='Propinas por método',rows=[['EFECTIVO',cash_tips],['TARJETA',card_tips]]))
    if enabled['cancellations']:sections.append(dict(title='Cuentas canceladas',rows=[['#'+str(r['order_id'])+' · '+r['reason'],r['total']] for r in cancellations]))
    if enabled['pending']:
        rows=[]
        for row in c.execute("SELECT o.id,COALESCE(t.name,'VENTA DIRECTA') location FROM orders o LEFT JOIN tables t ON t.id=o.table_id WHERE status='open' AND EXISTS(SELECT 1 FROM lines WHERE order_id=o.id)"):
            total=c.execute('SELECT COALESCE(SUM(qty*price),0) FROM lines WHERE order_id=?',(row['id'],)).fetchone()[0]
            paid=c.execute('SELECT COALESCE(SUM(amount),0) FROM payments WHERE order_id=?',(row['id'],)).fetchone()[0]
            rows.append([row['location']+' #'+str(row['id']),total-paid])
        sections.append(dict(title='Cuentas abiertas ahora',rows=rows))
    return dict(session_id=sid,business_day=session['business_day'],opened=session['opened'],
        sections=sections,opening=session['opening'],opened_by_name=opened_user[0] if opened_user else 'ANTERIOR',pending_tickets=pending,revision=session['revision'],status=session['status'],
        sales=sales['total'],tickets=sales['tickets'],cash_sales=cash,cash_tips=cash_tips,
        card_sales=card,card_tips=card_tips,collected=cash+card,tips=cash_tips+card_tips,
        income=incoming,expenses=expenses,withdrawals=withdrawn,
        expected_cash=session['opening']+cash+cash_tips+incoming-expenses-withdrawn,
        expected_card=card+card_tips,movements=moves,payments_by_user=[[k,v] for k,v in users.items()],
        cancellations=cancellations,generated=datetime.now().isoformat(timespec='seconds'),
        note='Control operativo interno. Los ingresos y salidas de caja no se suman a las ventas. No es un documento fiscal.')


def report(store,identifier=None,kind='x'):
    with store.db() as c:
        c.execute('BEGIN')
        session=_session(c,identifier)
        if session['status']=='closed':
            result=json.loads(session['snapshot']);result['kind']='Z';return result
        if kind.lower()=='z':raise ValueError('La jornada sigue abierta. Consulta X o cierra la jornada para generar Z.')
        result=_snapshot(c,session);result['kind']='X';return result


def history(store):
    with store.db() as c:
        return [dict(r) for r in c.execute('SELECT id,business_day,opened,closed,status,opening FROM cash_sessions ORDER BY id DESC LIMIT 100')]


def mutate(store,action,data,actor):
    from store import money
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        _actor(c,actor,{'cash_open':'cash_open','cash_move':'cash_move','cash_close':'cash_close'}[action])
        request=_request(data)
        if action=='cash_open':
            old=c.execute('SELECT id FROM cash_sessions WHERE open_request=?',(request,)).fetchone()
            if old:return {'session_id':old['id'],'duplicate':True}
            if c.execute("SELECT 1 FROM cash_sessions WHERE status='open'").fetchone():raise ValueError('Ya hay una jornada abierta. Actualiza la pantalla.')
            if 'opening' not in data:raise ValueError('Indica el dinero con el que empiezas; puede ser 0.')
            amount=money(data['opening'])
            sid=c.execute('INSERT INTO cash_sessions(business_day,opened,opened_by,opening,open_request) VALUES(?,?,?,?,?)',(date.today().isoformat(),datetime.now().isoformat(timespec='seconds'),actor,amount,request)).lastrowid
            store.audit(c,actor,'cash_open');return {'session_id':sid}
        if action=='cash_close':
            old=c.execute('SELECT snapshot FROM cash_sessions WHERE close_request=?',(request,)).fetchone()
            if old:return {'report':json.loads(old['snapshot']),'duplicate':True}
        else:
            old=c.execute('SELECT id FROM cash_movements WHERE request_id=?',(request,)).fetchone()
            if old:return {'movement_id':old['id'],'duplicate':True}
        session=require_open(c)
        if type(data.get('session_id')) is not int or data['session_id']!=session['id']:raise ValueError('La jornada ha cambiado. Abre de nuevo la pantalla de caja.')
        before=_snapshot(c,session)
        if action=='cash_move':
            kind=data.get('kind');reason=str(data.get('reason','')).strip()
            if kind not in ('income','expense','withdrawal'):raise ValueError('Movimiento de caja no válido.')
            if not 3<=len(reason)<=300:raise ValueError('Indica un concepto entre 3 y 300 caracteres.')
            amount=money(data.get('amount'))
            if amount<=0:raise ValueError('El importe debe ser mayor que cero.')
            if kind!='income' and amount>before['expected_cash']:raise ValueError('La salida supera el efectivo teórico de caja.')
            mid=c.execute('INSERT INTO cash_movements(session_id,kind,amount,reason,created,user_id,request_id) VALUES(?,?,?,?,?,?,?)',(session['id'],kind,amount,reason,datetime.now().isoformat(timespec='seconds'),actor,request)).lastrowid
            c.execute('UPDATE cash_sessions SET revision=revision+1 WHERE id=?',(session['id'],))
            store.audit(c,actor,'cash_'+kind);return {'movement_id':mid}
        if type(data.get('expected_revision')) is not int or data['expected_revision']!=session['revision']:raise ValueError('La caja ha cambiado durante el recuento. Actualiza y revisa los importes.')
        pending=c.execute("SELECT COUNT(*) FROM orders o WHERE status='open' AND (EXISTS(SELECT 1 FROM lines WHERE order_id=o.id) OR EXISTS(SELECT 1 FROM payments WHERE order_id=o.id))").fetchone()[0]
        if pending:raise ValueError('Hay '+str(pending)+' cuentas abiertas con productos o pagos. Cóbralas o cancélalas antes de cerrar.')
        if 'counted_cash' not in data:raise ValueError('Indica el efectivo contado.')
        counted=money(data['counted_cash']);declared_card=money(data['counted_card']) if str(data.get('counted_card','')).strip() else None
        denominations=data.get('denominations')
        if denominations is not None:
            if not isinstance(denominations,dict):raise ValueError('Recuento de monedas y billetes no válido.')
            total=0
            for key,qty in denominations.items():
                if not str(key).isdigit() or int(key) not in DENOMINATIONS or type(qty) is not int or not 0<=qty<=100000:raise ValueError('Revisa las unidades de monedas y billetes.')
                total+=int(key)*qty
            if total!=counted:raise ValueError('El recuento de monedas y billetes no coincide con el efectivo declarado.')
        difference=counted-before['expected_cash'];card_difference=None if declared_card is None else declared_card-before['expected_card']
        reason=str(data.get('reason','')).strip()
        if len(reason)>300 or ((difference or card_difference) and len(reason)<3):raise ValueError('Explica el descuadre antes de cerrar la jornada.')
        now=datetime.now().isoformat(timespec='seconds')
        closed_user=c.execute('SELECT name FROM users WHERE id=?',(actor,)).fetchone()
        before.update(kind='Z',status='closed',closed=now,closed_by=actor,closed_by_name=closed_user[0] if closed_user else 'ANTERIOR',
            counted_cash=counted,cash_difference=difference,counted_card=declared_card,
            card_difference=card_difference,denominations=denominations,reason=reason,z_number=f"Z-{session['id']:06d}")
        c.execute("UPDATE cash_sessions SET status='closed',closed=?,closed_by=?,snapshot=?,close_request=? WHERE id=?",(now,actor,json.dumps(before,ensure_ascii=False),request,session['id']))
        # Empty, unpaid accounts can safely release their tables at closing.
        c.execute("UPDATE orders SET status='void' WHERE status='open' AND NOT EXISTS(SELECT 1 FROM lines WHERE order_id=orders.id) AND NOT EXISTS(SELECT 1 FROM payments WHERE order_id=orders.id)")
        store.audit(c,actor,'cash_close');return {'report':before}


def cancel_ticket(store,c,order,data,actor):
    session=require_open(c)
    _actor(c,actor,'ticket_void')
    if order['payments']:raise ValueError('La cuenta tiene pagos. No se puede cancelar; necesita una devolución.')
    if any(l['kitchen']!='new' for l in order['lines']):_actor(c,actor,'ticket_cancel_prepared')
    reason=str(data.get('reason','')).strip()
    if not 3<=len(reason)<=300:raise ValueError('Indica un motivo de cancelación entre 3 y 300 caracteres.')
    c.execute('INSERT INTO ticket_cancellations(order_id,session_id,total,reason,created,user_id,snapshot) VALUES(?,?,?,?,?,?,?)',(order['id'],session['id'],order['total'],reason,datetime.now().isoformat(timespec='seconds'),actor,json.dumps(order,ensure_ascii=False)))
    c.execute("UPDATE orders SET status='void',total=? WHERE id=?",(order['total'],order['id']))
    c.execute("UPDATE lines SET kitchen='cancelled' WHERE order_id=?",(order['id'],))
    return {'ok':True,'order_id':order['id']}


def text_report(r):
    eur=lambda n:f'{n/100:.2f} EUR'
    lines=['MARCHAN2 / CAJA',('CIERRE '+r['z_number']) if r['kind']=='Z' else 'INFORME X / JORNADA ABIERTA',
        'Jornada '+str(r['session_id'])+' / '+r['business_day'],'Inicio: '+r['opened']]
    lines.append('Abre: '+r.get('opened_by_name','ANTERIOR'))
    if r.get('closed'):lines.extend(['Cierre: '+r['closed'],'Cierra: '+r.get('closed_by_name','ANTERIOR')])
    for label,key in [('Fondo inicial','opening'),('Ventas cerradas','sales'),('Cobros efectivo','cash_sales'),('Propinas efectivo','cash_tips'),('Cobros tarjeta','card_sales'),('Propinas tarjeta','card_tips'),('Ingresos caja','income'),('Gastos caja','expenses'),('Retiradas caja','withdrawals'),('Efectivo teorico','expected_cash')]:lines.append(label+': '+eur(r[key]))
    if r['kind']=='Z':
        lines.extend(['Efectivo contado: '+eur(r['counted_cash']),'Diferencia efectivo: '+eur(r['cash_difference'])])
        if r['counted_card'] is not None:lines.extend(['Tarjeta declarada: '+eur(r['counted_card']),'Diferencia tarjeta: '+eur(r['card_difference'])])
        if r['reason']:lines.append('Observacion: '+r['reason'])
    lines.extend(['MOVIMIENTOS']+[m['created']+' '+m['kind']+' '+eur(m['amount'])+' '+m['reason'] for m in r['movements']])
    lines.extend(['COBROS POR USUARIO']+[name+': '+eur(amount) for name,amount in r['payments_by_user']])
    for section in r.get('sections',[]):
        lines.append(section['title'])
        lines.extend(label+': '+eur(value) for label,value in section['rows'])
    lines.extend(['Cuentas canceladas: '+str(len(r['cancellations'])),r['note']]);return '\n'.join(lines)


def analytics_report(store,name,start,end):
    from analytics import bounds
    a,b=bounds(start,end)
    with store.db() as c:
        c.execute('BEGIN')
        if name=='Movimientos de caja':
            columns=[['Fecha','text'],['Jornada','number'],['Tipo','text'],['Concepto','text'],['Usuario','text'],['Efectivo','money']]
            rows=[[r['created'],r['session_id'],r['kind'],r['reason'],r['user_name'],r['amount'] if r['kind']=='income' else -r['amount']] for r in c.execute("SELECT m.*,COALESCE(u.name,'ANTERIOR') user_name FROM cash_movements m LEFT JOIN users u ON u.id=m.user_id WHERE m.created>=? AND m.created<? ORDER BY m.id",(a,b))]
            note='Movimientos manuales por fecha de registro. Los gastos y retiradas se muestran con signo negativo; no son ventas.'
        else:
            columns=[['Z','text'],['Día de apertura','text'],['Cierre','text'],['Ventas cerradas','money'],['Cobros','money'],['Teórico efectivo','money'],['Contado efectivo','money'],['Diferencia','money']]
            rows=[]
            for row in c.execute("SELECT snapshot FROM cash_sessions WHERE status='closed' AND closed>=? AND closed<? ORDER BY id",(a,b)):
                r=json.loads(row['snapshot']);rows.append([r['z_number'],r['business_day'],r['closed'],r['sales'],r['collected'],r['expected_cash'],r['counted_cash'],r['cash_difference']])
            note='Cierres operativos por fecha de cierre. Los importes proceden de los Z guardados, sin recalcular. No es un documento fiscal.'
    return dict(id=name,name=name,available=True,columns=columns,rows=rows,note=note,start=start,end=end)
