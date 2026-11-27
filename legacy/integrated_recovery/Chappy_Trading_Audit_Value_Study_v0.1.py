"""R138: fixed audit cost, delay, missingness. Synthetic only; no market inputs."""
import argparse, hashlib, json, math, runpy
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parent
PARENT='Chappy_Trading_Observation_Identity_Study_v0.1.py'
SHA='fa4add9b464bb226e8a66ceb33c4d55eb654e36d6900a18da66243fc8f434411'
if hashlib.sha256((ROOT/PARENT).read_bytes()).hexdigest()!=SHA: raise ValueError('parent hash')
R=runpy.run_path(str(ROOT/PARENT)); H=R['H']; A=R['AUDIT']; K=R['K']; N=len(A)
SEEDS=range(138000,138512); COST=(1,100,1000,3000); DELAY=(0,32,128,256)
# Percent probability of receipt conditional on win/loss. No incorrect reports.
SOURCES={'complete':(100,100),'missing10':(90,90),'missing25':(75,75),'loss_missing':(100,10),'win_missing':(75,100)}
PLAN=dict(parent=SHA,horizon=H,audit=list(A),threshold=K,seeds=list(SEEDS),cost=COST,delay=DELAY,sources=SOURCES,priors=[.1,.5,.9],scope='fixed preselected audit; all 32 purchased even if late; one look if completion strictly before horizon, unknown not wins; HOLD until pass; fixed cost and same sunk base as R137; no post-admission monitor')
def exact(p,r): return R['exact'](p*r,K)
def oracle(p,r):
    q=p*r; d=[F(1)]
    for _ in A:
        a=[F(0)]*(len(d)+1)
        for k,v in enumerate(d):a[k]+=v*(1-q);a[k+1]+=v*q
        d=a
    return sum(d[K:])
def decision(w,r,delay):
    t=A[-1]+delay
    # All reports arriving on the boundary precede the admission; no horizon admission.
    return t if t<H and sum(int(x==1 and v) for x,v in zip(w,r))>=K else None

def study():
    c=Counter(); rows=[]; samples={}; ps={'good':F(9,10),'bad':F(3,10)}; base=-H-200
    def ck(k,b):
        if not b: raise AssertionError(k)
        c[k]+=1
    ck('fixed_parent',N==32 and K==28 and A[-1]==288)
    # Common random draws for every cost/delay/source, coupled worlds inherited from R137.
    for seed in SEEDS:
        _,ys=R['world'](seed); rng=np.random.default_rng(seed+1000000); u=rng.integers(0,100,N)
        samples[seed]=(ys,u)
    for name,(rw,rl) in SOURCES.items():
        for delay in DELAY:
            t=A[-1]+delay; rem=max(0,H-t); look=int(t<H)
            for cost in COST:
                worlds={}
                for n,p in ps.items():
                    pr=exact(p,F(rw,100)); ck('exact_dp',pr==oracle(p,F(rw,100)))
                    ck('no_false_evidence',pr<=R['exact'](p,K)); ck('alpha',exact(F(6,10),F(rw,100))<=F(1,700))
                    g=2000*p-1200; prob=pr*look; expected=prob*rem*g-N*cost
                    z=Counter()
                    for seed,(ys,u) in samples.items():
                        y=ys[n]; w=y[np.array(A)-1]; r=u<np.where(w==1,rw,rl); a=decision(w,r,delay)
                        known_wins=int(np.count_nonzero((w==1)&r)); passed=bool(look and known_wins>=K)
                        ck('decision_oracle',(a is not None)==passed);ck('lower_bound',known_wins<=int(w.sum()));ck('budget',34+look<=35)
                        trades=H-a if a is not None else 0; wins=int(y[a:].sum()) if a is not None else 0
                        ck('authority',0<=trades<=rem and (a is None or A[-1]<=a<H));ck('account',2000*wins-1200*trades==sum(800 if x else -1200 for x in (y[a:] if a is not None else [])))
                        z['passes']+=int(passed);z['net']+=base+2000*wins-1200*trades-N*cost;z['trades']+=trades
                    worlds[n]=dict(pass_probability=float(prob),expected_net=float(base+expected),increment_vs_hold=float(expected),mean_net=z['net']/len(SEEDS),passes=z['passes'],mean_trades=z['trades']/len(SEEDS))
                mix={}
                for prior in (F(1,10),F(1,2),F(9,10)):
                    gross=rem*look*(prior*exact(ps['good'],F(rw,100))*600-(1-prior)*exact(ps['bad'],F(rw,100))*600)
                    net=gross-N*cost; mix[str(prior)]=dict(increment_vs_hold=float(net),break_even_per_sample=float(gross/N),expected_net=float(base+net))
                    ck('mixture',abs(float(net)-(float(prior)*worlds['good']['increment_vs_hold']+float(1-prior)*worlds['bad']['increment_vs_hold']))<1e-7)
                rows.append(dict(source=name,delay=delay,cost=cost,remaining=rem,look=look,worlds=worlds,mixture=mix))
    # Exhaustively verify 32-count boundary and final horizon, including all unknown.
    for wins in range(33):
        for unknown in range(33-wins):
            w=[1]*wins+[0]*(32-wins-unknown)+[1]*unknown;r=[True]*(32-unknown)+[False]*unknown
            for delay in (0,223,224,256):
                a=decision(w,r,delay);ck('boundary',(a is not None)==(wins>=K and delay<224))
    return dict(passed=sum(c.values()),checks=dict(c)),dict(plan=PLAN,plan_sha=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest(),baseline_hold=base,cases=rows)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='.');a=p.parse_args();t,e=study();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
    for n,z in [('tests',t),('examples',e)]:(o/f'Trading_Round138_{n}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(t)
