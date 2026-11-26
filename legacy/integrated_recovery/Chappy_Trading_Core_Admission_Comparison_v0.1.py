"""R145 synthetic-only core admission comparison; fixed schedules, no orders."""
import hashlib,json,math,runpy,types
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import numpy as np
from scipy.stats import binom
P=Path(__file__).with_name('Chappy_Trading_Capital_Comparison_v0.1.py')
HASH='9bcae09e6015b1885f69bb771f8f8493e759c1c8d5c4f55e4914efa7659b69f1'
if hashlib.sha256(P.read_bytes()).hexdigest()!=HASH:raise ValueError('R142 hash')
C=runpy.run_path(str(P)); R=C['R']; Q=R['R']['R']; K=R['K']; cutoff=Q['cutoff']
S={'CURRENT':dict(K),'EARLY12':{n:cutoff(n,200) for n in (12,16,32,64,256)},'SPREAD':{n:K[n] for n in (16,64,256)}}
SEEDS=range(145000,145016)
PLAN=dict(parent=HASH, schedules=S, seeds=list(SEEDS), cases=list(C['CASES']), costs=[200,400], horizon=C['H'], alpha_per_look='1/200', max_epochs=2, max_looks_per_epoch=5, policy_training_cost=200, exact_p=[50,60,65,70,75,90], frequencies=[.01,.05,1.], synthetic_only=True, choice='fixed before computation; no threshold optimization')
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()
def bind(fn,k):return types.FunctionType(fn.__code__,dict(fn.__globals__,K=k),fn.__name__)
def exact(p,k):
    a=[1]; out=[]
    for n in range(1,257):
        b=[0]*(n+1)
        for w,v in enumerate(a):b[w]+=v*(100-p);b[w+1]+=v*p
        a=b
        if n in k:
            q=sum(a[k[n]:]);a[k[n]:]=[0]*len(a[k[n]:]);out.append((n,F(q,100**n)))
    return out,F(sum(a),100**256)
def reference(p,k):
    a={0:1};prev=0;out=[]
    for n,lim in k.items():
        d=n-prev; b=Counter();cs=[math.comb(d,i)*p**i*(100-p)**(d-i) for i in range(d+1)]
        for w,v in a.items():
            for i,c in enumerate(cs):b[w+i]+=v*c
        out.append((n,F(sum(v for w,v in b.items() if w>=lim),100**n)));a={w:v for w,v in b.items() if w<lim};prev=n
    return out,F(sum(a.values()),100**prev)
def study():
    c=Counter(); theory={};summary={}
    def ck(n,v):
        if not v:raise AssertionError(n)
        c[n]+=1
    for m,k in S.items():
        ck('look_budget',len(k)<=5 and list(k)==sorted(k) and max(k)==256)
        for n,w in k.items():
            tail=sum(math.comb(n,i)*3**i*2**(n-i) for i in range(w,n+1));ck('alpha_bound',200*tail<=5**n)
        theory[m]={}
        for p in PLAN['exact_p']:
            a,b=exact(p,k);ck('exact_oracle',(a,b)==reference(p,k));ck('mass',sum(v for _,v in a)+b==1)
            if p<=60:ck('null_union',1-b<=F(len(k),200))
            row=dict(pass_probability=float(1-b),first_pass={n:float(v) for n,v in a},mean_eligible_if_pass=float(sum(n*v for n,v in a)/(1-b)))
            row['calendar_4096']={str(f):sum(float(v)*float(binom.sf(n-1,4095,f)) for n,v in a) for f in PLAN['frequencies']}
            theory[m][str(p)]=row
    for case in C['CASES']:
        rows={m:{str(f):[] for f in PLAN['costs']} for m in S}
        for seed in SEEDS:
            x,y=Q['R']['series'](seed,case);first=[]
            for m,k in S.items():
                sim=bind(R['simulate'],k);ora=bind(R['oracle'],k);z=sim(x,y,'E_REFRESH');tr,ev=ora(x,y,'E_REFRESH')
                ck('core_oracle',z['trades']==tr and z['epochs']==ev);ck('epoch_budget',len(ev)<=2 and sum(len(e['looks']) for e in ev)<=10)
                if m=='CURRENT':ck('unchanged_baseline',z==R['simulate'](x,y,'E_REFRESH'))
                first.append(ev[0]['candidate']);a=[(i,d) for i,d,_ in tr];cut=4096; yy=y.copy(); yy[cut:]*=-1;zz=sim(x,yy,'E_REFRESH');aa=[(i,d) for i,d,_ in zz['trades']]
                ck('prefix',[t for t in a if t[0]<cut]==[t for t in aa if t[0]<cut])
                for e in ev:
                    for t,n,w in e['looks']:ck('look_boundary',n in k and 0<=w<=n and t>e['train_end'])
                    if e['admit'] is not None:ck('admission',e['looks'][-1][0]==e['admit'] and e['looks'][-1][2]>=k[e['looks'][-1][1]])
                for cost in PLAN['costs']:
                    s=C['settle'](y,a,cost);ck('cash_oracle',s==C['oracle'](y,a,cost));ck('accounting',s['net']==s['gross']-s['fees']);ck('funds',s['final']>=0)
                    t=C['settle'](yy,aa,cost);ck('fill_prefix',[f for f in s['fills'] if f[0]<cut]==[f for f in t['fills'] if f[0]<cut])
                    rows[m][str(cost)].append(dict(net=s['net'],dd=s['drawdown'],trades=len(s['fills']),admit=ev[0]['admit'],refresh=int(len(ev)>1),stops=sum(e['stop'] is not None for e in ev)))
            ck('matched_candidate',len(set(first))==1)
        summary[case]={m:{cost:dict(mean_net=sum(t['net'] for t in rs)/len(rs),mean_dd=sum(t['dd'] for t in rs)/len(rs),mean_trades=sum(t['trades'] for t in rs)/len(rs),admissions=sum(t['admit'] is not None for t in rs),mean_admit=sum(t['admit'] for t in rs if t['admit'] is not None)/max(1,sum(t['admit'] is not None for t in rs)),refresh=sum(t['refresh'] for t in rs),stops=sum(t['stops'] for t in rs)) for cost,rs in v.items()} for m,v in rows.items()}
    return dict(plan=PLAN,plan_sha=SHA,checks=dict(c),passed=sum(c.values()),theory=theory,summary=summary)
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2))
