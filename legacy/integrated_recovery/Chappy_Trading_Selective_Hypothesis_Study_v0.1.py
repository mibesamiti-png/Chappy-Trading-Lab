"""R99: finite cell-selective hypotheses, independent single audit, synthetic only."""
import argparse, hashlib, json, math, runpy
from functools import lru_cache
from itertools import product
from pathlib import Path
import numpy as np
from scipy.stats import binom
p=Path(__file__).with_name('Chappy_Trading_Observation_Imbalance_Study_v0.1.py')
if hashlib.sha256(p.read_bytes()).hexdigest()!='426709b3d3ded3dfb7c760883abbede4f44e0bf18b54094ea0b0de3ef0575a61':raise ValueError('R98 hash')
R=runpy.run_path(str(p)); MAT=R['MAT']; CELLS=R['CELLS']; STATES=R['STATES']; C=R['C']; OLD=R['R']; TH=OLD['S']['TH'][60]
MODELS=dict(R['MODELS'],rare_boundary=(50,50,50,60)); WEIGHTS=R['WEIGHTS']; SEEDS=range(99000,99128); LENGTHS=(64,256,1024); AUDITS=(256,4096); EVAL=1024; OFF=(0,100000,200000)
METHODS=('FULL256','CV2','FULL_WAIT','SELECTIVE')
# WAIT first, then full tables in old order, then 4 directional maps per cell.
T=np.array([(0,)*8]+list(map(tuple,MAT))+[tuple(d[0 if s==R['SIGNS'][0] else 1] if c==cell else 0 for c,s in STATES) for cell in CELLS for d in product((-1,1),repeat=2)],dtype=np.int64)
ABS=np.abs(T); MASK=np.array([CELLS.index(c) for c,s in STATES]); PLAN=dict(synthetic_only=True,models=MODELS,weights=WEIGHTS,seeds=list(SEEDS),train=LENGTHS,audit=AUDITS,evaluation=EVAL,offsets=OFF,methods=METHODS,selection='maximize total training net, WAIT wins zero ties; CV2 unchanged',candidates='256 full + 16 cell-specific + WAIT',gate='one independent conditional binomial test, p<=3/5, alpha=1/20; no re-test',cost_bps=20,amplitude_bps=100,notional_yen=100000)
SHA=C['B']['digest'](PLAN)
def counts(x,y):
    n=np.bincount(x,minlength=8); v=np.bincount(x,weights=y,minlength=8).astype(np.int64); a=ABS@n; h=(a+T@v)//2
    return a,h

def tail(n,k):
    if k>n:return 0
    term=math.comb(n,k)*3**k*2**(n-k); total=term
    for i in range(k,n):
        term=term*(n-i)*3//((i+1)*2);total+=term
    return total
@lru_cache(None)
def cutoff(n):
    if n<=256:return TH[n]
    k=int(binom.isf(.05,n,.6))+1;den=5**n
    while k<=n and 20*tail(n,k)>den:k+=1
    while k>0 and 20*tail(n,k-1)<=den:k-=1
    return k

def theory(m,w):
    # integer numerator of unconditional expected yen per opportunity, denominator 20000
    win=np.array([[0 if a==0 else (m[CELLS.index(c)] if a==s else 100-m[CELLS.index(c)]) for (c,s),a in zip(STATES,t)] for t in T]); weights=np.array([w[k] for k in MASK]);return 2000*(win@weights)-1200*100*(ABS@weights)

def choose(x,y,n):
    a,h=counts(x[:n],y[:n]); score=2000*h-1200*a; half=n//2
    _,ha=counts(x[:half],y[:half]);_,hb=counts(x[half:n],y[half:n]);old,_=OLD['choose'](h[1:257],ha[1:257],hb[1:257]);return (1+int(np.argmax(h[1:257])),1+old[-1][0],int(np.argmax(score[:257])),int(np.argmax(score)))

def study(test=False):
    checks={};out={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        checks[k]=checks.get(k,0)+1
    ck('unique',len(set(map(tuple,T))),273);ck('seed_disjoint',len({s+o for s,o in product(SEEDS,OFF)}),len(SEEDS)*3);ck('old_prefix',bool(np.array_equal(T[1:257],MAT)),True)
    for model,m in MODELS.items():
        out[model]={}
        for freq,w in WEIGHTS.items():
            q=theory(m,w);rows={(n,b,k):[] for n,b,k in product(LENGTHS,AUDITS,METHODS)}
            if test:
                for j,t in enumerate(T):
                    v=sum(w[CELLS.index(c)]*sum(0 if a==0 else (800 if a==s*(1 if u<m[CELLS.index(c)] else -1) else -1200) for u in range(100)) for (c,s),a in zip(STATES,t));ck('theory',int(q[j]),int(v))
            for seed in SEEDS:
                x,y,_=R['inputs'](seed,max(LENGTHS),w,m);ax,ay,_=R['inputs'](seed+OFF[1],max(AUDITS),w,m);ex,ey,_=R['inputs'](seed+OFF[2],EVAL,w,m);ea,eh=counts(ex,ey);aud={b:counts(ax[:b],ay[:b]) for b in AUDITS}
                for n in LENGTHS:
                    js=choose(x,y,n)
                    if test:
                        d=T[:,x[:n]];a=np.count_nonzero(d,axis=1);h=np.count_nonzero(d==y[:n],axis=1);v=2000*h-1200*a
                        ck('select',(js[0],js[2],js[3]),(1+int(np.argmax(h[1:257])),int(np.argmax(v[:257])),int(np.argmax(v))))
                        left=np.count_nonzero(d[1:257,:n//2]==y[:n//2],axis=1);right=np.count_nonzero(d[1:257,n//2:]==y[n//2:n],axis=1);pools=(16,24,256);scores=[int(right[int(np.argmax(left[:k]))]+left[int(np.argmax(right[:k]))]) for k in pools];pool=pools[int(np.argmax(scores))];ck('cv2_choice',js[1],1+int(np.argmax(h[1:1+pool])))
                    for b in AUDITS:
                        aa,ah=aud[b]
                        for k,j in zip(METHODS,js):
                            na,nh=int(aa[j]),int(ah[j]);g=bool(na and nh>=cutoff(na));ne,he=int(ea[j]),int(eh[j]);net=(2000*he-1200*ne) if g else 0
                            rows[n,b,k].append((j,g,net,na,nh,ne if g else 0))
                            if test:
                                d=T[j,ax[:b]];e=T[j,ex];a0=int(np.count_nonzero(d));h0=int(np.count_nonzero(d==ay[:b]));e0=int(np.count_nonzero(e));h1=int(np.count_nonzero(e==ey));ck('audit_counts',(na,nh),(a0,h0));ck('eval_counts',(ne,he),(e0,h1));ck('gate',g,a0>0 and h0>=cutoff(a0));ck('net',net,(800*h1-1200*(e0-h1)) if g else 0)
            out[model][freq]={'oracle_full_yen_per_slot':float(max(q[1:257])/20000),'oracle_selective_yen_per_slot':float(max(q)/20000),'conditions':{}}
            for (n,b,k),rs in rows.items():
                z=len(rs); ad=[r for r in rs if r[1]];selected=[r for r in rs if r[0]>0];rare=[r for r in rs if r[0]>=269];out[model][freq]['conditions'].setdefault(str(n),{}).setdefault(str(b),{})[k]=dict(admitted=len(ad),admitted_nonpositive=sum(q[r[0]]<=0 for r in ad),chosen_wait=z-len(selected),chosen_cell_only=sum(r[0]>256 for r in rs),chosen_rare=len(rare),chosen_rare_admitted=sum(r[1] for r in rare),optimal_positive=sum(q[r[0]]==max(q) and q[r[0]]>0 for r in rs),mean_audit_trades=sum(r[3] for r in rs)/z,mean_rare_audit_trades=sum(r[3] for r in rare)/len(rare) if rare else None,mean_eval_trades=sum(r[5] for r in rs)/z,mean_gated_eval_net=sum(r[2] for r in rs)/z,expected_gated_eval_net=sum(int(q[r[0]]) for r in ad)*EVAL/z/20000,mean_true_selected_net_per_slot=sum(int(q[r[0]]) for r in rs)/z/20000)
    if test:
        for n in [0,1,2,5,8,9,16,32,64,128,256,257,1024,4096]:
            k=cutoff(n);den=5**n;ck('threshold_valid',20*tail(n,k)<=den,True);ck('threshold_minimal',20*tail(n,k-1)>den,True)
        return dict(passed=sum(checks.values()),counts=checks,plan_sha=SHA)
    return dict(plan=PLAN,plan_sha=SHA,summary=out)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(study(a.self_test),indent=2,sort_keys=True,default=lambda v:v.item()))
