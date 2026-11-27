"""R124: sparse/fresh schedules in R121 allocation, synthetic only."""
import argparse, hashlib, json, runpy
from pathlib import Path
from collections import Counter
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Admission_Allocation_Study_v0.1.py')
HASH='af6ee2c9beb5b76b3c8d0c7cc933181f5dccc54dd061b9dd07ce90e67432d2dc'
D=P.with_name('Chappy_Trading_Admission_Drift_Study_v0.1.py');DH='7caf4fb1116575da2566c56f8a2c121d87ffda22f8c621179a6dcb58c0ae8b29'
for f,h in [(P,HASH),(D,DH)]:
    if hashlib.sha256(f.read_bytes()).hexdigest()!=h:raise ValueError('parent hash')
R=runpy.run_path(str(P));K=R['K'];Q=R['Q'];A,B,H=R['A'],R['B'],R['H'];BASE=R['MODES'];NEW=('SPREAD','FRESH128','FRESH64');MODES=BASE+NEW
SEEDS=range(124000,124064)
CASES={k:(v[0],((0,v[1]),(1024,v[2]),(2048,v[3]))) for k,v in R['CASES'].items()}
for name,t,p0,p1 in [('drift_middle',2176,70,30),('drift_late',2272,70,30),('drift_after',2304,70,30),('late_collapse',2288,90,50),('late_recovery',2176,50,70)]:CASES[name]=(True,((0,50),(1024,50),(2048,p0),(t,p1)))
SP={1:(256,),2:(16,256),3:(16,64,256),4:(16,32,64,256),5:tuple(K)}
PLAN=dict(parents=[HASH,DH],cases=CASES,seeds=list(SEEDS),modes=MODES,thresholds=K,sparse=SP,prior_spend=15,total_cap=35,fee=200,obs=1,scope='R121 allocation unchanged until recovery2; fixed schedule before batch; latest window only at final look; forced stop; no monitoring; synthetic only')
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()
def schedule(mode,route,k):
    ns=SP[k] if mode in NEW and route=='recovery2' else tuple(K)[:k]
    return tuple((n,int(mode[5:]) if mode.startswith('FRESH') and route=='recovery2' and n==256 else n) for n in ns)
class Ledger(R['Budget']):
    def __init__(self,mode):super().__init__('FLEX_SHORT' if mode in NEW else mode);self.policy=mode
    def start(self,route,t,js):
        js=super().start(route,t,js)
        if js:self.active['schedule']=schedule(self.policy,route,self.active['nlooks'])
        return js
    def spend(self,j,n,t,w):
        a=self.active
        if a is None or j not in a['counts'] or a['counts'][j]>=a['nlooks']:raise ValueError('lane')
        end,window=a['schedule'][a['counts'][j]]
        if n!=end or t!=a['start']+end or not 0<=w<=window or self.spent>=35:raise ValueError('look')
        if self.entries and t<self.entries[-1]['t']:raise ValueError('chronology')
        if any(e['route']==a['route'] and e['j']==j and e['pass'] for e in self.entries):raise ValueError('closed lane')
        e=dict(route=a['route'],j=j,n=n,t=t,w=w,window=window,**{'pass':w>=K[window]});self.entries.append(e);self.spent+=1;a['counts'][j]+=1;return e['pass']
def simulate(y,req,mode):
    b=Ledger(mode);act=np.full(H,B,dtype=int);act[1024:]=0;fee=cost=0;ad={}
    for route,t,js in [('parallel',0,[A]),('recovery1',1024,[A,B]),('recovery2',2048,[A,B])]:
        if (route=='parallel' and not req) or (route=='recovery2' and 'recovery1' in ad):continue
        js=b.start(route,t,js)
        if not js:continue
        for n,w in b.active['schedule']:
            winners=[]
            for j in js:
                wins=int(np.count_nonzero(y[t+n-w:t+n]==Q[j,7]))
                if b.spend(j,n,t+n,wins):winners.append(j)
            if winners:
                ad[route]=(winners[0],t+n);act[t+n:1024 if route=='parallel' else H]=winners[0];fee+=200;break
        b.close(t+n);cost+=n
    gross=int(np.sum(np.where(act==0,0,np.where(Q[act,7]==y,800,-1200))))
    return dict(entries=b.entries,batches=b.opened,spent=b.spent,admissions=ad,actions=act,gross=gross,fee=fee,cost=cost,net=gross-fee-cost)
def oracle(y,req,mode):
    spent=15;ad={};entries=[];cost=fee=0;act=np.r_[np.full(1024,B),np.zeros(H-1024,dtype=int)];prefix=np.r_[0,np.cumsum(y==1)]
    for route,t,js in [('parallel',0,[A]),('recovery1',1024,[A,B]),('recovery2',2048,[A,B])]:
        if (route=='parallel' and not req) or (route=='recovery2' and 'recovery1' in ad):continue
        if mode=='RECOVERY_FIRST':c=0 if route=='parallel' else 2
        elif mode=='RESERVED':c=2 if route=='recovery1' else 1
        else:c=(35-spent)//5
        k=5
        if mode in ('FLEX_SHORT',*NEW) and route=='recovery2' and 35-spent>=2:c=2;k=min(5,(35-spent)//2)
        js=js[:c]
        if not js:continue
        ns=([256],[16,256],[16,64,256],[16,32,64,256],[16,32,64,128,256])[k-1] if mode in NEW and route=='recovery2' else [16,32,64,128,256][:k]
        for n in ns:
            w=128 if mode=='FRESH128' and route=='recovery2' and n==256 else 64 if mode=='FRESH64' and route=='recovery2' and n==256 else n
            plus=int(prefix[t+n]-prefix[t+n-w]);winner=None
            for j in js:
                wins=plus if Q[j,7]==1 else w-plus;ok=wins>=K[w];spent+=1;entries.append(dict(route=route,j=j,n=n,t=t+n,w=wins,window=w,**{'pass':ok}))
                if ok and winner is None:winner=j
            if winner is not None:
                ad[route]=(winner,t+n);act[t+n:1024 if route=='parallel' else H]=winner;fee+=200;break
        cost+=n
    gross=0
    for j in (A,B):
        mask=act==j;wins=int(np.sum(y[mask]==Q[j,7]));gross+=2000*wins-1200*int(mask.sum())
    return entries,ad,act,spent,gross-fee-cost

def study():
    c=Counter();out={};fixtures={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def check(y,req,m):
        z=simulate(y,req,m);e,ad,a,sp,net=oracle(y,req,m)
        ck('oracle_entries',e==z['entries']);ck('oracle_admissions',ad==z['admissions']);ck('oracle_actions',np.array_equal(a,z['actions']));ck('oracle_accounting',net==z['net']);ck('cap',sp==z['spent']<=35);ck('accounting',z['net']==z['gross']-z['fee']-z['cost'])
        prev=0;seen=set()
        for b in z['batches']:
            ck('batch_nonoverlap',prev<=b['start']<b['end']);prev=b['end'];ck('reservation',b['before']+b['reserved']<=35 and b['after']-b['before']<=b['reserved']);ck('schedule_frozen',b['schedule']==schedule(m,b['route'],b['nlooks']))
        for e in z['entries']:
            key=(e['route'],e['j'],e['n']);ck('unique_look',key not in seen);seen.add(key);ck('threshold',e['pass']==(e['w']>=K[e['window']]))
            start=e['t']-e['window'];ck('evidence',start>=next(b['start'] for b in z['batches'] if b['route']==e['route']) and e['w']==int(np.sum(y[start:e['t']]==Q[e['j'],7])))
        if m in BASE:
            old=R['simulate'](y,req,m);ck('R121_regression',all(z[k]==old[k] for k in ('net','spent','admissions','gross','cost','fee')) and np.array_equal(z['actions'],old['actions']) and [{k:v for k,v in e.items() if k!='window'} for e in z['entries']]==old['entries'])
        return z
    for name,(req,phases) in CASES.items():
        ps=np.zeros(H,dtype=int)
        for t,p in phases:ps[t:]=p
        totals={m:Counter() for m in MODES}
        for seed in SEEDS:
            y=np.where(np.random.default_rng(seed).random(H)<ps/100,1,-1)
            for m in MODES:
                z=check(y,req,m);s=totals[m];s['net']+=z['net'];s['spent']+=z['spent'];s['obs']+=z['cost'];ad=z['admissions'].get('recovery2')
                if ad:
                    j,t=ad;p=ps[t] if Q[j,7]==1 else 100-ps[t];s['recovery2_pass']+=1;s['recovery2_A']+=int(j==A);s['recovery2_B']+=int(j==B);s['recovery2_nonpositive']+=int(p<=60);s['recovery2_t']+=t-2048
                if seed==SEEDS[0]:
                    for b in z['batches']:
                        t=b['end'];yy=y.copy();yy[t:]*=-1;other=simulate(yy,req,m);ck('future_prefix',np.array_equal(z['actions'][:t],other['actions'][:t]) and [e for e in z['entries'] if e['t']<=t]==[e for e in other['entries'] if e['t']<=t])
        out[name]={m:{**dict(s),'mean_net':s['net']/len(SEEDS),'mean_spent':s['spent']/len(SEEDS),'mean_obs':s['obs']/len(SEEDS)} for m,s in totals.items()}
    for name,last in [('stable_B',np.full(2048,-1)),('late_B',np.r_[np.ones(224),-np.ones(1824)]),('after_boundary',np.r_[np.ones(256),-np.ones(1792)])]:
        y=np.r_[np.tile([1,-1],1024),last].astype(int);y[2048:2064]=np.tile([1,-1],8);fixtures[name]={}
        for m in MODES:
            z=check(y,True,m);fixtures[name][m]={k:z[k] for k in ('spent','admissions','net','entries')}
    ck('sparse_recovers_B',fixtures['stable_B']['SPREAD']['admissions']['recovery2'][0]==B and 'recovery2' not in fixtures['stable_B']['FLEX_SHORT']['admissions'])
    ck('fresh_rejects_stale_A',fixtures['late_B']['SPREAD']['admissions']['recovery2'][0]==A and 'recovery2' not in fixtures['late_B']['FRESH64']['admissions'])
    ck('boundary_example',fixtures['after_boundary']['SPREAD']['admissions']['recovery2']==(A,2304))
    return dict(passed=sum(c.values()),counts=dict(c),random_trials=len(CASES)*len(SEEDS)*len(MODES),fixtures=len(fixtures)*len(MODES),plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,summary=out,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,v in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round124_{k}.json').write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
