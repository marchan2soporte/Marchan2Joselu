"""Separate local TPV/admin entry points with shared SQLite and authenticated roles."""
import argparse
from urllib.parse import urlparse,parse_qs
from analytics import dashboard,report,report_catalog
import inventory
import company
import series
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

TPV_ACTIONS={'open','add','quantity','send','march','course','note','move','pay','split_pay','ready','close_empty'}
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
            return {k:u[k] for k in ('id','name','role','active')}

        def do_GET(self):
            if not self.allowed():return self.reply(403,{'error':'Acceso local requerido.'})
            try:
                path=self.path.split('?')[0]
                if path=='/':
                    html=(assets/'index.html').read_text(encoding='utf8').replace('__TOKEN__',token).replace('__MODE__',args.app).replace('__APPNAME__','TPV' if args.app=='tpv' else 'Administración')
                    return self.reply(200,html.encode(),'text/html; charset=utf-8')
                if path=='/logo.png':return self.reply(200,(assets/'logo.png').read_bytes(),'image/png')
                if path in ('/app.js','/style.css',f'/{args.app}.js',f'/{args.app}-extras.js'):
                    return self.reply(200,(assets/path[1:]).read_bytes(),'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
                if path=='/api/access':
                    users=store.users()
                    if args.app=='admin':users=[u for u in users if u['role']=='admin']
                    return self.reply(200,dict(app=args.app,users=users,user=self.user(),version='0.7'))
                user=self.user()
                if not user:return self.reply(401,{'error':'Selecciona tu usuario e introduce el PIN.'})
                if path=='/api/company':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,company.read(store))
                if path=='/api/series':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,series.list_all(store))
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
                if path=='/api/state':
                    data=store.state();data['user']=user
                    if args.app=='tpv':
                        for key in ('stats','history','payment_history'):data.pop(key,None)
                    else:data['users']=store.users(False)
                    return self.reply(200,data)
                if path=='/api/preparation' and args.app=='tpv':return self.reply(200,store.preparation())
                if path.startswith('/api/receipt/'):return self.reply(200,store.receipt(int(path.rsplit('/',1)[1])))
                self.reply(404,{'error':'No encontrado.'})
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
                if action=='company':
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,company.save(store,data))
                if action in ('series_save','series_delete'):
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,series.save(store,data) if action=='series_save' else series.delete(store,data))
                if action=='shutdown':
                    self.reply(200,{'ok':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
                if action in ('supplier','stock_item','stock_move'):
                    if args.app!='admin':return self.reply(403,{'error':'Solo Administración.'})
                    return self.reply(200,inventory.mutate(store,action,data,user['id']))
                allowed=TPV_ACTIONS if args.app=='tpv' else ADMIN_ACTIONS
                if action not in allowed:return self.reply(403,{'error':'Esta operación pertenece a la otra aplicación.'})
                self.reply(200,store.mutate(action,data,actor=user['id']))
            except sqlite3.IntegrityError:self.reply(409,{'error':'La operación ya está registrada o ese nombre está en uso. Actualiza la pantalla.'})
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
