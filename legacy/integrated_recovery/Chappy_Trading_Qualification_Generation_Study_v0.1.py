"""R117: qualification-generation monitoring integrated into R115. Synthetic only."""
import argparse, hashlib, json, runpy
from pathlib import Path
from collections import Counter
from fractions import Fraction
from math import comb
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Monitor_Evidence_Study_v0.1.py')
PARENT='5ef476cd9edc9c9944f7dc0f785cd954657a79c1d731b73da72d8aacc6dbfac1'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PARENT:raise ValueError('R116 hash')
M=runpy.run_path(str(P)); R=M['R']; Q=R['Q']; T=R['T']; B=R['B']; TRAIN=R['TRAIN']; COOL=R['COOL']; N=R['N']; LOOKS=R['LOOKS']; LIMIT=R['LIMIT']; REL=R['REL']; K=R['K']; H=R['H']
SEEDS=range(117000,117004)
PLAN=dict(parent=PARENT,baseline=M['PARENT'],seeds=list(SEEDS),horizon=8192,monitor='after own qualification only, nonoverlap 32 per generation, retire on absolute stop or new audit, latch until requalified',max_candidates=2,max_monitor_looks=512,threshold=LIMIT,short_pause='unchanged/reset on activation',relative='unchanged except deny alarmed target',synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def simulate(x,y,mode='FULL'):
    if not (0<len(x)==len(y)<=8192):raise ValueError('horizon')
    qualified={}; generations=Counter(); monitor=[]; denied=[]; monitor_looks=0
    h=len(x); state='TRAIN'; train_start=0; active=0; archive=[]; audits={}; passed={}; phase='initial'; cool_end=0; refreshed=resumed=attempts=looks=0; compare_start=None; compare_done=False; switched=rolled=False; old=0; hist=[]; block=[]; rel=[]; gross=fees=obs=trades=0; events=[]; actions=np.zeros(h,dtype=np.int16); observed=np.zeros(h,dtype=bool)
    def event(t,kind,**kw):events.append(dict(t=t,kind=kind,**kw))
    def select(j,t,kind):
        nonlocal active,hist,block,rel
        active=j;hist=[];block=[];rel=[];event(t,kind,j=j)
    def start_audit(js,t,p):
        nonlocal audits,passed,phase,state
        qualified.clear()
        audits={int(j):[0,0,False] for j in dict.fromkeys(js) if j};passed={};phase=p;state='AUDIT' if audits else 'DONE';event(t,'audit_start',phase=p,js=list(audits))
    def stop(t):
        nonlocal active,state,train_start,refreshed,cool_end,audits,compare_start,compare_done,old
        event(t,'stop',j=active);active=0;audits={};old=0;qualified.clear()
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
                hist.append(win)
        # Each generation starts strictly after its own admission look.
        for k,g in qualified.items():
            d0=int(T[k,xx])
            if g['alarm'] or not d0:continue
            g['buffer'].append((i,int(d0==yy)))
            if len(g['buffer'])==32:
                z=g['buffer'];w=sum(v for _,v in z);g['alarm']=w<=LIMIT;g['buffer']=[];monitor_looks+=1
                monitor.append(dict(t=t,j=k,generation=g['generation'],start=g['start'],indices=[a for a,_ in z],wins=w,alarm=g['alarm']))
        if j:
            if qualified[j]['alarm']:
                stop(t);continue
            d=int(T[j,xx]);win=d==yy
            if switched and not rolled and old and np.array_equal(T[j]!=0,T[old]!=0) and d and d!=int(T[old,xx]):
                rel.append(win)
                if len(rel)==32:
                    if sum(rel)<=REL and t<h:
                        rolled=True
                        if old in qualified and not qualified[old]['alarm']:
                            fees+=200;select(old,t,'rollback');continue
                        denied.append(dict(t=t,j=old,kind='rollback',reason='inactive_or_alarm'))
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
                    if ok:
                        passed[k]=t;v[2]=True;generations[k]+=1
                        qualified[k]=dict(generation=generations[k],start=t,buffer=[],alarm=False)
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
            if ok and (other not in qualified or qualified[other]['alarm']):
                denied.append(dict(t=t,j=other,kind='switch',reason='inactive_or_alarm'));ok=False
            event(t,'compare',j=active,other=other,start=compare_start,accepted=bool(ok));compare_done=True;compare_start=None
            if ok:old=active;switched=True;fees+=200;select(other,t,'switch')
    return dict(net=gross-obs-fees,gross=gross,obs=obs,fees=fees,trades=trades,events=events,actions=actions,observed=observed,looks=looks,attempts=attempts,monitor=monitor,monitor_looks=monitor_looks,denied=denied,generations=dict(generations))

def fixtures():
    out=R['fixtures']();x,y=R['R']['fixture']();x[4144:4176]=7;y[4144:4176]=1;out['alarm_denies_switch']=x,y
    # Old qualification's aligned group fails after the switch, but new wins.
    x,y=R['R']['fixture']();x[4176:4240]=7;y[4176:4240]=-1;x[4240:4304]=np.tile([0,7],32);y[4240:4304]=1;out['alarm_denies_rollback']=x,y
    return out

def audit(x,y,r,ck):
    # Reconstruct candidate generations from actual admission evidence, independently
    # split eligible indices in each generation and compare all monitor records.
    end=r['obs']; periods=[]; openp={}; gen=Counter(); starts={}; expected=[]
    for e in r['events']:
        t=e['t'];k=e['kind'];j=e.get('j')
        if k in ('stop','audit_start'):
            for v in openp.values():v['end']=t
            openp={}
        if k=='audit_start':starts={j:t for j in e['js']}
        if k=='look':
            ix=np.flatnonzero(T[j,x[starts[j]:t]]!=0)+starts[j];w=int(np.sum(T[j,x[ix]]==y[ix]));ck('admission_evidence',len(ix)==e['n'] and w==e['w'] and e['passed']==(w>=K[len(ix)]))
            if e['passed']:
                gen[j]+=1;v=dict(j=j,generation=gen[j],start=t,end=end);periods.append(v);openp[j]=v
    for v in periods:
        j=v['j'];ix=np.flatnonzero(T[j,x[v['start']:v['end']]]!=0)+v['start']
        for i in range(0,len(ix)-31,32):
            z=ix[i:i+32];w=int(np.sum(T[j,x[z]]==y[z]));e=dict(t=int(z[-1])+1,j=j,generation=v['generation'],start=v['start'],indices=z.tolist(),wins=w,alarm=w<=LIMIT);expected.append(e)
            if e['alarm']:break
    expected.sort(key=lambda e:(e['t'],next(i for i,v in enumerate(periods) if v['j']==e['j'] and v['generation']==e['generation'])))
    ck('independent_group_reconstruction',expected==r['monitor']);ck('generation_counts',dict(gen)==r['generations']);ck('monitor_budget',len(expected)==r['monitor_looks']<=512);ck('admission_budget',r['looks']<=35)
    # Check every activation against its generation and alarm status. Then reconstruct actions and accounting.
    by={};bad={};active=0;hist=[];gross=fees=trades=0;events=r['events'];valid={}; actions=np.zeros(len(x),dtype=np.int16)
    for e in events:by.setdefault(e['t'],[]).append(e)
    for e in expected:
        if e['alarm']:bad[e['j'],e['generation']]=e['t']
        ck('evidence_identity',len(e['indices'])==32 and len(set(e['indices']))==32 and min(e['indices'])>=e['start'] and max(e['indices'])==e['t']-1)
    used=set()
    for e in expected:
        keys={(e['j'],i) for i in e['indices']};ck('no_reuse',not used.intersection(keys));used.update(keys)
    g=Counter()
    for i in range(end):
        t=i+1
        if active:
            d=int(T[active,x[i]])
            if d:
                win=int(d==y[i]);
                if len(hist)>=4 and sum(hist[-4:])>=3:actions[i]=active;gross+=800 if win else -1200;trades+=1
                hist.append(win)
        es=by.get(t,[])
        alarm=bool(active and bad.get((active,valid[active]),len(x)+1)==t)
        if alarm:ck('stop_priority',[e['kind'] for e in es if e['kind'] in ('stop','switch','rollback','admit','resume')]==['stop'])
        for e in es:
            k=e['kind'];j=e.get('j')
            if k in ('stop','audit_start'):valid={};active=0;hist=[]
            if k=='look' and e['passed']:g[j]+=1;valid[j]=g[j]
            if k in ('admit','resume','switch','rollback'):
                ck('activation_authority',j in valid and bad.get((j,valid[j]),len(x)+1)>t and t<len(x));active=j;hist=[];fees+=200*int(k!='admit')
    ck('action_replay',np.array_equal(actions,r['actions']));ck('account',gross==r['gross'] and fees==r['fees'] and trades==r['trades'] and gross-fees-end==r['net'])
    for d in r['denied']:ck('denial_evidence',any(e['j']==d['j'] and e['alarm'] and e['t']<=d['t'] for e in expected))

def study():
    c=Counter(); samples={};summary={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    tail=sum(Fraction(comb(32,i)*3**i*2**(32-i),5**32) for i in range(LIMIT+1));ck('global_absolute_budget',512*tail<=Fraction(1,20))
    for name,(x,y) in fixtures().items():
        r=simulate(x,y);old=R['simulate'](x,y);audit(x,y,r,ck)
        for t in (1024,1072,2112,4176,4240):
            if t>=len(x):continue
            yy=y.copy();yy[t:]*=-1;rr=simulate(x,yy);ck('future_prefix',np.array_equal(r['actions'][:t],rr['actions'][:t]) and all([e for e in r[k] if e['t']<=t]==[e for e in rr[k] if e['t']<=t] for k in ('events','monitor','denied')))
        samples[name]=dict(net=r['net'],old_net=old['net'],events=r['events'],old_events=old['events'],generations=r['generations'],monitor_looks=r['monitor_looks'],alarms=[e for e in r['monitor'] if e['alarm']],denied=r['denied'])
    ck('switch_denied',any(d['kind']=='switch' for d in samples['alarm_denies_switch']['denied']))
    ck('rollback_denied',any(d['kind']=='rollback' for d in samples['alarm_denies_rollback']['denied']))
    ck('fresh_generation',samples['compare_stop']['generations'].get(9)==3 and any(e['kind']=='resume' for e in samples['compare_stop']['events']))
    for case in R['R']['CASES']:
        acc=Counter()
        for seed in SEEDS:
            x,y=R['R']['generate'](seed,case);r=simulate(x,y);old=R['simulate'](x,y);audit(x,y,r,ck)
            for label,z in [('old',old),('new',r)]:
                acc[label+'_net']+=z['net'];acc[label+'_stops']+=sum(e['kind']=='stop' for e in z['events']);acc[label+'_resumes']+=sum(e['kind']=='resume' for e in z['events'])
            acc['monitor_looks']+=r['monitor_looks'];acc['denied']+=len(r['denied']);acc['changed']+=int(r['events']!=old['events'] or r['net']!=old['net'])
        summary[case]=dict(acc);summary[case].update(old_mean_net=acc['old_net']/len(SEEDS),new_mean_net=acc['new_net']/len(SEEDS))
    return dict(passed=sum(c.values()),counts=dict(c),fixture_trials=len(samples),random_trials=len(summary)*len(SEEDS),plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,absolute_union_bound=float(512*tail),fixtures=samples,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,z in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round117_{k}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
