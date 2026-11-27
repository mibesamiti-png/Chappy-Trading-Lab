"""R102: bounded synthetic refresh, no orders."""
import argparse,hashlib,json,math,runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Integrated_Hypothesis_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='377898f4b86a7e505bda78e5ce0ff713e623c9432c46258a251c755bfc7663c2':raise ValueError('R101 hash')
R=runpy.run_path(str(P)); T=R['T']; S=R['S']; H=R['H']; SHIFT=R['SHIFT']; TRAIN=R['TRAIN']; LOOKS=(16,32,64,128,256); SEEDS=range(102000,102064); PERIOD=3072
# Five looks per audit; at most two audits, 0.5% each in matched methods.
def cutoff(n,denom):
    den=5**n; tail=0; k=n+1
    for i in range(n,-1,-1):
        tail+=math.comb(n,i)*3**i*2**(n-i)
        if denom*tail<=den:k=i
        else:break
    return k
K={a:{n:cutoff(n,a) for n in LOOKS} for a in (100,200)}
METHODS={'R101_MONITOR':(100,'never'),'MATCHED':(200,'never'),'REACTIVE':(200,'reactive'),'PERIODIC':(200,'periodic')}
PLAN=dict(seeds=list(SEEDS),cases=R['CASES'],horizon=H,train=TRAIN,shift=SHIFT,looks=LOOKS,methods=METHODS,periodic_slot=PERIOD,reactive='first four live eligible shadow outcomes with <=1 win; R81 -200bps threshold on eligible clock',max_audits=2,fee_per_observed_slot=1,win=800,loss=-1200,synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def select(x,y):return S['choose'](x,y,len(x))[3]
def simulate(x,y,method):
    h=len(x);alpha,policy=METHODS[method];start=0;epochs=[];fees=trades=gross=post=post_fee=0;refresh=None
    def charge(a,b):
        nonlocal fees,post_fee
        fees+=b-a;post_fee+=max(0,b-max(a,SHIFT))
    for cycle in range(2 if policy!='never' else 1):
        te=min(start+TRAIN,h);charge(start,te)
        if te-start<TRAIN:break
        j=select(x[start:te],y[start:te]);e=dict(start=start,train_end=te,candidate=j,pass_at=None,audit_end=te,audit_n=0,audit_w=0,live_end=None,trigger=None);epochs.append(e)
        if not j:break
        d=T[j,x];ix=np.flatnonzero(d[te:])+te;hits=d[ix]==y[ix];cs=np.cumsum(hits);n=len(ix);end=h;passed=False
        for k in LOOKS:
            if len(ix)<k:break
            if int(cs[k-1])>=K[alpha][k]:n=k;end=int(ix[k-1])+1;passed=True;break
            if k==LOOKS[-1]:n=k;end=int(ix[k-1])+1
        charge(te,end);e.update(audit_end=end,audit_n=n,audit_w=int(cs[n-1]) if n else 0)
        if not passed:break
        e['pass_at']=end;le=h;trigger=None
        if cycle==0 and policy=='reactive':
            for k in range(n+3,len(ix)):
                if int(hits[k-3:k+1].sum())<=1:le=int(ix[k])+1;trigger='reactive';break
        if cycle==0 and policy=='periodic' and end<=PERIOD<h:le=PERIOD;trigger='periodic'
        eligible=np.arange(n,int(np.searchsorted(ix,le)))
        # R82 NET is equivalent to >=3 wins in preceding four for this fixed payoff.
        prior=np.concatenate(([0],cs));allowed=(eligible>=4)&((prior[eligible]-prior[np.maximum(0,eligible-4)])>=3)
        live=ix[eligible[allowed]];pnl=np.where(d[live]==y[live],800,-1200);gross+=int(pnl.sum());post+=int(pnl[live>=SHIFT].sum());trades+=len(live);charge(end,le)
        e.update(live_end=le,trigger=trigger)
        if trigger is None or le>=h:break
        refresh=le;start=le
    return dict(net=gross-fees,gross=gross,fees=fees,trades=trades,post_net=post-post_fee,refresh=refresh,epochs=epochs)
def oracle(x,y,method):
    alpha,policy=METHODS[method];st='TRAIN';bx=[];by=[];hist=[];lh=[];n=w=fees=gross=post=pf=trades=cycle=0;ref=None;passes=[];j=0
    for i,(a,b) in enumerate(zip(x,y)):
        if st=='LIVE' and cycle==0 and policy=='periodic' and i==PERIOD:st='TRAIN';cycle=1;ref=i;bx=[];by=[]
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
                    if w>=K[alpha][n]:st='LIVE';passes.append(i+1)
                    elif n==256:st='DONE'
        elif T[j,a]:
            win=T[j,a]==b
            if len(hist)>=4 and sum(hist[-4:])>=3:
                p=800 if win else -1200;gross+=p;trades+=1;post+=p if i>=SHIFT else 0
            hist.append(win);lh.append(win)
            if cycle==0 and policy=='reactive' and len(lh)>=4 and sum(lh[-4:])<=1 and i+1<len(x):st='TRAIN';cycle=1;ref=i+1;bx=[];by=[]
    return gross-fees,gross,fees,trades,post-pf,ref,passes

def study(test):
    counts={};out={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        counts[k]=counts.get(k,0)+1
    for a in K:
        for n in LOOKS:
            k=K[a][n];tail=lambda j:sum(math.comb(n,i)*3**i*2**(n-i) for i in range(j,n+1));ck('exact_cutoff',a*tail(k)<=5**n<a*tail(k-1),True)
    for case in R['CASES']:
        rows={m:[] for m in METHODS}
        for seed in SEEDS:
            x,y=R['series'](seed,case)
            for m in METHODS:
                r=simulate(x,y,m);rows[m].append(r)
                if test:
                    ck('accounting',r['net'],r['gross']-r['fees']);ck('audit_budget',len(r['epochs'])<= (1 if METHODS[m][1]=='never' else 2),True)
                    for e in r['epochs']:
                        ck('chronology',e['start']<=e['train_end']<=e['audit_end']<=H,True)
                        if e['pass_at'] is not None:ck('audit_pass',e['audit_w']>=K[METHODS[m][0]][e['audit_n']],True)
                    if seed<SEEDS.start+8:
                        ck('independent_replay',tuple(r[k] for k in ('net','gross','fees','trades','post_net','refresh'))+([e['pass_at'] for e in r['epochs'] if e['pass_at'] is not None],),oracle(x,y,m))
                    if m=='R101_MONITOR':
                        j=select(x[:TRAIN],y[:TRAIN]);z=R['simulate'](x,y,j,'SPEND',True);ck('R101_equivalence',(r['net'],r['gross'],r['trades'],r['post_net']),(z['net'],z['gross'],z['trades'],z['post_net']))
                    if r['refresh'] is not None:
                        q=simulate(x[:r['refresh']],y[:r['refresh']],m);ck('refresh_prefix',q['epochs'][0]['pass_at'],r['epochs'][0]['pass_at'])
            if test:ck('matched_first_audit',rows['MATCHED'][-1]['epochs'][0]['pass_at'],rows['REACTIVE'][-1]['epochs'][0]['pass_at'])
        out[case]={}
        for m,rs in rows.items():
            ref=[r for r in rs if r['refresh'] is not None];out[case][m]=dict(**{'mean_'+k:sum(r[k] for r in rs)/len(rs) for k in ('net','gross','fees','trades','post_net')},initial_pass=sum(r['epochs'][0]['pass_at'] is not None for r in rs),refreshes=len(ref),second_pass=sum(len(r['epochs'])==2 and r['epochs'][1]['pass_at'] is not None for r in rs),mean_refresh_slot=sum(r['refresh'] for r in ref)/len(ref) if ref else None,refresh_before_shift=sum(r['refresh']<SHIFT for r in ref))
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA) if test else dict(plan=PLAN,plan_sha=SHA,summary=out)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(study(a.self_test),sort_keys=True,indent=2))
