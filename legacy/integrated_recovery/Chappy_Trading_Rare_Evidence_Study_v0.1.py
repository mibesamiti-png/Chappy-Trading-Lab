"""R100: fixed frozen selective candidate; evidence clock versus calendar clock. Synthetic only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
from itertools import product
import numpy as np
from scipy.stats import binom, nbinom
from functools import lru_cache
ROOT=Path(__file__).parent

def load(name,sha):
    p=ROOT/name
    if hashlib.sha256(p.read_bytes()).hexdigest()!=sha: raise ValueError(name+' hash')
    return runpy.run_path(str(p))
R=load('Chappy_Trading_Sequential_Gate_Study_v0.1.py','cbd53caad43237dfc40fadf0a569cba582ca3f2f78fd89af0bb91ada2adea9af')
S=load('Chappy_Trading_Selective_Hypothesis_Study_v0.1.py','da45cbba59a269bc24379e0fffa7060562fdd1e0ed5e3c0681552cecb8dd1854')
POL={'FIXED32':((32,5),),'FIXED64':((64,5),),'FIXED256':R['POL']['FIXED'],'NAIVE':R['POL']['NAIVE'],'SPEND':R['POL']['SPEND']}
FREQ=(.01,.05,.25); Q=(.5,.6,.7,.9); H=(256,1024,4096,16384); FEES=(0,.1,1,10)
PLAN=dict(synthetic_only=True,frozen_candidate=True,policies=POL,frequencies=FREQ,hit_rates=Q,calendar_horizons=H,fees_yen_per_calendar_slot=FEES,notional=100000,win_yen=800,loss_yen=-1200,no_retest=True,independent_hits_and_arrivals=True,learning_cost_excluded=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
# R88's selected-observation clock, no skipped observations on that clock.
D={(q,p):R['first_pass'](1.,q,s)[0] for q,p in product(Q,POL) for s in [POL[p]]}
@lru_cache(None)
def calendar(k,f,h):
    # T_k = calendar slot at kth eligible observation. Truncated remaining time.
    prob=float(binom.sf(k-1,h,f))
    rem=max(0.,h*prob-k/f*float(binom.sf(k,h+1,f)))
    return prob,rem

def evaluate(q,p,f,h,fee):
    hits=D[q,p]; last=POL[p][-1][0]; total=math.fsum(hits.values()); fail=max(0.,1-total)
    passed=math.fsum(v*calendar(k,f,h)[0] for k,v in hits.items())
    usable=math.fsum(v*calendar(k,f,h-1)[0] for k,v in hits.items())
    remaining=math.fsum(v*calendar(k,f,h)[1] for k,v in hits.items())
    observed=h-remaining-fail*calendar(last,f,h)[1]
    e=f*(2000*q-1200)
    return dict(q=q,policy=p,freq=f,horizon=h,fee=fee,pass_probability=passed,usable_probability=usable,expected_observation_slots=observed,expected_live_slots=remaining,expected_net_yen=remaining*e-observed*fee)

def tests():
    c={}
    def ck(k,b):
        if not b: raise AssertionError(k)
        c[k]=c.get(k,0)+1
    for k in range(257):ck('R99_cutoff',R['cutoff'](k,5)==S['cutoff'](k))
    for q,p in D:
        hits=D[q,p];ck('mass',0<=sum(hits.values())<=1+1e-12)
        if q<=.6 and p!='NAIVE':ck('false_accept_bound',sum(hits.values())<=.05+1e-12)
        if p.startswith('FIXED'):
            k=POL[p][0][0];ck('direct_binomial',abs(hits[k]-binom.sf(R['cutoff'](k,5)-1,k,q))<1e-12)
    for k,f,h in product((1,16,32,64,128,256),FREQ,H):
        prob,rem=calendar(k,f,h);t=np.arange(k,h+1);pmf=nbinom.pmf(t-k,k,f)
        ck('calendar_probability',abs(prob-float(pmf.sum()))<1e-10)
        ck('calendar_remaining',abs(rem-float((h-t)@pmf))<1e-6)
    for q,p,f,h,fee in product(Q,POL,FREQ,H,FEES):
        row=evaluate(q,p,f,h,fee);hits=D[q,p];last=POL[p][-1][0]
        # Independent calendar survival sums for truncated stop time.
        t=np.arange(h);stop=math.fsum(v*float(binom.cdf(k-1,t,f).sum()) for k,v in hits.items())+max(0,1-sum(hits.values()))*float(binom.cdf(last-1,t,f).sum())
        ck('observation_time',abs(stop-row['expected_observation_slots'])<1e-6)
        ck('net',abs(row['expected_net_yen']-(row['expected_live_slots']*f*(2000*q-1200)-stop*fee))<1e-5)
        ck('time_budget',row['expected_observation_slots']+row['expected_live_slots']<=h+1e-7)
        ck('usable_subset',row['usable_probability']<=row['pass_probability']+1e-12)
    # exact finite path enumeration with reduced schedule, arrival independent of win.
    from fractions import Fraction as F
    f=F(1,2);q=F(3,4);H0=8
    # R88 precomputed cutoff table only supports alpha 1,5; use 5% and k>=4.
    sched=((6,5),(8,5));hits=R['first_pass'](1,float(q),sched)[0]
    expected=sum(v*calendar(k,float(f),H0)[1] for k,v in hits.items())
    direct=F(0)
    for seq in product(range(3),repeat=H0):
        w=n=0;weight=math.prod((1-f,f*q,f*(1-q))[z] for z in seq)
        for t,z in enumerate(seq,1):
            n+=z!=0;w+=z==1
            if z and n in dict(sched) and w>=R['cutoff'](n,5):direct+=weight*(H0-t);break
    ck('finite_paths',direct>0 and abs(expected-float(direct))<1e-12)
    return dict(passed=sum(c.values()),counts=c,plan_sha=SHA)
def examples():
    return dict(plan=PLAN,plan_sha=SHA,first_pass=[dict(q=q,policy=p,probability=sum(h.values()),conditional_observations=sum(k*v for k,v in h.items())/sum(h.values()) if sum(h.values()) else None,by_observation=h) for (q,p),h in D.items()],rows=[evaluate(*a) for a in product(Q,POL,FREQ,H,FEES)])
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
