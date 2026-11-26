"""R141 minimum core comparison. Synthetic offline only; no orders or market data."""
import hashlib,json,runpy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parent
P=ROOT/'Chappy_Trading_Refresh_Trigger_Study_v0.1.py'
R=runpy.run_path(str(P)); T=R['T']; select=R['R']['select']; K=R['K']; TRAIN=R['TRAIN']; H=R['H']
MODES=('A_FIXED','B_LEARN','C_AUDIT','D_STOP','E_REFRESH')
SEEDS=range(141000,141008)
PLAN=dict(modes=MODES,seeds=list(SEEDS),cases=list(R['CASES']),horizon=H,training=TRAIN,fee_per_slot=1,win=800,loss=-1200,baseline=9,audit=K,monitor=R['LIMITS']['BLOCK_SPEND'],refresh_max=1,synthetic_only=True,capital_model='fixed 100000 yen notional; additive PnL; no capital constraint; not executable',common_warmup=True,short_pause=False,source_sha=hashlib.sha256(P.read_bytes()).hexdigest())
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()
def simulate(x,y,m):
    h=len(x); trades=[]; epochs=[]; start=0
    for cycle in range(2 if m=='E_REFRESH' else 1):
        te=start+TRAIN
        if te>=h: break
        j=9 if m=='A_FIXED' else select(x[start:te],y[start:te]); d=T[j,x]; ix=np.flatnonzero(d[te:])+te; hits=d[ix]==y[ix]; cs=np.cumsum(hits)
        e=dict(start=start,train_end=te,candidate=j,admit=None,stop=None,looks=[]);epochs.append(e)
        if not j: break
        n=0; end=te
        if m not in MODES[:2]:
            passed=False
            for k,lim in K.items():
                if len(ix)<k:break
                n=k;end=int(ix[k-1])+1;e['looks'].append([end,k,int(cs[k-1])])
                if cs[k-1]>=lim and end<h:passed=True;break
            if not passed:break
        e['admit']=end
        trigger=R['trigger'](hits[n:],'BLOCK_SPEND') if m in MODES[3:] else None
        le=h if trigger is None else int(ix[n+trigger])+1
        live=ix[n:np.searchsorted(ix,le)];trades.extend((int(i),int(d[i]),800 if d[i]==y[i] else -1200) for i in live)
        if trigger is None:break
        e['stop']=le;start=le
    pnl=np.full(h,-1,dtype=int)
    for i,_,v in trades:pnl[i]+=v
    curve=np.r_[0,np.cumsum(pnl)]; dd=int(np.max(np.maximum.accumulate(curve)-curve))
    return dict(trades=trades,epochs=epochs,net=int(curve[-1]),drawdown=dd,fee=h)
def oracle(x,y,m):
    st='TRAIN'; bx=[];by=[];j=0;cycle=0;n=w=0;block=[];tr=[];ev=[];h=len(x)
    for i,(a,b) in enumerate(zip(x,y)):
        if st=='DONE':continue
        if st=='TRAIN':
            bx.append(a);by.append(b)
            if len(bx)==TRAIN and i+1<h:
                d=T[:,np.asarray(bx)]; j=9 if m=='A_FIXED' else int(np.argmax(np.where(d==0,0,np.where(d==np.asarray(by),800,-1200)).sum(axis=1)))
                e=dict(start=i+1-TRAIN,train_end=i+1,candidate=j,admit=None,stop=None,looks=[]);ev.append(e);n=w=0;block=[]
                if not j:st='DONE'
                elif m in MODES[:2]:st='LIVE';e['admit']=i+1
                else:st='AUDIT'
        elif st=='AUDIT' and T[j,a]:
            n+=1;w+=int(T[j,a]==b)
            if n in K:
                e['looks'].append([i+1,n,w])
                if w>=K[n] and i+1<h:st='LIVE';e['admit']=i+1
                elif n==256:st='DONE'
        elif st=='LIVE' and T[j,a]:
            win=T[j,a]==b;tr.append((i,int(T[j,a]),800 if win else -1200));block.append(int(win))
            if m in MODES[3:] and len(block)==32:
                alarm=sum(block)<=R['LIMITS']['BLOCK_SPEND'];block=[]
                if alarm:
                    e['stop']=i+1
                    if m=='E_REFRESH' and cycle==0:cycle+=1;st='TRAIN';bx=[];by=[]
                    else:st='DONE'
    return tr,ev

def study():
    counts={};out={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        counts[k]=counts.get(k,0)+1
    for case in R['CASES']:
        rows={m:[] for m in MODES}
        for seed in SEEDS:
            x,y=R['R']['R']['series'](seed,case)
            rr={}
            for m in MODES:
                z=simulate(x,y,m);rr[m]=z;tr,ev=oracle(x,y,m)
                ck('independent_actions',z['trades']==tr);ck('independent_epochs',z['epochs']==ev)
                ck('accounting',z['net']==sum(t[2] for t in tr)-H);ck('audit_budget',sum(len(e['looks']) for e in ev)<=10)
                ck('no_warmup_trade',all(i>=TRAIN for i,_,_ in tr));ck('unique_trade',len({i for i,_,_ in tr})==len(tr))
                cut=4096; yy=y.copy();yy[cut:]*=-1; zz=simulate(x,yy,m)
                ck('future_prefix',[t for t in tr if t[0]<cut]==[t for t in zz['trades'] if t[0]<cut])
                rows[m].append(dict(net=z['net'],drawdown=z['drawdown'],trades=len(tr),admissions=sum(e['admit'] is not None for e in ev),stops=sum(e['stop'] is not None for e in ev),refresh=int(len(ev)>1)))
            ck('matched_initial',rr['C_AUDIT']['epochs'][0]['admit']==rr['D_STOP']['epochs'][0]['admit']==rr['E_REFRESH']['epochs'][0]['admit'])
        out[case]={m:{'mean_'+k:sum(z[k] for z in rs)/len(rs) for k in rs[0]} for m,rs in rows.items()}
    return dict(plan=PLAN,plan_sha=SHA,summary=out,checks=counts,passed=sum(counts.values()))
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2))
