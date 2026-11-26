"""R112: separate absolute viability and relative superiority; synthetic only."""
import argparse, hashlib, json, math, runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Post_Switch_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='154b2e211fd4ab6d26a6f8e5d18d30965b15187f3df40935ef646d2540bf8d0d':raise ValueError('R111 hash')
R=runpy.run_path(str(P)); D=R['R']; B=R['B']; H=R['H']; JS=R['JS']; W=D['W']; P0=D['P0']; BLOCK=32; DEN=20*(H//BLOCK)
Q=Path(__file__).with_name('Chappy_Trading_Refresh_Trigger_Study_v0.1.py')
if hashlib.sha256(Q.read_bytes()).hexdigest()!='cb4d0570492b17d7e4fb963cba0191572463e67d96adb805d44af5fbb9d244ca':raise ValueError('R103 hash')
A=runpy.run_path(str(Q)); K=A['LIMITS']['BLOCK_SPEND']; SEEDS=range(112000,112256)
# phase changes relative to stable audit completion; comparison ends at +2048.
CASES={'stable':[], 'relative_flip':[(2048,85,90)], 'both_loss':[(2048,45,10)], 'both_severe':[(2048,25,10)], 'both_loss_and_flip':[(2048,45,90)], 'temporary_loss':[(2048,25,10),(2560,85,10)], 'weak_loss':[(2048,55,10)]}
METHODS=('KEEP','RELATIVE','ABSOLUTE','DUAL')
PLAN=dict(seeds=list(SEEDS),cases=CASES,methods=METHODS,horizon=H,block=BLOCK,absolute_limit=K,relative_limit=R['K']['BLOCK_SPEND'],denominator=DEN,observation_fee=1,rollback_fee=200,absolute_priority=True,absolute_stop_terminal=True,synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def generate(seed,changes):
    rng=np.random.default_rng(seed);x=np.searchsorted(np.cumsum(W),rng.integers(0,100,H),side='right');u=rng.integers(0,100,H);p=np.array(P0)[x];y0=np.where(u<p,1,-1);aa=[B['audit'](x,y0,j,0) for j in JS];start=max(z['end'] for z in aa);common=np.full(H,85);diff=np.full(H,10)
    for offset,c,d in changes:common[start+offset:]=c;diff[start+offset:]=d
    y=np.where(u<np.where(x==7,diff,common),1,-1);return x,y,aa,common,diff,start

def absolute(p):
    # Both frozen candidates act on every opportunity. Nonoverlapping blocks.
    n=len(p)//BLOCK; hits=(p[:n*BLOCK].reshape(n,BLOCK)>0).sum(axis=1);ix=np.flatnonzero(hits<=K)
    return (int(ix[0])+1)*BLOCK if len(ix) else None

def run(x,y,b,m):
    e,inc,fin=b['end'],b['inc'],b['fin']; sw=inc!=fin; p=B['netvec'](x[e:],y[e:],fin);q=B['netvec'](x[e:],y[e:],inc);n=len(p)
    rel=m in ('RELATIVE','DUAL') and sw; ab=m in ('ABSOLUTE','DUAL') and fin!=0
    ro=R['trigger'](p-q,'BLOCK_SPEND') if rel else None; ao=absolute(p) if ab else None
    # At a shared event, absolute stop takes priority. No decision at horizon.
    rollback=ro if ro is not None and ro<n and (ao is None or ro<ao) else None
    stop=None
    if rollback is not None:
        if ab:
            a=absolute(q[rollback:]);stop=rollback+a if a is not None and rollback+a<n else None
    elif ao is not None and ao<n:stop=ao
    end=n if stop is None else stop
    gross=int(p[:end].sum()) if rollback is None else int(p[:rollback].sum()+q[rollback:end].sum())
    obs=end if ab else ((rollback if rollback is not None else n) if rel else 0)
    net=b['net']-int(p.sum())+gross-obs-200*int(rollback is not None)
    return dict(net=net,rollback=None if rollback is None else e+rollback,stop=None if stop is None else e+stop,obs=obs,post_gross=gross,initial_switch=sw,post_trades=end,fee=200*int(rollback is not None))

def oracle(p,q,sw,m):
    a=[];r=[];rollback=stop=None;gross=obs=0;active=p;ab=m in ('ABSOLUTE','DUAL');rel=m in ('RELATIVE','DUAL') and sw
    for i in range(len(p)):
        v=active[i];gross+=int(v);obs+=int(ab or rel);a.append(v>0)
        if rel and p[i]!=q[i]:r.append(p[i]>q[i])
        if i+1==len(p):break
        if ab and len(a)==32:
            if sum(a)<=K:stop=i+1;break
            a=[]
        if rel and len(r)==32:
            if sum(r)<=R['K']['BLOCK_SPEND']:
                rollback=i+1;active=q;rel=False;a=[]
            r=[]
    return rollback,stop,gross,obs

def study():
    counts={};summary={};theory={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        counts[k]=counts.get(k,0)+1
    tail=lambda k:sum(math.comb(32,i)*3**i*2**(32-i) for i in range(k+1))
    ck('threshold',DEN*tail(K)<=5**32<DEN*tail(K+1));ck('full_support',all(B['payoff'](j,x,y) in (-1200,800) for j in JS for x in range(8) for y in (-1,1)))
    for p in [np.zeros(0),np.full(31,-1200),np.full(32,-1200),np.full(32,800),np.r_[np.full(32,800),np.full(32,-1200)]]:
        ck('absolute_fixture',absolute(p)==next((i for i in range(32,len(p)+1,32) if sum(p[i-32:i]>0)<=K),None))
    for c,d in {(85,10),*( (c,d) for changes in CASES.values() for _,c,d in changes)}:
        theory[f'{c}/{d}']={str(j):sum(W[x]*( (d if x==7 else c)*B['payoff'](j,x,1)+(100-(d if x==7 else c))*B['payoff'](j,x,-1)) for x in range(8))/10000 for j in JS}
    for name,changes in CASES.items():
        rows={m:[] for m in METHODS}
        for seed in SEEDS:
            x,y,aa,c,d,start=generate(seed,changes);b=B['run'](x,y,JS,aa,'EB',2048);e=b['end'];inc=b['inc'];fin=b['fin'];p=B['netvec'](x[e:],y[e:],fin);q=B['netvec'](x[e:],y[e:],inc)
            ck('audit',aa==[B['audit'](x,y,j,0) for j in JS]);ck('both_admitted',all(z['passed'] for z in aa));ck('comparison_stationary',np.all(c[:e]==85) and np.all(d[:e]==10))
            for m in METHODS:
                r=run(x,y,b,m);t=r['rollback'];s=r['stop'];end=H if s is None else s;rt=end if t is None else t
                ck('clock',e<=rt<=end<=H and (s is None or s<H) and (t is None or e<t<end));ck('fee',r['fee']==200*int(t is not None));ck('accounting',r['net']==int(B['netvec'](x[b['first']:e],y[b['first']:e],inc).sum()+p[:rt-e].sum()+q[rt-e:end-e].sum())-e-b['fee']-r['fee']-r['obs']);ck('trades',r['post_trades']==end-e)
                if m=='RELATIVE':
                    prev=R['run'](x,y,b,'BLOCK_SPEND');ck('R111',r['net']==prev['net'] and t==prev['rollback'])
                if seed<112016:
                    o=oracle(p,q,inc!=fin,m);ck('oracle',o==(None if t is None else t-e,None if s is None else s-e,r['post_gross'],r['obs']))
                    if s is not None or t is not None:
                        k=s if t is None else t;yy=y.copy();yy[k:]*=-1;rr=run(x,yy,b,m);ck('future_mask',rr['rollback']==t if t is not None else rr['stop']==s)
                rows[m].append(r)
        summary[name]={m:dict(mean_net=float(np.mean([r['net'] for r in rr])),stops=sum(r['stop'] is not None for r in rr),rollbacks=sum(r['rollback'] is not None for r in rr),switches=sum(r['initial_switch'] for r in rr),mean_stop_delay=float(np.mean([r['stop'] for r in rr if r['stop'] is not None])) if any(r['stop'] is not None for r in rr) else None,mean_post_gross=float(np.mean([r['post_gross'] for r in rr])),mean_obs=float(np.mean([r['obs'] for r in rr]))) for m,rr in rows.items()}
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,theory=theory,summary=summary)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--outdir',type=Path,required=True);z=a.parse_args();t,e=study()
    for n,v in [('tests',t),('examples',e)]:(z.outdir/f'Trading_Round112_{n}.json').write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
