"""Separate local TPV/admin entry points with shared SQLite and authenticated roles."""
import argparse
from urllib.parse import urlparse,parse_qs
from analytics import dashboard,report,report_catalog
import inventory
import company
import series
import global_config
import ticket_templates
import daily_close
import pos_profiles
import z_report
import peripherals
import printing
import permissions
import cash_register
import button_layout
import line_pricing
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import webbrowser
from store import Store

TPV_ACTIONS={'open','add','quantity','send','march','course','note','move','pay','split_pay','ready','close_empty','cancel_line','cancel_ticket'}
ADMIN_ACTIONS={'product','category','center','user','user_disable'}


def main(default_app='tpv'):
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--data')
    parser.add_argument('--app',choices=['tpv','admin'],default=default_app)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    folder=Path(args.data) if args.data else Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Marchan2'
    folder.mkdir(parents=True,exist_ok=True)
    store=Store(folder/'marchan2.db')
    inventory.initialize(store)
    series.initialize(store)
    ticket_templates.initialize(store)
    pos_profiles.initialize(store)
    assets=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'web'
    token=secrets.token_urlsafe(32)
    sessions={};attempts={};guard=threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*values):pass

        def reply(self,status,value,kind='application/json; charset=utf-8'):
            body=json.dumps(value,ensure_ascii=False).encode() if not isinstance(value,bytes) else value
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            self.end_headers();self.wfile.write(body)

        def allowed(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'

        def user(self):
            key=self.headers.get('X-Marchan2-Session')
            with guard:session=sessions.get(key)
            if not session or time.monotonic()>session['expiry']:return None
            with store.db() as c:u=c.execute('SELECT * FROM users WHERE id=? AND active=1',(session['id'],)).fetchone()
            if not u or u['pin_hash']!=session['signature'] or (args.app=='admin' and u['role']!='admin'):return None
            return {k:u[k] for k in ('id','name','role','active','profile_id')}

        def do_GET(self):
            if not self.allowed():return self.reply(403,{'error':'Acceso local requerido.'})
            try:
                path=self.path.split('?')[0]
                if path=='/':
                    html=(assets/'index.html').read_text(encoding='utf8').replace('__TOKEN__',token).replace('__MODE__',args.app).replace('__APPNAME__','TPV' if args.app=='tpv' else 'Administración')
                    return self.reply(200,html.encode(),'text/html; charset=utf-8')
                if path=='/logo.png':return self.reply(200,(assets/'logo.png').read_bytes(),'image/png')
                if path in ('/app.js','/receipt.js','/style.css','/global-config.js','/printing-admin.js','/user-profiles.js','/button-editor.js','/calculator.js','/cash-ui.js',f'/{args.app}.js',f'/{args.app}-extras.js'):
                    return self.reply(200,(assets/path[1:]).read_bytes(),'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
                if path=='/api/access':
                    users=store.users()
                    if args.app=='admin':users=[u for u in users if u['role']=='admin']
                    return self.reply(200,dict(app=args.app,users=users,user=self.user(),version='0.22'))
                user=self.user()
                if not user:return self.reply(401,{'error':'Selecciona tu usuario e introduce el PIN.'})
                if path=='/api/company':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,company.read(store))
                if path=='/api/series':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,series.list_all(store))
                if path=='/api/global_config':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,global_config.read(store))
                if path=='/api/ticket_templates':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,ticket_templates.list_all(store))
                if path=='/api/pos_profiles':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,pos_profiles.list_all(store))
                if path=='/api/user_profiles':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,permissions.list_all(store))
                if path=='/api/inventory':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,inventory.state(store))
                if path.startswith('/api/analytics'):
                    if args.app!='admin':return self.reply(403,{'error':'Acceso exclusivo de Administración.'})
                    q=parse_qs(urlparse(self.path).query)
                    if path=='/api/analytics/catalog':return self.reply(200,report_catalog())
                    if path=='/api/analytics/dashboard':return self.reply(200,dashboard(store))
                    if path=='/api/analytics/report':return self.reply(200,report(store,q.get('id',[''])[0],q.get('start',[''])[0],q.get('end',[''])[0]))
                    return self.reply(404,{'error':'Informe no encontrado.'})
                if path=='/api/button_layout':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    profile_id=int(parse_qs(urlparse(self.path).query).get('profile_id',[0])[0]) or None
                    return self.reply(200,button_layout.read(store,profile_id))
                if path in ('/api/cash','/api/cash/history'):
                    if args.app=='tpv':permissions.require(store,user['id'],'cash_view')
                    if path.endswith('/history'):return self.reply(200,cash_register.history(store))
                    q=parse_qs(urlparse(self.path).query)
                    return self.reply(200,cash_register.report(store,int(q.get('session_id',[0])[0]) or None,q.get('kind',['x'])[0]))
                if path=='/api/state':
                    data=store.state();data['user']=user;data['pos_profile']=pos_profiles.active(store)
                    with store.db() as c:data['permissions']=permissions.rights(c,user['id'])
                    data['cash_session']=cash_register.status(store)
                    data['button_layout']=button_layout.read(store)
                    data['ticket_template']=ticket_templates.current(store)
                    profile_template=data['pos_profile']['options']['receipt_template_id'] if data['pos_profile'] else None
                    if profile_template:
                        data['ticket_template']=next((t for t in ticket_templates.list_all(store) if t['id']==profile_template),data['ticket_template'])
                    data['company']=company.read(store)
                    data['global_config']=global_config.read(store)
                    command_id=data['global_config']['preferences']['command_template']
                    data['command_template']=next((t for t in ticket_templates.list_all(store) if str(t['id'])==str(command_id)),None)
                    if args.app=='tpv' and data['global_config']['preferences']['stock_warning']:
                        data['stock_warnings']=[{'name':i['name'],'unit':i['unit'],'balance':i['balance'],'minimum':i['minimum']}
                            for i in inventory.state(store)['items'] if i['minimum'] and i['balance']<i['minimum']]
                    if args.app=='tpv':
                        if data['pos_profile']['options']['show_last_sale']:
                            data['last_sale']=data['history'][0] if data['history'] else None
                        for key in ('stats','history','payment_history'):data.pop(key,None)
                    else:
                        data['users']=store.users(False)
                        data['user_profiles']=permissions.list_all(store)['profiles']
                    return self.reply(200,data)
                if path=='/api/preparation' and args.app=='tpv':
                    permissions.require(store,user['id'],'kitchen_view');return self.reply(200,store.preparation())
                if path=='/api/daily_close' and args.app=='tpv':
                    permissions.require(store,user['id'],'daily_view');return self.reply(200,daily_close.preview(store))
                if path=='/api/z_report' and args.app=='tpv':
                    permissions.require(store,user['id'],'z_view');return self.reply(200,z_report.preview(store))
                if path=='/api/peripheral_ports' and args.app=='admin':return self.reply(200,peripherals.serial_ports())
                if path=='/api/printing':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    profile_id=int(parse_qs(urlparse(self.path).query).get('profile_id',[0])[0])
                    return self.reply(200,printing.configuration(store,profile_id))
                if path=='/api/print_jobs':
                    if args.app=='tpv':permissions.require(store,user['id'],'print_retry')
                    return self.reply(200,printing.jobs(store))
                if path=='/api/last_receipt':
                    if args.app!='tpv':return self.reply(403,{'error':'Solo TPV.'})
                    permissions.require(store,user['id'],'ticket_print')
                    with store.db() as c:last=c.execute("SELECT id FROM orders WHERE status='paid' ORDER BY paid_at DESC,id DESC LIMIT 1").fetchone()
                    if not last:raise ValueError('Todavía no hay cuentas cobradas.')
                    return self.reply(200,store.receipt(last['id']))
                if path.startswith('/api/receipt/'):
                    if args.app=='tpv':permissions.require(store,user['id'],'ticket_print')
                    return self.reply(200,store.receipt(int(path.rsplit('/',1)[1])))
                self.reply(404,{'error':'No encontrado.'})
            except PermissionError as error:self.reply(403,{'error':str(error)})
            except (ValueError,KeyError) as error:self.reply(400,{'error':str(error)})
            except Exception:self.reply(500,{'error':'No se pudo leer la información.'})

        def do_POST(self):
            if not self.allowed() or self.headers.get('X-Marchan2-Token')!=token:return self.reply(403,{'error':'Vuelve a abrir Marchan2 para continuar.'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<1 or size>1_000_000:raise ValueError('Petición demasiado grande o vacía.')
                data=json.loads(self.rfile.read(size));action=self.path.removeprefix('/api/')
                if action=='login':
                    uid=int(data['user_id'])
                    with guard:
                        failures,until=attempts.get(uid,(0,0))
                        if time.monotonic()<until:return self.reply(429,{'error':'Demasiados intentos. Espera 30 segundos.'})
                        try:
                            user=store.authenticate(uid,data.get('pin',''))
                            if args.app=='admin' and user['role']!='admin':raise ValueError('Este usuario no tiene acceso a Administración.')
                        except ValueError:
                            failures+=1;attempts[uid]=(failures,time.monotonic()+30 if failures>=5 else 0)
                            raise
                        attempts.pop(uid,None)
                        with store.db() as c:signature=c.execute('SELECT pin_hash FROM users WHERE id=?',(uid,)).fetchone()[0]
                        key=secrets.token_urlsafe(32);sessions[key]={'id':uid,'signature':signature,'expiry':time.monotonic()+12*3600}
                    return self.reply(200,{'session':key,'user':user})
                if action=='logout':
                    with guard:sessions.pop(self.headers.get('X-Marchan2-Session'),None)
                    return self.reply(200,{'ok':True})
                user=self.user()
                if not user:return self.reply(401,{'error':'La sesión ha terminado. Entra con tu usuario.'})
                if action in ('line_discount','line_weight'):
                    if args.app!='tpv':return self.reply(403,{'error':'Los cambios de línea se realizan en el TPV.'})
                    return self.reply(200,line_pricing.mutate(store,action,data,user['id']))
                if action=='button_layout_save':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,button_layout.save(store,data,user['id']))
                if action in ('cash_open','cash_move','cash_close'):
                    if args.app!='tpv':return self.reply(403,{'error':'Las operaciones de caja se realizan desde el TPV.'})
                    return self.reply(200,cash_register.mutate(store,action,data,user['id']))
                if action=='company':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,company.save(store,data))
                if action in ('user_profile_save','user_profile_delete'):
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,permissions.save(store,data) if action=='user_profile_save' else permissions.delete(store,data))
                if action in ('series_save','series_delete'):
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,series.save(store,data) if action=='series_save' else series.delete(store,data))
                if action=='global_config':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,global_config.save(store,data))
                if action in ('ticket_template_save','ticket_template_delete'):
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,ticket_templates.save(store,data) if action=='ticket_template_save' else ticket_templates.delete(store,data))
                if action in ('pos_profile_save','pos_profile_activate','pos_profile_delete'):
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    handler={'pos_profile_save':pos_profiles.save,'pos_profile_activate':pos_profiles.activate,'pos_profile_delete':pos_profiles.delete}[action]
                    return self.reply(200,handler(store,data))
                if action in ('printer_probe','scale_probe'):
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,peripherals.printer_probe(store) if action=='printer_probe' else peripherals.scale_probe(store))
                if action in ('printing_document_save','printing_kitchen_save','printing_kitchen_delete','printing_test'):
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    handlers={'printing_document_save':printing.save_document,
                              'printing_kitchen_save':printing.save_kitchen,
                              'printing_kitchen_delete':printing.delete_kitchen,
                              'printing_test':lambda s,d:printing.test_print(s,d.get('printer_name'),
                                  d.get('backend','auto'),d.get('raw_columns',48),
                                  d.get('feed_lines',4),d.get('cut_mode','none'))}
                    result=handlers[action](store,data)
                    if result.get('job_id'):
                        result['print_warnings']=printing.dispatch(store,[result['job_id']])
                    return self.reply(200,result)
                if action=='print_document':
                    if args.app!='tpv':return self.reply(403,{'error':'Solo TPV.'})
                    kind=data.get('kind')
                    permissions.require(store,user['id'],'ticket_print' if kind=='receipt' else 'z_print')
                    if kind=='receipt':
                        result=printing.enqueue_receipt(store,int(data['order_id']))
                    elif kind in ('cash_x','cash_z'):
                        permissions.require(store,user['id'],'cash_view')
                        report=cash_register.report(store,int(data.get('session_id',0)) or None,'z' if kind=='cash_z' else 'x')
                        result=printing.enqueue_text(store,'z_report',cash_register.text_report(report))
                    elif kind=='z_report':
                        report=z_report.preview(store)
                        lines=['MARCHAN2 · INFORME Z DE PRUEBA',report['day'],
                               f"Ventas: {report['sales']/100:.2f} EUR",
                               f"Cobros: {report['payments']/100:.2f} EUR"]
                        for section in report['sections']:
                            lines.append(section['title'])
                            for row in section['rows']:
                                last = row[-1]
                                if section['columns'][-1] in ('Importe','Pendiente'):
                                    last = f'{last/100:.2f} EUR'
                                lines.append('  '.join(map(str,[*row[:-1],last])))
                        lines.append(report['note'])
                        result=printing.enqueue_text(store,'z_report','\n'.join(lines))
                    else:raise ValueError('Documento no disponible para impresión directa.')
                    if result.get('job_id'):
                        result['print_warnings']=printing.dispatch(store,[result['job_id']])
                    return self.reply(200,result)
                if action=='print_retry':
                    if args.app=='tpv':permissions.require(store,user['id'],'print_retry')
                    result={'print_warnings':printing.dispatch(store,[int(data['job_id'])])}
                    return self.reply(200,result)
                if action=='shutdown':
                    self.reply(200,{'ok':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
                if action in ('supplier','stock_item','stock_move'):
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,inventory.mutate(store,action,data,user['id']))
                allowed=TPV_ACTIONS if args.app=='tpv' else ADMIN_ACTIONS
                if action not in allowed:return self.reply(403,{'error':'Esta operación pertenece a la otra aplicación.'})
                if args.app=='tpv':
                    needed=permissions.ACTION.get(action)
                    if needed:permissions.require(store,user['id'],needed)
                    if action=='cancel_line':
                        with store.db() as c:
                            row=c.execute('SELECT kitchen FROM lines WHERE id=?',(data.get('line_id'),)).fetchone()
                        if row and row['kitchen']!='new':permissions.require(store,user['id'],'ticket_cancel_prepared')
                    if action=='cancel_ticket':
                        with store.db() as c:
                            if c.execute("SELECT 1 FROM lines WHERE order_id=? AND kitchen<>'new'",(data.get('order_id'),)).fetchone():permissions.require(store,user['id'],'ticket_cancel_prepared')
                result=store.mutate(action,data,actor=user['id'])
                if args.app=='tpv':
                    if action in ('pay','split_pay') and result.get('receipt',{}).get('status')=='paid':
                        printing.enqueue_receipt(store,result['receipt']['id'],automatic=True)
                    result['print_warnings']=printing.dispatch(store)
                self.reply(200,result)
            except sqlite3.IntegrityError:self.reply(409,{'error':'La operación ya está registrada o ese nombre está en uso. Actualiza la pantalla.'})
            except PermissionError as error:self.reply(403,{'error':str(error)})
            except (ValueError,KeyError,TypeError) as error:self.reply(400,{'error':str(error)})
            except Exception:self.reply(500,{'error':'No se pudo guardar. La operación se ha deshecho.'})

    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    url=f'http://127.0.0.1:{server.server_port}'
    (folder/f'session-{args.app}.json').write_text(json.dumps({'url':url,'pid':os.getpid(),'app':args.app}),encoding='utf8')
    if not args.no_browser:webbrowser.open(url)
    print('Marchan2 '+args.app+' · '+url,flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
