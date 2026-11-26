"""R101: single-clock synthetic hypothesis selection, audit and deployment. No orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from itertools import product
import numpy as np
ROOT=Path(__file__).parent

def load(name,sha):
    p=ROOT/name
    if hashlib.sha256(p.read_bytes()).hexdigest()!=sha: raise ValueError(name+' hash')
    return runpy.run_path(str(p))
R=load('Chappy_Trading_Rare_Evidence_Study_v0.1.py','c3197b341bd9abe81b21a5d0cb44f6d84dad3daab5d1151adb08f46ca267677a')
M=load('Chappy_Trading_Economic_Monitor_Study_v0.1.py','e3e830034f1e13382232ebe6d5658ff38722e36570ab0e34210ab294abe919d4')
S=R['S']; T=S['T']; inputs=S['R']['inputs']; W=S['WEIGHTS']['skewed']; TRAIN=1024; H=8192; SHIFT=4096; SEEDS=range(101000,101064); FEE=1
CASES={'null':((50,)*4,(50,)*4),'rare_boundary':((50,50,50,60),)*2,'strong':((75,25,25,75),)*2,'rare':((50,50,50,90),)*2,'strong_reversal':((75,25,25,75),(25,75,75,25)),'rare_disappears':((50,50,50,90),(50,)*4)}
METHODS={'FULL_FIXED32':(2,'FIXED32',False),'SELECT_FIXED32':(3,'FIXED32',False),'SELECT_FIXED256':(3,'FIXED256',False),'SELECT_SPEND':(3,'SPEND',False),'SELECT_SPEND_MONITOR':(3,'SPEND',True),'WAIT':None}
PLAN=dict(synthetic_only=True,seed=list(SEEDS),weights=W,cases=CASES,train=TRAIN,horizon=H,shift=SHIFT,methods=METHODS,observation_fee=FEE,win_yen=800,loss_yen=-1200,clock='input at slot start; outcome at end; audit pass applies next slot',monitor='R82 NET on last 4 eligible mature shadow outcomes since training ended; no re-selection; 1 yen per live calendar slot',no_retest=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
# Same fixed direction net gate, translated from R82 calendar to eligible-outcome clock.
NET={v:M['decide']('NET',6,20,[dict(index=i,received=i+3,bps=100*x) for i,x in enumerate(v)])['action']=='TRADE' for v in product((-1,1),repeat=4)}

def series(seed,case):
    a,b=CASES[case]; x,y,_=inputs(seed,SHIFT,W,a);xx,yy,_=inputs(seed+100000,H-SHIFT,W,b)
    return np.concatenate((x,xx)),np.concatenate((y,yy))

def simulate(x,y,j,policy,monitor):
    if j==0:return dict(candidate=0,admitted=False,pass_at=None,stop=TRAIN,audit_n=0,audit_w=0,train_fee=TRAIN,audit_fee=0,monitor_fee=0,trades=0,gross=0,net=-TRAIN,pre_net=-TRAIN,post_net=0,post_trades=0,eligible_live=0)
    d=T[j,x]; ix=np.flatnonzero(d[TRAIN:])+TRAIN; hits=(d[ix]==y[ix]); cs=np.cumsum(hits); passed=False; stop=H; n=len(ix)
    for k,a in R['POL'][policy]:
        if len(ix)<k:break
        stop=int(ix[k-1])+1;n=k
        if int(cs[k-1])>=R['R']['K'][a][k]:passed=True;break
    else: pass
    # If not enough observations for the final look and not already passed, observe to horizon.
    if not passed and len(ix)<R['POL'][policy][-1][0]:stop=H;n=len(ix)
    w=int(cs[n-1]) if n else 0
    live=ix[n:] if passed else ix[:0]
    if monitor and passed:
        allowed=np.array([k>=4 and NET[tuple(1 if z else -1 for z in hits[k-4:k])] for k in range(n,len(ix))],dtype=bool)
        live=live[allowed]
    pnl=np.where(d[live]==y[live],800,-1200); gross=int(pnl.sum());post=int(pnl[live>=SHIFT].sum());mf=H-stop if monitor and passed else 0
    audit_fee=stop-TRAIN;pre_fee=min(stop,SHIFT)+ (max(0,SHIFT-stop) if monitor and passed else 0);post_fee=max(0,stop-SHIFT)+(H-max(stop,SHIFT) if monitor and passed else 0)
    return dict(candidate=j,admitted=passed,pass_at=stop if passed else None,stop=stop,audit_n=n,audit_w=w,train_fee=TRAIN,audit_fee=audit_fee,monitor_fee=mf,trades=len(live),gross=gross,net=gross-stop-mf,pre_net=gross-post-pre_fee,post_net=post-post_fee,post_trades=int(np.count_nonzero(live>=SHIFT)),eligible_live=len(ix)-n if passed else 0)

def oracle(x,y,j,policy,monitor):
    # Independent per-slot state machine; action before observing current outcome.
    st='AUDIT' if j else 'DONE';n=w=trades=gross=post=pt=af=mf=live=0;stop=TRAIN;passed=False;hist=[];schedule=dict(R['POL'][policy]); last=max(schedule);pa=None
    for i in range(TRAIN,H):
        d=int(T[j,x[i]]); win=d==int(y[i]);
        if st=='AUDIT':
            af+=1;stop=i+1
            if d:
                n+=1;w+=win;hist.append(win)
                if n in schedule:
                    if w>=R['R']['K'][schedule[n]][n]:st='LIVE';passed=True;pa=i+1
                    elif n==last:st='DONE'
        elif st=='LIVE':
            mf+=monitor
            if d:
                live+=1
                if not monitor or (len(hist)>=4 and sum(hist[-4:])>=3):
                    p=800 if win else -1200;gross+=p;trades+=1
                    if i>=SHIFT:post+=p;pt+=1
                hist.append(win)
    return (passed,pa,stop,n,w,af,mf,trades,gross,gross-TRAIN-af-mf,pt,live)

def study(test=False):
    c={};out={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        c[k]=c.get(k,0)+1
    for v,g in NET.items():ck('monitor_map',g,sum(v)>0.8)
    for case in CASES:
        rows={k:[] for k in METHODS};truth={m:S['theory'](m,W)/20000 for m in set(CASES[case])}
        for seed in SEEDS:
            x,y=series(seed,case);js=S['choose'](x,y,TRAIN)
            if test:
                d=T[:,x[:TRAIN]];score=np.where(d==0,0,np.where(d==y[:TRAIN],800,-1200)).sum(axis=1)
                ck('selection',(js[2],js[3]),(int(np.argmax(score[:257])),int(np.argmax(score))))
            for method,opt in METHODS.items():
                if opt is None:r=dict(candidate=0,admitted=False,pass_at=None,stop=0,audit_n=0,audit_w=0,train_fee=0,audit_fee=0,monitor_fee=0,trades=0,gross=0,net=0,pre_net=0,post_net=0,post_trades=0,eligible_live=0)
                else:
                    idx,p,mon=opt;j=js[idx];r=simulate(x,y,j,p,mon)
                    if test:
                        ck('replay',tuple(r[k] for k in ('admitted','pass_at','stop','audit_n','audit_w','audit_fee','monitor_fee','trades','gross','net','post_trades','eligible_live')),oracle(x,y,j,p,mon))
                        ck('fee_balance',r['net'],r['gross']-r['train_fee']-r['audit_fee']-r['monitor_fee']);ck('phase_balance',r['net'],r['pre_net']+r['post_net']);ck('no_pre_adoption_trade',r['trades']<=r['eligible_live'],True)
                        if r['admitted']:
                            # Mask all future outcomes at approval: approval and evidence cannot change.
                            yy=y.copy();yy[r['stop']:]*=-1;z=simulate(x,yy,j,p,False);ck('future_mask',tuple(r[k] for k in ('pass_at','audit_n','audit_w')),tuple(z[k] for k in ('pass_at','audit_n','audit_w')))
                r['initial_expected_yen_per_slot']=float(truth[CASES[case][0]][r['candidate']]);rows[method].append(r)
            if test:
                a=rows['SELECT_SPEND'][-1];b=rows['SELECT_SPEND_MONITOR'][-1];ck('paired_approval',(a['candidate'],a['pass_at'],a['audit_n']),(b['candidate'],b['pass_at'],b['audit_n']))
        out[case]={}
        for method,rs in rows.items():
            ad=[r for r in rs if r['admitted']];out[case][method]=dict(admitted=len(ad),nonpositive_initial_admissions=sum(r['initial_expected_yen_per_slot']<=0 for r in ad),mean_pass_slot=sum(r['pass_at'] for r in ad)/len(ad) if ad else None,**{'mean_'+k:sum(r[k] for r in rs)/len(rs) for k in ('train_fee','audit_fee','monitor_fee','trades','gross','net','pre_net','post_net','post_trades')})
    return dict(passed=sum(c.values()),counts=c,plan_sha=SHA) if test else dict(plan=PLAN,plan_sha=SHA,summary=out)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(study(a.self_test),indent=2,sort_keys=True))
