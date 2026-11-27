"""R119: bounded rollback after parallel requalification; shared admission ledger prototype. Synthetic only."""
import argparse, hashlib, json, runpy, math
from pathlib import Path
from collections import Counter
from fractions import Fraction
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Parallel_Requalification_Study_v0.1.py')
HASH='632d55bfc5e2db136173ee0f085c631860d33ad68967b7a945195a5fd6aa3d52'
if hashlib.sha256(P.read_bytes()).hexdigest()!=HASH:raise ValueError('R118 hash')
R=runpy.run_path(str(P)); T=R['T']; A=R['ACTIVE']; O=R['OLD']; H=R['H']; K=R['K']; LIMIT=R['LIMIT']; N=R['N']
P2=P.with_name('Chappy_Trading_Post_Switch_Study_v0.1.py'); H2='154b2e211fd4ab6d26a6f8e5d18d30965b15187f3df40935ef646d2540bf8d0d'
if hashlib.sha256(P2.read_bytes()).hexdigest()!=H2:raise ValueError('R111 hash')
M=runpy.run_path(str(P2)); RL=M['K']['BLOCK_SPEND']
LANES=('initial','update_old','update_new','restart1_old','restart1_new','restart2_one','parallel'); METHODS=('LATCH','COMPARE','SHADOW','ROLLBACK'); SEEDS=range(119000,119064)
# Preserve R118 cases. Add fixed 3 scenarios to expose guard/rollback and absolute-stop priority.
CASES=dict(R['CASES'],late_reversal=[(3400,85,20,90),(H,85,20,10)],late_common_loss=[(3400,85,20,90),(H,10,20,10)],incumbent_recovery=[(3000,85,20,90),(3400,10,20,90),(H,85,20,10)])
PLAN=dict(parent=HASH,relative_parent=H2,cases=CASES,seeds=list(SEEDS),methods=METHODS,lanes=LANES,looks=list(K),alpha='1/700',relative_limit=RL,rollback_max=1,extra_shadow_cost=1,fee=200,scope='focused prequalified incumbent and alarmed challenger; full support; no actual trading; second restart at most one preselected candidate in proposed ledger')
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
class Ledger:
    def __init__(self):self.entries=[]
    def spend(self,lane,n,t):
        # Fixed routes, strictly increasing look schedule; no refund/reuse on cancellation.
        if lane not in LANES or type(n) is not int or type(t) is not int or t<0:return False
        prev=[e for e in self.entries if e[0]==lane]
        if len(prev)>=len(K) or n!=list(K)[len(prev)] or (prev and t<=prev[-1][2]) or (self.entries and t<self.entries[-1][2]) or len(self.entries)>=35:return False
        self.entries.append((lane,n,t));return True

def gen(seed,case):
    rng=np.random.default_rng(seed);xs=[];ys=[];start=0
    for end,c,f,p in CASES[case]:
        x=np.where(rng.integers(0,100,end-start)<f,7,0); y=np.where(rng.integers(0,100,end-start)<np.where(x==7,p,c),1,-1);xs.append(x);ys.append(y);start=end
    return np.concatenate(xs),np.concatenate(ys)

def run(x,y,mode):
    h=len(x); base=R['run'](x,y,'LATCH' if mode=='LATCH' else 'REQUAL_COMPARE'); L=Ledger()
    for t,n,w,ok in base['looks']:
        if not L.spend('parallel',n,t):raise ValueError('budget')
    sw=base['switch']; end=base['end']; rb=None; denied=None; obs=0; requests=0
    actions=base['actions'].copy(); a=T[A,x]==y;b=T[O,x]==y
    if sw is not None and mode in ('SHADOW','ROLLBACK'):
        obs=end-sw
        if mode=='ROLLBACK':
            d=(b[sw:end].astype(int)-a[sw:end].astype(int))*2000
            z=M['trigger'](d,'BLOCK_SPEND'); requests=int(z is not None and sw+z<end and sw+z<h)
            if requests:
                t=sw+z; old_alarm=R['alarm'](a[:t],0)
                if old_alarm is not None:denied=t
                else:
                    rb=t;obs=t-sw;next_alarm=R['alarm'](a,0);end=next_alarm if next_alarm is not None else h
                    actions[t:]=0;actions[t:end]=A
    gross=int(np.sum(np.where(actions!=0,np.where(np.where(actions==A,a,b),800,-1200),0)))
    fee=base['fee']+200*int(rb is not None)
    return dict(net=gross-end-base['research']-obs-fee,gross=gross,end=end,research=base['research'],shadow=obs,fee=fee,looks=L.entries,qualified=base['qualified'],switch=sw,rollback=rb,denied=denied,request=requests,actions=actions)

def reference_post(x,y,base,mode):
    # Scalar post-switch replay. Preserve the incumbent's absolute monitor alignment from t0.
    h=len(x);sw=base['switch'];actions=base['actions'].copy();end=base['end'];rb=None;denied=None;obs=0;request=0
    if sw is None or mode not in ('SHADOW','ROLLBACK'):return actions,end,rb,denied,obs,request
    own=[];other=[];rel=[];other_bad=False;active=O;monitor=True
    for i in range(h):
        a=int(T[A,int(x[i])]==int(y[i]));b=int(T[O,int(x[i])]==int(y[i]));other.append(a)
        if len(other)==32:
            if sum(other)<=LIMIT:other_bad=True
            other=[]
        if i<sw:continue
        actions[i]=active
        if monitor:obs+=1
        if active==O:
            own.append(b)
            if len(own)==32:
                if sum(own)<=LIMIT:end=i+1;actions[end:]=0;break
                own=[]
        elif other_bad:end=i+1;actions[end:]=0;break
        if monitor and mode=='ROLLBACK' and not request and a!=b:
            rel.append(b)
            if len(rel)==32:
                if sum(rel)<=RL and i+1<h:
                    request=1
                    if other_bad:denied=i+1
                    else:rb=i+1;active=A;monitor=False;end=h
                rel=[]
    return actions,end,rb,denied,obs,request

def fixtures():
    x=np.tile([0,0,0,7],H//4);y=np.ones(H,dtype=int)
    sw=R['run'](x,y,'REQUAL_COMPARE')['switch']; assert sw is not None
    flip=y.copy();flip[sw:]=np.where(x[sw:]==7,-1,1)
    both=flip.copy();both[sw:sw+64]=-1
    # Old incumbent alarms after switch, then recovers; its stale alarm blocks rollback.
    deny=flip.copy();deny[sw:sw+32]=-1
    # force incumbent losses without active challenger losses on first block
    xd=x.copy();yd=y.copy();xd[sw:sw+64]=7;yd[sw:sw+64]=1;yd[sw+64:]=np.where(xd[sw+64:]==7,-1,1)
    return {'stable':(x,y),'rollback':(x,flip),'both_stop':(x,both),'denied':(xd,yd),'final':(x[:sw],y[:sw])}

def study():
    C=Counter();summary={};samples={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        C[k]+=1
    # Ledger routes and limit, interleaved spends at same time, invalid attempts nonmutating.
    L=Ledger()
    for i,n in enumerate(K):
        for lane in LANES:ck('ledger_spend',L.spend(lane,n,100+i))
    ck('ledger_cap',len(L.entries)==35 and Fraction(len(L.entries),700)==Fraction(1,20))
    for lane,n,t in [('parallel',16,110),('unknown',16,110),('initial',256,110)]:
        before=L.entries[:];ck('ledger_reject',not L.spend(lane,n,t) and L.entries==before)
    L=Ledger();ck('ledger_wrong_look',not L.spend('initial',32,0));ck('ledger_first',L.spend('initial',16,1));ck('ledger_duplicate',not L.spend('initial',16,2));ck('ledger_time',not L.spend('initial',32,1));ck('ledger_global_time',not L.spend('update_old',16,0));ck('ledger_no_refund',len(L.entries)==1)
    def check(x,y,m,r,deep):
        h=len(x);base=R['run'](x,y,'LATCH' if m=='LATCH' else 'REQUAL_COMPARE');sw=r['switch'];rb=r['rollback'];ck('budget',len(r['looks'])<=5 and 30+len(r['looks'])<=35);ck('account',r['net']==r['gross']-r['end']-r['research']-r['shadow']-r['fee']);ck('authority',rb is None or sw is not None and sw<rb<h and R['alarm']((T[A,x[:rb]]==y[:rb]),0) is None);ck('stop',not np.any(r['actions'][r['end']:]));ck('unchanged_admission',r['switch']==base['switch'] and r['qualified']==base['qualified']);ck('fee',r['fee']==base['fee']+200*int(rb is not None));ck('direct_gross',r['gross']==int(np.sum(np.where(r['actions']!=0,np.where(T[r['actions'].astype(int),x]==y,800,-1200),0))))
        if m in ('LATCH','COMPARE'):ck('r118',r['net']==base['net'] and np.array_equal(r['actions'],base['actions']))
        if deep:
            a,e,b,d,o,q=reference_post(x,y,base,m);ck('scalar_actions',np.array_equal(a,r['actions']));ck('scalar_state',(e,b,d,o,q)==(r['end'],rb,r['denied'],r['shadow'],r['request']))
    for name,(x,y) in fixtures().items():
        samples[name]={}
        for m in METHODS:
            r=run(x,y,m);check(x,y,m,r,True);samples[name][m]={k:v for k,v in r.items() if k!='actions'}
            for t in [256,272,r['switch'],r['rollback'],r['denied']]:
                if t is None or t>=len(x):continue
                yy=y.copy();yy[t:]*=-1;rr=run(x,yy,m);ck('future_mask',np.array_equal(r['actions'][:t],rr['actions'][:t]));ck('future_looks',[z for z in r['looks'] if z[2]<=t]==[z for z in rr['looks'] if z[2]<=t])
    ck('fixture_rollback',samples['rollback']['ROLLBACK']['rollback'] is not None);ck('fixture_deny',samples['denied']['ROLLBACK']['denied'] is not None);ck('fixture_final',samples['final']['ROLLBACK']['switch'] is None)
    for case in CASES:
        rows={m:Counter() for m in METHODS}
        for seed in SEEDS:
            x,y=gen(seed,case)
            for m in METHODS:
                r=run(x,y,m);check(x,y,m,r,seed<119004);z=rows[m];z['net']+=r['net'];z['switch']+=int(r['switch'] is not None);z['rollback']+=int(r['rollback'] is not None);z['denied']+=int(r['denied'] is not None);z['stopped']+=int(r['end']<H);z['shadow']+=r['shadow'];z['looks']+=len(r['looks']);z['rollback_delay']+=(r['rollback']-r['switch']) if r['rollback'] is not None else 0
        summary[case]={m:dict(z,mean_net=z['net']/len(SEEDS),mean_rollback_delay=z['rollback_delay']/z['rollback'] if z['rollback'] else None) for m,z in rows.items()}
    return dict(passed=sum(C.values()),counts=dict(C),random_trials=len(CASES)*len(SEEDS)*len(METHODS),fixture_trials=len(samples)*len(METHODS),plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,fixtures=samples,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,z in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round119_{k}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
