"""R88: fixed looks vs one-shot screening, synthetic independent blocks only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
from itertools import product
from fractions import Fraction as F
import numpy as np
from scipy.stats import binom
P=Path(__file__).with_name('Chappy_Trading_Evidence_Lifetime_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='f274f4dd7d2fbb598f883178edd771fe86483a61dde67adaa10310540ab50c4d': raise ValueError('R87 hash')
R=runpy.run_path(str(P))
LOOKS=(16,32,64,128,256)
POL={'FIXED':((256,5),),'NAIVE':tuple((b,5) for b in LOOKS),'SPEND':tuple((b,1) for b in LOOKS)}
PARAM={m:R['params'](m) for m in R['MODES']}
PARAM.update(boundary=(.625,.6,0.0))
H=(160,640,1280,2560,10240); FEES=(0,10)
PLAN=dict(looks=LOOKS,policies=POL,null_hit_rate='3/5',block_slots=5,warmup=4,horizons=H,fees=FEES,synthetic_only=True,stop_at_first_pass=True,observe_until_pass_or_max_or_horizon=True,independent_evaluation=True,never_select_best_setting=True)
def cutoff(n,alpha):
    # Exact integer binomial tail under q=3/5, percent alpha.
    den=5**n; tail=0; k=n+1
    for i in range(n,-1,-1):
        tail+=math.comb(n,i)*3**i*2**(n-i)
        if 100*tail<=alpha*den: k=i
        else: break
    return k
K={a:np.array([cutoff(n,a) for n in range(257)]) for a in (1,5)}
def first_pass(t,q,schedule):
    # state indexed by wins and losses; no-action leaves both unchanged.
    d=np.ones((1,1)); hits={}; alpha=dict(schedule); masses=[]
    for b in range(1,max(alpha)+1):
        z=np.zeros((b+1,b+1)); z[:-1,:-1]+=d*(1-t); z[1:,:-1]+=d*t*q; z[:-1,1:]+=d*t*(1-q); d=z
        if b in alpha:
            w,l=np.indices(d.shape); n=w+l; mask=(n<=b)&(w>=K[alpha[b]][np.minimum(n,256)])
            hits[b]=float(d[mask].sum()); d[mask]=0
        masses.append(float(d.sum()))
    return hits,masses
D={(m,p):first_pass(*PARAM[m][:2],s) for m,p,s in [(m,p,POL[p]) for m,p in product(PARAM,POL)]}
def evaluate(m,p,h,fee):
    hits,survival=D[m,p]; max_b=POL[p][-1][0]; stop=min(max_b,h//5); e=PARAM[m][2]
    # Charge complete observation blocks even if the regime ends before a pass.
    eb=math.fsum([1.0]+survival[:stop-1]) if stop else 0.0
    admitted=math.fsum(v for b,v in hits.items() if b<=stop)
    usable=math.fsum(v for b,v in hits.items() if 5*b+4<h)
    gross=math.fsum(v*max(0,h-5*b-4)*e for b,v in hits.items() if b<=stop)
    return dict(mode=m,policy=p,horizon=h,fee=fee,pass_probability=admitted,usable_probability=usable,expected_blocks=eb,expected_observation_fee=eb*fee,expected_net_yen=gross-eb*fee)
def examples():
    return dict(plan=PLAN,plan_sha=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest(),params=PARAM,first_pass=[dict(mode=m,policy=p,probabilities=hits,total=math.fsum(hits.values()),conditional_blocks=math.fsum(b*v for b,v in hits.items())/math.fsum(hits.values()) if math.fsum(hits.values()) else None) for (m,p),(hits,_) in D.items()],rows=[evaluate(*x) for x in product(PARAM,POL,H,FEES)])
def tests():
    c={}
    def ck(n,x):
        if not x: raise AssertionError(n)
        c[n]=c.get(n,0)+1
    for a in K:
        for n,k in enumerate(K[a]):
            tail=lambda j:sum(math.comb(n,i)*3**i*2**(n-i) for i in range(j,n+1))
            ck('threshold_valid',100*tail(k)<=a*5**n); ck('threshold_minimal',100*tail(k-1)>a*5**n)
            if a==5: ck('R87_threshold',k==R['TH'][256,60][n])
    for (m,p),(hits,surv) in D.items():
        t,q,e=PARAM[m]; prev=1
        for b,s in enumerate(surv,1):
            ck('mass_conservation',abs(s+math.fsum(v for j,v in hits.items() if j<=b)-1)<1e-11)
            ck('survival_nonincreasing',s<=prev+1e-13); ck('first_pass_mass',abs(prev-s-hits.get(b,0))<1e-12); prev=s
        if p=='FIXED':
            n=np.arange(257); expected=float(np.dot(binom.pmf(n,256,t),binom.sf(K[5]-1,n,q)))
            ck('fixed_direct',abs(expected-hits[256])<1e-11)
            if m in R['MODES']: ck('R87_power',abs(hits[256]-R['POW'][m,256,60])<1e-11)
        if p=='SPEND' and q<=.6: ck('union_bound',math.fsum(hits.values())<=.05+1e-12)
    # independent brute force paths with short schedules and exact Fraction weights
    for t,q in [(F(1,2),F(1,2)),(F(3,4),F(3,5)),(F(3,4),F(9,10))]:
        sched=((3,5),(6,5)); h,_=first_pass(float(t),float(q),sched); oracle={b:F(0) for b,_ in sched}
        for seq in product(range(3),repeat=6):
            weight=math.prod([(1-t,t*q,t*(1-q))[z] for z in seq]); w=l=0
            for b,z in enumerate(seq,1):
                w+=z==1; l+=z==2
                if b in dict(sched) and w>=cutoff(w+l,dict(sched)[b]): oracle[b]+=weight; break
        for b in oracle: ck('path_enumeration',abs(h[b]-float(oracle[b]))<1e-12)
    for m,p,h,f in product(PARAM,POL,H,FEES):
        row=evaluate(m,p,h,f); hits,_=D[m,p]; end=min(h//5,POL[p][-1][0]); e=PARAM[m][2]
        eb=sum(b*v for b,v in hits.items() if b<=end)+end*(1-sum(v for b,v in hits.items() if b<=end))
        ck('expected_blocks',abs(eb-row['expected_blocks'])<1e-9)
        ck('net',abs(row['expected_net_yen']-(sum(v*max(0,h-5*b-4)*e for b,v in hits.items() if b<=end)-eb*f))<1e-7)
        ck('usable_subset',row['usable_probability']<=row['pass_probability']+1e-13)
    return dict(passed=sum(c.values()),counts=c)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
