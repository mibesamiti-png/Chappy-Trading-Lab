"""R132 synthetic reason-specific recovery; no market data or order execution."""
import argparse, hashlib, json, runpy
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
ROOT=Path(__file__).parent
P=ROOT/'Chappy_Trading_Delayed_Coverage_Study_v0.1.py'
PIN='e266a077e929dec881b29fee71129c0f3e8e521b395fb5488f982cd5f0e92868'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PIN:raise ValueError('R131 hash')
R=runpy.run_path(str(P)); N,K=R['N'],R['K']; digest=R['digest']
H=2048; COOL=256; Q=28; SEEDS=range(132000,132064)
# phase start, win percent, receipt percent, max delay; fixed eligibility percent
CASES={
 'stable':(25,[(0,90,100,0)]),
 'outage_stable':(25,[(0,90,100,0),(256,90,0,0),(640,90,100,0)]),
 'outage_bad':(25,[(0,90,100,0),(256,10,0,0),(640,10,100,0)]),
 'outage_weak':(25,[(0,90,100,0),(256,45,0,0),(640,45,100,0)]),
 'economic_recovery':(100,[(0,90,100,0),(256,10,100,0),(512,90,100,0)]),
 'economic_permanent':(100,[(0,90,100,0),(256,10,100,0)]),
 'outage_relapse':(25,[(0,90,100,0),(256,90,0,0),(640,90,100,0),(1408,10,100,0)]),
 'persistent_missing':(25,[(0,90,50,32)]),
 'rare_outage':(5,[(0,90,100,0),(256,90,0,0),(640,90,100,0)]),
}
MODES=('TERMINAL','ALL_REQUAL','REASON')
PLAN=dict(parent=PIN,horizon=H,seeds=list(SEEDS),cases=CASES,modes=MODES,initial_used=[34,35],monitor='R131 WAIT_HOLD fixed nonoverlap groups, global shadow observation, correction terminal',data_resume='first fresh fully received CLEAR group after UNKNOWN; economic alarm escalates; no alpha spend; retains original qualification',requal='first fresh group entirely after 256 ticks since stop/escalation; one look 32/28, known wins lower bound, one remaining look required; failure terminal',max_resume=1,fee='1 per calendar tick all modes including terminal shadow, 200 per resume, +800/-1200 per eligible active trade')
def generate(seed,case):
    p,phases=case;rng=np.random.default_rng(seed);e=rng.random(H)<p/100;u=rng.random(H);v=rng.random(H);truth=np.zeros(H,dtype=int);events=[];phase=0
    for i in range(H):
        if phase+1<len(phases) and i>=phases[phase+1][0]:phase+=1
        _,w,rec,d=phases[phase];truth[i]=int(u[i]<w/100)
        if e[i] and v[i]<rec/100:events.append((i+1+int(rng.integers(d+1)),i+1,1,int(truth[i])))
    return e,truth,sorted(events)
def timeline(d):
    groups=defaultdict(list);corrections=set()
    for g in d['sealed']:groups[g[0]].append(g)
    for t,i,rev,v,g,kind in d['audit']:
        row=d['sealed'][g];used=row[3][row[2].index(i)]
        if used is not None and used!=v:corrections.add(t)
    return groups,corrections

def gate(e,truth,d,mode,used):
    h=len(e);groups,corr=timeline(d);state='ACTIVE';why=None;st=0;resumed=False;log=[];actions=[];gross=0;fees=0;initial=used
    for t in range(1,h+1):
        trade=bool(e[t-1] and state=='ACTIVE');actions.append(int(trade));gross+= (800 if truth[t-1] else -1200) if trade else 0
        gs=groups.get(t,());reason='CORRECTION' if t in corr else 'ALARM' if any(g[-1]=='ALARM' for g in gs) else 'UNKNOWN' if any(g[-1]=='UNKNOWN' for g in gs) else None
        if state=='DEAD':continue
        if reason=='CORRECTION':
            state='DEAD';log.append((t,'STOP','CORRECTION'));continue
        if state=='ACTIVE' and reason:
            log.append((t,'STOP',reason));why=reason;st=t
            state='DEAD' if mode=='TERMINAL' or resumed else 'HOLD';continue
        if state!='HOLD':continue
        if reason=='ALARM' and why=='UNKNOWN':
            why='ALARM';st=t;log.append((t,'ESCALATE','ALARM'));continue
        if t>=h:continue
        if why=='UNKNOWN' and mode=='REASON':
            if not reason and any(g[2][0]>st and g[-1]=='CLEAR' and None not in g[3] for g in gs):
                state='ACTIVE';resumed=True;fees+=200;log.append((t,'RESUME','DATA'))
            continue
        if used>=35:continue
        fresh=[g for g in gs if g[2][0]>st+COOL]
        if fresh:
            g=fresh[0];used+=1;log.append((t,'LOOK',g[3].count(1)))
            if g[3].count(1)>=Q and not reason:
                state='ACTIVE';resumed=True;fees+=200;log.append((t,'RESUME','REQUAL'))
            else:state='DEAD';log.append((t,'FAIL','REQUAL'))
    return dict(log=log,actions=actions,net=gross-h-fees,gross=gross,fees=fees,used=used,initial=initial)

def reference(e,truth,d,mode,used):
    # Independent event-boundary reconstruction; calculate trades from active intervals.
    h=len(e);initial=used;log=[];open_at=0;closed=[];hold=None;resumed=False;dead=False
    all_times=sorted(set([g[0] for g in d['sealed']]+[a[0] for a in d['audit']]))
    for t in all_times:
        gs=[g for g in d['sealed'] if g[0]==t];ss={g[-1] for g in gs}
        bad=any(a[0]==t and d['sealed'][a[4]][3][d['sealed'][a[4]][2].index(a[1])] not in (None,a[3]) for a in d['audit'])
        why='CORRECTION' if bad else 'ALARM' if 'ALARM' in ss else 'UNKNOWN' if 'UNKNOWN' in ss else None
        if dead:break
        if bad or (open_at is not None and why):
            if open_at is not None:closed.append((open_at,t));open_at=None
            log.append((t,'STOP',why));dead=bad or resumed or mode=='TERMINAL';hold=(t,why);continue
        if open_at is not None or hold is None:continue
        st,r=hold
        if r=='UNKNOWN' and why=='ALARM':hold=(t,'ALARM');log.append((t,'ESCALATE','ALARM'));continue
        if t==h:continue
        if r=='UNKNOWN' and mode=='REASON':
            ok=why is None and any(min(g[2])>st and g[-1]=='CLEAR' and all(v is not None for v in g[3]) for g in gs);kind='DATA'
        else:
            fresh=next((g for g in gs if min(g[2])>st+COOL),None)
            if used==35 or fresh is None:continue
            wins=sum(v==1 for v in fresh[3]);used+=1;log.append((t,'LOOK',wins));ok=wins>=Q and why is None;kind='REQUAL'
            if not ok:dead=True;log.append((t,'FAIL','REQUAL'))
        if ok:open_at=t;hold=None;resumed=True;log.append((t,'RESUME',kind))
    if open_at is not None:closed.append((open_at,h))
    actions=[int(bool(v) and any(a<i<=b for a,b in closed)) for i,v in enumerate(e,1)]
    gross=sum((800 if y else -1200)*a for y,a in zip(truth,actions));fees=200*sum(a[1]=='RESUME' for a in log)
    return dict(log=log,actions=actions,net=gross-h-fees,gross=gross,fees=fees,used=used,initial=initial)

def study():
    c=Counter();results={};fixtures={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def check(e,y,ev,m,u,d=None,ref=None):
        if d is None:d=R['run'](e,ev,'WAIT_HOLD')
        a=gate(e,y,d,m,u);b=reference(e,y,ref if ref is not None else R['oracle'](e,ev,'WAIT_HOLD'),m,u)
        ck('oracle',a==b);ck('budget',u<=a['used']<=35 and a['used']-u<=1);ck('accounting',a['net']==a['gross']-len(e)-a['fees']);ck('support',all(not v or e[i] for i,v in enumerate(a['actions'])));ck('one_resume',sum(z[1]=='RESUME' for z in a['log'])<=1)
        for t,kind,val in a['log']:
            if kind=='STOP':ck('stop_next_slot',t==len(e) or not a['actions'][t])
            if kind=='RESUME':ck('resume_boundary',t<len(e) and (t==0 or not a['actions'][t-1]));ck('resume_authority',val=='DATA' and m=='REASON' or val=='REQUAL' and a['used']>u)
        return a
    for name,case in CASES.items():
        agg={(m,u):Counter() for m in MODES for u in (34,35)}
        for seed in SEEDS:
            e,y,ev=generate(seed,case);d=R['run'](e,ev,'WAIT_HOLD');ref=R['oracle'](e,ev,'WAIT_HOLD')
            for (m,u),z in agg.items():
                a=check(e,y,ev,m,u,d,ref);z['net']+=a['net'];z['looks']+=a['used']-u;z['trades']+=sum(a['actions']);z['stops']+=sum(q[1]=='STOP' for q in a['log']);z['escalations']+=sum(q[1]=='ESCALATE' for q in a['log']);z['resumes']+=sum(q[1]=='RESUME' for q in a['log']);z['data_resumes']+=sum(q[1:] == ('RESUME','DATA') for q in a['log']);z['requal_resumes']+=sum(q[1:] == ('RESUME','REQUAL') for q in a['log'])
                if seed==SEEDS[0]:
                    cut=1000;prefix=gate(e[:cut],y[:cut],R['run'](e[:cut],ev,'WAIT_HOLD'),m,u);ck('future_prefix',prefix['actions']==a['actions'][:cut] and [q for q in prefix['log'] if q[0]<cut]==[q for q in a['log'] if q[0]<cut])
        results[name]={f'{m}_{u}':dict(z,mean_net=z['net']/len(SEEDS)) for (m,u),z in agg.items()}
    # fixed fixtures: unknown 32, then fresh complete group 64; bad group escalates; correction terminal.
    for name,ev in {'data':[(i,i,1,1) for i in range(33,641)],'bad':[(i,i,1,0) for i in range(33,641)],'correction':[(i,i,1,1) for i in range(1,641)]+[(40,1,2,0)],'economic':[(i,i,1,int(i>32)) for i in range(1,641)]}.items():
        e=[True]*640;y=[int(name!='bad')]*640
        if name=='economic':y[:32]=[0]*32
        if name=='correction':y[0]=0
        ev=sorted(ev);fixtures[name]={}
        for m in MODES:
            for u in (34,35):
                a=check(e,y,ev,m,u);fixtures[name][f'{m}_{u}']={k:v for k,v in a.items() if k!='actions'}
    ck('data_no_budget',fixtures['data']['REASON_35']['log']==[(48,'STOP','UNKNOWN'),(96,'RESUME','DATA')]);ck('all_requal_no_budget',not any(q[1]=='RESUME' for q in fixtures['data']['ALL_REQUAL_35']['log']));ck('escalation',any(q[1]=='ESCALATE' for q in fixtures['bad']['REASON_34']['log']));ck('correction_terminal',fixtures['correction']['REASON_34']['log']==[(40,'STOP','CORRECTION')]);ck('economic_requal',fixtures['economic']['REASON_34']['used']==35 and any(q[1]=='RESUME' for q in fixtures['economic']['REASON_34']['log']))
    return dict(passed=sum(c.values()),checks=dict(c)),dict(plan=PLAN,plan_sha=digest(PLAN),cases=results,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='.');a=p.parse_args();t,e=study();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for n,z in [('tests',t),('examples',e)]:(out/f'Trading_Round132_{n}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(t)
