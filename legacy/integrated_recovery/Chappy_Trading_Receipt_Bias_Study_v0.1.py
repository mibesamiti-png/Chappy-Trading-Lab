"""R135 synthetic outcome-dependent receipt stress. No market data or orders."""
import argparse, hashlib, json, runpy
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parent
P=ROOT/'Chappy_Trading_Mature_Evidence_Study_v0.1.py'
PIN='251f811b587bbf6e3a5157b52295c571103e04d73b5c0c7d7355758a0c6822ae'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PIN:raise ValueError('R134 hash')
R=runpy.run_path(str(P)); B=R['B']; D=R['D']; MODES=R['MODES']; H=R['H']
# after fixed common recovery phase: win %, win/loss reception %, win/loss delays
CASES={'stable_unbiased':(90,100,100,16,16),'weak_unbiased':(45,100,100,16,16),'weak_win_fast':(45,100,100,0,24),'weak_loss_fast':(45,100,100,24,0),'weak_loss_missing':(45,100,10,0,0),'good_win_missing':(90,10,100,0,0),'good_win_fast':(90,100,100,0,24),'good_loss_fast':(90,100,100,24,0)}
SEEDS=range(135000,135032); DIRECT=range(135100,135228)
PLAN=dict(parent=PIN,cases=CASES,seeds=list(SEEDS),direct_seeds=list(DIRECT),modes=MODES,horizon=H,direct_horizon=512,integrated='25% support, wins90% until 1024, outage256:640, immediate full receipt before/after outage until 1024; test bias thereafter; parent R132 authority initial34; no thresholds changed',direct='full support, fixed authority after32, stationary iid; no monitor, isolate gate',metrics='true win rates of selected evidence and next trades; latest four true outcomes at same permitted times; results are diagnostic not investment advice')
def generate(seed,case,direct=False):
    p,rw,rl,dw,dl=case; h=512 if direct else H; rng=np.random.default_rng(seed)
    e=rng.random(h)<(1 if direct else .25); u=rng.random(h); v=rng.random(h); q=rng.random(h)
    y=(u<np.where((np.arange(h)>=1024)|direct,p/100,.9)).astype(int);ev=[]
    for k in np.flatnonzero(e):
        i=int(k); w=y[i];rec,d=(rw,dw) if w else (rl,dl)
        if not direct and i<1024:rec,d=(0,0) if 256<=i<640 else (100,0)
        if v[i]<rec/100:ev.append((i+1+int(q[i]*(d+1)),i+1,1,int(w)))
    return e,y,sorted(ev)
def direct_base(e,y):
    acts=[int(i>32 and v) for i,v in enumerate(e,1)];fee=200;h=len(e)
    return dict(actions=acts,log=[(32,'RESUME','DATA')],initial=34,used=34,fees=fee,net=sum((800 if w else -1200)*a for w,a in zip(y,acts))-h-fee)
def study():
    c=Counter(); summaries={};fixtures={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def check(e,y,ev,a,m,start):
        acts,proof=R['filter_actions'](e,ev,a,m); ref,pr=R['oracle'](e,ev,a,m)
        ck('window_oracle',acts==ref and proof==pr);ck('authority',all(x<=z for x,z in zip(acts,a['actions'])));ck('support',all(not x or e[i] for i,x in enumerate(acts)))
        resume=next((t for t,k,v in a['log'] if (k,v)==('RESUME','DATA')),None)
        times={i:(t,v) for t,i,r,v in ev}; slots=[i for i,v in enumerate(e,1) if v and (resume is not None and i>resume)];pos={t:j for j,t in enumerate(slots)}
        z=Counter(net=sum((800 if w else -1200)*x for w,x in zip(y,acts))-len(e)-a['fees'],trades=sum(acts),data_resumes=int(resume is not None))
        for t in range(start+1,len(e)+1):
            if not a['actions'][t-1]:continue
            z['base_opportunities']+=1;z['base_wins']+=int(y[t-1]);z['post_trades']+=acts[t-1];z['post_wins']+=int(y[t-1])*acts[t-1]
        for t,w in proof.items():
            j=pos[t];idx=pos[w[-1]];ck('causal_window',tuple(slots[idx-3:idx+1])==w and idx<j and all(times[i][0]<t for i in w));ck('threshold',sum(times[i][1] for i in w)>=3);ck('freshness',m!='MATURE16' or t-w[-1]<=16)
            if t<=start:continue
            z['proof_n']+=4;z['proof_wins']+=sum(int(y[i-1]) for i in w);z['latest_n']+=4;z['latest_wins']+=sum(int(y[i-1]) for i in slots[j-4:j]);z['age_sum']+=t-w[-1];z['stale']+=int(t-w[-1]>16)
        ck('account',z['net']==a['net']+sum((800 if w else -1200)*(x-b) for w,x,b in zip(y,acts,a['actions'])));ck('budget',a['used']<=35)
        return z,acts,proof
    for direct,seeds in ((False,SEEDS),(True,DIRECT)):
        for name,case in CASES.items():
            agg={m:Counter() for m in MODES}
            for seed in seeds:
                e,y,ev=generate(seed,case,direct)
                if direct:a=direct_base(e,y)
                else:
                    d=D['run'](e,ev,'WAIT_HOLD');ref=D['oracle'](e,ev,'WAIT_HOLD');ck('monitor_oracle',d==ref);a=B['gate'](e,y,d,'REASON',34);ck('parent_gate',a==B['reference'](e,y,ref,'REASON',34))
                for m in MODES:
                    z,acts,proof=check(e,y,ev,a,m,32 if direct else 1024);agg[m].update(z)
                    if seed==seeds[0]:
                        cut=256 if direct else 1536
                        if direct:b=direct_base(e[:cut],y[:cut])
                        else:b=B['gate'](e[:cut],y[:cut],D['run'](e[:cut],ev,'WAIT_HOLD'),'REASON',34)
                        x,q=R['filter_actions'](e[:cut],ev,b,m);ck('future_prefix',x==acts[:cut] and q=={t:w for t,w in proof.items() if t<=cut})
            summaries[('direct_' if direct else 'integrated_')+name]={m:dict(z,mean_net=z['net']/len(seeds),mean_post_trades=z['post_trades']/len(seeds),proof_rate=z['proof_wins']/max(1,z['proof_n']),latest_rate=z['latest_wins']/max(1,z['latest_n']),trade_rate=z['post_wins']/max(1,z['post_trades']),base_rate=z['base_wins']/max(1,z['base_opportunities'])) for m,z in agg.items()}
    # same truth, opposite reporting priorities: 4 wins then 4 losses; current slot 9.
    e=[True]*64;y=[1]*32+[1,1,1,1,0,0,0,0]+[0]*24;a=direct_base(e,y)
    for name,dw,dl in [('wins_first',0,24),('losses_first',24,0),('unbiased',0,0)]:
        ev=sorted((i+(dw if w else dl),i,1,w) for i,w in enumerate(y,1));fixtures[name]={}
        for m in MODES:
            z,acts,proof=check(e,y,ev,a,m,32);fixtures[name][m]=dict(action41=acts[40],proof41=proof.get(41),net=z['net'])
    ck('same_truth_different_decision',fixtures['wins_first']['MATURE']['action41']==1 and fixtures['losses_first']['MATURE']['action41']==0 and fixtures['unbiased']['MATURE']['action41']==0)
    return dict(passed=sum(c.values()),checks=dict(c)),dict(plan=PLAN,plan_sha=B['digest'](PLAN),cases=summaries,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='.');a=p.parse_args();t,e=study();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for n,z in [('tests',t),('examples',e)]:(out/f'Trading_Round135_{n}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(t)
