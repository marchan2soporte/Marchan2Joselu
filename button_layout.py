"""Validated, per-POS-profile button placement with optimistic concurrency."""
import json
from datetime import datetime

CATALOG=[
 ('prepare','Preparar','♨','ticket_send'),('march','Marchar','↗','ticket_march'),
 ('course','Orden preparación','1·2·3','ticket_course'),('move','Cambiar mesa','⇄','ticket_move'),
 ('receipt','Ver cuenta','▤','ticket_print'),('payments','Pagos','€','ticket_pay'),
 ('others','Otros','•••',''),('cancel_ticket','Cancelar ticket','×','ticket_void'),
 ('print_ticket','Imprimir ticket','▥','ticket_print'),('cash_income','Ingresos','+€','cash_move'),
 ('cash_expense','Gastos','−€','cash_move'),('cash_withdrawal','Retirar efectivo','↧','cash_move'),
 ('cash_count','Cuadre de caja','≋','cash_view'),('report_x','Informe X','X','cash_view'),
 ('close_shift','Cerrar jornada','Z','cash_close'),('cash_history','Cierres anteriores','◷','cash_view'),
 ('last_receipt','Último ticket','↶','ticket_print'),('open_tickets','Tickets abiertos','☷','ticket_open'),
 ('note','Añadir nota','✎','ticket_note'),('cancel_line','Cancelar línea','⌫','ticket_cancel'),
 ('switch_user','Cambiar usuario','↪','')]
DEFAULT={'right':['prepare','march','course','receipt','payments','others'],
         'others':[r[0] for r in CATALOG if r[0] not in ('prepare','march','course','receipt','payments','others')]}

def initialize(store):
    with store.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS pos_button_layouts(
        profile_id INTEGER PRIMARY KEY REFERENCES pos_profiles(id) ON DELETE CASCADE,
        layout TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,updated TEXT NOT NULL,calculator_enabled INTEGER NOT NULL DEFAULT 1)''')
        c.execute('BEGIN IMMEDIATE')
        if 'calculator_enabled' not in [r['name'] for r in c.execute('PRAGMA table_info(pos_button_layouts)')]:
            c.execute('ALTER TABLE pos_button_layouts ADD COLUMN calculator_enabled INTEGER NOT NULL DEFAULT 1')

def read(store,profile_id=None):
    with store.db() as c:
        if profile_id is None:profile_id=c.execute('SELECT id FROM pos_profiles WHERE active=1').fetchone()[0]
        if not c.execute('SELECT 1 FROM pos_profiles WHERE id=?',(profile_id,)).fetchone():raise ValueError('Punto de venta inexistente.')
        row=c.execute('SELECT * FROM pos_button_layouts WHERE profile_id=?',(profile_id,)).fetchone()
        return dict(profile_id=profile_id,layout=json.loads(row['layout']) if row else {k:list(v) for k,v in DEFAULT.items()},revision=row['revision'] if row else 0,calculator_enabled=bool(row['calculator_enabled']) if row else True,catalog=[dict(id=i,label=l,icon=g,permission=p) for i,l,g,p in CATALOG])

def save(store,data,actor):
    calculator=data.get('calculator_enabled',True)
    if type(calculator) is not bool:raise ValueError('Visibilidad de calculadora no válida.')
    layout=data.get('layout');all_ids={r[0] for r in CATALOG}
    if not isinstance(layout,dict) or set(layout)!=set(DEFAULT):raise ValueError('Distribución de botones no válida.')
    if any(not isinstance(layout[k],list) or any(not isinstance(i,str) for i in layout[k]) for k in DEFAULT):raise ValueError('Botones no válidos.')
    ids=layout['right']+layout['others']
    if len(ids)!=len(set(ids)) or set(ids)!=all_ids:raise ValueError('Cada botón debe aparecer una sola vez.')
    if not {'others','payments'}<=set(layout['right']):raise ValueError('Otros y Pagos deben permanecer en la zona principal.')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute('SELECT 1 FROM users WHERE id=? AND role=\'admin\' AND active=1',(actor,)).fetchone():raise PermissionError('Solo Administración puede organizar los botones.')
        profile_id=data.get('profile_id')
        if not c.execute('SELECT 1 FROM pos_profiles WHERE id=?',(profile_id,)).fetchone():raise ValueError('Punto de venta inexistente.')
        row=c.execute('SELECT revision FROM pos_button_layouts WHERE profile_id=?',(profile_id,)).fetchone()
        revision=row[0] if row else 0
        if type(data.get('revision')) is not int or revision!=data['revision']:raise ValueError('La distribución ha cambiado. Vuelve a cargarla antes de guardar.')
        c.execute('INSERT INTO pos_button_layouts(profile_id,layout,revision,updated,calculator_enabled) VALUES(?,?,?,?,?) ON CONFLICT(profile_id) DO UPDATE SET layout=excluded.layout,revision=excluded.revision,updated=excluded.updated,calculator_enabled=excluded.calculator_enabled',(profile_id,json.dumps(layout),revision+1,datetime.now().isoformat(timespec='seconds'),int(calculator)))
        store.audit(c,actor,'button_layout_save')
    return {'ok':True,'revision':revision+1}
