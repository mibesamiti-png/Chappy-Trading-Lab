"""R103: separate short-term pause from bounded knowledge refresh. Synthetic only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Integrated_Refresh_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='f7967f8bff45c20fa7e87be185b822088439ef51ac33ebf868ee0967cf4b66a7':raise ValueError('R102 hash')
R=runpy.run_path(str(P)); T=R['T']; H=R['H']; SHIFT=R['SHIFT']; TRAIN=R['TRAIN']; LOOKS=R['LOOKS']; K=R['K'][200]; CASES=R['R']['CASES']; SEEDS=range(103000,103064)
BLOCK=32; MAX_LOOKS=H//BLOCK; DEN=20*MAX_LOOKS
METHODS=('MATCHED','REACTIVE','BLOCK_NAIVE','BLOCK_SPEND')
def lower(denom):
    z=0; k=-1
    for i in range(BLOCK+1):
        z+=math.comb(BLOCK,i)*3**i*2**(BLOCK-i)
        if denom*z>5**BLOCK:break
        k=i
    return k
LIMITS={'BLOCK_NAIVE':lower(20),'BLOCK_SPEND':lower(DEN)}
PLAN=dict(seeds=list(SEEDS),cases=CASES,horizon=H,train=TRAIN,shift=SHIFT,methods=METHODS,block=BLOCK,max_looks=MAX_LOOKS,denom=DEN,limits=LIMITS,audit_alpha_den=200,looks=LOOKS,refresh_limit=1,monitor='R102 unchanged',fee=1,win=800,loss=-1200,synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def trigger(hits,method):
    if method=='REACTIVE':
        v=np.convolve(hits.astype(int),np.ones(4,dtype=int),'valid') if len(hits)>=4 else []
        z=np.flatnonzero(np.asarray(v)<=1);return int(z[0])+3 if len(z) else None
    if method in LIMITS:
        n=min(len(hits)//BLOCK,MAX_LOOKS);z=np.flatnonzero(hits[:n*BLOCK].reshape(n,BLOCK).sum(axis=1)<=LIMITS[method]);return (int(z[0])+1)*BLOCK-1 if len(z) else None
    return None

def simulate(x,y,method):
    h=len(x);start=fees=gross=post=pf=trades=0;refresh=None;epochs=[]
    def charge(a,b):
        nonlocal fees,pf
        fees+=b-a;pf+=max(0,b-max(a,SHIFT))
    for cycle in range(1 if method=='MATCHED' else 2):
        te=min(start+TRAIN,h);charge(start,te)
        if te-start<TRAIN:break
        j=R['select'](x[start:te],y[start:te]);e=dict(start=start,train_end=te,candidate=j,pass_at=None,audit_end=te,audit_n=0,audit_w=0,live_end=None,trigger=None);epochs.append(e)
        if not j:break
        d=T[j,x];ix=np.flatnonzero(d[te:])+te;hits=d[ix]==y[ix];cs=np.cumsum(hits);n=len(ix);end=h;passed=False
        for k in LOOKS:
            if len(ix)<k:break
            if int(cs[k-1])>=K[k]:n=k;end=int(ix[k-1])+1;passed=True;break
            if k==LOOKS[-1]:n=k;end=int(ix[k-1])+1
        charge(te,end);e.update(audit_end=end,audit_n=n,audit_w=int(cs[n-1]) if n else 0)
        if not passed:break
        e['pass_at']=end;le=h;trig=trigger(hits[n:],method) if cycle==0 else None
        if trig is not None:le=int(ix[n+trig])+1
        eligible=np.arange(n,int(np.searchsorted(ix,le)));prior=np.concatenate(([0],cs));allowed=(eligible>=4)&((prior[eligible]-prior[np.maximum(0,eligible-4)])>=3)
        live=ix[eligible[allowed]];pnl=np.where(d[live]==y[live],800,-1200);gross+=int(pnl.sum());post+=int(pnl[live>=SHIFT].sum());trades+=len(live);charge(end,le)
        e.update(live_end=le,trigger=method if trig is not None else None)
        if trig is None or le>=h:break
        refresh=le;start=le
    return dict(net=gross-fees,gross=gross,fees=fees,trades=trades,post_net=post-pf,refresh=refresh,epochs=epochs)

def oracle(x,y,method):
    st='TRAIN';bx=[];by=[];hist=[];lh=[];n=w=fees=gross=post=pf=trades=cycle=0;ref=None;passes=[];j=0
    for i,(a,b) in enumerate(zip(x,y)):
        if st=='DONE':continue
        fees+=1;pf+=i>=SHIFT
        if st=='TRAIN':
            bx.append(a);by.append(b)
            if len(bx)==TRAIN:
                z=T[:,np.asarray(bx)];j=int(np.argmax(np.where(z==0,0,np.where(z==np.asarray(by),800,-1200)).sum(axis=1)));hist=[];lh=[];n=w=0;st='AUDIT' if j else 'DONE'
        elif st=='AUDIT':
            if T[j,a]:
                n+=1;win=T[j,a]==b;w+=win;hist.append(win)
                if n in LOOKS:
                    if w>=K[n]:st='LIVE';passes.append(i+1)
                    elif n==256:st='DONE'
        elif T[j,a]:
            win=T[j,a]==b
            if len(hist)>=4 and sum(hist[-4:])>=3:
                p=800 if win else -1200;gross+=p;trades+=1;post+=p if i>=SHIFT else 0
            hist.append(win);lh.append(win)
            fire=method=='REACTIVE' and len(lh)>=4 and sum(lh[-4:])<=1
            if method in LIMITS:fire=len(lh)%BLOCK==0 and len(lh)//BLOCK<=MAX_LOOKS and sum(lh[-BLOCK:])<=LIMITS[method]
            if cycle==0 and fire and i+1<len(x):st='TRAIN';cycle=1;ref=i+1;bx=[];by=[]
    return gross-fees,gross,fees,trades,post-pf,ref,passes

def study(test):
    counts={};out={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        counts[k]=counts.get(k,0)+1
    tail=lambda k:sum(math.comb(BLOCK,i)*3**i*2**(BLOCK-i) for i in range(k+1))
    for m,d in [('BLOCK_NAIVE',20),('BLOCK_SPEND',DEN)]:
        k=LIMITS[m];ck('integer_threshold',d*tail(k)<=5**BLOCK<d*tail(k+1),True)
    theory={}
    for p in (.25,.5,.6,.75,.9):
        theory[str(p)]={}
        for m,k in LIMITS.items():
            q=sum(math.comb(BLOCK,i)*p**i*(1-p)**(BLOCK-i) for i in range(k+1));theory[str(p)][m]={'one_block':q,'256_blocks':-math.expm1(MAX_LOOKS*math.log1p(-q)) if q<1 else 1}
    for case in CASES:
        rows={m:[] for m in METHODS}
        for seed in SEEDS:
            x,y=R['R']['series'](seed,case)
            for m in METHODS:
                r=simulate(x,y,m);rows[m].append(r)
                if test:
                    ck('accounting',r['net'],r['gross']-r['fees']);ck('budget',len(r['epochs'])<=2,True)
                    if m in ('MATCHED','REACTIVE'):ck('R102_equivalence',r,R['simulate'](x,y,m) if m=='MATCHED' else _normalize(R['simulate'](x,y,m)))
                    for e in r['epochs']:
                        ck('chronology',e['start']<=e['train_end']<=e['audit_end']<=H,True)
                        if e['pass_at'] is not None:ck('audit_pass',e['audit_w']>=K[e['audit_n']],True)
                    if seed<SEEDS.start+8:
                        ck('independent_replay',tuple(r[k] for k in ('net','gross','fees','trades','post_net','refresh'))+([e['pass_at'] for e in r['epochs'] if e['pass_at'] is not None],),oracle(x,y,m))
                    if r['refresh'] is not None:
                        q=simulate(x[:r['refresh']],y[:r['refresh']],m);ck('prefix_trigger',q['epochs'][0]['live_end'],r['refresh']);ck('prefix_audit',q['epochs'][0]['pass_at'],r['epochs'][0]['pass_at'])
            if test:ck('matched_admission',len({rows[m][-1]['epochs'][0]['pass_at'] for m in METHODS}),1)
        out[case]={}
        for m,rs in rows.items():
            ref=[r for r in rs if r['refresh'] is not None];out[case][m]=dict(**{'mean_'+k:sum(r[k] for r in rs)/len(rs) for k in ('net','gross','fees','trades','post_net')},initial_pass=sum(r['epochs'][0]['pass_at'] is not None for r in rs),refreshes=len(ref),second_pass=sum(len(r['epochs'])==2 and r['epochs'][1]['pass_at'] is not None for r in rs),mean_refresh_slot=sum(r['refresh'] for r in ref)/len(ref) if ref else None,refresh_before_shift=sum(r['refresh']<SHIFT for r in ref))
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA) if test else dict(plan=PLAN,plan_sha=SHA,theory=theory,summary=out)
def _normalize(r):
    for e in r['epochs']:
        if e['trigger']=='reactive':e['trigger']='REACTIVE'
    return r
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(study(a.self_test),sort_keys=True,indent=2))
