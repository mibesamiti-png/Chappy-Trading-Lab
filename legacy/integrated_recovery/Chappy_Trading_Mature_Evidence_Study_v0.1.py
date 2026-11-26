"""R134 synthetic post-data-resume gate; no market data/orders."""
import argparse, hashlib, json, runpy, bisect
from pathlib import Path
from collections import Counter, defaultdict
ROOT=Path(__file__).parent
P=ROOT/'Chappy_Trading_Data_Recovery_Gate_Study_v0.1.py'
PIN='e322ce2efff263bbac94aa56b1b41775ba94f603cc328a33b001390d43e4ecb0'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PIN:raise ValueError('R133 hash')
R=runpy.run_path(str(P)); B=R['R']; D=R['D']; H=R['H']; SEEDS=range(134000,134016)
CASES=dict(R['CASES']);CASES.update({'delayed_relapse':(25,[(0,90,100,0),(256,90,0,0),(640,90,100,32),(1408,10,100,32)]),'delayed_weak':(25,[(0,90,100,0),(256,45,0,0),(640,45,100,32)]),'delayed_rare':(5,[(0,90,100,0),(256,90,0,0),(640,90,100,32)])})
MODES=('REASON','STRICT','MATURE','MATURE16','FIXED16')
PLAN=dict(parent=PIN,seeds=list(SEEDS),cases=CASES,modes=MODES,initial=[34,35],horizon=H,rule='after DATA resume only, choose four consecutive eligible observations since resume; STRICT latest four; MATURE latest fully received consecutive four, not four arbitrary arrivals; MATURE16 newest event age <=16 calendar ticks; FIXED16 latest four at or before t-17 (16 complete calendar ticks before action), require all received; all use >=3 wins as of strictly before action; no new alpha spend; R132 authority/fees unchanged; true results evaluation only')

def filter_actions(e,events,a,m):
    resume=next((t for t,k,v in a['log'] if (k,v)==('RESUME','DATA')),None)
    out=list(a['actions']); evidence={}
    if resume is None or m=='REASON':return out,evidence
    by=defaultdict(list)
    for t,i,r,v in events:by[t].append((i,r,v))
    slots=[];received={}
    for t in range(resume+1,len(e)+1):
        if out[t-1]:
            end=len(slots) if m!='FIXED16' else bisect.bisect_right(slots,t-17)
            ends=range(end,3,-1) if m in ('MATURE','MATURE16') else ([end] if end>=4 else [])
            chosen=None
            for j in ends:
                w=slots[j-4:j]
                if m=='MATURE16' and t-w[-1]>16:break
                if all(i in received for i in w):chosen=w;break
            if chosen is None or sum(received[i] for i in chosen)<3:out[t-1]=0
            else:evidence[t]=tuple(chosen)
        if e[t-1]:slots.append(t)
        for i,r,v in by[t]:
            if i>resume:received[i]=v
    return out,evidence

def oracle(e,events,a,m):
    resume=next((t for t,k,v in a['log'] if (k,v)==('RESUME','DATA')),None);out=list(a['actions']);evidence={}
    if resume is None or m=='REASON':return out,evidence
    slots=[i for i,v in enumerate(e,1) if v and i>resume]; by=defaultdict(list)
    for t,i,r,v in events:by[i].append((t,v))
    # windows available after the last first receipt; revision is read as-of decision
    first={i:by[i][0][0] for i in slots if by[i]}
    windows=[(tuple(slots[j-3:j+1]),max(first.get(i,10**9) for i in slots[j-3:j+1])) for j in range(3,len(slots))]
    for j,t in enumerate(slots):
        if not out[t-1]:continue
        k=j-4 if m!='FIXED16' else bisect.bisect_right(slots,t-17)-4
        if m in ('MATURE','MATURE16'):
            k=next((q for q in range(k,-1,-1) if windows[q][1]<t),-1)
        if k<0:out[t-1]=0;continue
        w,ready=windows[k]
        if ready>=t or (m=='MATURE16' and t-w[-1]>16):out[t-1]=0;continue
        vals=[next(v for r,v in reversed(by[i]) if r<t) for i in w]
        if sum(vals)<3:out[t-1]=0
        else:evidence[t]=w
    return out,evidence

def study():
    c=Counter();results={};fixtures={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def check(e,y,ev,a,m):
        acts,proof=filter_actions(e,ev,a,m);ref,pr=oracle(e,ev,a,m)
        ck('oracle',acts==ref and proof==pr);ck('authority',all(x<=z for x,z in zip(acts,a['actions'])));ck('support',all(not x or e[i] for i,x in enumerate(acts)))
        if m=='STRICT':ck('R133_same_input',acts==R['filter_actions'](e,ev,a))
        resume=next((t for t,k,v in a['log'] if (k,v)==('RESUME','DATA')),None)
        ck('pre_resume',acts[:resume]==a['actions'][:resume] if resume is not None else acts==a['actions'])
        ck('budget',a['initial']<=a['used']<=35)
        times=defaultdict(list)
        for t,i,r,v in ev:times[i].append((t,v))
        for t,w in proof.items():
            ck('causal_evidence',resume<w[0]<w[-1]<t and all(e[i-1] for i in w) and all(any(q<t for q,v in times[i]) for i in w));ck('fresh_bound',m!='MATURE16' or t-w[-1]<=16)
        gross=sum((800 if w else -1200)*v for w,v in zip(y,acts));net=gross-len(e)-a['fees'];ck('account',net==a['net']+sum((800 if w else -1200)*(x-z) for w,x,z in zip(y,acts,a['actions'])))
        return acts,proof,net
    for name,case in CASES.items():
        agg={(m,u):Counter() for m in MODES for u in (34,35)}
        for seed in SEEDS:
            e,y,ev=B['generate'](seed,case);d=D['run'](e,ev,'WAIT_HOLD');ref=D['oracle'](e,ev,'WAIT_HOLD');ck('monitor_oracle',d==ref)
            for u in (34,35):
                a=B['gate'](e,y,d,'REASON',u);ck('base_oracle',a==B['reference'](e,y,ref,'REASON',u))
                for m in MODES:
                    acts,proof,net=check(e,y,ev,a,m);z=agg[m,u];z['net']+=net;z['trades']+=sum(acts);z['data_resumes']+=sum((k,v)==('RESUME','DATA') for t,k,v in a['log']);z['proof_trades']+=len(proof);z['age_sum']+=sum(t-w[-1] for t,w in proof.items());z['oldest_age_sum']+=sum(t-w[0] for t,w in proof.items());z['stale_trades']+=sum(t-w[-1]>16 for t,w in proof.items());z['max_age']=max(z['max_age'],max((t-w[-1] for t,w in proof.items()),default=0))
                    if seed==SEEDS[0]:
                        cut=1000;b=B['gate'](e[:cut],y[:cut],D['run'](e[:cut],ev,'WAIT_HOLD'),'REASON',u);p,q=filter_actions(e[:cut],ev,b,m);ck('prefix',p==acts[:cut] and q=={t:w for t,w in proof.items() if t<=cut})
        results[name]={f'{m}_{u}':dict(z,mean_net=z['net']/len(SEEDS),mean_trades=z['trades']/len(SEEDS),mean_age=z['age_sum']/max(1,z['proof_trades'])) for (m,u),z in agg.items()}
    # direct synthetic gate authority fixture isolates delayed-window decisions, actual parent checked above
    for name in ('delay4','delay24','hole','stale_flip','revision','no_data_resume'):
        h=128;e=[True]*h;y=[1]*h;ev=[];resume=32
        if name=='stale_flip':y[48:]=[0]*(h-48)
        for i in range(1,h+1):
            if name=='hole' and i%5==0:continue
            if name=='stale_flip' and i>48:continue
            delay=4 if name=='delay4' else 24 if name=='delay24' else 0
            ev.append((i+delay,i,1,y[i-1]))
        if name=='revision':ev.append((45,41,2,0));ev.append((45,42,2,0))
        ev.sort();base=[0]*resume+[1]*(h-resume);a=dict(actions=base,log=[] if name=='no_data_resume' else [(resume,'RESUME','DATA')],used=35,initial=35,fees=200,net=sum((800 if w else -1200)*v for w,v in zip(y,base))-h-200)
        fixtures[name]={}
        for m in MODES:
            acts,proof,net=check(e,y,ev,a,m);fixtures[name][m]=dict(trades=sum(acts),first=next((i for i,v in enumerate(acts,1) if v),None),last=next((i for i in range(h,0,-1) if acts[i-1]),None),net=net,stale=sum(t-w[-1]>16 for t,w in proof.items()))
    ck('delay4',fixtures['delay4']['STRICT']['trades']==0 and fixtures['delay4']['MATURE16']['first']==41);ck('delay24',fixtures['delay24']['MATURE']['trades']>0 and fixtures['delay24']['MATURE16']['trades']==0);ck('stale_flip',fixtures['stale_flip']['MATURE']['last']==128 and fixtures['stale_flip']['MATURE16']['last']==64);ck('revision',fixtures['revision']['MATURE']['trades']<fixtures['revision']['REASON']['trades']);ck('hole',fixtures['hole']['MATURE']['trades']>0 and fixtures['hole']['STRICT']['trades']<fixtures['hole']['MATURE']['trades'])
    return dict(passed=sum(c.values()),checks=dict(c)),dict(plan=PLAN,plan_sha=B['digest'](PLAN),cases=results,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='.');a=p.parse_args();t,e=study();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for n,z in [('tests',t),('examples',e)]:(out/f'Trading_Round134_{n}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(t)
