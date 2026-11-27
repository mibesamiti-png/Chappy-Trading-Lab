"""R83: synthetic diagnostic-conditioned response, not live trading."""
import argparse, hashlib, json, runpy
from pathlib import Path
from itertools import product
from fractions import Fraction as F
P=Path(__file__).with_name('Chappy_Trading_Economic_Monitor_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='e3e830034f1e13382232ebe6d5658ff38722e36570ab0e34210ab294abe919d4': raise ValueError('R82 hash')
R=runpy.run_path(str(P)); digest=R['digest']
POLICIES=('FIXED','PAUSE','SYMMETRIC','TARGETED','WAIT')
NAMES=R['NAMES']+['rare_adverse','rare_favorable']
PLAN={'slots':60,'policies':POLICIES,'window':4,'delay':3,'notional':100000,'cost':'R82 known current cost','evidence':'same free shadow observations for every policy','targeted':'reverse only if opposite net mean positive AND adverse majority AND not low magnitude; missing requests recovery without simulating recovery','response':'one-slot decisions; no persistent learning, actual recovery or order execution','extra_fixtures':'after slot 20 repeat [10,10,10,-400] or [-10,-10,-10,400]'}
def truth(n,i):
    if n in R['NAMES']: return R['truth'](n,i)
    if i<20: return R['truth']('stable',i)
    return ([10,10,10,-400] if n=='rare_adverse' else [-10,-10,-10,400])[(i-20)%4]
def cost(n,i): return R['cost'](n,i)
def receipts(n):
    return [dict(index=i,received=i+3,bps=truth(n,i)) for i in range(60) if not(n=='missing' and 20<=i<30 and i%2==0)]
def decide(p,i,c,rec):
    d=R['decide']('DIAGNOSTIC',i,c,rec); s=d['gross_sum']; flags=d['flags']; action=0; response='WAIT'
    if p=='FIXED': action=1; response='KEEP'
    elif p=='WAIT': pass
    elif s is None: response='RECOVERY_REQUEST' if i>=6 else 'WARMUP'
    elif s>4*c: action=1; response='KEEP'
    elif p in ('SYMMETRIC','TARGETED') and -s>4*c and (p=='SYMMETRIC' or ('ADVERSE_DIRECTION_MAJORITY' in flags and 'LOW_MAGNITUDE' not in flags)):
        action=-1; response='REVERSE_CANDIDATE'
    elif p=='TARGETED' and -s>4*c: response='CONFLICT_REVIEW'
    else: response='ECONOMIC_PAUSE'
    return dict(evidence=d['evidence'],gross_sum=s,flags=flags,action=action,response=response)
def simulate(n,p):
    rec=receipts(n); rows=[]
    for i in range(60):
        c=cost(n,i); d=decide(p,i,c,rec); a=d['action']; v=truth(n,i)
        rows.append(dict(d,index=i,cost_bps=c,truth_bps=v,net_yen=10*(a*v-c) if a else 0))
    return {'records':rows,'summary':{'net_yen':sum(r['net_yen'] for r in rows),'post20_net':sum(r['net_yen'] for r in rows[20:]),'forward':sum(r['action']==1 for r in rows),'reverse':sum(r['action']==-1 for r in rows),'wait':sum(r['action']==0 for r in rows),'recovery_requests':sum(r['response']=='RECOVERY_REQUEST' for r in rows),'conflict_reviews':sum(r['response']=='CONFLICT_REVIEW' for r in rows)}}
def examples():return {'synthetic_only':True,'plan':PLAN,'plan_sha':digest(PLAN),'cases':{n:{p:simulate(n,p) for p in POLICIES} for n in NAMES}}
def tests():
    checks=[]
    def ck(n,a,b):
        if a!=b: raise AssertionError((n,a,b))
        checks.append({'name':n,'pass':True})
    for n,p in product(NAMES,POLICIES):
        out=simulate(n,p); rec=receipts(n); rows=out['records']
        for i,r in enumerate(rows):
            tag=f'{n}:{p}:{i}:'; c=cost(n,i); prefix=[q for q in rec if q['received']<=i]; future=[dict(q,bps=99999) for q in rec if q['received']>i]; d=decide(p,i,c,prefix)
            ck(tag+'prefix',d,decide(p,i,c,rec));ck(tag+'future',d,decide(p,i,c,prefix+future));ck(tag+'order',d,decide(p,i,c,prefix[::-1]))
            ids=[j for j in range(max(0,i-6),max(0,i-2)) if any(q['index']==j for q in prefix)]; vals=[truth(n,j) for j in ids]; ready=len(ids)==4; m=F(sum(vals),4) if ready else None
            ck(tag+'ids',d['evidence'],ids)
            a=1 if p=='FIXED' else 0
            if p not in ('FIXED','WAIT') and ready:
                if m>c:a=1
                elif m< -c and (p=='SYMMETRIC' or p=='TARGETED' and sum(v<0 for v in vals)>sum(v>0 for v in vals) and F(sum(map(abs,vals)),4)>25):a=-1
            ck(tag+'action',r['action'],a);ck(tag+'pnl',r['net_yen'],int(F(100000*(a*truth(n,i)-c),10000)) if a else 0)
            ck(tag+'recovery',r['response']=='RECOVERY_REQUEST',p not in ('FIXED','WAIT') and i>=6 and not ready)
        ck(n+p+'partition',sum(out['summary'][k] for k in ('forward','reverse','wait')),60)
        if n in R['NAMES'] and p=='PAUSE':ck(n+'R82 reproduction',out['summary']['net_yen'],R['simulate'](n,'NET')['summary']['net_yen'])
    for vals in product((-400,-100,-10,0,10,100,400),repeat=4):
        rec=[dict(index=j,received=j+3,bps=v) for j,v in enumerate(vals)]
        for c in (20,80):
            m=F(sum(vals),4); a=decide('SYMMETRIC',6,c,rec)['action']; b=decide('TARGETED',6,c,rec)['action']; tag=str(vals)+str(c)
            ck(tag+'symmetric',a,1 if m>c else -1 if m< -c else 0)
            ck(tag+'targeted',b,1 if m>c else -1 if m< -c and sum(v<0 for v in vals)>sum(v>0 for v in vals) and sum(map(abs,vals))>100 else 0)
            ck(tag+'subset',b in (0,a),True)
    return {'passed':len(checks),'tests':checks}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
