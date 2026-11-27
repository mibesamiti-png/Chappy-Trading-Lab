"""Round 47: synthetic hypothesis/risk audit. No market feeds or orders.
Python 3.10+. Integer yen, shares, seconds, basis points. Long-only scenario.
"""
from dataclasses import dataclass, replace
from fractions import Fraction
import argparse,json

@dataclass(frozen=True)
class Evidence:
    field:str; value:int; event:int; received:int; source:str; snapshot:str
@dataclass(frozen=True)
class Predicate:
    field:str; op:str; threshold:int
@dataclass(frozen=True)
class Plan:
    entry:Predicate; refute:Predicate; confirm:Predicate; deadline:int
    qty:int; capital:int; cash:int; risk_bps:int; cost_bps:int; gap_yen:int
    action:str='BUY'; wait_reason:str=''

FIELDS={'close':600,'volume':600,'bid':10,'ask':10,'bid_depth':10,'ask_depth':10}
BOOK={'bid','ask','bid_depth','ask_depth'}
OPS={'>','>=','<','<='}
def integer(v,minimum=0): return type(v) is int and v>=minimum

def collect(rows,now,supported):
    states={}; values={}; selected={}
    for f,age in FIELDS.items():
        if f not in supported: states[f]='UNSUPPORTED'; continue
        relevant=[r for r in rows if r.field==f]
        if any(not integer(r.received) for r in relevant): states[f]='INVALID'; continue
        available=[r for r in relevant if r.received<=now]
        if any(not (integer(r.event) and r.event<=r.received and integer(r.value,1 if f in {'close','bid','ask'} else 0) and r.source and r.snapshot) for r in available):
            states[f]='INVALID'; continue
        if not available: states[f]='FUTURE' if relevant else 'UNKNOWN'; continue
        t=max(r.event for r in available); latest=[r for r in available if r.event==t]
        if len({r.value for r in latest})!=1: states[f]='CONFLICT'; continue
        if now-t>age: states[f]='STALE'; continue
        # Identical duplicates do not increase confidence. Ambiguous snapshot provenance blocks book use.
        if f in BOOK and len({(r.source,r.snapshot) for r in latest})!=1: states[f]='CONFLICT'; continue
        states[f]='OK'; values[f]=latest[0].value; selected[f]=latest[0]
    if BOOK<=values.keys() and len({(selected[f].source,selected[f].snapshot,selected[f].event) for f in BOOK})!=1:
        for f in BOOK: states[f]='INCOHERENT'; values.pop(f,None)
    return states,values

def valid_pred(p): return p.field in FIELDS and p.op in OPS and integer(p.threshold)
def truth(p,values):
    if p.field not in values: return 'UNKNOWN'
    a,b=values[p.field],p.threshold
    return 'TRUE' if {'>':a>b,'>=':a>=b,'<':a<b,'<=':a<=b}[p.op] else 'FALSE'

def evaluate(plan,rows,now,supported):
    if not integer(now): raise ValueError('invalid decision clock')
    states,values=collect(rows,now,supported); errors=[]; blockers=[]; risk=None
    ps=(plan.entry,plan.refute,plan.confirm)
    if not all(valid_pred(p) for p in ps): errors.append('INVALID_PREDICATE')
    # Restricted explicit long hypothesis: entry >= E, refute <= S, confirm >= T, S<E<T.
    if not (all(p.field=='close' for p in ps) and plan.entry.op=='>=' and plan.refute.op=='<=' and plan.confirm.op=='>=' and all(integer(p.threshold,1) for p in ps) and plan.refute.threshold<plan.entry.threshold<plan.confirm.threshold): errors.append('INVALID_LONG_HYPOTHESIS')
    if not integer(plan.deadline,now+1): errors.append('INVALID_DEADLINE')
    if not (integer(plan.qty,100) and plan.qty%100==0 and integer(plan.capital,1) and integer(plan.cash) and plan.cash<=plan.capital and integer(plan.risk_bps,1) and plan.risk_bps<=10000 and integer(plan.cost_bps) and plan.cost_bps<=10000 and integer(plan.gap_yen)): errors.append('INVALID_RISK_INPUT')
    if plan.action not in ('BUY','WAIT'): errors.append('INVALID_ACTION')
    if errors: return {'gate':'BLOCK','errors':errors,'blockers':[],'states':states,'risk':None,'execution_proven':False}
    for f in sorted(BOOK|{'close'}):
        if states[f]!='OK': blockers.append(f'{f}:{states[f]}')
    if truth(plan.entry,values)!='TRUE': blockers.append('ENTRY_NOT_ESTABLISHED')
    if truth(plan.refute,values)=='TRUE': blockers.append('ALREADY_REFUTED')
    if truth(plan.confirm,values)=='TRUE': blockers.append('ALREADY_CONFIRMED')
    if BOOK<=values.keys():
        bid,ask=values['bid'],values['ask']
        if bid>=ask: blockers.append('LOCKED_OR_CROSSED')
        if ask-bid>2: blockers.append('SPREAD_LIMIT')
        if values['ask_depth']<plan.qty: blockers.append('DEPTH_LIMIT')
        if ask>=plan.confirm.threshold: blockers.append('ENTRY_AT_OR_ABOVE_TARGET')
        exit_price=max(0,plan.refute.threshold-plan.gap_yen)
        if ask<=exit_price: blockers.append('INVALID_STOP_GEOMETRY')
        entry_cost=Fraction(ask*plan.qty*plan.cost_bps,10000)
        exit_cost=Fraction(exit_price*plan.qty*plan.cost_bps,10000)
        cash_needed=ask*plan.qty+entry_cost
        loss=(ask-exit_price)*plan.qty+entry_cost+exit_cost
        budget=Fraction(plan.capital*plan.risk_bps,10000)
        risk={'cash_required':str(cash_needed),'scenario_loss':str(loss),'budget':str(budget),'exit_scenario':exit_price}
        if cash_needed>plan.cash: blockers.append('CASH_LIMIT')
        if loss>budget: blockers.append('RISK_LIMIT')
    if plan.action=='WAIT':
        gate='WAIT_SUPPORTED' if plan.wait_reason in blockers else 'WAIT_UNVERIFIED'
    else: gate='BLOCK' if blockers else 'RESEARCH_ELIGIBLE'
    return {'gate':gate,'errors':errors,'blockers':blockers,'states':states,'risk':risk,'execution_proven':False}

def review(plan,rows,decision_time,now,supported):
    # First observable decisive event, ordered by receipt, not retroactive market timestamp.
    if not integer(now,decision_time) or not integer(decision_time): raise ValueError('invalid review clock')
    if not (all(valid_pred(p) for p in (plan.entry,plan.refute,plan.confirm)) and all(p.field=='close' for p in (plan.entry,plan.refute,plan.confirm)) and plan.entry.op=='>=' and plan.refute.op=='<=' and plan.confirm.op=='>=' and 0<plan.refute.threshold<plan.entry.threshold<plan.confirm.threshold and integer(plan.deadline,decision_time+1)): raise ValueError('invalid hypothesis')
    for t in sorted({r.received for r in rows if integer(r.received) and decision_time<r.received<=min(now,plan.deadline)}):
        states,values=collect([r for r in rows if integer(r.received) and r.received<=t and (not integer(r.event) or r.event>decision_time)],t,supported)
        if states['close']!='OK': continue
        if truth(plan.refute,values)=='TRUE': return 'REFUTED'
        if truth(plan.confirm,values)=='TRUE': return 'CONFIRMED_OBSERVED'
    return 'EXPIRED_UNRESOLVED' if now>=plan.deadline else 'OPEN_UNRESOLVED'

def self_test():
    tests=[]
    def check(n,a,b):
        if a!=b: raise RuntimeError(f'{n}: {a!r} != {b!r}')
        tests.append({'test':n,'result':'PASS'})
    s=set(FIELDS); p=Plan(Predicate('close','>=',100),Predicate('close','<=',95),Predicate('close','>=',110),1100,100,100000,100000,100,10,1)
    rows=[Evidence(f,v,995,997,'feed','A') for f,v in {'close':100,'bid':99,'ask':100,'bid_depth':100,'ask_depth':100,'volume':0}.items()]
    def ev(p=p,rows=rows,s=s): return evaluate(p,rows,1000,s)
    def edit(f,**kw): return [replace(r,**kw) if r.field==f else r for r in rows]
    def block(n,p=p,rows=rows,s=s): check(n,ev(p,rows,s)['gate'],'BLOCK')
    check('baseline',ev()['gate'],'RESEARCH_ELIGIBLE'); check('risk exact',ev()['risk']['scenario_loss'],'3097/5'); check('cash exact',ev()['risk']['cash_required'],'10010'); check('budget',ev()['risk']['budget'],'1000'); check('execution unproven',ev()['execution_proven'],False)
    block('bar only',s={'close','volume'}); block('snapshot mismatch',rows=edit('ask',snapshot='B')); block('timestamp mismatch',rows=edit('ask',event=996)); block('source mismatch',rows=edit('ask',source='other')); block('stale',rows=edit('ask',event=980)); block('future',rows=edit('ask',received=1001)); block('clock inversion',rows=edit('ask',received=994)); block('zero depth',rows=edit('ask_depth',value=0)); block('locked',rows=edit('bid',value=100)); block('crossed',rows=edit('bid',value=101)); block('spread',rows=edit('bid',value=96)); block('conflict',rows=rows+[replace(rows[0],value=101,source='other')]); check('duplicate identical',ev(rows=rows+[rows[0]])['gate'],'RESEARCH_ELIGIBLE'); check('future conflict ignored',ev(rows=rows+[replace(rows[0],value=101,received=1001)])['gate'],'RESEARCH_ELIGIBLE'); check('future malformed value ignored',ev(rows=rows+[replace(rows[0],value=-1,received=1001)])['gate'],'RESEARCH_ELIGIBLE'); block('entry unmet',rows=edit('close',value=99)); block('already refuted',rows=edit('close',value=94)); block('already confirmed',rows=edit('close',value=110)); block('predicate overlap',p=replace(p,refute=Predicate('close','<=',100))); block('meaningless field',p=replace(p,entry=Predicate('volume','>=',100))); block('bad operator',p=replace(p,entry=Predicate('close','=',100))); block('deadline elapsed',p=replace(p,deadline=1000)); block('cash too low',p=replace(p,cash=10000)); block('risk too high',p=replace(p,risk_bps=60)); block('lot mismatch',p=replace(p,qty=101)); block('negative gap',p=replace(p,gap_yen=-1)); block('negative cost',p=replace(p,cost_bps=-1)); block('bool capital',p=replace(p,capital=True)); block('cash exceeds capital',p=replace(p,cash=100001)); block('short unsupported',p=replace(p,action='SELL')); block('depth insufficient',p=replace(p,qty=200)); block('price above target',rows=edit('ask',value=110));
    check('supported wait',ev(replace(p,action='WAIT',wait_reason='bid:UNSUPPORTED'),s={'close','volume'})['gate'],'WAIT_SUPPORTED'); check('unverified wait',ev(replace(p,action='WAIT',wait_reason='SPREAD_LIMIT'))['gate'],'WAIT_UNVERIFIED'); check('wait no false necessity',ev(replace(p,action='WAIT'))['gate'],'WAIT_UNVERIFIED')
    def r(v,e,t): return Evidence('close',v,e,t,'feed',str(e))
    def rev(rs,now=1100): return review(p,rs,1000,now,s)
    check('refute',rev([r(94,1010,1011)]),'REFUTED'); check('confirm',rev([r(111,1010,1011)]),'CONFIRMED_OBSERVED'); check('first receipt refute persists',rev([r(94,1010,1011),r(111,1020,1021)]),'REFUTED'); check('first receipt confirm persists',rev([r(111,1010,1011),r(94,1020,1021)]),'CONFIRMED_OBSERVED'); check('late arrival not retroactive',rev([r(94,1005,1030),r(111,1010,1011)]),'CONFIRMED_OBSERVED'); check('future receipt ignored',rev([r(94,1099,1101)]),'EXPIRED_UNRESOLVED'); check('missing not refuted',rev([]),'EXPIRED_UNRESOLVED'); check('open',rev([],1050),'OPEN_UNRESOLVED'); check('predecision observation ignored',rev([r(94,999,1001)]),'EXPIRED_UNRESOLVED'); check('simultaneous conflicting close',rev([r(94,1010,1011),r(111,1010,1011)]),'EXPIRED_UNRESOLVED'); check('deadline inclusive',rev([r(94,1099,1100)]),'REFUTED'); check('unmet confirm not proof refute',rev([r(102,1010,1011)]),'EXPIRED_UNRESOLVED')
    return {'test_count':len(tests),'tests':tests,'scope':'synthetic; structured long hypothesis; scenario loss not loss bound'}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--self-test',action='store_true');a=ap.parse_args()
    if not a.self_test: ap.error('use --self-test')
    print(json.dumps(self_test(),ensure_ascii=False,indent=2))
