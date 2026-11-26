"""R147: fixed candidate, fixed known costs, synthetic exact diagnostic only."""
import hashlib,json,math,runpy
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
from functools import lru_cache
import numpy as np
from scipy.stats import binom,nbinom
P=Path(__file__).with_name('Chappy_Trading_Core_Cost_Comparison_v0.1.py')
HASH='40587dff6323c193833bb4b72ad68b8d1361ce511cc110aeee1254e5733e8c3d'
if hashlib.sha256(P.read_bytes()).hexdigest()!=HASH:raise ValueError('parent hash')
R=runpy.run_path(str(P)); A=R['A'];
PLAN=dict(parent=HASH,costs=[200,400],p=[60,65,70,72,75,80,90],freq=[.01,.05,.25,1.],horizons=[256,1024,4096,7168,16384],observation_fee=1,gross=1000,alpha_per_look='1/200',scope='one frozen candidate, after training, no refresh, no cash constraint, all-calendar observation fee; no new policy')
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()
@lru_cache(None)
def clock(n,f,h):
    usable=float(binom.sf(n-1,h-1,f)); reached=float(binom.sf(n-1,h,f))
    rem=max(0.,h*reached-n/f*float(binom.sf(n,h+1,f)))
    return usable,rem

def study():
    checks=Counter(); rows=[]; evidence=[]
    def ck(k,v):
        if not v:raise AssertionError(k)
        checks[k]+=1
    for cost in PLAN['costs']:
        k,_=R['bounds'](cost)
        for p in PLAN['p']:
            hits,fail=A['exact'](p,k);ck('independent_exact',(hits,fail)==A['reference'](p,k));ck('probability_mass',sum(v for _,v in hits)+fail==1)
            if p<=(1000+cost)/20:ck('null_union',1-fail<=F(5,200))
            evidence.append(dict(cost=cost,p=p,pass_probability=float(1-fail),mean_eligible_if_pass=float(sum(n*v for n,v in hits)/(1-fail)),first_pass={n:float(v) for n,v in hits}))
            for f in PLAN['freq']:
                for h in PLAN['horizons']:
                    usable=math.fsum(float(v)*clock(n,f,h)[0] for n,v in hits)
                    live=math.fsum(float(v)*clock(n,f,h)[1] for n,v in hits)
                    # R100 calendar formula checked independently by negative binomial enumeration.
                    ref=0.; refp=0.
                    for n,v in hits:
                        t=np.arange(n,h+1);mass=nbinom.pmf(t-n,n,f)
                        ref+=float(v)*float((h-t)@mass);refp+=float(v)*float(mass[t<h].sum())
                    ck('calendar_probability',abs(usable-refp)<1e-10);ck('calendar_remaining',abs(live-ref)<1e-6)
                    edge=20*p-1000-cost; trades=f*live; net=edge*trades-h
                    ck('time_bound',0<=live<=h+1e-7 and usable<=float(1-fail)+1e-10)
                    ck('accounting',abs(net-(edge*f*ref-h))<1e-6)
                    rows.append(dict(cost=cost,p=p,freq=f,horizon=h,usable_probability=usable,expected_live_slots=live,expected_trades=trades,expected_net=net,hold_net=-h,oracle_always_net=edge*f*h-h,delta_hold=edge*trades))
    # At most H-1 observations are usable; deterministic fixture.
    ck('last_boundary',clock(16,1.,16)==(0.,0.));ck('next_slot',clock(16,1.,17)==(1.,1.))
    return dict(plan=PLAN,plan_sha=SHA,checks=dict(checks),passed=sum(checks.values()),evidence=evidence,rows=rows)
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2))
