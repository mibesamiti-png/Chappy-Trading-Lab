"""R144: reuse R101/R103 short pause in R142 E. Synthetic only."""
import hashlib,json,runpy,itertools
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Capital_Comparison_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='9bcae09e6015b1885f69bb771f8f8493e759c1c8d5c4f55e4914efa7659b69f1':raise ValueError('R142 hash')
R=runpy.run_path(str(P)); C=R['R']; T=C['T']; H=R['H']; SHIFT=4096; SEEDS=range(144000,144032); CASES=R['CASES']; NET=C['R']['R']['R']['NET']
PLAN=dict(source_sha=hashlib.sha256(P.read_bytes()).hexdigest(),seeds=list(SEEDS),cases=list(CASES),costs=R['PLAN']['costs'],initial=200000,notional=100000,horizon=H,gate='R101/R103 last four eligible shadow outcomes since epoch training end including audit; >=3 wins; reset each epoch; current excluded',unchanged='selection, audit, absolute monitor, refresh, execution, observation fees',synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()
def gate(x,y,epochs):
    out=[]; withheld=[]; evidence={}
    for e in epochs:
        if e['admit'] is None:continue
        d=T[e['candidate'],x]; end=e['stop'] if e['stop'] is not None else len(x)
        ix=np.flatnonzero(d[e['train_end']:end])+e['train_end']; hits=(d[ix]==y[ix]).astype(int); cs=np.r_[0,np.cumsum(hits)]
        for k in range(int(np.searchsorted(ix,e['admit'])),len(ix)):
            i=int(ix[k]);order=(i,int(d[i])); allowed=k>=4 and cs[k]-cs[k-4]>=3
            if allowed:out.append(order);evidence[i]=tuple(int(z) for z in ix[k-4:k])
            else:withheld.append(order)
    return out,withheld,evidence
def reference(x,y,epochs):
    out=[];withheld=[];ev={}
    for e in epochs:
        if e['admit'] is None:continue
        hist=[];end=e['stop'] if e['stop'] is not None else len(x);j=e['candidate']
        for i in range(e['train_end'],end):
            d=int(T[j,x[i]])
            if not d:continue
            if i>=e['admit']:
                if len(hist)==4 and NET[tuple(1 if w else -1 for _,w in hist)]:out.append((i,d));ev[i]=tuple(t for t,_ in hist)
                else:withheld.append((i,d))
            hist.append((i,d==y[i]));hist=hist[-4:]
    return out,withheld,ev
def study():
    counts={}; summary={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        counts[k]=counts.get(k,0)+1
    for case in CASES:
        rows={str(c):[] for c in PLAN['costs']}
        for seed in SEEDS:
            x,y=C['R']['R']['R']['series'](seed,case)
            base=C['simulate'](x,y,'E_REFRESH');tr,ep=C['oracle'](x,y,'E_REFRESH'); ck('base_oracle',tr==base['trades'] and ep==base['epochs'])
            orders=[(i,d) for i,d,_ in tr];a,b,ev=gate(x,y,ep);ck('gate_oracle',(a,b,ev)==reference(x,y,ep));ck('partition',sorted(a+b)==orders and not set(a)&set(b))
            for i,d in a:
                ix=ev[i];ck('causal_evidence',len(ix)==4 and max(ix)<i and sum(d0==y[t] for t,d0 in zip(ix,T[next(e['candidate'] for e in ep if e['admit'] is not None and e['admit']<=i and (e['stop'] is None or i<e['stop'])),x[list(ix)]]))>=3)
            yy=y.copy();yy[SHIFT:]*=-1;bb=C['simulate'](x,yy,'E_REFRESH');aa,_,ee=gate(x,yy,bb['epochs']);ck('future_prefix',[(i,d,ev[i]) for i,d in a if i<SHIFT]==[(i,d,ee[i]) for i,d in aa if i<SHIFT])
            for cost in PLAN['costs']:
                z=R['settle'](y,orders,cost);q=R['settle'](y,a,cost);ck('capital_oracle',z==R['oracle'](y,orders,cost) and q==R['oracle'](y,a,cost));ck('conservation',all(t['net']==t['gross']-t['fees'] and t['final']>=0 for t in (z,q)))
                ck('fill_prefix',[f for f in q['fills'] if f[0]<SHIFT]==[f for f in R['settle'](yy,aa,cost)['fills'] if f[0]<SHIFT])
                vals=dict(base_net=z['net'],pause_net=q['net'],delta=q['net']-z['net'],base_dd=z['drawdown'],pause_dd=q['drawdown'],base_trades=len(z['fills']),pause_trades=len(q['fills']),base_blocked=len(z['blocked']),pause_blocked=len(q['blocked']),withheld=len(b),base_post=sum(f[2]-cost for f in z['fills'] if f[0]>=SHIFT),pause_post=sum(f[2]-cost for f in q['fills'] if f[0]>=SHIFT),admitted=int(any(e['admit'] is not None for e in ep)),refresh=int(len(ep)>1),withheld_pnl=sum((1000 if d==y[i] else -1000)-cost for i,d in b))
                ck('cost_effect',z['intents']==len(orders) and q['intents']==len(a));rows[str(cost)].append({k:int(v) for k,v in vals.items()})
        summary[case]={c:dict(**{'mean_'+k:sum(r[k] for r in rs)/len(rs) for k in rs[0]},improved=sum(r['delta']>0 for r in rs),worse=sum(r['delta']<0 for r in rs),same=sum(r['delta']==0 for r in rs),base_positive=sum(r['base_net']>0 for r in rs),pause_positive=sum(r['pause_net']>0 for r in rs)) for c,rs in rows.items()}
    theory={str(p):dict(allow=p**4+4*p**3*(1-p),expected_200=2000*p-1200,expected_400=2000*p-1400) for p in (.25,.5,.6,.7,.75,.9)}
    for bits in itertools.product((-1,1),repeat=4):ck('existing_gate_truth_table',NET[bits]==(sum(b==1 for b in bits)>=3))
    x=np.full(80,7,dtype=int); y=np.ones(80,dtype=int); y[20:24]=-1
    ep=[dict(train_end=0,admit=16,stop=40,candidate=9),dict(train_end=40,admit=56,stop=None,candidate=9)]
    a,b,ev=gate(x,y,ep);ck('fixture_oracle',(a,b,ev)==reference(x,y,ep));ck('fixture_current_loss_allowed',20 in ev);ck('fixture_wait',21 in ev and 22 not in ev and 23 not in ev and 24 not in ev and 27 in ev);ck('fixture_reset',min(ev[56])>=40)
    return dict(plan=PLAN,plan_sha=SHA,summary=summary,theory=theory,checks=counts,passed=sum(counts.values()))
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2))
