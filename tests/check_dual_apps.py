"""End-to-end authenticated app boundary checks, on isolated data only."""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError

root=Path(__file__).resolve().parent.parent
urlopen=build_opener(ProxyHandler({})).open
parser=argparse.ArgumentParser();parser.add_argument('--frozen',action='store_true');args=parser.parse_args()


class Client:
    def __init__(self,app,folder):
        name='Marchan2_TPV.exe' if app=='tpv' else 'Marchan2_Administracion.exe'
        command=[str(root/'dist/Marchan2_v0.15'/name)] if args.frozen else [sys.executable,str(root/(app+'.py'))]
        (folder/f'session-{app}.json').unlink(missing_ok=True)
        self.proc=subprocess.Popen(command+['--data',str(folder),'--no-browser'],creationflags=subprocess.CREATE_NO_WINDOW)
        self.session='';self.token='';self.url=''
        for _ in range(100):
            if self.proc.poll() is not None:raise AssertionError('Server exited')
            path=folder/f'session-{app}.json'
            if path.exists():
                info=json.loads(path.read_text())
                if info.get('url'):
                    try:
                        self.url=info['url'];html=urlopen(self.url,timeout=1).read().decode()
                        self.token=re.search(r'name="marchan-token" content="([^"]+)"',html)[1]
                        assert f'content="{app}"' in html
                        break
                    except OSError:pass
            time.sleep(.1)
        else:self.proc.terminate();raise AssertionError('Server startup timed out')

    def request(self,path,data=None,status=200,csrf=True):
        headers={'X-Marchan2-Session':self.session,'Content-Type':'application/json'}
        if csrf:headers['X-Marchan2-Token']=self.token
        req=Request(self.url+'/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urlopen(req,timeout=10) as r:
                result=json.loads(r.read());actual=r.status
        except HTTPError as e:actual=e.code;result=json.loads(e.read())
        assert actual==status,(path,actual,status,result)
        return result

    def login(self,uid=1,pin='1234'):
        result=self.request('login',{'user_id':uid,'pin':pin});self.session=result['session']

    def stop(self):
        try:self.login();self.request('shutdown',{});self.proc.wait(timeout=5)
        except Exception:self.proc.terminate();self.proc.wait(timeout=5)


with tempfile.TemporaryDirectory() as tmp:
    folder=Path(tmp);tpv=None;admin=None
    try:
        tpv=Client('tpv',folder);admin=Client('admin',folder)
        for client in (tpv,admin):
            assert 'pin_hash' not in json.dumps(client.request('access'))
            client.request('state',status=401)
            client.request('company',status=401)
            client.request('company',{'legal_name':'BLOCKED'},status=401)
            client.request('open',{'direct':True},status=401)
            client.request('login',{'user_id':1,'pin':'0000'},status=400)
        admin.login();assert len(admin.request('analytics/dashboard')['cards'])==4
        assert admin.request('pos_profiles')[0]['active']
        assert admin.request('peripheral_ports')['ports'] is not None
        admin.request('printer_probe',{},status=400)
        admin.request('scale_probe',{},status=400)
        assert admin.request('ticket_templates')==[]
        admin.request('ticket_template_save',{'name':'QA','base':'80 mm','header':'Cabecera QA',
            'footer':'Pie QA','show_time':True,'show_user':True,'show_tax':True,'is_default':True})
        assert admin.request('state')['ticket_template']['header']=='Cabecera QA'
        assert admin.request('series')==[]
        admin.request('series_save',{'name':'F QA','type':'Factura','next_number':'1','active':True})
        assert admin.request('series')[0]['name']=='F QA'
        config=admin.request('global_config');assert config['pos_series']['Factura'] is None
        config['pos_series']['Factura']=admin.request('series')[0]['id']
        config['preferences']['stock_warning']=True
        config['preferences']['command_template']=str(admin.request('ticket_templates')[0]['id'])
        config['preferences']['include_center_sales']=True
        config['preferences']['include_pending']=True
        admin.request('global_config',config)
        assert admin.request('global_config')['pos_series']['Factura']==config['pos_series']['Factura']
        assert admin.request('global_config')['preferences']['stock_warning']
        admin.request('series_save',{'name':'F QA','type':'Factura','next_number':'2'},status=409)
        assert admin.request('company')['legal_name']==''
        admin.request('company',{'legal_name':'EMPRESA QA','postal_code':'01001'})
        assert admin.request('company')['postal_code']=='01001'
        assert admin.request('state')['company']['legal_name']=='EMPRESA QA'
        admin.request('company',{'email':'invalid'},status=400)
        assert admin.request('company')['legal_name']=='EMPRESA QA'
        assert len(admin.request('analytics/catalog'))>50
        admin.request('supplier',{'name':'PROVEEDOR QA'})
        admin.request('stock_item',{'name':'HARINA QA','unit':'KG','minimum':'2'})
        admin.request('stock_move',{'item_id':1,'supplier_id':1,'qty':'1.250','cost':'2.40','kind':'receipt','request_id':'stock-qa','reference':'QA'})
        assert admin.request('inventory')['items'][0]['balance']==1250
        assert admin.request('analytics/dashboard')['stock']['current']==300
        admin.request('open',{'direct':True},status=403)
        admin.request('user',{'name':'ANA QA','pin':'4567','role':'staff'})
        ana=next(u for u in admin.request('state')['users'] if u['name']=='ANA QA')
        admin.request('login',{'user_id':ana['id'],'pin':'4567'},status=400)
        tpv.login(ana['id'],'4567')
        tpv.request('analytics/dashboard',status=403)
        tpv.request('inventory',status=403)
        tpv.request('company',status=403)
        tpv.request('series',status=403)
        tpv.request('global_config',status=403)
        tpv.request('pos_profiles',status=403)
        tpv.request('printer_probe',{},status=403)
        assert tpv.request('z_report')['kind']=='z_preview'
        assert tpv.request('state')['ticket_template']['header']=='Cabecera QA'
        assert tpv.request('state')['global_config']['preferences']['stock_warning']
        assert tpv.request('state')['command_template']['header']=='Cabecera QA'
        assert [s['title'] for s in tpv.request('daily_close')['sections']]==['Ventas por centro','Cuentas pendientes ahora']
        tpv.request('ticket_templates',status=403)
        tpv.request('ticket_template_save',{'name':'BLOCKED'},status=403)
        tpv.request('series_save',{'name':'BLOCKED'},status=403)
        tpv.request('company',{'legal_name':'BLOCKED'},status=403)
        tpv.request('product',{'name':'BLOCKED'},status=403)
        tpv.request('open',{'direct':True},csrf=False,status=403)
        tpv.request('open',{},status=400)
        state=tpv.request('state');assert not any(k in state for k in ('stats','history','users'))
        assert state['company']['legal_name']=='EMPRESA QA'
        assert state['stock_warnings'][0]['name']=='HARINA QA'
        product=next(p for p in state['products'] if p['name']=='JHONNY NEGRO')
        oid=tpv.request('open',{'table_id':1})['order_id']
        for fmt in product['formats']:tpv.request('add',{'order_id':oid,'format_id':fmt['id']})
        order=tpv.request('state')['orders'][0]
        assert order['created_by']==ana['id'] and order['total']==12900
        tpv.request('march',{'order_id':oid,'line_ids':[order['lines'][0]['id']]})
        order=tpv.request('state')['orders'][0];assert [l['kitchen'] for l in order['lines']]==['pending','new']
        tpv.request('pay',{'order_id':oid,'expected_total':12900,'expected_due':12900,'payment':'card','amount':6400,'request_id':'dual-part1'})
        assert admin.request('state')['stats']['revenue']==6400
        remaining=tpv.request('state')['orders'][0];assert remaining['due']==6500
        tpv.request('move',{'order_id':oid,'table_id':2})
        tpv.request('pay',{'order_id':oid,'expected_total':12900,'expected_due':6500,'payment':'cash','tendered':'70','request_id':'dual-part2'})
        receipt=tpv.request('receipt/'+str(oid));assert receipt['due']==0 and receipt['payments'][-1]['change_due']==500
        assert receipt['table_name']=='M2' and receipt['payments'][0]['user_id']==ana['id']
        admin.request('user',{'id':ana['id'],'name':'ANA QA','pin':'5678','role':'staff'})
        tpv.request('state',status=401)
        tpv.login(ana['id'],'5678');tpv.request('logout',{});tpv.request('state',status=401)
        admin.request('user',{'id':1,'name':'ADMIN','role':'staff'},status=400)
        tpv.stop();tpv=Client('tpv',folder);tpv.login()
        assert tpv.request('receipt/'+str(oid))['total']==12900
        for script in ('app.js','tpv.js'):
            assert urlopen(tpv.url+'/'+script).status==200
        try:urlopen(Request(tpv.url+'/admin.js',headers={'X-Marchan2-Session':tpv.session}));raise AssertionError('Admin script served by TPV')
        except HTTPError as e:assert e.code==404
        print('PASS: '+('FROZEN' if args.frozen else 'SOURCE')+' dual apps, shared data, login, staff/admin boundaries, explicit sale context, selected-line preparation, partial/mixed payments, move, actor attribution, PIN revocation, logout and restart.')
    finally:
        if tpv and tpv.proc.poll() is None:tpv.stop()
        if admin and admin.proc.poll() is None:admin.stop()
