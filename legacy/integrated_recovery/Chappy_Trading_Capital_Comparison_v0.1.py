"""R142: synthetic fixed notional, fully funded one-slot execution; no real orders."""
import hashlib,json,runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Core_Comparison_v0.1.py')
R=runpy.run_path(str(P)); H=R['H']; TRAIN=R['TRAIN']; CASES=R['R']['CASES']; MODES=('HOLD','CHASE','FADE')+R['MODES']; SEEDS=range(142000,142016)
PLAN=dict(source_sha=hashlib.sha256(P.read_bytes()).hexdigest(),seeds=list(SEEDS),cases=list(CASES),modes=MODES,horizon=H,warmup=TRAIN,initial=200000,notional=100000,observation_prepaid=H,gross_win=1000,gross_loss=-1000,costs=[200,400],policy_training_cost=200,capital='full notional reserved for either direction; one slot settlement; no borrowing; shadow observations prepaid; no sizing/compounding',synthetic_only=True)
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()
def intents(x,y,m):
    if m in R['MODES']:
        z=R['simulate'](x,y,m); return [(i,d) for i,d,_ in z['trades']],z['epochs']
    if m=='HOLD':return [],[]
    return [(i,int(y[i-1])*(1 if m=='CHASE' else -1)) for i in range(TRAIN,len(y))],[]
def settle(y,orders,cost,initial=200000,notional=100000):
    if initial<len(y) or notional<1000+cost or cost<0:raise ValueError('capital')
    cash=initial-len(y);peak=initial;dd=len(y); fills=[];blocked=[]
    for i,d in orders:
        if cash<notional:blocked.append(i);continue
        gross=1000 if d==y[i] else -1000
        cash+=gross-cost;peak=max(peak,cash);dd=max(dd,peak-cash);fills.append((i,d,gross,cash))
    return dict(fills=fills,blocked=blocked,final=cash,net=cash-initial,drawdown=dd,fees=len(y)+len(fills)*cost,gross=sum(f[2] for f in fills),intents=len(orders))
def oracle(y,orders,cost,initial=200000,notional=100000):
    cash=initial-len(y); path=[initial,cash];f=[];b=[]; gross=0; lookup=dict(orders)
    for i,actual in enumerate(y):
        if i not in lookup:continue
        d=lookup[i]
        if cash<notional:b.append(i);continue
        cash-=notional; proceeds=notional+(1000 if d==actual else -1000)-cost;cash+=proceeds
        gross+=proceeds-notional+cost;path.append(cash);f.append((i,d,proceeds-notional+cost,cash))
    a=np.asarray(path,dtype=np.int64)
    return dict(fills=f,blocked=b,final=cash,net=cash-initial,drawdown=int(np.max(np.maximum.accumulate(a)-a)),fees=len(y)+len(f)*cost,gross=gross,intents=len(orders))
def study():
    counts={};summary={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        counts[k]=counts.get(k,0)+1
    for case in CASES:
        rows={str(c):{m:[] for m in MODES} for c in PLAN['costs']}
        for seed in SEEDS:
            x,y=R['R']['R']['R']['series'](seed,case)
            for m in MODES:
                a,ep=intents(x,y,m)
                if m in R['MODES']:
                    tr,ev=R['oracle'](x,y,m);ck('core_oracle',a==[(i,d) for i,d,_ in tr] and ep==ev)
                cut=4096;yy=y.copy();yy[cut:]*=-1;aa,_=intents(x,yy,m)
                ck('intent_prefix',[(i,d) for i,d in a if i<cut]==[(i,d) for i,d in aa if i<cut])
                for c in PLAN['costs']:
                    z=settle(y,a,c);q=oracle(y,a,c);ck('execution_oracle',z==q)
                    ck('cash_nonnegative',z['final']>=0 and all(f[3]>=0 for f in z['fills']))
                    ck('conservation',z['net']==z['gross']-z['fees']);ck('intent_partition',len(z['fills'])+len(z['blocked'])==len(a));ck('warmup_unique',all(i>=TRAIN for i,d in a) and len(dict(a))==len(a))
                    prev=200000-H
                    for _,_,g,cash in z['fills']:
                        ck('funded_trade',prev>=100000 and cash==prev+g-c);prev=cash
                    zz=settle(yy,aa,c);ck('fill_prefix',[f for f in z['fills'] if f[0]<cut]==[f for f in zz['fills'] if f[0]<cut]);ck('blocked_prefix',[i for i in z['blocked'] if i<cut]==[i for i in zz['blocked'] if i<cut])
                    rows[str(c)][m].append(dict(net=z['net'],final=z['final'],drawdown=z['drawdown'],trades=len(z['fills']),blocked=len(z['blocked']),intents=len(a),fees=z['fees'],capital_block=int(bool(z['blocked'])),admissions=sum(e['admit'] is not None for e in ep),stops=sum(e['stop'] is not None for e in ep),refresh=int(len(ep)>1)))
        summary[case]={c:{m:{**{'mean_'+k:sum(t[k] for t in rs)/len(rs) for k in rs[0]},'positive_runs':sum(t['net']>0 for t in rs),'min_final':min(t['final'] for t in rs)} for m,rs in modes.items()} for c,modes in rows.items()}
    fixtures=[]
    for initial in (100003,100004,101203,101204,200000):
        y=np.array([-1,1,1,1]);a=[(i,1) for i in range(4)];z=settle(y,a,200,initial);ck('fixture_oracle',z==oracle(y,a,200,initial));fixtures.append(dict(initial=initial,result=z))
    ck('one_yen_short',len(fixtures[0]['result']['fills'])==0);ck('exact_capital',len(fixtures[1]['result']['fills'])==1);ck('post_loss_exact',len(fixtures[3]['result']['fills'])==4);ck('post_loss_short',len(fixtures[2]['result']['fills'])==1)
    return dict(plan=PLAN,plan_sha=SHA,summary=summary,fixtures=fixtures,checks=counts,passed=sum(counts.values()))
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2))
