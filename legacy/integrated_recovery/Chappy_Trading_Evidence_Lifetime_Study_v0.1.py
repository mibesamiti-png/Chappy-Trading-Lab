"""R87: fixed one-shot gates, observation time and finite synthetic regime lifetime."""
import argparse, hashlib, json, math, runpy
from fractions import Fraction as F
from pathlib import Path
from itertools import product
import numpy as np
from scipy.stats import binom
P=Path(__file__).with_name('Chappy_Trading_Statistical_Gate_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='27df717768cc5ada8d11f7d53ede615c24399eb125c68d2b29e2883503ee6b8b':raise ValueError('R86 hash')
R=runpy.run_path(str(P))
MODES=('iid','weak','moderate','strong'); B=(16,32,64,128,256,512,1024,2048,4096); H=(160,640,2560,10240,40960); G=(50,60); FEES=(0,10)
PLAN=dict(blocks=B,horizons=H,gates=G,alpha='1/20',block_slots=5,eval_warmup=4,observation_fee_yen_per_block=FEES,shift='after horizon, independent iid stream, 256 evaluation slots',candidate='R86 SYMMETRIC',modes=MODES,synthetic_only=True,one_shot=True,never_select_best_setting=True)
PARAM={m:R['exact'](m) for m in MODES}
# numerical binomial quantile; verify the tail and its adjacent threshold.
def thresholds(b,g):
    n=np.arange(b+1); p=g/100
    k=binom.isf(.05,n,p).astype(int)+1
    # Make threshold robust to quantile rounding.
    while np.any(binom.sf(k-1,n,p)>.05):k+=binom.sf(k-1,n,p)>.05
    while np.any((k>0)&(binom.sf(k-2,n,p)<=.05)):k-=((k>0)&(binom.sf(k-2,n,p)<=.05))
    return k
TH={(b,g):thresholds(b,g) for b,g in product(B,G)}
def power(b,g,t,q):
    n=np.arange(b+1); k=TH[b,g]
    return float(np.clip(np.dot(binom.pmf(n,b,t),binom.sf(k-1,n,q)),0,1))
def params(m):
    p=PARAM[m];return float(F(p['trade_probability'])),float(F(p['accuracy'])),float(F(p['expected_yen_per_mature_slot']))
POW={(m,b,g):power(b,g,*params(m)[:2]) for m,b,g in product(MODES,B,G)}
def evaluate(m,b,g,h,fee):
    t,q,e=params(m);p=POW[m,b,g]; duration=5*b; mature=max(0,h-duration-4)
    # No test is started if it cannot leave any mature evaluation opportunity.
    feasible=mature>0
    spent=b*fee if feasible else 0
    return dict(mode=m,blocks=b,gate=g,horizon=h,fee=fee,calibration_slots=duration,mature_eval_slots=mature,feasible=feasible,power=p if feasible else None,expected_net_yen=p*mature*e-spent if feasible else 0,expected_ungated_yen=max(0,h-4)*e,expected_fee=spent,expected_stale_yen=p*252*params('iid')[2]-b*fee)
def examples():
    return dict(plan=PLAN,plan_sha=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest(),theory=PARAM,powers=[dict(mode=m,blocks=b,gate=g,power=POW[m,b,g]) for m,b,g in product(MODES,B,G)],rows=[evaluate(*x) for x in product(MODES,B,G,H,FEES)])
def tests():
    counts={}
    def ck(n,ok):
        if not ok:raise AssertionError(n)
        counts[n]=counts.get(n,0)+1
    for (b,g),k in TH.items():
        n=np.arange(b+1);p=g/100
        ck('threshold_valid',np.all(binom.sf(k-1,n,p)<=.05));ck('threshold_minimal',np.all(binom.sf(k-2,n,p)>.05));ck('threshold_range',np.all((k>=1)&(k<=n+1)))
        if b<=256:
            for i,j in enumerate(k):ck('R86_exact_threshold',j==R['TH'][g][i])
    for m,b,g in product(MODES,B,G):
        p=POW[m,b,g];t,q,e=params(m);ck('power_range',0<=p<=1)
        if b==256:ck('R86_power',abs(p-PARAM[m][f'gate{g}_power'])<1e-10)
        if b<=32:
            k=TH[b,g];direct=math.fsum(math.comb(b,n)*t**n*(1-t)**(b-n)*math.fsum(math.comb(n,i)*q**i*(1-q)**(n-i) for i in range(k[n],n+1)) for n in range(b+1));ck('direct_power',abs(p-direct)<1e-12)
        if q<=g/100:ck('null_size',p<=.05+1e-12)
    for m,b in product(MODES,B):ck('nested_power',POW[m,b,60]<=POW[m,b,50]+1e-12)
    for x in product(MODES,B,G,H,FEES):
        m,b,g,h,fee=x;r=evaluate(*x);t,q,e=params(m);remaining=h-5*b-4
        ck('time_budget',r['mature_eval_slots']==max(0,remaining));ck('feasibility',r['feasible']==(remaining>0));ck('fee',r['expected_fee']==(b*fee if remaining>0 else 0));ck('economic',abs(r['expected_net_yen']-(POW[m,b,g]*remaining*e-b*fee if remaining>0 else 0))<1e-8);ck('stale',r['expected_stale_yen']<=0);ck('baseline',abs(r['expected_ungated_yen']-(h-4)*e)<1e-8)
    return dict(passed=sum(counts.values()),counts=counts)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
