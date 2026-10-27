import json,tempfile,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from store import Store
import cash_register as cash
import button_layout as buttons
import permissions

class CashTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'test.db');self.counter=0
    def key(self):
        self.counter+=1;return 'request-test-'+str(self.counter)
    def opening(self,amount='100'):
        self.sid=cash.mutate(self.store,'cash_open',{'opening':amount,'request_id':self.key()},1)['session_id'];return self.sid
    def sale(self,method='cash',tip='0',partial=None):
        oid=self.store.mutate('open',{'direct':True},1)['order_id']
        self.store.mutate('add',{'order_id':oid,'format_id':1},1)
        order=self.store.receipt(oid)
        data=dict(order_id=oid,expected_total=order['total'],payment=method,tendered='100',tip=tip,request_id=self.key())
        if partial is not None:data['amount']=partial
        result=self.store.mutate('pay',data,1);return oid,result
    def close(self,**extra):
        r=cash.report(self.store);data=dict(session_id=r['session_id'],expected_revision=r['revision'],counted_cash=f"{r['expected_cash']/100:.2f}",request_id=self.key());data.update(extra)
        return cash.mutate(self.store,'cash_close',data,1)
    def movement(self,kind='income',amount='20',**extra):
        data=dict(session_id=self.sid,kind=kind,amount=amount,reason='Concepto de prueba',request_id=self.key());data.update(extra)
        return cash.mutate(self.store,'cash_move',data,1)
    def test_opening_required_and_explicit_zero_allowed(self):
        with self.assertRaises(ValueError):self.store.mutate('open',{'direct':True},1)
        with self.assertRaises(ValueError):cash.mutate(self.store,'cash_open',{'request_id':self.key()},1)
        self.opening('0');self.assertEqual(cash.report(self.store)['opening'],0)
        self.assertTrue(self.store.mutate('open',{'direct':True},1)['order_id'])
    def test_cash_tips_change_card_and_manual_moves_reconcile(self):
        self.opening();oid,paid=self.sale(tip='.50');self.assertEqual(paid['change'],9500)
        self.sale('card',tip='1');self.movement();self.movement('expense','3');self.movement('withdrawal','10')
        r=cash.report(self.store);self.assertEqual(r['sales'],900);self.assertEqual(r['collected'],900)
        self.assertEqual(r['cash_tips'],50);self.assertEqual(r['expected_cash'],11200);self.assertEqual(r['expected_card'],550)
        closed=self.close(counted_card='5.50')['report'];self.assertEqual(closed['cash_difference'],0);self.assertEqual(closed['card_difference'],0)
        self.assertIn('Z-000001',cash.text_report(closed))
    def test_duplicate_open_move_close_idempotent(self):
        request='same-opening';data={'opening':'0','request_id':request};a=cash.mutate(self.store,'cash_open',data,1);b=cash.mutate(self.store,'cash_open',data,1);self.sid=a['session_id'];self.assertEqual(a['session_id'],b['session_id'])
        data=dict(session_id=self.sid,kind='income',amount='2',reason='Cambio inicial',request_id='same-movement')
        cash.mutate(self.store,'cash_move',data,1);cash.mutate(self.store,'cash_move',data,1)
        self.assertEqual(cash.report(self.store)['expected_cash'],200)
        r=cash.report(self.store);data=dict(session_id=self.sid,expected_revision=r['revision'],counted_cash='2',request_id='same-closing')
        a=cash.mutate(self.store,'cash_close',data,1);b=cash.mutate(self.store,'cash_close',data,1);self.assertEqual(a['report'],b['report']);self.assertEqual(len(cash.history(self.store)),1)
    def test_cannot_close_pending_or_partially_paid(self):
        self.opening();oid,_=self.sale(partial=200)
        with self.assertRaises(ValueError):self.close()
        with self.assertRaises(ValueError):self.store.mutate('cancel_ticket',{'order_id':oid,'reason':'No permitido'},1)
        o=self.store.receipt(oid);self.store.mutate('pay',dict(order_id=oid,expected_total=o['total'],expected_due=o['due'],payment='card',request_id=self.key()),1)
        r=self.close()['report'];self.assertEqual(r['cash_sales'],200);self.assertEqual(r['card_sales'],250)
    def test_cancel_ticket_preserves_audit_and_cancels_preparation(self):
        self.opening();oid=self.store.mutate('open',{'table_id':1},1)['order_id'];self.store.mutate('add',{'order_id':oid,'format_id':1},1);self.store.mutate('send',{'order_id':oid},1)
        self.store.mutate('cancel_ticket',{'order_id':oid,'reason':'Error al tomar comanda'},1)
        self.assertEqual(self.store.receipt(oid)['status'],'void');self.assertFalse(self.store.preparation());self.assertFalse(self.store.state()['orders'])
        r=self.close()['report'];self.assertEqual(r['sales'],0);self.assertEqual(r['expected_cash'],10000);self.assertEqual(len(r['cancellations']),1)
        with self.store.db() as c:self.assertEqual(json.loads(c.execute('SELECT snapshot FROM ticket_cancellations').fetchone()[0])['total'],450)
    def test_discrepancies_need_reason_and_stale_count_rejected(self):
        self.opening();old=cash.report(self.store);self.movement()
        with self.assertRaises(ValueError):self.close(expected_revision=old['revision'])
        with self.assertRaises(ValueError):self.close(counted_cash='119')
        with self.assertRaises(ValueError):self.close(counted_card='1')
        r=self.close(counted_cash='119',counted_card='1',reason='Diferencia revisada')['report'];self.assertEqual(r['cash_difference'],-100);self.assertEqual(r['card_difference'],100)
    def test_denominations_consistent_and_invalid_quantities_rejected(self):
        self.opening('12.34')
        for values in ({'1000':1},{'1000':True},{'1000':-1},{'3':1}):
            with self.assertRaises(ValueError):self.close(denominations=values)
        r=self.close(denominations={'1000':1,'200':1,'20':1,'10':1,'2':2})['report'];self.assertEqual(r['counted_cash'],1234)
    def test_closed_snapshot_is_immutable_and_next_session_isolated(self):
        self.opening();self.sale();z=self.close()['report'];self.opening('20');self.sale('card')
        self.assertEqual(cash.report(self.store,z['session_id']),z);self.assertEqual(cash.report(self.store)['expected_cash'],2000)
        with self.assertRaises(ValueError):cash.report(self.store,kind='z')
    def test_outgoing_cannot_exceed_cash_and_no_negative_amounts(self):
        self.opening('0')
        for kind,amount in [('expense','1'),('withdrawal','1'),('income','-1'),('income','0'),('income','NaN')]:
            with self.assertRaises(ValueError):self.movement(kind,amount)
        self.assertEqual(cash.report(self.store)['movements'],[])
    def test_concurrent_openings_and_close_vs_movement(self):
        def attempt_open(n):
            try:return cash.mutate(self.store,'cash_open',{'opening':'10','request_id':'thread-open-'+str(n)},1)['session_id']
            except ValueError:return None
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(attempt_open,range(2)))
        self.assertEqual(sum(x is not None for x in results),1);self.sid=next(x for x in results if x);r=cash.report(self.store)
        def attempt(action):
            try:
                if action=='move':self.movement(amount='1')
                else:self.close(expected_revision=r['revision'],counted_cash='10')
                return True
            except ValueError:return False
        with ThreadPoolExecutor(2) as pool:outcomes=list(pool.map(attempt,['move','close']))
        self.assertEqual(sum(outcomes),1)
    def test_custom_profile_does_not_gain_cash_rights(self):
        profile=permissions.save(self.store,{'name':'Solo venta','permissions':['ticket_open']})['id']
        self.store.mutate('user',{'name':'ANA','pin':'1234','role':'staff','profile_id':profile},1)
        uid=next(u['id'] for u in self.store.users() if u['name']=='ANA')
        with self.assertRaises(PermissionError):cash.mutate(self.store,'cash_open',{'opening':'0','request_id':self.key()},uid)
        self.opening()
        with self.assertRaises(PermissionError):cash.mutate(self.store,'cash_move',dict(session_id=self.sid,kind='income',amount='1',reason='No autorizado',request_id=self.key()),uid)
    def test_historical_unassigned_payments_are_not_imported_to_new_shift(self):
        self.opening();oid,_=self.sale()
        with self.store.db() as c:c.execute('UPDATE payments SET cash_session_id=NULL WHERE order_id=?',(oid,))
        r=cash.report(self.store);self.assertEqual(r['cash_sales'],0)

class ButtonLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store(Path(self.tmp.name)/'test.db')
    def test_profile_layout_persists_and_stale_save_rejected(self):
        data=buttons.read(self.store);data['layout']['right'].remove('prepare');data['layout']['others'].append('prepare')
        buttons.save(self.store,data,1);self.assertIn('prepare',buttons.read(self.store)['layout']['others'])
        with self.assertRaises(ValueError):buttons.save(self.store,data,1)
        import pos_profiles
        other=pos_profiles.save(self.store,{'name':'SEGUNDO','group_name':'PRUEBA','options':pos_profiles.DEFAULT})['id']
        self.assertIn('prepare',buttons.read(self.store,other)['layout']['right'])
    def test_layout_rejects_missing_duplicate_unknown_or_hidden_required(self):
        for change in ('missing','duplicate','unknown','hide'):
            data=buttons.read(self.store)
            if change=='missing':data['layout']['right'].remove('march')
            elif change=='duplicate':data['layout']['right'].append('march')
            elif change=='unknown':data['layout']['others'].append('run-code')
            else:data['layout']['right'].remove('payments');data['layout']['others'].append('payments')
            with self.assertRaises(ValueError):buttons.save(self.store,data,1)
    def test_layout_save_requires_admin(self):
        self.store.mutate('user',{'name':'ANA','role':'staff','pin':'1234'},1)
        uid=next(u['id'] for u in self.store.users() if u['name']=='ANA')
        with self.assertRaises(PermissionError):buttons.save(self.store,buttons.read(self.store),uid)

if __name__=='__main__':unittest.main()
