"""R116: candidate-specific absolute monitor evidence. Synthetic fixed switch, not full lifecycle."""
import argparse, hashlib, json, runpy
from pathlib import Path
from collections import Counter
from fractions import Fraction
from math import comb
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Lifecycle_Priority_Study_v0.1.py')
PARENT='4366b6760745a4164bc9ecc0e4fbf744b6e0222d2a5844b653a1dea420ed6a1c'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PARENT:raise ValueError('parent hash')
R=runpy.run_path(str(P)); T=R['T']; LIMIT=R['LIMIT']; W=32; H=1024
METHODS=('RESET','BLIND','CANDIDATE')
CASES=('stable','shared_loss','new_good','new_bad','disjoint','weak_loss')
SEEDS=tuple(range(116000,116128))
PLAN=dict(parent=PARENT,methods=METHODS,cases=CASES,seeds=SEEDS,horizon=H,switch=127,limit=LIMIT,block=W,max_horizon=8192,prequalified=True,trade='all eligible; no short pause',observation_fee=1,switch_fee=200,absolute_priority=True,invalid_candidate='latched; no requalification',synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def simulate(x,y,a,b,s,mode):
    h=len(x)
    if not (0<s<h<=8192 and a!=b and a and b and mode in METHODS):raise ValueError('scope')
    active=a; buffers={a:[],b:[]}; invalid=set(); looks=0; net=0; obs=fees=trades=0; events=[]; actions=[]
    for i,(xx,yy) in enumerate(zip(x,y)):
        if not active:break
        t=i+1; xx=int(xx); yy=int(yy); obs+=1; net-=1; d=int(T[active,xx]); actions.append(active if d else 0)
        if d:trades+=1;net+=800 if d==yy else -1200
        for j in (a,b) if mode=='CANDIDATE' else (active,):
            if j in invalid:continue
            v=int(T[j,xx])
            if not v:continue
            z=buffers[j];z.append((i,v==yy))
            if len(z)==W:
                wins=sum(w for _,w in z); looks+=1; alarm=wins<=LIMIT
                events.append(dict(t=t,kind='look',j=j,wins=wins,indices=[k for k,_ in z],alarm=alarm));z.clear()
                if alarm:invalid.add(j)
        if active in invalid:events.append(dict(t=t,kind='stop',j=active));active=0;continue
        if t==s:
            if b in invalid:events.append(dict(t=t,kind='deny',j=b));continue
            if mode=='BLIND':buffers[b]=buffers[a];buffers[a]=[]
            elif mode=='RESET':buffers[b]=[]
            active=b;fees+=200;net-=200;events.append(dict(t=t,kind='switch',j=b))
    return dict(net=net,obs=obs,fees=fees,trades=trades,looks=looks,events=events,actions=actions)
def oracle(x,y,a,b,s,mode):
    # Independent vector-group calculation of first alarms, then action schedule.
    h=len(x); events=[]; blocks=[]
    def groups(j,indices):
        nonlocal blocks
        z=[]
        for ix,owner in indices:
            d=int(T[owner,int(x[ix])]);
            if d:z.append((ix,int(d==int(y[ix]))))
        for k in range(0,len(z)-31,32):
            q=z[k:k+32];w=sum(v for _,v in q);e=dict(t=q[-1][0]+1,kind='look',j=j,wins=w,indices=[i for i,_ in q],alarm=w<=LIMIT);blocks.append(e)
            if e['alarm']:return e['t']
        return h+1
    if mode=='CANDIDATE':
        ea=groups(a,((i,a) for i in range(h)));eb=groups(b,((i,b) for i in range(h)))
        switched=ea>s and eb>s;denied=ea>s and eb<=s
        stop=eb if switched else ea
    else:
        ea=groups(a,((i,a) for i in range(s)));switched=ea>s;denied=False;stop=ea
        if switched:
            # Only complete groups before the boundary count. Blind transfers old partial group.
            last=max((e['t'] for e in blocks if e['j']==a),default=0)
            start=last if mode=='BLIND' else s
            stop=groups(b,((i,a if i<s else b) for i in range(start,h)))
    end=min(h,stop); blocks=[e for e in blocks if e['t']<=end]
    events=blocks[:]
    if switched:events.append(dict(t=s,kind='switch',j=b))
    if denied:events.append(dict(t=s,kind='deny',j=b))
    if stop<=h:events.append(dict(t=stop,kind='stop',j=b if switched else a))
    events.sort(key=lambda e:(e['t'],0 if e['kind']=='look' else 1,0 if e['j']==a else 1))
    actions=[];gross=0
    for i in range(end):
        j=b if switched and i>=s else a; d=int(T[j,int(x[i])]);actions.append(j if d else 0)
        if d:gross+=800 if d==int(y[i]) else -1200
    fees=200*int(switched)
    return dict(net=gross-end-fees,obs=end,fees=fees,trades=sum(bool(j) for j in actions),looks=len(blocks),events=events,actions=actions)
def fixtures():
    def pair(xx,yy,a=9,b=256,s=31):return np.array(xx,dtype=int),np.array(yy,dtype=int),a,b,s
    return {
      'shared_bad':pair([0]*128,[-1]*128),
      'opposite_new_good':pair([7]*128,[-1]*128),
      'opposite_new_bad':pair([7]*128,[1]*128,s=40),
      'disjoint_partial':pair([0]*31+[7]*97,[-1]*128,260,272),
      'shared_good':pair([0]*128,[1]*128),
      'stop_switch_same_slot':pair([0]*128,[-1]*128,s=32),
      'inactive_bad_same_slot':pair([7]*128,[1]*128,s=32),
      'no_support':pair([0]*128,[1]*128,260,272,s=40),
    }
def generate(seed,case):
    rng=np.random.default_rng(seed);s=127;a,b=9,256
    x=rng.choice(8,H,p=[.1]*7+[.3]);u=rng.random(H)
    p=np.full(H,.85);p[x==7]=.5
    if case=='shared_loss':p[96:]=.1;p[(x==7)&(np.arange(H)>=96)]=.5
    elif case=='new_good':x[96:]=7;p[96:]=.1
    elif case=='new_bad':x[:]=7;p[:]=.9
    elif case=='disjoint':a,b=260,272;x[:]=np.where(np.arange(H)<s,0,7);p[:]=.1
    elif case=='weak_loss':p[96:]=.55
    y=np.where(u<p,1,-1);return x,y,a,b,s
def study():
    counts=Counter(); out={};summary={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        counts[k]+=1
    tail=lambda k:sum(Fraction(comb(W,i)*3**i*2**(W-i),5**W) for i in range(k+1))
    ck('global_monitor_budget',512*tail(LIMIT)<=Fraction(1,20));ck('next_threshold_exceeds_budget',512*tail(LIMIT+1)>Fraction(1,20))
    def test(z,mode):
        x,y,a,b,s=z;r=simulate(*z,mode);o=oracle(*z,mode);ck('independent_oracle',r==o);ck('look_budget',r['looks']<=512);ck('one_switch',sum(e['kind']=='switch' for e in r['events'])<=1)
        for e in r['events']:
            if e['kind']=='look':
                ck('evidence_chronology',len(set(e['indices']))==32 and max(e['indices'])==e['t']-1)
                if mode!='BLIND':ck('candidate_identity',all(T[e['j'],x[i]] for i in e['indices']) and sum(T[e['j'],x[i]]==y[i] for i in e['indices'])==e['wins'])
        ck('account',r['obs']==len(r['actions']) and r['trades']==sum(bool(j) for j in r['actions']))
        return r
    for name,z in fixtures().items():
        out[name]={}
        for m in METHODS:
            r=test(z,m);out[name][m]={k:v for k,v in r.items() if k!='actions'}
            x,y,a,b,s=z
            for t in (1,s,min(s+1,len(x)),min(64,len(x))):
                alt=y.copy();alt[t:]*=-1;rr=simulate(x,alt,a,b,s,m)
                ck('future_prefix',r['actions'][:t]==rr['actions'][:t] and [e for e in r['events'] if e['t']<=t]==[e for e in rr['events'] if e['t']<=t])
    stop=lambda n,m:next((e['t'] for e in out[n][m]['events'] if e['kind']=='stop'),None)
    ck('carry_shared',stop('shared_bad','RESET')==63 and stop('shared_bad','CANDIDATE')==32)
    ck('blind_false_stop',stop('opposite_new_good','BLIND')==32 and stop('opposite_new_good','CANDIDATE') is None)
    ck('disjoint_not_transfer',stop('disjoint_partial','BLIND')==32 and stop('disjoint_partial','CANDIDATE')==63)
    ck('inactive_denial',any(e['kind']=='deny' for e in out['opposite_new_bad']['CANDIDATE']['events']) and not any(e['kind']=='switch' for e in out['opposite_new_bad']['CANDIDATE']['events']))
    ck('stop_priority',all(stop('stop_switch_same_slot',m)==32 for m in METHODS))
    for case in CASES:
        acc={m:Counter() for m in METHODS}
        for seed in SEEDS:
            z=generate(seed,case)
            for m in METHODS:
                r=test(z,m);c=acc[m];c['net']+=r['net'];c['obs']+=r['obs'];c['looks']+=r['looks'];c['stops']+=sum(e['kind']=='stop' for e in r['events']);c['denied']+=sum(e['kind']=='deny' for e in r['events']);c['switches']+=sum(e['kind']=='switch' for e in r['events']);c['stop_time']+=sum(e['t'] for e in r['events'] if e['kind']=='stop')
        summary[case]={m:dict(mean_net=c['net']/len(SEEDS),mean_obs=c['obs']/len(SEEDS),mean_looks=c['looks']/len(SEEDS),stops=c['stops'],denied=c['denied'],switches=c['switches'],mean_stop=c['stop_time']/c['stops'] if c['stops'] else None) for m,c in acc.items()}
    return dict(passed=sum(counts.values()),counts=dict(counts),fixture_trials=len(out)*3,random_trials=len(CASES)*len(SEEDS)*3,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,tail=float(tail(LIMIT)),union_bound=float(512*tail(LIMIT)),fixtures=out,summary=summary)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,z in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round116_{k}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
