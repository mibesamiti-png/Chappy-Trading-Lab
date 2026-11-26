"""R133 synthetic data recovery versus economic eligibility; no live data/orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from collections import Counter, defaultdict, deque
ROOT=Path(__file__).parent
P=ROOT/'Chappy_Trading_Stop_Reason_Study_v0.1.py'
PIN='4d7b0432b3422cb0d451ab0dcb97b3d0960f7733548139240e5077d85314b53b'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PIN:raise ValueError('R132 hash')
R=runpy.run_path(str(P)); D=R['R']; H=R['H']; SEEDS=range(133000,133032)
CASES=dict(R['CASES']);CASES.update({'outage_moderate':(25,[(0,90,100,0),(256,55,0,0),(640,55,100,0)]),'outage_delayed':(25,[(0,90,100,0),(256,90,0,0),(640,90,100,32)]),'outage_mild_good':(25,[(0,90,100,0),(256,70,0,0),(640,70,100,0)])})
MODES=('TERMINAL','ALL_REQUAL','REASON','DATA_PAUSE')
PLAN=dict(parent=PIN,seed=list(SEEDS),cases=CASES,modes=MODES,initial=[34,35],horizon=H,filter='only after DATA resume; last four eligible slots strictly after resume, all four results received before trade boundary, at least three wins; no change to R132 stop/requalification; same fees; no new alpha spend; count suppressed trade and true gain for evaluation only')
def filter_actions(e,events,a):
    h=len(e); actions=list(a['actions']); resume=next((t for t,k,v in a['log'] if k=='RESUME' and v=='DATA'),None)
    if resume is None:return actions
    by=defaultdict(list)
    for t,i,r,v in events:by[t].append((i,r,v))
    recent=deque(maxlen=4);received={}
    for t in range(resume+1,h+1):
        if actions[t-1] and not (len(recent)==4 and all(i in received for i in recent) and sum(received[i] for i in recent)>=3):actions[t-1]=0
        if e[t-1]:recent.append(t)
        for i,r,v in by[t]:
            if i>resume:received[i]=v
    return actions

def oracle_filter(e,events,a):
    resume=next((t for t,k,v in a['log'] if (k,v)==('RESUME','DATA')),None)
    if resume is None:return list(a['actions'])
    slots=[i for i,x in enumerate(e,1) if x and i>resume];by=defaultdict(list)
    for t,i,r,v in events:by[i].append((t,r,v))
    out=list(a['actions'])
    for j,t in enumerate(slots):
        if not out[t-1]:continue
        if j<4:out[t-1]=0;continue
        vals=[next((v for a,r,v in reversed(by[i]) if a<t),None) for i in slots[j-4:j]]
        out[t-1]=int(None not in vals and vals.count(1)>=3)
    return out

def run(e,y,ev,d,m,u):
    a=R['gate'](e,y,d,'REASON' if m=='DATA_PAUSE' else m,u)
    if m=='DATA_PAUSE':
        actions=filter_actions(e,ev,a);gross=sum((800 if w else -1200)*v for w,v in zip(y,actions));a=dict(a,actions=actions,gross=gross,net=gross-len(e)-a['fees'])
    return a

def study():
    c=Counter();results={};fixtures={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def check(e,y,ev,m,u,d,ref):
        a=run(e,y,ev,d,m,u);b=R['reference'](e,y,ref,'REASON' if m=='DATA_PAUSE' else m,u)
        if m=='DATA_PAUSE':
            actions=oracle_filter(e,ev,b);gross=sum((800 if w else -1200)*v for w,v in zip(y,actions));b=dict(b,actions=actions,gross=gross,net=gross-len(e)-b['fees'])
        ck('oracle',a==b);ck('budget',u<=a['used']<=35);ck('support',all(not v or e[i] for i,v in enumerate(a['actions'])));ck('account',a['net']==sum((800 if w else -1200)*v for w,v in zip(y,a['actions']))-len(e)-a['fees'])
        if m=='DATA_PAUSE':
            old=R['gate'](e,y,d,'REASON',u);ck('same_authority',a['log']==old['log'] and a['used']==old['used'] and a['fees']==old['fees']);ck('only_suppress',all(x<=z for x,z in zip(a['actions'],old['actions'])))
            t=next((t for t,k,v in a['log'] if (k,v)==('RESUME','DATA')),len(e));ck('pre_resume_unchanged',a['actions'][:t]==old['actions'][:t])
        return a
    for name,case in CASES.items():
        agg={(m,u):Counter() for m in MODES for u in (34,35)}
        for seed in SEEDS:
            e,y,ev=R['generate'](seed,case);d=D['run'](e,ev,'WAIT_HOLD');ref=D['oracle'](e,ev,'WAIT_HOLD');ck('monitor_oracle',d==ref)
            for (m,u),z in agg.items():
                a=check(e,y,ev,m,u,d,ref);z['net']+=a['net'];z['trades']+=sum(a['actions']);z['looks']+=a['used']-u;z['resumes']+=sum(k=='RESUME' for t,k,v in a['log']);z['data_resumes']+=sum((k,v)==('RESUME','DATA') for t,k,v in a['log']);z['stops']+=sum(k=='STOP' for t,k,v in a['log'])
                if m=='DATA_PAUSE':
                    old=R['gate'](e,y,d,'REASON',u);z['suppressed']+=sum(old['actions'])-sum(a['actions'])
                if seed==SEEDS[0]:
                    cut=1000;b=run(e[:cut],y[:cut],ev,D['run'](e[:cut],ev,'WAIT_HOLD'),m,u);ck('prefix',b['actions']==a['actions'][:cut] and [q for q in b['log'] if q[0]<cut]==[q for q in a['log'] if q[0]<cut])
        results[name]={f'{m}_{u}':dict(z,mean_net=z['net']/len(SEEDS),mean_trades=z['trades']/len(SEEDS)) for (m,u),z in agg.items()}
    for name,delay,pattern in [('win',0,[1]),('weak',0,[1,0]),('delayed',4,[1]),('correction',0,[1]),('missing',0,[1])]:
        e=[True]*192;y=[1]*96+[pattern[i%len(pattern)] for i in range(96)];ev=[]
        for i in range(33,193):
            if name=='missing' and i>96 and i%4==0:continue
            ev.append((i+(delay if i>96 else 0),i,1,y[i-1]))
        if name=='correction':ev.append((110,33,2,0));y[32]=0
        ev.sort();d=D['run'](e,ev,'WAIT_HOLD');ref=D['oracle'](e,ev,'WAIT_HOLD');fixtures[name]={}
        for m in MODES:
            a=check(e,y,ev,m,35,d,ref);fixtures[name][m]=dict(log=a['log'],net=a['net'],trades=sum(a['actions']),first_after_resume=next((i for i,v in enumerate(a['actions'],1) if v and i>96),None))
    ck('warmup',fixtures['win']['DATA_PAUSE']['first_after_resume']==101);ck('weak_suppress',fixtures['weak']['DATA_PAUSE']['first_after_resume'] is None);ck('delay_suppress',fixtures['delayed']['DATA_PAUSE']['first_after_resume'] is None);ck('correction',fixtures['correction']['DATA_PAUSE']['log'][-1]==(110,'STOP','CORRECTION'));ck('missing_suppress',fixtures['missing']['DATA_PAUSE']['first_after_resume'] is None)
    return dict(passed=sum(c.values()),checks=dict(c)),dict(plan=PLAN,plan_sha=R['digest'](PLAN),cases=results,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='.');a=p.parse_args();t,e=study();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for n,z in [('tests',t),('examples',e)]:(out/f'Trading_Round133_{n}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(t)
