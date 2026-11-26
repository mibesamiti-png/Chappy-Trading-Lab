"""R146: fixed known cost consistency; synthetic only, no market access or orders."""
import json, hashlib, math, runpy, types
from pathlib import Path
from collections import Counter
from fractions import Fraction as F
from functools import lru_cache
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Core_Admission_Comparison_v0.1.py')
HASH='f5278f2d16ec89f19d997f2515ea9b2f5ebe178d0ea9437a2f8aa1b34fd2f43b'
if hashlib.sha256(P.read_bytes()).hexdigest()!=HASH:raise ValueError('parent hash')
A=runpy.run_path(str(P)); C=A['C']; R=A['R']; Q=R['R']; T=R['T']; H=R['H']; TRAIN=R['TRAIN']; I=Q['R']['R']; K=R['K']
SEEDS=range(146000,146016); CASES=dict(I['CASES'],marginal=((65,35,35,65),)*2,moderate_decay=((90,10,10,90),(65,35,35,65)))
MODES=('FIXED','SELECT','ADMIT','FULL')
PLAN=dict(parent=HASH,seeds=list(SEEDS),cases=CASES,modes=MODES,costs=[200,400],gross=1000,alpha_look='1/200',monitor_alpha='1/5120',monitor_block=32,initial=200000,notional=100000,synthetic_only=True,known_cost_constant=True,choice='fixed before evaluation; no tuning')
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()
@lru_cache(maxsize=None)
def bounds(cost):
    p=F(1000+cost,2000); a,b=p.numerator,p.denominator;d=b-a
    def mass(n,i):return math.comb(n,i)*a**i*d**(n-i)
    k={n:next(i for i in range(n+2) if 200*sum(mass(n,j) for j in range(i,n+1))<=b**n) for n in K}
    lower=max([-1]+[i for i in range(33) if 5120*sum(mass(32,j) for j in range(i+1))<=b**32])
    return k,lower

def config(mode,cost):
    s=cost if mode!='FIXED' else 200; a=cost if mode in ('ADMIT','FULL') else 200; m=cost if mode=='FULL' else 200
    return s,bounds(a)[0],bounds(m)[1]
def sim(x,y,mode,cost):
    s,k,l=config(mode,cost)
    def select(a,b):
        d=T[:,a];return int(np.argmax(np.where(d==0,0,np.where(d==b,1000-s,-1000-s)).sum(axis=1)))
    def trigger(hits,method):
        n=len(hits)//32; z=np.flatnonzero(hits[:n*32].reshape(n,32).sum(axis=1)<=l);return int((z[0]+1)*32-1) if len(z) else None
    fn=R['simulate'];f=types.FunctionType(fn.__code__,dict(fn.__globals__,select=select,K=k,R=dict(Q,trigger=trigger)),fn.__name__)
    return f(x,y,'E_REFRESH')
def oracle(x,y,mode,cost):
    s,k,l=config(mode,cost); st='TRAIN'; start=0; ep=[]; orders=[]; n=w=0; block=[]
    for i,(a,b) in enumerate(zip(x,y)):
        if st=='TRAIN':
            if i+1-start==TRAIN and i+1<len(x):
                d=T[:,x[start:i+1]]; wins=np.sum(d==y[start:i+1],axis=1); active=np.count_nonzero(d,axis=1); j=int(np.argmax(2000*wins-(1000+s)*active));e=dict(start=start,train_end=i+1,candidate=j,admit=None,stop=None,looks=[]);ep.append(e);n=w=0;block=[];st='AUDIT' if j else 'DONE'
        elif st=='AUDIT' and T[j,a]:
            n+=1;w+=int(T[j,a]==b)
            if n in k:
                e['looks'].append([i+1,n,w])
                if w>=k[n] and i+1<len(x):e['admit']=i+1;st='LIVE'
                elif n==256:st='DONE'
        elif st=='LIVE' and T[j,a]:
            orders.append((i,int(T[j,a])));block.append(int(T[j,a]==b))
            if len(block)==32:
                alarm=sum(block)<=l;block=[]
                if alarm:e['stop']=i+1;start=i+1;st='TRAIN' if len(ep)==1 else 'DONE'
    return orders,ep

def series(seed,case):
    a,b=CASES[case];x,y,_=I['inputs'](seed,I['SHIFT'],I['W'],a);xx,yy,_=I['inputs'](seed+100000,H-I['SHIFT'],I['W'],b);return np.r_[x,xx],np.r_[y,yy]
def study():
    checks=Counter(); summary={}; theory={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        checks[k]+=1
    for cost in PLAN['costs']:
        k,l=bounds(cost);p=F(1000+cost,2000);tail=lambda n,i:sum(math.comb(n,j)*p**j*(1-p)**(n-j) for j in range(i,n+1));low=lambda i:sum(math.comb(32,j)*p**j*(1-p)**(32-j) for j in range(i+1))
        for n,i in k.items():ck('exact_upper',tail(n,i)<=F(1,200)<tail(n,i-1))
        ck('exact_lower',low(l)<=F(1,5120)<low(l+1))
        theory[str(cost)]=dict(break_even=float(p),admission=k,monitor=l,monitor_at_p65=float(sum(math.comb(32,i)*.65**i*.35**(32-i) for i in range(l+1))))
    ck('legacy_thresholds',bounds(200)==(K,Q['LIMITS']['BLOCK_SPEND']))
    for case in CASES:
        rows={str(c):{m:[] for m in MODES} for c in PLAN['costs']}
        for seed in SEEDS:
            x,y=series(seed,case);yy=y.copy();yy[4096:]*=-1
            for cost in PLAN['costs']:
                first=None
                for m in MODES:
                    z=sim(x,y,m,cost);orders=[(i,d) for i,d,_ in z['trades']];ep=z['epochs'];ck('state_oracle',(orders,ep)==oracle(x,y,m,cost));ck('budget',sum(len(e['looks']) for e in ep)<=10 and len(ep)<=2)
                    zz=sim(x,yy,m,cost);aa=[(i,d) for i,d,_ in zz['trades']];ck('prefix',[v for v in orders if v[0]<4096]==[v for v in aa if v[0]<4096]);v=C['settle'](y,orders,cost);ck('cash_oracle',v==C['oracle'](y,orders,cost));ck('accounting',v['net']==v['gross']-v['fees'] and v['final']>=0);vv=C['settle'](yy,aa,cost);ck('fill_prefix',[f for f in v['fills'] if f[0]<4096]==[f for f in vv['fills'] if f[0]<4096]);
                    if cost==200 or m=='FIXED':ck('baseline',z==R['simulate'](x,y,'E_REFRESH'))
                    if cost==200:
                        if first is None:first=z
                        else:ck('normal_cost_identity',z==first)
                    rows[str(cost)][m].append(dict(net=v['net'],dd=v['drawdown'],trades=len(v['fills']),admit=int(ep[0]['admit'] is not None),refresh=int(len(ep)>1),stops=sum(e['stop'] is not None for e in ep)))
        summary[case]={c:{m:{k:sum(t[k] for t in rs)/len(rs) for k in rs[0]} for m,rs in ms.items()} for c,ms in rows.items()}
    return dict(plan=PLAN,plan_sha=SHA,checks=dict(checks),passed=sum(checks.values()),theory=theory,summary=summary)
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2))
