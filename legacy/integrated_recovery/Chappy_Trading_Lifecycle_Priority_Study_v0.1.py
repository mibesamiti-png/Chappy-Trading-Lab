"""R115: deterministic priority and horizon boundary audit, synthetic only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
from collections import Counter
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Lifecycle_Audit_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='62b7e8475d70e76eb04201a4cdbb6a192a718f3a63dc6753a3e4e05675cf19ca':raise ValueError('R114 hash')
R=runpy.run_path(str(P)); Q=R['Q']; T=R['T']; B=R['B']; TRAIN=R['TRAIN']; COOL=R['COOL']; N=R['N']; LOOKS=R['LOOKS']; LIMIT=R['LIMIT']; REL=R['REL']; K=R['K']; H=R['H']
PLAN=dict(parent=R['SHA'],changes='no activation, resume or rollback at final boundary',cases=['full','compare_stop','rollback_stop','audit_stop','exhaust','dedup','support_mismatch','terminal_resume','terminal_rollback','terminal_admit','terminal_compare'],seeds=list(range(115000,115008)),synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def simulate(x,y,mode='FULL'):
    h=len(x); state='TRAIN'; train_start=0; active=0; archive=[]; audits={}; passed={}; phase='initial'; cool_end=0; refreshed=resumed=attempts=looks=0; compare_start=None; compare_done=False; switched=rolled=False; old=0; hist=[]; block=[]; rel=[]; gross=fees=obs=trades=0; events=[]; actions=np.zeros(h,dtype=np.int16); observed=np.zeros(h,dtype=bool)
    def event(t,kind,**kw):events.append(dict(t=t,kind=kind,**kw))
    def select(j,t,kind):
        nonlocal active,hist,block,rel
        active=j;hist=[];block=[];rel=[];event(t,kind,j=j)
    def start_audit(js,t,p):
        nonlocal audits,passed,phase,state
        audits={int(j):[0,0,False] for j in dict.fromkeys(js) if j};passed={};phase=p;state='AUDIT' if audits else 'DONE';event(t,'audit_start',phase=p,js=list(audits))
    def stop(t):
        nonlocal active,state,train_start,refreshed,cool_end,audits,compare_start,compare_done,old
        event(t,'stop',j=active);active=0;audits={};old=0
        if compare_start is not None:compare_done=True
        compare_start=None
        if mode=='FULL' and not refreshed:
            refreshed=1;train_start=t;state='TRAIN';event(t,'refresh')
        elif mode=='FULL' and not resumed and attempts<2:
            cool_end=t+COOL;state='COOL'
        else:state='DONE'
    for i in range(h):
        if state=='DONE':break
        observed[i]=True;obs+=1; t=i+1; xx=int(x[i]); yy=int(y[i]); j=active
        # Action chosen exclusively from prior evidence and current input.
        if j:
            d=int(T[j,xx]);win=d==yy
            if d:
                if len(hist)>=4 and sum(hist[-4:])>=3:
                    actions[i]=j;gross+=800 if win else -1200;trades+=1
                hist.append(win);block.append(win)
            absolute_alarm=len(block)==32 and sum(block)<=LIMIT
            if len(block)==32:block=[]
            if absolute_alarm:
                stop(t);continue
            if switched and not rolled and old and np.array_equal(T[j]!=0,T[old]!=0) and d and d!=int(T[old,xx]):
                rel.append(win)
                if len(rel)==32:
                    if sum(rel)<=REL and t<h:
                        rolled=True;fees+=200;select(old,t,'rollback');continue
                    rel=[]
        if state=='TRAIN' and t-train_start==TRAIN:
            new=int(Q['R']['select'](x[train_start:t],y[train_start:t]));event(t,'selected',j=new,start=train_start)
            js=[new] if not refreshed else [*archive,new];archive=list(dict.fromkeys(j for j in js if j));start_audit(archive,t,'refresh' if refreshed else 'initial');continue
        if state=='COOL' and t>=cool_end:
            attempts+=1;start_audit(archive,t,'recovery');continue
        if state=='AUDIT':
            for k,v in audits.items():
                if v[2]:continue
                d=int(T[k,xx]);
                if not d:continue
                v[0]+=1;v[1]+=int(d==yy)
                if v[0] in K:
                    looks+=1;ok=v[1]>=K[v[0]];event(t,'look',phase=phase,j=k,n=v[0],w=v[1],passed=ok)
                    if ok:passed[k]=t;v[2]=True
                    elif v[0]==LOOKS[-1]:v[2]=True
            if passed and not active and t<h:
                k=next(iter(passed));select(k,t,'resume' if phase=='recovery' else 'admit');
                if phase=='recovery':resumed=1;fees+=200;state='LIVE';audits={};continue
            if all(v[2] for v in audits.values()):
                if active:
                    state='LIVE'
                    if mode=='FULL' and len(passed)==2 and not compare_done:compare_start=t
                elif mode=='FULL' and phase!='initial' and not resumed and attempts<2:
                    state='COOL';cool_end=t+COOL
                else:state='DONE'
        if active and compare_start is not None and t==compare_start+N:
            other=next(k for k in passed if k!=active);d=B['netvec'](x[compare_start:t],y[compare_start:t],other)-B['netvec'](x[compare_start:t],y[compare_start:t],active);lo,hi=B['bounds'](active,other);mar=B['margin']('EB',N,hi-lo,float(d.var(ddof=1)));ok=t<h and (float(d.mean())-mar)*(h-t)>200
            event(t,'compare',j=active,other=other,start=compare_start,accepted=bool(ok));compare_done=True;compare_start=None
            if ok:old=active;switched=True;fees+=200;select(other,t,'switch')
    return dict(net=gross-obs-fees,gross=gross,obs=obs,fees=fees,trades=trades,events=events,actions=actions,observed=observed,looks=looks,attempts=attempts)

def fixtures():
    f=R['fixture']; out={'full':f()}
    x,y=f();x[2096:2112]=0;y[2096:2112]=1;y[2112:4160]=T[256,x[2112:4160]];x[4128:4160]=7;y[4128:4160]=-1;out['compare_stop']=x,y
    x,y=f();x[4176:4208]=0;y[4176:4208]=1;x[4208:4240]=7;y[4208:4240]=1;out['rollback_stop']=x,y
    x,y=f();x[2096:2112]=0;y[2096:2112]=1;y[2096]=-1;x[2112:2128]=np.tile([7,0,0,0],4);x[2112:2114]=7;y[2112:2128]=1;x[2128:2160]=7;y[2128:2160]=-1;out['audit_stop']=x,y
    x,y=f();x[4272:]=0;y[4272:]=np.tile([1,-1],(len(y)-4272)//2);out['exhaust']=x,y
    x,y=f();y[1072:2096]=1;out['dedup']=x,y
    x,y=f()
    for i in range(1024):y[i]=-1 if x[i]<2 else (1 if (i//8)%2==0 else -1)
    x[1024:1072]=0;y[1024:1040]=-1;y[1040:1072]=1;y[1072:2096]=1
    x[2096:2112]=0;y[2096:2112]=-1;x[2112:4288]=2;y[2112:4288]=1
    x[4288:4352]=np.tile([0,2],32);y[4288:4352]=np.tile([-1,1],32);out['support_mismatch']=x,y
    for name,h in [('terminal_resume',4544),('terminal_rollback',4240),('terminal_admit',1040),('terminal_compare',4176)]:
        x,y=f();out[name]=x[:h],y[:h]
    return out

def replay(x,y,r,ck):
    # Independent scalar event/action/monitor oracle; not an independent training state machine.
    by={}; starts={}; approved=set(); current=prior=0; did_rollback=False; recent=[]; block=[]; relative=[]; gross=0; seen=0; fees=0; h=len(x)
    for e in r['events']:by.setdefault(e['t'],[]).append(e)
    for i,(a,b) in enumerate(zip(x,y)):
        t=i+1;a=int(a);b=int(b);es=by.get(t,[]); kinds=[e['kind'] for e in es]; obs=bool(r['observed'][i]); d=int(T[current,a]); expected=0; abs_alarm=rel_alarm=False
        if obs:
            seen+=1
            if current and d:
                win=int(d==b)
                if len(recent)>=4 and sum(recent[-4:])>=3:expected=current;gross+=800 if win else -1200
                recent.append(win);block.append(win)
                if len(block)==32:abs_alarm=sum(block)<=LIMIT;block=[]
                if not abs_alarm and prior and not did_rollback and all(bool(u)==bool(v) for u,v in zip(T[current],T[prior])) and d!=int(T[prior,a]):
                    relative.append(win)
                    if len(relative)==32:rel_alarm=sum(relative)<=REL and t<h;relative=[]
        ck('scalar_action',int(r['actions'][i])==expected)
        ck('absolute_priority',('stop' in kinds)==abs_alarm)
        ck('relative_priority',('rollback' in kinds)==rel_alarm)
        if abs_alarm:ck('stop_exclusive',not any(k in kinds for k in ('look','compare','switch','rollback','admit','resume')))
        for e in es:
            k=e['kind'];j=e.get('j',0)
            if k=='audit_start':
                starts={j:t for j in e['js']};approved=set() if not current else approved;ck('unique_candidates',len(starts)==len(e['js']) and all(starts))
            elif k=='look':
                vals=[int(T[j,int(a0)])==int(b0) for a0,b0 in zip(x[starts[j]:t],y[starts[j]:t]) if T[j,int(a0)]]
                ck('scalar_audit',len(vals)==e['n'] and sum(vals)==e['w'] and e['passed']==(sum(vals)>=K[len(vals)]))
                if e['passed']:approved.add(j)
            elif k=='stop':current=prior=0;recent=[];block=[];relative=[]
            elif k=='compare':
                other=e['other'];diff=[B['payoff'](other,int(a0),int(b0))-B['payoff'](j,int(a0),int(b0)) for a0,b0 in zip(x[e['start']:t],y[e['start']:t])];mean=sum(diff)/len(diff);var=sum((v-mean)**2 for v in diff)/(len(diff)-1);bounds=[B['payoff'](other,a0,b0)-B['payoff'](j,a0,b0) for a0 in range(8) for b0 in (-1,1)];width=max(bounds)-min(bounds);margin=math.sqrt(2*var*math.log(40)/len(diff))+7*width*math.log(40)/(3*(len(diff)-1));ck('scalar_compare',e['accepted']==(t<h and (mean-margin)*(h-t)>200) and j==current and other in approved)
            elif k in ('admit','resume','switch','rollback'):
                ck('activation_authority',j in approved and t<h)
                if k=='switch':prior=current;fees+=200
                elif k=='rollback':did_rollback=True;fees+=200;ck('rollback_target',j==prior)
                elif k=='resume':fees+=200
                current=j;recent=[];block=[];relative=[]
    ck('scalar_account',r['net']==gross-seen-fees and r['gross']==gross and r['obs']==seen and r['fees']==fees)
    ck('finite_budget',r['looks']<=35 and r['attempts']<=2 and all(sum(e['kind']==k for e in r['events'])<=1 for k in ('switch','rollback','resume','refresh')))

def study():
    c=Counter(); samples={}; regress=0
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    for name,(x,y) in fixtures().items():
        r=simulate(x,y);old=R['simulate'](x,y);replay(x,y,r,ck);ev=r['events'];h=len(x); kinds=lambda t:[e['kind'] for e in ev if e['t']==t]
        if name=='compare_stop':
            ck('compare_stop',kinds(4160)==['stop']);d=B['netvec'](x[2112:4160],y[2112:4160],256)-B['netvec'](x[2112:4160],y[2112:4160],9);lo,hi=B['bounds'](9,256);ck('suppressed_winning_compare',(float(d.mean())-B['margin']('EB',N,hi-lo,float(d.var(ddof=1))))*(h-4160)>200)
        elif name=='rollback_stop':ck('rollback_stop',kinds(4240)==['stop'] and np.all(T[256,x[4208:4240]]!=y[4208:4240]) and np.all(T[9,x[4208:4240]]==y[4208:4240]))
        elif name=='audit_stop':ck('audit_stop',kinds(2160)==['stop'] and int((T[256,x[2096:2160]]==y[2096:2160]).sum())>=K[64])
        elif name=='exhaust':ck('exhaust',r['attempts']==2 and r['obs']==5296 and not any(e['kind']=='resume' for e in ev) and not r['actions'][5296:].any())
        elif name=='dedup':ck('dedup',[e['js'] for e in ev if e['kind']=='audit_start']==[[9],[9]])
        elif name=='support_mismatch':ck('support_mismatch',any(e['kind']=='switch' and e['j']==9 for e in ev) and not any(e['kind']=='rollback' for e in ev) and np.all(T[9,x[4288:4352:2]]!=y[4288:4352:2]))
        elif name.startswith('terminal_'):
            ck('terminal_no_activation',not any(e['t']==h and e['kind'] in ('admit','switch','rollback','resume') for e in ev));ck('terminal_same_actions',np.array_equal(r['actions'],old['actions']));ck('terminal_fee',old['fees']-r['fees']==(200 if name in ('terminal_resume','terminal_rollback') else 0))
        if not name.startswith('terminal_'):ck('unchanged_fixture',ev==old['events'] and r['net']==old['net'] and np.array_equal(r['actions'],old['actions']))
        samples[name]=dict(net=r['net'],old_net=old['net'],fees=r['fees'],old_fees=old['fees'],obs=r['obs'],attempts=r['attempts'],looks=r['looks'],events=ev)
    for case in R['CASES']:
        for seed in PLAN['seeds']:
            x,y=R['generate'](seed,case)
            for mode in ('FULL','STOP_ONLY'):
                r=simulate(x,y,mode);old=R['simulate'](x,y,mode);replay(x,y,r,ck);ck('parent_regression',r['events']==old['events'] and r['net']==old['net'] and np.array_equal(r['actions'],old['actions']));regress+=1
    return dict(passed=sum(c.values()),counts=dict(c),plan_sha=SHA,fixtures=len(samples),regression_trials=regress),dict(plan=PLAN,plan_sha=SHA,fixtures=samples)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();t,e=study()
    for k,z in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round115_{k}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
