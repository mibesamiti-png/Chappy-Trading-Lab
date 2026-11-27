"""R58: synthetic global restart gate; no execution or market data."""
import argparse, hashlib, importlib.util, json, copy
from pathlib import Path
ROOT=Path(__file__).parent
R57_SHA='c1cb74de5f5cd0424ace77d59bf6d0f142bacf0d8155e16b9b4550c70b4db37c'
p=ROOT/'Chappy_Trading_Dependency_Study_v0.1.py'
if hashlib.sha256(p.read_bytes()).hexdigest()!=R57_SHA: raise ValueError('R57 hash mismatch')
spec=importlib.util.spec_from_file_location('r57',p); dep=importlib.util.module_from_spec(spec); spec.loader.exec_module(dep)
STEP=5; SHADOW_COUNT=2

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def snapshot(t,cash=100000,holdings=None,pending=(),terminal=None):
    return {'event':t,'received':t,'cash':cash,'holdings':dict.fromkeys('ABC',0) if holdings is None else holdings,'pending':list(pending),'terminal':{} if terminal is None else terminal}

def validate_snapshot(s,now):
    if s is None:return False
    if set(s)!={'event','received','cash','holdings','pending','terminal'} or any(type(s[k]) is not int for k in ('event','received','cash')):raise ValueError('snapshot structure')
    if not 0<=s['event']<=s['received']<=now or s['cash']<0:raise ValueError('snapshot time or cash')
    if set(s['holdings'])!=set('ABC') or any(type(v) is not int or v<0 for v in s['holdings'].values()):raise ValueError('holdings')
    if type(s['pending']) is not list or any(type(x) is not str or not x for x in s['pending']) or len(set(s['pending']))!=len(s['pending']):raise ValueError('pending')
    if type(s['terminal']) is not dict or any(type(k) is not str or not k or v not in ('FILLED','CANCELLED','REJECTED') for k,v in s['terminal'].items()) or set(s['pending'])&set(s['terminal']):raise ValueError('terminal')
    return s['event']==now and s['received']==now

def account_payload(s):return {k:s[k] for k in ('cash','holdings','pending','terminal')}

class Gate:
    def __init__(self):
        self.state='HALTED';self.epoch=0;self.last=None;self.events=[];self.unresolved=set();self.terminal={};self.shadow=0;self.ready=None;self.account=None
    def tick(self,now,events,local=None,external=None,approval=None,exit_requested=()):
        # Commit only on successful structural validation; invalid input does not mutate state.
        candidate=copy.deepcopy(self);out=candidate._tick(now,events,local,external,approval,exit_requested);self.__dict__.update(candidate.__dict__);return out
    def _tick(self,now,events,local,external,approval,exit_requested):
        if type(now) is not int or now<0 or (self.last is not None and now<=self.last):raise ValueError('tick order')
        if any(e['received']>now or (self.last is not None and e['received']<=self.last) for e in events):raise ValueError('batch receipt order')
        self.events.extend(copy.deepcopy(events));health=dep.health(self.events,now)[0]
        gap=self.last is not None and now-self.last!=STEP
        fresh_l=validate_snapshot(local,now);fresh_e=validate_snapshot(external,now)
        for s in (local,external):
            if s is not None:self.unresolved.update(s['pending'])
        payload_l=account_payload(local) if fresh_l else None;payload_e=account_payload(external) if fresh_e else None
        matched=payload_l is not None and payload_l==payload_e and health['account']=='OK'
        reasons=[]
        if gap:reasons.append('TICK_GAP')
        bad=[n for n in dep.ROOTS if health[n]!='OK']
        if bad:reasons.extend('HEALTH:'+n for n in bad)
        if not matched:reasons.append('ACCOUNT_UNRECONCILED')
        terminal_conflict=matched and any(payload_l['terminal'].get(k)!=v for k,v in self.terminal.items())
        if terminal_conflict:reasons.append('TERMINAL_HISTORY_CHANGED')
        if matched and not terminal_conflict:
            self.terminal.update(payload_l['terminal']);self.unresolved.difference_update(self.terminal)
        if self.unresolved or (matched and payload_l['pending']):reasons.append('PENDING_UNRESOLVED')
        # A known terminal ID reopening is never accepted, even if both ledgers agree.
        if matched and set(payload_l['pending'])&set(self.terminal):reasons.append('TERMINAL_REOPENED')
        before=self.state; accepted=False;approval_result='NONE' if approval is None else 'DENIED'
        payload_hash=digest(payload_l) if matched else None
        if reasons:
            if self.state!='HALTED':self.epoch+=1
            self.state='HALTED';self.shadow=0;self.ready=None;self.account=None
        elif self.state=='HALTED' or (self.state!='NORMAL' and self.account!=payload_hash):
            if self.state!='HALTED':self.epoch+=1
            self.state='RECONCILED';self.account=payload_hash;self.shadow=0;self.ready=None
        elif self.state in ('RECONCILED','SHADOW'):
            self.shadow+=1;self.state='SHADOW'
            if self.shadow>=SHADOW_COUNT:
                self.state='READY';self.ready={'epoch':self.epoch,'ready_at':now,'account_sha':payload_hash}
        elif self.state=='READY' and approval==self.ready and now>self.ready['ready_at']:
            self.state='NORMAL';accepted=True;approval_result='ACCEPTED';self.ready=None
        # While NORMAL, the two ledgers may move together; this model does not authorize those changes.
        if self.state=='NORMAL':self.account=payload_hash
        self.last=now
        # R57 route never treats mismatched account as verified; use an independent artificial UNKNOWN override.
        reported=external['holdings'] if external is not None else dict.fromkeys('ABC',0)
        route_events=self.events if matched and not terminal_conflict else self.events+[{'node':'account','event':now,'received':now,'status':'UNKNOWN'}]
        routing=dep.route(route_events,now,reported,exit_requested)['strategies']
        for s in routing.values():
            s['restart_gate']='ELIGIBLE' if self.state=='NORMAL' and s['new_entry']=='ELIGIBLE' else 'BLOCKED'
        return {'at':now,'before':before,'state':self.state,'epoch':self.epoch,'reasons':reasons,'approval':approval_result,'ready_token':copy.deepcopy(self.ready),'shadow_count':self.shadow,'unresolved':sorted(self.unresolved),'routing':routing,'account_matched':bool(matched and not terminal_conflict),'actual_orders':False,'live_adoption':False}

def tick(g,t,changes=None,local=None,external=None,approval=None,missing=False,exit_requested=()):
    l=snapshot(t) if local is None else local;e=snapshot(t) if external is None else external
    return g.tick(t,dep.feed(changes,t),l,None if missing else e,approval,exit_requested)

def sequence(g,start=100):return [tick(g,t) for t in range(start,start+20,5)]
def example():
    g=Gate();r=sequence(g);r.append(tick(g,120,approval=r[-1]['ready_token']));r.append(tick(g,125,{'news':'FAILED'},local=snapshot(125,holdings={'A':100,'B':0,'C':0},pending=['P1']),external=snapshot(125,holdings={'A':100,'B':0,'C':0},pending=['P1']),exit_requested=('A',)))
    r.append(tick(g,130,local=snapshot(130),external=snapshot(130)))
    for t in (135,140,145):r.append(tick(g,t,local=snapshot(t,terminal={'P1':'CANCELLED'}),external=snapshot(t,terminal={'P1':'CANCELLED'})))
    r.append(tick(g,150,local=snapshot(150,terminal={'P1':'CANCELLED'}),external=snapshot(150,terminal={'P1':'CANCELLED'}),approval=r[-1]['ready_token']))
    return {'timeline':r,'scope':'synthetic global restart gate; health and accounting claims not authenticated'}

def self_test():
    tests=[]
    def ck(n,a,b=True):
        if a!=b:raise AssertionError((n,a,b))
        tests.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except ValueError:ck(n,True)
        else:ck(n,False)
    ex=example()['timeline'];ck('example timeline',[x['state'] for x in ex],['RECONCILED','SHADOW','READY','READY','NORMAL','HALTED','HALTED','RECONCILED','SHADOW','READY','NORMAL'])
    ck('no auto restart',ex[3]['state'],'READY');ck('explicit restart',ex[4]['approval'],'ACCEPTED');ck('pending not silently cleared',ex[6]['unresolved'],['P1']);ck('resolved terminal',ex[7]['unresolved'],[])
    ck('exit independent of global latch',ex[5]['routing']['A']['exit'],'SIMULATED_EXIT_ELIGIBLE');ck('global gate blocks unaffected strategy',ex[5]['routing']['A']['restart_gate'],'BLOCKED');ck('no real orders',all(not x['actual_orders'] and not x['live_adoption'] for x in ex))
    for root in dep.ROOTS:
        g=Gate();r=sequence(g);tick(g,120,approval=r[-1]['ready_token']);v=tick(g,125,{root:'FAILED'});ck(root+' halt',v['state'],'HALTED');ck(root+' no entry',all(x['restart_gate']=='BLOCKED' for x in v['routing'].values()));ck(root+' no auto restart',tick(g,130)['state'],'RECONCILED')
    for label,l,e in [('cash',snapshot(100,cash=1),snapshot(100)),('holdings',snapshot(100,holdings={'A':100,'B':0,'C':0}),snapshot(100)),('pending',snapshot(100,pending=['X']),snapshot(100)),('terminal',snapshot(100,terminal={'X':'FILLED'}),snapshot(100,terminal={'X':'CANCELLED'})),('stale',snapshot(99),snapshot(100))]:
        g=Gate();v=tick(g,100,local=l,external=e);ck(label+' no reconcile',v['state'],'HALTED');ck(label+' exposure unverified',v['routing']['C']['holdings_verified'],False)
    g=Gate();ck('missing external',tick(g,100,missing=True)['state'],'HALTED')
    g=Gate();r=sequence(g);token=r[-1]['ready_token'];ck('wrong token',tick(g,120,approval={**token,'epoch':99})['state'],'READY');ck('valid later token',tick(g,125,approval=token)['state'],'NORMAL');ck('gap latches',tick(g,135)['state'],'HALTED');ck('gap reason',tick(g,145)['reasons'],['TICK_GAP'])
    g=Gate();r=sequence(g);token=r[-1]['ready_token'];v=tick(g,120,local=snapshot(120,cash=2),external=snapshot(120,cash=2),approval=token);ck('changed balance resets',v['state'],'RECONCILED');ck('changed balance denies approval',v['approval'],'DENIED');ck('stale epoch',v['epoch'],1)
    g=Gate();tick(g,100,local=snapshot(100,pending=['P']),external=snapshot(100,pending=['P']));ck('pending disappears without terminal',tick(g,105)['state'],'HALTED');ck('different terminal',tick(g,110,local=snapshot(110,terminal={'P':'FILLED'}),external=snapshot(110,terminal={'P':'CANCELLED'}))['state'],'HALTED');ck('terminal reconciled',tick(g,115,local=snapshot(115,terminal={'P':'FILLED'}),external=snapshot(115,terminal={'P':'FILLED'}))['state'],'RECONCILED');ck('terminal changed',tick(g,120,local=snapshot(120,terminal={'P':'CANCELLED'}),external=snapshot(120,terminal={'P':'CANCELLED'}))['state'],'HALTED')
    g=Gate();tick(g,100,local=snapshot(100,terminal={'P':'FILLED'}),external=snapshot(100,terminal={'P':'FILLED'}));ck('terminal reopening',tick(g,105,local=snapshot(105,pending=['P']),external=snapshot(105,pending=['P']))['state'],'HALTED')
    g=Gate();tick(g,100);old=copy.deepcopy(g.__dict__);reject('duplicate tick',lambda:tick(g,100));ck('invalid atomic',g.__dict__,old);reject('future event',lambda:g.tick(105,dep.feed(t=106),snapshot(105),snapshot(105)));ck('future atomic',g.__dict__,old);reject('old receipt',lambda:g.tick(105,dep.feed(t=100),snapshot(105),snapshot(105)));reject('negative cash',lambda:tick(g,105,local=snapshot(105,cash=-1)));reject('duplicate pending',lambda:tick(g,105,local=snapshot(105,pending=['P','P'])));reject('pending terminal overlap',lambda:tick(g,105,local=snapshot(105,pending=['P'],terminal={'P':'FILLED'})));ck('invalid batches atomic',g.__dict__,old)
    g=Gate();tick(g,100);tick(g,105);v=tick(g,110,approval={'epoch':0,'ready_at':110,'account_sha':digest(account_payload(snapshot(110)))});ck('same tick approval denied',v['approval'],'DENIED');ck('ready state',v['state'],'READY')
    # Exhaustive root failure masks with startup latch and verified account/exit separation.
    for mask in range(1<<len(dep.ROOTS)):
        changes={n:'FAILED' for i,n in enumerate(dep.ROOTS) if mask&(1<<i)};g=Gate();v=tick(g,100,changes);expected='HALTED' if mask else 'RECONCILED'
        if v['state']!=expected or any(x['restart_gate']!='BLOCKED' for x in v['routing'].values()):raise AssertionError(('mask',mask))
    ck('all startup masks',True)
    return {'test_count':len(tests),'exhaustive_startup_masks':1<<len(dep.ROOTS),'tests':tests}

if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(self_test() if a.self_test else example(),indent=2,sort_keys=True))
