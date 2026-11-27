"""R137: observational equivalence and independent complete audit. Synthetic only."""
import argparse, hashlib, json, math, runpy
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parent
PARENTS={'Chappy_Trading_Bounded_Receipt_Gate_Study_v0.1.py':'5fa34efdd009efa1790f4fd41473149f0862a43873ed1eed07b0f4354473678a','Chappy_Trading_Coverage_Monitor_Study_v0.1.py':'7a4b57b376dd80b2373815f07ed99ba4abbeaabb9da8db610f436946a53fc0ac','Chappy_Trading_Admission_Depth_Study_v0.1.py':'30a626a694630da343775db24ad61ddfc3dd222ebfe5837d6ce30688dbe47a8c'}
for p,h in PARENTS.items():
    if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise ValueError(p)
R,C,A=[runpy.run_path(str(ROOT/p)) for p in PARENTS]; H=512; SEEDS=range(137000,137256); MODES=R['MODES']; AUDIT=tuple(range(40,289,8)); K=A['K'][32]
PLAN=dict(parents=PARENTS,horizon=H,seeds=list(SEEDS),reported=[27,7,66],worlds={'good':[90,30,70],'bad':[30,90,10]},modes=MODES,audit=list(AUDIT),threshold=K,scope='iid coupled worlds, exact same receipt history; full support, parent direct authority after32; R130 diagnostic only; independent preselected complete audit source, one existing admission look; hold until pass at288 then allow remaining slots, no subsequent monitor; common observation cost1/slot and sunk qualification fee200, audit extra1/sample, no actual orders')
def world(seed):
    rng=np.random.default_rng(seed); u=rng.integers(0,100,H); v=rng.integers(0,66,H)
    r=np.where(u<27,1,np.where(u<34,0,-1)); y={n:np.where(r>=0,r,(v<k).astype(int)) for n,k in [('good',63),('bad',3)]}
    return r,y

def exact(p,k):return sum(F(math.comb(32,i))*p**i*(1-p)**(32-i) for i in range(k,33))
def study():
    c=Counter(); agg={n:{m:Counter() for m in (*MODES,'HOLD','AUDIT32')} for n in ('good','bad')}; alarms=Counter(); pairs=[]
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    for p,rw,rl in PLAN['worlds'].values():
        ck('exact_receipt_law', F(p*rw,10000)==F(27,100) and F((100-p)*rl,10000)==F(7,100))
    ck('economic_sign',800*.9-1200*.1==600 and 800*.3-1200*.7==-600)
    ck('fixed_audit',len(AUDIT)==32 and K==28 and AUDIT[-1]==288)
    for seed in SEEDS:
        r,ys=world(seed);e=np.ones(H,dtype=bool); ev=[(i,i,1,int(w)) for i,w in enumerate(r,1) if w>=0]; results={};
        for n,y in ys.items():
            ck('truth_consistent',bool(np.all(y[r>=0]==r[r>=0]))); a=R['R']['direct_base'](e,y); acts={}; proofs={}
            for m in MODES:
                if m in ('BOUNDS','FIXED16_BOUNDS'):
                    x,p,s=R['bounded'](e,ev,a,m);ck('gate_oracle',(x,p,s)==R['oracle'](e,ev,a,m))
                else:
                    x,p=R['M']['filter_actions'](e,ev,a,m);ck('gate_oracle',(x,p)==R['M']['oracle'](e,ev,a,m))
                acts[m]=x;proofs[m]=p
            results[n]=(acts.copy(),proofs)
            score=sum(int(y[i-1]) for i in AUDIT); passed=score>=K
            acts['HOLD']=[0]*H;acts['AUDIT32']=[int(passed and t>AUDIT[-1]) for t in range(1,H+1)]
            ck('audit_oracle',passed==(sum(y[np.array(AUDIT)-1])>=K));ck('audit_boundary',not any(acts['AUDIT32'][:288]));ck('budget',a['used']+1<=35)
            for m,x in acts.items():
                ck('authority',all(v<=b for v,b in zip(x,a['actions']))); z=agg[n][m]; z['trades']+=sum(x);z['wins']+=sum(int(w)*v for w,v in zip(y,x));z['net']+=sum((800 if w else -1200)*v for w,v in zip(y,x))-H-200-(32 if m=='AUDIT32' else 0);z['passes']+=int(passed) if m=='AUDIT32' else 0
                wins=sum(int(y[i]) for i,v in enumerate(x) if v); trades=sum(x); ck('account',sum((800 if w else -1200)*v for w,v in zip(y,x))==2000*wins-1200*trades and z['trades']>=z['wins'])
        ck('identical_actions_and_proofs',results['good']==results['bad'])
        for m in C['PLAN']['modes']:
            a,g=C['scan'](e,r,m);ck('monitor_oracle',(a,g)==C['oracle'](e,r,m));alarms[m]+=a is not None
            if m=='BOUNDS':
                for _,_,_,s,ix in g:
                    for y in ys.values():ck('bounds_truth',s=='UNKNOWN' or (s=='ALARM')==(sum(y[i] for i in ix)<=C['K']))
        if seed==SEEDS[0]:
            pairs=dict(receipts=r[:16].tolist(),good=ys['good'][:16].tolist(),bad=ys['bad'][:16].tolist())
        if seed in range(SEEDS.start,SEEDS.start+16):
            cut=256
            for m in MODES:
                a=R['R']['direct_base'](e[:cut],ys['good'][:cut]);ev2=[v for v in ev if v[0]<=cut]
                if m in ('BOUNDS','FIXED16_BOUNDS'):x,p,_=R['bounded'](e[:cut],ev2,a,m)
                else:x,p=R['M']['filter_actions'](e[:cut],ev2,a,m)
                ck('future_prefix',x==results['good'][0][m][:cut] and p=={t:w for t,w in results['good'][1][m].items() if t<=cut})
    exacts={}
    for p in (F(3,10),F(6,10),F(9,10)):
        v=exact(p,K); q=sum(F(math.comb(32,j))*(1-p)**j*p**(32-j) for j in range(33-K));ck('exact_audit_oracle',v==q);exacts[str(p)]=float(v)
    ck('audit_alpha',exact(F(6,10),K)<=F(1,700))
    out={n:{m:dict(z,mean_net=z['net']/len(SEEDS),mean_trades=z['trades']/len(SEEDS),win_rate=z['wins']/max(1,z['trades'])) for m,z in a.items()} for n,a in agg.items()}
    return dict(passed=sum(c.values()),checks=dict(c)),dict(plan=PLAN,plan_sha=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest(),cases=out,alarm_counts=dict(alarms),pair_example=pairs,exact_audit_pass=exacts,population_identified_interval=[.27,.93],expected_per_trade={'good':600,'bad':-600})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='.');a=p.parse_args();t,e=study();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
    for n,z in [('tests',t),('examples',e)]:(o/f'Trading_Round137_{n}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(t)
