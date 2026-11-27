"""R125: R124 admission plus existing R103 absolute stop, synthetic only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
from collections import Counter
import numpy as np
D=Path(__file__).parent
P=D/'Chappy_Trading_Admission_Integration_Study_v0.1.py'; M=D/'Chappy_Trading_Refresh_Trigger_Study_v0.1.py'
HASH='62d2f2fa19717d4565048a47496bdd983b357670f67a8a6af3c26c02e4a25472'; MH='cb4d0570492b17d7e4fb963cba0191572463e67d96adb805d44af5fbb9d244ca'
for f,h in ((P,HASH),(M,MH)):
    if hashlib.sha256(f.read_bytes()).hexdigest()!=h:raise ValueError('parent hash')
R=runpy.run_path(str(P)); T=runpy.run_path(str(M));Q=R['Q'];A,B,H=R['A'],R['B'],R['H'];MODES=R['MODES'];BLOCK=T['BLOCK'];K=T['LIMITS']['BLOCK_SPEND'];MAX=T['MAX_LOOKS'];DEN=T['DEN']
POLICIES=('OFF','SHADOW','STOP');SEEDS=range(125000,125064)
CASES=dict(R['CASES']);CASES.update(post_weak_loss=(True,((0,50),(1024,50),(2048,90),(2304,55))),post_temporary_loss=(True,((0,50),(1024,50),(2048,90),(2304,20),(2432,90))),post_stable_weak=(True,((0,50),(1024,50),(2048,70))))
PLAN=dict(parents=[HASH,MH],seeds=list(SEEDS),cases=CASES,modes=MODES,policies=POLICIES,block=BLOCK,threshold=K,denom=DEN,max_looks=MAX,monitor_fee=1,scope='monitor only after recovery1/2 admission; first alarm ends monitoring in SHADOW and STOP; STOP terminal; unchanged admissions; no short pause; synthetic only')
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()
def apply(y,z,policy):
    a=z['actions'].copy();ad=z['admissions'].get('recovery1') or z['admissions'].get('recovery2');groups=[];alarm=None;obs=0
    if ad and policy!='OFF':
        j,t=ad;hits=y[t:]==Q[j,7];n=min(len(hits)//BLOCK,MAX)
        for k,w in enumerate(hits[:n*BLOCK].reshape(n,BLOCK).sum(axis=1),1):
            end=t+k*BLOCK;groups.append((end,int(w)))
            if w<=K:alarm=end;break
        obs=(alarm if alarm is not None else min(H,t+MAX*BLOCK))-t
        if alarm is not None and policy=='STOP':a[alarm:]=0
    gross=int(np.where(a==0,0,np.where(Q[a,7]==y,800,-1200)).sum())
    return dict(actions=a,groups=groups,alarm=alarm,obs=obs,gross=gross,net=gross-z['cost']-z['fee']-obs,admission=ad)
def oracle(y,z,policy):
    a=z['actions'].copy();ad=z['admissions'].get('recovery1') or z['admissions'].get('recovery2');groups=[];alarm=None;obs=0
    if ad and policy!='OFF':
        j,t=ad;prefix=np.r_[0,np.cumsum(y==Q[j,7])];end=t
        while end+BLOCK<=H and len(groups)<MAX:
            w=int(prefix[end+BLOCK]-prefix[end]);end+=BLOCK;groups.append((end,w))
            if w<=K:alarm=end;break
        obs=(end if alarm is not None or len(groups)==MAX else H)-t
        if alarm is not None and policy=='STOP':a[alarm:]=0
    gross=0
    for j in (A,B):
        selected=y[a==j];gross+=2000*int(np.sum(selected==Q[j,7]))-1200*len(selected)
    return dict(actions=a,groups=groups,alarm=alarm,obs=obs,gross=gross,net=gross-z['cost']-z['fee']-obs,admission=ad)
def study():
    c=Counter();out={};fixtures={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def check(y,req,m):
        z=R['simulate'](y,req,m);e,ad,a,sp,net=R['oracle'](y,req,m)
        ck('parent_oracle',e==z['entries'] and ad==z['admissions'] and np.array_equal(a,z['actions']) and sp==z['spent'] and net==z['net']);ck('admission_budget',sp<=35)
        zz={p:apply(y,z,p) for p in POLICIES}
        for p,s in zz.items():
            q=oracle(y,z,p);ck('monitor_oracle',all(s[k]==q[k] for k in s if k!='actions') and np.array_equal(s['actions'],q['actions']));ck('accounting',s['net']==s['gross']-z['cost']-z['fee']-s['obs']);ck('monitor_budget',len(s['groups'])<=MAX);ck('permission',np.all((s['actions']==0)|(s['actions']==z['actions'])))
            if s['admission']:
                j,t=s['admission'];ck('pre_admission_unchanged',np.array_equal(s['actions'][:t],z['actions'][:t]));prev=t
                for end,w in s['groups']:
                    ck('fresh_disjoint_group',end-prev==BLOCK and w==int(np.sum(y[prev:end]==Q[j,7])));prev=end
                if s['alarm'] is not None:ck('first_alarm',s['groups'][-1][0]==s['alarm'] and s['groups'][-1][1]<=K and all(w>K for _,w in s['groups'][:-1]))
            if p=='STOP' and s['alarm'] is not None:ck('terminal_stop',np.all(s['actions'][s['alarm']:]==0))
        ck('off_regression',zz['OFF']['net']==z['net'] and np.array_equal(zz['OFF']['actions'],z['actions']));ck('matched_monitor_cost',zz['SHADOW']['obs']==zz['STOP']['obs'] and zz['SHADOW']['groups']==zz['STOP']['groups']);ck('shadow_trades_unchanged',np.array_equal(zz['SHADOW']['actions'],z['actions']))
        return z,zz
    for name,(req,phases) in CASES.items():
        ps=np.zeros(H,dtype=int)
        for t,p in phases:ps[t:]=p
        totals={m:{p:Counter() for p in POLICIES} for m in MODES}
        for seed in SEEDS:
            y=np.where(np.random.default_rng(seed).random(H)<ps/100,1,-1)
            for m in MODES:
                z,zz=check(y,req,m)
                for p,s in zz.items():
                    v=totals[m][p];v['net']+=s['net'];v['monitor_cost']+=s['obs'];v['trades']+=int(np.count_nonzero(s['actions']));ad=s['admission']
                    if ad:
                        j,t=ad;winp=int(ps[t]) if Q[j,7]==1 else 100-int(ps[t]);v['admitted']+=1;v['nonpositive_at_admission']+=int(winp<=60)
                        if s['alarm'] is not None:
                            v['alarms']+=1;v['delay_sum']+=s['alarm']-t;v['alarms_nonpositive_at_admission']+=int(winp<=60);v['stops']+=int(p=='STOP')
                if seed==SEEDS[0] and zz['STOP']['admission']:
                    t=zz['STOP']['admission'][1]
                    for cut in {t,min(H,t+32),zz['STOP']['alarm'] or H}:
                        yy=y.copy();yy[cut:]*=-1;other=R['simulate'](yy,req,m);s=apply(yy,other,'STOP');ref=zz['STOP'];ck('future_prefix',np.array_equal(s['actions'][:cut],ref['actions'][:cut]) and [g for g in s['groups'] if g[0]<=cut]==[g for g in ref['groups'] if g[0]<=cut])
        out[name]={m:{p:{**dict(v),'mean_net':v['net']/len(SEEDS),'mean_monitor_cost':v['monitor_cost']/len(SEEDS),'mean_delay':v['delay_sum']/v['alarms'] if v['alarms'] else None} for p,v in mm.items()} for m,mm in totals.items()}
    for name,tail in [('stable',np.ones(H-2304,dtype=int)),('boundary_flip',-np.ones(H-2304,dtype=int)),('weak_loss',np.tile([1,1,1,-1,-1,-1,-1,-1],(H-2304+7)//8)[:H-2304]),('temporary',np.r_[-np.ones(32,dtype=int),np.ones(H-2336,dtype=int)])]:
        y=np.r_[np.tile([1,-1],1032),np.ones(240,dtype=int),tail].astype(int);z,zz=check(y,True,'SPREAD');ck('fixture_admission',z['admissions'].get('recovery2')==(A,2304));fixtures[name]={p:{k:v for k,v in s.items() if k not in ('actions','groups')} for p,s in zz.items()}
    ck('immediate_stop',fixtures['boundary_flip']['STOP']['alarm']==2336);ck('no_stop_stable',fixtures['stable']['STOP']['alarm'] is None);ck('weak_not_detected',fixtures['weak_loss']['STOP']['alarm'] is None);ck('temporary_stop',fixtures['temporary']['STOP']['alarm']==2336)
    for remaining in (0,1,31,32,33):
        t=H-remaining;y=-np.ones(H,dtype=int);a=np.zeros(H,dtype=int);a[t:]=A;z=dict(actions=a,admissions={'recovery2':(A,t)},cost=0,fee=0)
        s=apply(y,z,'STOP');q=oracle(y,z,'STOP');ck('boundary',s['alarm']==(t+32 if remaining>=32 else None) and s['obs']==min(remaining,32) and np.array_equal(s['actions'],q['actions']))
    tail=sum(math.comb(BLOCK,i)*3**i*2**(BLOCK-i) for i in range(K+1))/5**BLOCK
    ck('parent_alarm_bound',tail*DEN<=1);bound=((H-1040)//BLOCK)*tail
    return dict(passed=sum(c.values()),counts=dict(c),random_trials=len(CASES)*len(SEEDS)*len(MODES)*len(POLICIES),fixture_trials=4*3,plan_sha=SHA,alarm_bound=bound),dict(plan=PLAN,plan_sha=SHA,summary=out,fixtures=fixtures,alarm_bound=bound)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,v in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round125_{k}.json').write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
