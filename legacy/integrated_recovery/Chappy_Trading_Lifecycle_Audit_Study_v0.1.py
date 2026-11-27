"""R114: bounded chronological lifecycle integration audit. Artificial data only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
from collections import Counter
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Recovery_Requalification_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='cb5390fef100ed9e77d1879766308e0bff4d8b03ca591b6a827b21b0bb8e8c39':raise ValueError('R113 hash')
R=runpy.run_path(str(P)); A=R['A']; Q=A['B']; T=A['T']; B=R['B']; H=R['H']; TRAIN=1024; COOL=256; N=2048; LOOKS=A['LOOKS']; LIMIT=R['K']; REL=R['R']['R']['K']['BLOCK_SPEND']; K={n:Q['R']['cutoff'](n,700) for n in LOOKS}; SEEDS=range(114000,114032)
# Up to 35 admission looks: 1 initial + 2 refresh + 2*2 recovery candidates, 5 looks each.
CASES={**A['R']['CASES'], 'null':[(H,(70,20,9,1),(50,)*4)], 'repeat':[(4096,(70,20,9,1),(75,25,25,75)),(4608,(70,20,9,1),(25,75,75,25)),(6656,(70,20,9,1),(75,25,25,75)),(H,(70,20,9,1),(25,75,75,25))]}
PLAN=dict(cases=CASES,seeds=list(SEEDS),horizon=H,train=TRAIN,cool=COOL,compare=N,admission_den=700,look_limit=35,absolute_limit=LIMIT,relative_limit=REL,refresh_max=1,recovery_attempts=2,resume_max=1,comparison_max=1,rollback_max=1,fee=200,observation_fee=1,fixtures='deterministic train/admit/stop/refresh/both pass/compare/switch/rollback/stop/resume and future masks',synthetic_only=True,relative_scope='identical nonzero support, only opposite directions differ',priority='absolute stop > rollback > comparison switch',short_pause='last four eligible shadows, >=3 wins',monitor='nonoverlapping 32 eligible live observations, reset on active identity change; not a global error bound')
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def generate(seed,case):
    xs=[];ys=[];start=0
    for i,(end,w,p) in enumerate(CASES[case]):
        x,y,_=A['R']['inputs'](seed+i*1000000,end-start,w,p);xs.append(x);ys.append(y);start=end
    return np.concatenate(xs),np.concatenate(ys)
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
                    if sum(rel)<=REL:
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
            if passed and not active:
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

def fixture():
    x=np.tile(np.arange(8),H//8);y=np.ones(H,dtype=int)
    y[1040:1072]=-1
    y[1072:2096]=T[256,x[1072:2096]]
    x[2096:2112]=np.tile([7,0,0,0],4);x[2112:2128]=0
    y[2128:4176]=T[256,x[2128:4176]]
    x[4176:4240]=np.tile([0,7],32);y[4176:4240]=1
    y[4240:4272]=-1
    return x,y

def study():
    counts=Counter();summary={};samples={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        counts[k]+=1
    for n,k in K.items():
        tail=lambda z:sum(math.comb(n,i)*3**i*2**(n-i) for i in range(z,n+1));ck('threshold',700*tail(k)<=5**n<700*tail(k-1))
    x,y=fixture();r=simulate(x,y);ev=r['events'];actual=[(e['t'],e['kind'],e.get('j')) for e in ev if e['kind'] in ('selected','admit','stop','switch','rollback','resume')]
    expected=[(1024,'selected',9),(1040,'admit',9),(1072,'stop',9),(2096,'selected',256),(2112,'admit',9),(4176,'switch',256),(4240,'rollback',9),(4272,'stop',9),(4544,'resume',9)]
    ck('fixture_path',actual==expected)
    for t,kind,j in actual:
        if kind in ('stop','selected'):ck('fixture_no_trade_next',r['actions'][t]==0)
        yy=y.copy();yy[t:]*=-1;z=simulate(x,yy);ck('fixture_prefix',[e for e in z['events'] if e['t']<=t]==[e for e in ev if e['t']<=t] and np.array_equal(z['actions'][:t],r['actions'][:t]))
    ck('fixture_budget',r['looks']<=35 and r['attempts']==1);ck('fixture_accounting',r['net']==sum(B['payoff'](int(j),int(a),int(b)) for j,a,b in zip(r['actions'],x,y))-r['obs']-r['fees']);samples['full_path_fixture']=ev
    for case in CASES:
        summary[case]={}
        for mode in ('STOP_ONLY','FULL'):
            rows=[]
            for seed in SEEDS:
                x,y=generate(seed,case);r=simulate(x,y,mode);ev=r['events'];act=r['actions'];approved=set();active=0;last=0;starts={};nlooks=0
                for e in ev:
                    t=e['t'];kind=e['kind'];ck('chronology',last<=t<=H);ck('action_authority',np.all((act[last:t]==0)|(act[last:t]==active)));last=t
                    if kind=='audit_start':starts={j:t for j in e['js']};approved=set() if not active else approved
                    elif kind=='selected':ck('selection_prefix',e['j']==Q['R']['select'](x[e['start']:t],y[e['start']:t]))
                    elif kind=='look':
                        j=e['j'];d=T[j,x[starts[j]:t]];mask=d!=0;ck('look_counts',e['n']==int(mask.sum()) and e['w']==int((d[mask]==y[starts[j]:t][mask]).sum()));ck('look_decision',e['passed']==(e['w']>=K[e['n']]));nlooks+=1
                        if e['passed']:approved.add(j)
                    elif kind in ('admit','resume','switch','rollback'):ck('admitted_only',e['j'] in approved);active=e['j']
                    elif kind=='stop':active=0
                    elif kind=='compare':ck('comparison_window',t-e['start']==N and e['j'] in approved and e['other'] in approved)
                ck('final_authority',np.all((act[last:]==0)|(act[last:]==active)));ck('budget',nlooks==r['looks']<=35 and r['attempts']<=2);ck('finite',all(sum(e['kind']==k for e in ev)<=1 for k in ('refresh','resume','switch','rollback','compare')));ck('fee',r['fees']==200*sum(e['kind'] in ('resume','switch','rollback') for e in ev));mask=act!=0;ck('accounting',r['net']==sum(B['payoff'](int(j),int(a),int(b)) for j,a,b in zip(act[mask],x[mask],y[mask]))-r['obs']-r['fees']);ck('observed',r['obs']==int(r['observed'].sum()) and np.all(~mask|r['observed']));ck('trades',r['trades']==int(mask.sum()))
                if seed==SEEDS.start:
                    for t in sorted(set(e['t'] for e in ev if 0<e['t']<H)):
                        # Keep total horizon fixed, alter only future outcomes.
                        yy=y.copy();yy[t:]*=-1;z=simulate(x,yy,mode);ck('future_actions',np.array_equal(act[:t],z['actions'][:t]));ck('future_events',[e for e in ev if e['t']<=t]==[e for e in z['events'] if e['t']<=t])
                rows.append(r)
            summary[case][mode]=dict(mean_net=float(np.mean([r['net'] for r in rows])),mean_trades=float(np.mean([r['trades'] for r in rows])),events={k:sum(sum(e['kind']==k for e in r['events']) for r in rows) for k in ('admit','stop','refresh','resume','switch','rollback','compare')},max_looks=max(r['looks'] for r in rows),mean_obs=float(np.mean([r['obs'] for r in rows])))
            samples[case+'/'+mode]=rows[0]['events']
    return dict(passed=sum(counts.values()),counts=dict(counts),plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,summary=summary,sample_events=samples)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();t,e=study()
    for k,z in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round114_{k}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
