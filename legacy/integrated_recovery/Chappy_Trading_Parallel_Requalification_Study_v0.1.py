"""R118: focused parallel requalification of a previously alarmed candidate. Synthetic only."""
import argparse, hashlib, json, runpy, math
from pathlib import Path
from collections import Counter
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Qualification_Generation_Study_v0.1.py')
PARENT='5f417e5ec3d7e523e3c1180d5828ff78b2ca44404c0e7496fd36d60c10203350'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PARENT:raise ValueError('R117 hash')
R=runpy.run_path(str(P)); T=R['T']; B=R['B']; K=R['K']; LIMIT=R['LIMIT']; N=R['N']; COOL=R['COOL']; H=8192
OLD=9; ACTIVE=256; SEEDS=range(118000,118064); METHODS=('LATCH','REQUAL_ONLY','REQUAL_COMPARE')
# Each tuple: end, common-state upward probability, disagreement probability, disagreement upward probability.
CASES={'recovered':[(H,85,20,90)],'still_inferior':[(H,85,20,10)],'equal':[(H,85,20,50)],'rare_recovery':[(H,85,1,90)],'temporary_recovery':[(2600,85,20,90),(H,85,20,10)],'both_deteriorate':[(1000,85,20,90),(H,10,20,50)]}
PLAN=dict(parent=PARENT,seeds=list(SEEDS),cases=CASES,methods=METHODS,horizon=H,cool=COOL,comparison=N,admission_thresholds=K,reserved_looks=5,other_look_budget=30,absolute_limit=LIMIT,fee=200,base_observation=1,incremental_research=1,scope='prequalified incumbent and alarmed challenger at t0; one attempt and at most one switch; no restart; no short pause; full support; synthetic only')
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def generate(seed,case):
    rng=np.random.default_rng(seed);xs=[];ys=[];start=0
    for end,c,f,p in CASES[case]:
        x=np.where(rng.integers(0,100,end-start)<f,7,0); y=np.where(rng.integers(0,100,end-start)<np.where(x==7,p,c),1,-1);xs.append(x);ys.append(y);start=end
    return np.concatenate(xs),np.concatenate(ys)
def alarm(w,start):
    # Complete non-overlapping 32-result groups from a candidate's own qualification boundary.
    n=(len(w)-start)//32
    if n<=0:return None
    z=np.flatnonzero(w[start:start+32*n].reshape(n,32).sum(axis=1)<=LIMIT)
    return start+32*(int(z[0])+1) if len(z) else None
def run(x,y,mode):
    h=len(x); a=T[ACTIVE,x]==y; b=T[OLD,x]==y
    sa=alarm(a,0); active_end=sa if sa is not None else h; events=[]; looks=[]; q=None; sw=None; ca=None; compare=None; research=0; end=active_end
    if mode!='LATCH' and active_end>COOL:
        audit_end=min(active_end,COOL+256)
        for n,k in K.items():
            t=COOL+n
            if t>audit_end or (sa is not None and t>=sa):break # absolute stop wins same boundary
            w=int(b[COOL:t].sum());looks.append((t,n,w,w>=k))
            if w>=k:q=t;break
        research=(q if q is not None else audit_end)-COOL
        if q is not None and q<h:
            ca=alarm(b,q)
            if mode=='REQUAL_ONLY':sw=q
            else:
                t=q+N; compare_end=min(t,active_end,ca if ca is not None else h);research+=max(0,compare_end-q)
                if t<h and t<active_end and (ca is None or t<ca):
                    d=(b[q:t].astype(np.int64)-a[q:t])*2000; mar=B['margin']('EB',N,4000,float(d.var(ddof=1)));ok=(float(d.mean())-mar)*(h-t)>200
                    compare=dict(start=q,end=t,mean=float(d.mean()),margin=mar,accepted=bool(ok))
                    if ok:sw=t
        if sw is not None:end=ca if ca is not None else h
    actions=np.zeros(h,dtype=np.int16);actions[:sw if sw is not None else end]=ACTIVE
    if sw is not None:actions[sw:end]=OLD
    w=np.where(actions==ACTIVE,a,b);gross=int(np.sum(np.where(actions!=0,np.where(w,800,-1200),0))); fee=200*int(sw is not None)
    return dict(net=gross-end-research-fee,gross=gross,end=end,research=research,fee=fee,looks=looks,qualified=q,switch=sw,compare=compare,actions=actions,stopped=end<h or (sw is None and sa==h) or (sw is not None and ca==h))
def oracle(x,y,mode):
    h=len(x); active=ACTIVE; buffers={ACTIVE:[]}; qualified=None; switched=None; looks=[]; audit=[]; diff=[]; comparing=False; researching=mode!='LATCH'; research=0; gross=0; actions=np.zeros(h,dtype=np.int16); compare=None; ca=None; stopped=False
    for i,(xx,yy) in enumerate(zip(x,y)):
        t=i+1; actions[i]=active; w=int(T[active,xx]==yy);gross+=800 if w else -1200
        if researching and i>=COOL:research+=1
        alarms=[]
        for j,buf in buffers.items():
            buf.append(int(T[j,xx]==yy))
            if len(buf)==32:
                if sum(buf)<=LIMIT:alarms.append(j)
                buf.clear()
        if active in alarms:stopped=True;break
        if OLD in alarms:
            ca=t;del buffers[OLD];comparing=False;researching=False
        if researching and i>=COOL and qualified is None:
            audit.append(int(T[OLD,xx]==yy));n=len(audit)
            if n in K:
                ok=sum(audit)>=K[n];looks.append((t,n,sum(audit),ok))
                if ok:
                    qualified=t
                    if t<h:
                        buffers[OLD]=[]
                        if mode=='REQUAL_ONLY':active=OLD;switched=t;researching=False;del buffers[ACTIVE]
                        else:comparing=True
                    continue
                if n==256:researching=False
        elif comparing:
            diff.append(2000*(int(T[OLD,xx]==yy)-int(T[ACTIVE,xx]==yy)))
            if len(diff)==N:
                comparing=False;researching=False
                if t<h:
                    s=sum(diff);ss=sum(z*z for z in diff);var=(N*ss-s*s)/(N*(N-1));mar=math.sqrt(2*var*math.log(40)/N)+7*4000*math.log(40)/(3*(N-1));ok=(s/N-mar)*(h-t)>200
                    compare=dict(start=qualified,end=t,mean=s/N,margin=mar,accepted=bool(ok))
                    if ok:active=OLD;switched=t;del buffers[ACTIVE]
    return dict(net=gross-t-research-200*int(switched is not None),gross=gross,end=t,research=research,fee=200*int(switched is not None),looks=looks,qualified=qualified,switch=switched,compare=compare,actions=actions,stopped=stopped)
def fixtures():
    x=np.tile([0,0,0,7],H//4);y=np.ones(H,dtype=int)
    a=x.copy();b=y.copy();b[a==7]=-1
    # incumbent stops during audit; no admission at same boundary
    c=x.copy();d=y.copy();d[:COOL]=np.where(c[:COOL]==7,-1,1);d[COOL:COOL+32]=1;c[COOL:COOL+32]=7
    # challenger qualifies, then loses its own first monitoring group; incumbent remains good
    e=x.copy();f=y.copy();e[COOL+16:COOL+48]=7;f[COOL+16:COOL+48]=-1
    g=c.copy();j=d.copy();j[COOL]=-1
    return {'stop_at_look':(g,j),'recovered':(x,y),'inferior':(a,b),'stop_during_audit':(c,d),'challenger_alarm':(e,f),'final_admission':(x[:COOL+16],y[:COOL+16])}
def study():
    counts=Counter();summary={};samples={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        counts[k]+=1
    def check(x,y,m,r,deep):
        h=len(x);sw=r['switch'];q=r['qualified'];ck('budget',len(r['looks'])<=5 and 30+len(r['looks'])<=35);ck('authority',sw is None or q is not None and q<=sw<h);ck('no_early_challenger',not np.any(r['actions'][:q if q is not None else h]==OLD));ck('no_action_after_stop',not np.any(r['actions'][r['end']:]));ck('account',r['net']==r['gross']-r['end']-r['research']-r['fee']);ck('fee',r['fee']==200*int(sw is not None))
        for t,n,w,ok in r['looks']:ck('fresh_evidence',t==COOL+n and w==sum(int(T[OLD,a]==b) for a,b in zip(x[COOL:t],y[COOL:t])) and ok==(w>=K[n]))
        if sw is not None and m=='REQUAL_COMPARE':ck('independent_compare',r['compare']['start']==q and r['compare']['end']==sw and r['compare']['accepted'])
        if deep:
            o=oracle(x,y,m)
            for key in ('net','gross','end','research','fee','looks','qualified','switch','stopped'):ck('oracle_'+key,r[key]==o[key])
            ck('oracle_actions',np.array_equal(r['actions'],o['actions']))
            ck('oracle_compare',(r['compare'] is None and o['compare'] is None) or r['compare'] is not None and o['compare'] is not None and all(r['compare'][k]==o['compare'][k] for k in ('start','end','accepted')) and math.isclose(r['compare']['margin'],o['compare']['margin'],abs_tol=1e-8))
    for name,(x,y) in fixtures().items():
        samples[name]={}
        for m in METHODS:
            r=run(x,y,m);check(x,y,m,r,True);samples[name][m]={k:v for k,v in r.items() if k!='actions'}
            for t in [COOL,COOL+16,COOL+16+N]:
                if t>=len(x):continue
                yy=y.copy();yy[t:]*=-1;rr=run(x,yy,m);ck('future_actions',np.array_equal(r['actions'][:t],rr['actions'][:t]));ck('future_looks',[z for z in r['looks'] if z[0]<=t]==[z for z in rr['looks'] if z[0]<=t])
    ck('fixture_stop_priority',samples['stop_at_look']['REQUAL_COMPARE']['qualified'] is None and samples['stop_at_look']['REQUAL_COMPARE']['end']==COOL+32);ck('fixture_recovered',samples['recovered']['REQUAL_COMPARE']['switch'] is not None);ck('fixture_alarm',samples['challenger_alarm']['REQUAL_COMPARE']['switch'] is None);ck('fixture_final',samples['final_admission']['REQUAL_ONLY']['switch'] is None)
    for case in CASES:
        a={m:Counter() for m in METHODS}
        for seed in SEEDS:
            x,y=generate(seed,case)
            for m in METHODS:
                r=run(x,y,m);check(x,y,m,r,seed<118004);z=a[m];z['net']+=r['net'];z['qualified']+=int(r['qualified'] is not None);z['switched']+=int(r['switch'] is not None);z['stopped']+=int(r['stopped']);z['research']+=r['research'];z['looks']+=len(r['looks'])
                if r['switch'] is not None:
                    t=r['switch'];start=0;future=0
                    for end,c,f,p in CASES[case]:
                        future+=max(0,end-max(start,t))*f/100*(2*p/100-1)*2000;start=end
                    z['nonbeneficial_switch']+=int(future<=200)
        summary[case]={m:dict(z,mean_net=z['net']/len(SEEDS),mean_research=z['research']/len(SEEDS)) for m,z in a.items()}
    return dict(passed=sum(counts.values()),counts=dict(counts),fixture_trials=len(samples)*len(METHODS),random_trials=len(CASES)*len(SEEDS)*len(METHODS),plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,fixtures=samples,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,z in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round118_{k}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
