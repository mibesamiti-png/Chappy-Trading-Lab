"""R82: synthetic common-evidence monitoring; no live data or orders."""
import argparse,hashlib,json,runpy
from pathlib import Path
from itertools import product
from fractions import Fraction as F
P=Path(__file__).with_name('Chappy_Trading_Knowledge_Refresh_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='620529a8bd827e567e6cb30a45575cf46b206b27b70f6e7cbdf27598279de707':raise ValueError('R81 hash')
R81=runpy.run_path(str(P)); digest=R81['digest']
PLAN={'slots':60,'direction':1,'delay':3,'window':4,'notional':100000,'baseline_cost':20,'low_magnitude_bps':25,'policies':['FIXED','GROSS_OLD','GROSS_ZERO','NET','DIAGNOSTIC','WAIT'],'shadow_observation':'all slots, assumed free; missing is explicit','warmup':'monitored policies wait until four scheduled mature results available','decision':'fixed direction only; no automatic refresh or reversal'}
NAMES=['stable','persistent_shift','temporary_shift','flat_shift','rapid_shift','small_move','cost_shock','missing','mixed']
def truth(n,i):
    if n in R81['NAMES']:return R81['truth'](n,i)
    b=R81['truth']('stable',i)
    if n=='small_move' and i>=20:return b//10
    if n=='mixed' and i>=20:return -b//10
    return b
def cost(n,i):return 80 if n in ('cost_shock','mixed') and i>=20 else 20
def receipt(n,i):return None if n=='missing' and 20<=i<30 and i%2==0 else {'index':i,'received':i+3,'bps':truth(n,i)}
def decide(p,i,c,receipts):
    ids=list(range(max(0,i-6),i-2)) if i>=3 else []
    visible={r['index']:r['bps'] for r in receipts if r['received']<=i and r['index'] in ids}
    evidence=sorted(visible); vals=[visible[j] for j in evidence]
    d={'action':'WAIT','evidence':evidence,'gross_sum':None,'net_sum':None,'reason':'INSUFFICIENT','flags':[]}
    if len(ids)==4 and len(vals)==4:
        s=sum(vals); net=s-4*c; flags=[]
        if sum(v<0 for v in vals)>sum(v>0 for v in vals):flags.append('ADVERSE_DIRECTION_MAJORITY')
        if sum(abs(v) for v in vals)<=4*PLAN['low_magnitude_bps']:flags.append('LOW_MAGNITUDE')
        if s>0 and net<=0:flags.append('COST_EXCEEDS_GROSS')
        if c>PLAN['baseline_cost']:flags.append('HIGHER_COST')
        trade={'GROSS_OLD':s>-200,'GROSS_ZERO':s>0,'NET':net>0,'DIAGNOSTIC':net>0}.get(p,False)
        d.update(action='TRADE' if trade else 'WAIT',gross_sum=s,net_sum=net,reason='PASS' if trade else 'PAUSE',flags=flags if p=='DIAGNOSTIC' else [])
    if p=='FIXED':d.update(action='TRADE',reason='FIXED')
    if p=='WAIT':d.update(action='WAIT',reason='WAIT')
    return d
def simulate(n,p):
    rec=[r for i in range(60) if (r:=receipt(n,i)) is not None];rows=[]
    for i in range(60):
        c=cost(n,i);d=decide(p,i,c,rec);v=truth(n,i)
        rows.append(dict(d,index=i,cost_bps=c,truth_bps=v,net_yen=10*(v-c) if d['action']=='TRADE' else 0))
    return {'records':rows,'summary':{'net_yen':sum(r['net_yen'] for r in rows),'trades':sum(r['action']=='TRADE' for r in rows),'waits':sum(r['action']=='WAIT' for r in rows),'post20_trades':sum(r['action']=='TRADE' for r in rows[20:]),'post20_net':sum(r['net_yen'] for r in rows[20:])}}
def examples():return {'synthetic_only':True,'plan':PLAN,'plan_sha':digest(PLAN),'cases':{n:{p:simulate(n,p) for p in PLAN['policies']} for n in NAMES}}
def tests():
    checks=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        checks.append({'name':n,'pass':True})
    for n,p in product(NAMES,PLAN['policies']):
        a=simulate(n,p); rows=a['records']; rec=[r for i in range(60) if (r:=receipt(n,i)) is not None]
        for i,r in enumerate(rows):
            tag=f'{n}:{p}:{i}:'; c=cost(n,i); prefix=[q for q in rec if q['received']<=i]; future=[q for q in rec if q['received']>i]
            d=decide(p,i,c,prefix)
            ck(tag+'prefix',d,{k:v for k,v in r.items() if k not in ('index','cost_bps','truth_bps','net_yen')});ck(tag+'future',d,decide(p,i,c,prefix+[{**q,'bps':99999} for q in future]));ck(tag+'order',d,decide(p,i,c,prefix[::-1]))
            expected=[j for j in range(60) if i-6<=j<=i-3 and receipt(n,j) is not None];ck(tag+'evidence',r['evidence'],expected)
            vs=[truth(n,j) for j in expected]; ready=len(vs)==4; s=sum(vs)
            ck(tag+'gross',r['gross_sum'],s if ready else None);ck(tag+'net',r['net_sum'],s-4*c if ready else None)
            trade=p=='FIXED' or (ready and ((p=='GROSS_OLD' and s>-200) or (p=='GROSS_ZERO' and s>0) or (p in ('NET','DIAGNOSTIC') and F(s,4)>c)))
            ck(tag+'trade',r['action']=='TRADE',trade);ck(tag+'pnl',r['net_yen'],100000*(truth(n,i)-c)//10000 if trade else 0)
        ck(n+p+'sum',a['summary']['net_yen'],sum(r['net_yen'] for r in rows));ck(n+p+'partition',a['summary']['trades']+a['summary']['waits'],60)
    for vals in product((-100,-10,0,10,100),repeat=4):
        for c in (20,80):
            rec=[dict(index=j,received=j+3,bps=v) for j,v in enumerate(vals)];d=decide('DIAGNOSTIC',6,c,rec);s=sum(vals);tag=str(vals)+str(c)
            ck(tag+'net gate',d['action']=='TRADE',F(s,4)>c);ck(tag+'cost flag','COST_EXCEEDS_GROSS' in d['flags'],0<F(s,4)<=c);ck(tag+'direction flag','ADVERSE_DIRECTION_MAJORITY' in d['flags'],sum(v<0 for v in vals)>sum(v>0 for v in vals));ck(tag+'magnitude flag','LOW_MAGNITUDE' in d['flags'],F(sum(map(abs,vals)),4)<=25)
    for n in NAMES:ck(n+'same decisions NET/DIAGNOSTIC',[r['action'] for r in simulate(n,'NET')['records']],[r['action'] for r in simulate(n,'DIAGNOSTIC')['records']])
    return {'passed':len(checks),'tests':checks}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
