"""R121: focused fixed-vs-flexible admission allocation, synthetic only."""
import argparse, hashlib, json, runpy
from pathlib import Path
from collections import Counter
from fractions import Fraction
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Admission_Evidence_Ledger_Study_v0.1.py')
HASH='798ee9a2ebf9199064d9fb8d502396aea3798fe0f837a119a457243997953d63'
if hashlib.sha256(P.read_bytes()).hexdigest()!=HASH:raise ValueError('R120 hash')
R=runpy.run_path(str(P));K=R['K']; LOOKS=tuple(K);Q=R['Q']; A,B=9,256;H=4096;SEEDS=range(121000,121128)
# request parallel, first-period P(up), recovery1 P(up), recovery2 P(up)
CASES={'no_parallel_A':(False,10,50,90),'no_parallel_B':(False,10,50,10),'parallel_easy_A':(True,95,50,90),'parallel_easy_B':(True,95,50,10),'parallel_fail_B':(True,50,50,10),'early_recovery':(True,95,90,10),'no_recovery':(True,50,50,50),'parallel_fail_weak_A':(True,50,50,70),'parallel_fail_weak_B':(True,50,50,30)}
MODES=('RECOVERY_FIRST','RESERVED','FLEX','FLEX_SHORT')
PLAN=dict(parent=HASH,prior_spend=15,cap=35,alpha='1/700',looks=LOOKS,seed=list(SEEDS),cases=CASES,methods=MODES,horizon=H,phases=[0,1024,2048,4096],short_schedule='recovery2 only: two candidates, min(5,floor(remaining/2)) looks each; no threshold change',scope='forced stop at 1024; full support opposite direction x=7; frozen candidates, no monitoring; comparative budget only',fee=200,cost=1)
SHA=R['digest'](PLAN)
class Budget:
    def __init__(self,mode):self.mode=mode;self.spent=15;self.entries=[];self.opened=[];self.active=None
    def start(self,route,t,js):
        if self.active is not None or route in [a['route'] for a in self.opened] or route not in ('parallel','recovery1','recovery2'):raise ValueError('route')
        limits={'RECOVERY_FIRST':{'parallel':0,'recovery1':2,'recovery2':2},'RESERVED':{'parallel':1,'recovery1':2,'recovery2':1}} 
        cap=min(len(js),(35-self.spent)//5) if self.mode in ('FLEX','FLEX_SHORT') else limits[self.mode][route]
        nlooks=5
        if self.mode=='FLEX_SHORT' and route=='recovery2' and len(js)==2 and 35-self.spent>=2:
            cap=2;nlooks=min(5,(35-self.spent)//2)
        cap=min(cap,len(js)); chosen=tuple(js[:cap]);
        if len(set(chosen))!=len(chosen) or self.spent+nlooks*len(chosen)>35:raise ValueError('reservation')
        if not chosen:return ()
        if self.opened and t<self.opened[-1]['end']:raise ValueError('overlap')
        self.active=dict(route=route,start=t,end=None,js=chosen,reserved=nlooks*len(chosen),nlooks=nlooks,before=self.spent,counts={j:0 for j in chosen});self.opened.append(self.active);return chosen
    def spend(self,j,n,t,w):
        a=self.active
        if a is None or j not in a['counts'] or a['counts'][j]>=a['nlooks'] or n!=LOOKS[a['counts'][j]] or t!=a['start']+n or not 0<=w<=n or self.spent>=35:raise ValueError('invalid spend')
        if self.entries and t<self.entries[-1]['t']:raise ValueError('chronology')
        if any(e['route']==a['route'] and e['j']==j and e['pass'] for e in self.entries):raise ValueError('closed lane')
        e=dict(route=a['route'],j=j,n=n,t=t,w=w,**{'pass':w>=K[n]});self.entries.append(e);self.spent+=1;a['counts'][j]+=1;return e['pass']
    def close(self,t):
        if self.active is None:raise ValueError('not open')
        self.active['end']=t;self.active['after']=self.spent;self.active=None

def simulate(y,request,mode):
    b=Budget(mode);a=np.full(len(y),B,dtype=int);a[1024:]=0;fees=0;cost=0;admissions={};
    def audit(route,t,js):
        nonlocal cost
        js=b.start(route,t,js)
        if not js:return None,t
        for n in LOOKS[:b.active['nlooks']]:
            winners=[]
            for j in js:
                w=int(np.count_nonzero(y[t:t+n]==Q[j,7]));
                if b.spend(j,n,t+n,w):winners.append(j)
            if winners:
                b.close(t+n);cost+=n;admissions[route]=(winners[0],t+n);return winners[0],t+n
        b.close(t+n);cost+=n;return None,t+n
    if request:
        j,t=audit('parallel',0,[A]);
        if j is not None:a[t:1024]=j;fees+=200
    j,t=audit('recovery1',1024,[A,B]);
    if j is None:j,t=audit('recovery2',2048,[A,B])
    if j is not None:a[t:]=j;fees+=200
    gross=int(np.sum(np.where(a==0,0,np.where(Q[a,7]==y,800,-1200))))
    return dict(net=gross-cost-fees,gross=gross,cost=cost,fee=fees,spent=b.spent,entries=b.entries,batches=b.opened,admissions=admissions,actions=a)

def reference(y,request,mode):
    spent=15;actions=[B]*1024+[0]*(len(y)-1024);events=[];ad={};cost=fee=0
    for route,t,js in [('parallel',0,[A]),('recovery1',1024,[A,B]),('recovery2',2048,[A,B])]:
        if route=='parallel' and not request:continue
        if route=='recovery2' and 'recovery1' in ad:continue
        if mode=='RECOVERY_FIRST':cap=0 if route=='parallel' else 2
        elif mode=='RESERVED':cap=2 if route=='recovery1' else 1
        else:cap=(35-spent)//5
        nlooks=5
        if mode=='FLEX_SHORT' and route=='recovery2' and 35-spent>=2:cap=2;nlooks=min(5,(35-spent)//2)
        js=js[:cap]
        if not js:continue
        counts={j:0 for j in js};win=None
        for i in range(t,t+LOOKS[nlooks-1]):
            for j in js:counts[j]+=int(int(y[i])==int(Q[j,7]))
            n=i-t+1
            if n in K:
                for j in js:
                    ok=counts[j]>=K[n];events.append(dict(route=route,j=j,n=n,t=i+1,w=counts[j],**{'pass':ok}));spent+=1
                    if ok and win is None:win=j
                if win is not None:break
        cost+=n
        if win is not None:
            ad[route]=(win,t+n);fee+=200;end=1024 if route=='parallel' else len(y);actions[t+n:end]=[win]*(end-t-n)
    gross=sum(0 if j==0 else 800 if int(Q[j,7])==int(v) else -1200 for j,v in zip(actions,y))
    return events,ad,actions,spent,gross-cost-fee

def study():
    c=Counter();out={};fixtures={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def check(y,req,mode):
        z=simulate(y,req,mode);e,ad,a,sp,net=reference(y,req,mode)
        ck('oracle_events',z['entries']==e);ck('oracle_admission',z['admissions']==ad);ck('oracle_actions',np.array_equal(z['actions'],a));ck('oracle_accounting',z['net']==net);ck('budget',z['spent']==sp<=35 and Fraction(sp,700)<=Fraction(1,20));ck('accounting',z['net']==z['gross']-z['cost']-z['fee'])
        end=0;seen=set()
        for b in z['batches']:
            ck('fresh_batch',end<=b['start']<b['end']);end=b['end'];ck('reservation',b['before']+b['reserved']<=35 and b['after']-b['before']<=b['reserved'])
        for e in z['entries']:
            key=e['route'],e['j'],e['n'];ck('unique_look',key not in seen);seen.add(key);ck('threshold',e['pass']==(e['w']>=K[e['n']]))
        return z
    for name,(req,p0,p1,p2) in CASES.items():
        totals={m:Counter() for m in MODES}
        for seed in SEEDS:
            rng=np.random.default_rng(seed);y=np.where(rng.random(H)<np.repeat([p0,p1,p2],[1024,1024,2048])/100,1,-1)
            for m in MODES:
                z=check(y,req,m);s=totals[m];s['net']+=z['net'];s['spent']+=z['spent'];s['parallel_pass']+=int('parallel' in z['admissions']);s['recovery1_pass']+=int('recovery1' in z['admissions']);s['recovery2_pass']+=int('recovery2' in z['admissions']);s['recovery2_two']+=sum(b['route']=='recovery2' and len(b['js'])==2 for b in z['batches']);s['recovery2_B']+=int(z['admissions'].get('recovery2',(None,))[0]==B)
                if seed==SEEDS[0]:
                    for b in z['batches']:
                        t=b['end']; yy=y.copy();yy[t:]*=-1;w=simulate(yy,req,m);ck('future_prefix',np.array_equal(z['actions'][:t],w['actions'][:t]) and [e for e in z['entries'] if e['t']<=t]==[e for e in w['entries'] if e['t']<=t])
        out[name]={m:{**dict(s),'mean_net':s['net']/len(SEEDS),'mean_spent':s['spent']/len(SEEDS)} for m,s in totals.items()}
    # Explicit worst-case paths with balanced samples, or fast success in parallel.
    for name,req,first,second in [('absent_B',False,False,-1),('early_parallel_B',True,True,-1),('spent_parallel_B',True,False,-1),('spent_parallel_A',True,False,1),('no_winner',True,False,0)]:
        y=np.tile([1,-1],H//2);y[:1024]=1 if first else y[:1024];y[2048:]=second if second else y[2048:];fixtures[name]={}
        for m in MODES:
            z=check(y,req,m);fixtures[name][m]={k:z[k] for k in ('spent','admissions','net','batches')}
    ck('absent_release',fixtures['absent_B']['FLEX']['admissions']['recovery2'][0]==B and 'recovery2' not in fixtures['absent_B']['RESERVED']['admissions'])
    ck('early_release',fixtures['early_parallel_B']['FLEX_SHORT']['admissions']['recovery2'][0]==B and 'recovery2' not in fixtures['early_parallel_B']['RESERVED']['admissions'])
    ck('exhaustion',fixtures['spent_parallel_B']['FLEX']['spent']==35 and 'recovery2' not in fixtures['spent_parallel_B']['FLEX']['admissions'])
    ck('full_cap',fixtures['no_winner']['FLEX']['spent']==35);ck('short_schedule',fixtures['spent_parallel_B']['FLEX_SHORT']['admissions']['recovery2'][0]==B and fixtures['spent_parallel_B']['FLEX_SHORT']['spent']<=35)
    return dict(passed=sum(c.values()),counts=dict(c),random_trials=len(CASES)*len(SEEDS)*len(MODES),fixtures=len(fixtures)*len(MODES),plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,summary=out,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,v in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round121_{k}.json').write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
