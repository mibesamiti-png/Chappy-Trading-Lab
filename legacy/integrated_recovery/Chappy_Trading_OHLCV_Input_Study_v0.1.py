"""R148 synthetic OHLCV input contract; offline only, no orders or real-market reads."""
import hashlib,json,runpy,random
from fractions import Fraction as F
from pathlib import Path
from statistics import median
from collections import Counter
ROOT=Path(__file__).parent
P=ROOT/'Chappy_Trading_Price_Response_Study_v0.1.py'; V=ROOT/'Chappy_Trading_Volume_Baseline_Study_v0.1.py'
for p,h in [(P,'1b9e2634cdfaeaa15b6d11446e187cfaa90a3d6daa89f64dc1e670a0685511a3'),(V,'719a82912c9fc817b03fc26755124b74bb641630673c7526a846fd47b06bb265')]:
    if hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise ValueError('dependency hash')
R=runpy.run_path(str(P)); B=runpy.run_path(str(V)); end=B['end']; digest=R['digest']
PLAN=dict(synthetic_only=True,segments=B['PLAN']['segments'],days=8,symbols=['X','Y'],signals=[3,6,23,26],first_day=5,entry_offset=1,exit_offset=3,notional=100000,fees_bps=[20,40],seeds=list(range(148000,148032)),features=['positive close change','positive candle body','same-slot median volume ratio >=2'],label='signed gross return, flat distinct; full future window required',receipt='decision includes receipt at cutoff; learning strictly after label receipt',cases=['complete','missing','delayed','zero_volume'])

def validate(rows):
    seen={}
    for r in rows:
        B['valid'](r); k=(r['symbol'],r['regime'],r['day'],r['slot'])
        if k in seen:raise ValueError('duplicate canonical bar')
        seen[k]=r
    return seen

def freeze(rows,day,s,symbol='X'):
    if day<5 or s not in PLAN['signals']:raise ValueError('not scheduled')
    t=end(day,s); start=B['segment'](s)
    prefix=[r for r in rows if r['received']<=t and r['symbol']==symbol and r['regime']=='V1' and (r['day']<day or r['day']==day and r['slot']<=s)]
    lookup=validate(prefix)
    local=[lookup.get((symbol,'V1',day,j)) for j in range(s-3,s+1)]
    out=dict(day=day,slot=s,symbol=symbol,decision=t,state=None,reason='unknown',momentum=0,feature_sha=None)
    if any(r is None for r in local):return out
    if any(r['volume']==0 for r in local):return dict(out,reason='zero_volume')
    bars=[R['bar'](r['slot']-start,r['open'],r['high'],r['low'],r['close'],r['volume'],r['received']-day*86400-start*300) for r in local]
    fr=R['freeze'](f'{symbol}:{day}:{s}',bars,s-start,(s-start+1)*300)
    vol=B['measure'](prefix,day,s,t,symbol)['same_slot_median']
    if fr['state']!='OBSERVED' or vol['state']!='OBSERVED':return dict(out,reason='undefined_or_history')
    delta=F(fr['feature']['close_change']); body=F(fr['feature']['body_fraction']); ratio=F(vol['ratio'])
    state=4*int(delta>0)+2*int(body>0)+int(ratio>=2)
    return dict(out,state=state,reason='ready',momentum=(delta>0)-(delta<0),feature_sha=digest([fr,vol]))

def label(d,lookup,cut):
    out=dict(gross=None,direction=None,mature=None,reason='feature_unavailable')
    if d['state'] is None:return out
    day,s,symbol=d['day'],d['slot'],d['symbol']; ks=[(symbol,'V1',day,j) for j in range(s+1,s+4)]
    if any(B['segment'](j)!=B['segment'](s) for j in range(s+1,s+4)):raise ValueError('cross session')
    w=[lookup.get(k) for k in ks]; out['reason']='unresolved'
    if any(r is None or r['received']>cut for r in w):return out
    if any(r['volume']==0 for r in w):return dict(out,reason='zero_volume_path')
    g=F(w[-1]['close']-w[0]['close'],w[0]['close']); m=max(r['received'] for r in w)
    return dict(gross=str(g),direction=(g>0)-(g<0),mature=m,reason='mature')

def learning_at(records,cutoff):
    return [(d['symbol'],d['day'],d['slot'],l['gross']) for d,l in records if l['mature'] is not None and l['mature']<cutoff]

def oracle(rows,day,s,symbol,cut):
    idx={(r['day'],r['slot']):r for r in rows if r['symbol']==symbol and r['regime']=='V1'}
    t=end(day,s); a=[idx.get((day,j)) for j in range(s-3,s+1)]; h=[idx.get((i,s)) for i in range(day-5,day)]
    if any(r is None or r['received']>t for r in a+h):return None,None,None
    if any(r['volume']==0 for r in a) or a[-1]['high']==a[-1]['low'] or median([r['volume'] for r in h])==0:return None,None,None
    b=a[-1]; delta=b['close']-a[-2]['close']; state=4*(delta>0)+2*(b['close']>b['open'])+(b['volume']>=2*median([r['volume'] for r in h])); mom=(delta>0)-(delta<0)
    f=[idx.get((day,j)) for j in range(s+1,s+4)]
    if any(r is None or r['received']>cut or r['volume']==0 for r in f):return state,mom,None
    return state,mom,(str(F(f[-1]['close']-f[0]['close'],f[0]['close'])),max(r['received'] for r in f))

def fixture(seed,case):
    rng=random.Random(seed); rows=[]
    for sym in PLAN['symbols']:
        for d in range(8):
            c=10000
            for a,b in PLAN['segments']:
                for s in range(a,b+1):
                    o=c;c=o+rng.choice([-40,-20,0,20,40]);v=rng.choice([100,150,200,400]); delay=0
                    if case=='missing' and rng.random()<.055:continue
                    if case=='delayed' and rng.random()<.16:delay=rng.choice([1,300,600])
                    if case=='zero_volume' and rng.random()<.05:v=0
                    rows.append(B['row'](d,s,v,received=end(d,s)+delay,symbol=sym,o=o,h=max(o,c)+5,l=min(o,c)-5,c=c))
    return rows

def study():
    checks=Counter(); report={}; samples=[]
    def ck(k,x):
        if not x:raise AssertionError(k)
        checks[k]+=1
    def reject(k,fn):
        try:fn()
        except ValueError:ck(k,True);return
        raise AssertionError(k)
    for case in PLAN['cases']:
        counts=Counter(); nets={f'{m}_{c}':F(0) for m in ['HOLD','CHASE','FADE'] for c in PLAN['fees_bps']}
        for seed in PLAN['seeds']:
            rows=fixture(seed,case);idx=validate(rows);cut=end(8,0); previous={}
            for d in range(5,8):
                for sym in PLAN['symbols']:
                    for s in PLAN['signals']:
                        z=freeze(rows,d,s,sym);l=label(z,idx,cut); state,mom,truth=oracle(rows,d,s,sym,cut)
                        ck('feature_oracle',z['state']==state and (state is None or z['momentum']==mom));ck('label_oracle',truth==(None if l['gross'] is None else (l['gross'],l['mature'])))
                        t=z['decision']; ck('prefix',z==freeze([r for r in rows if r['received']<=t],d,s,sym)); ck('input_order',z==freeze(rows[::-1],d,s,sym))
                        k=(sym,d);ck('nonoverlap',previous.get(k,-1)<s+1);previous[k]=s+3
                        ck('same_session',B['segment'](s)==B['segment'](s+3));counts['scheduled']+=1
                        if state is None:counts['feature_unknown']+=1;continue
                        counts['feature_ready']+=1
                        if l['gross'] is None:
                            counts['label_unresolved']+=1;ck('unresolved_never_learning',learning_at([(z,l)],cut+100000)==[]);continue
                        counts['label_ready']+=1; counts['flat']+=int(l['direction']==0)
                        m=l['mature'];ck('not_mature_before',label(z,idx,m-1)['gross'] is None);ck('mature_at_receipt',label(z,idx,m)==l);ck('strict_learning_boundary',learning_at([(z,l)],m)==[] and learning_at([(z,l)],m+1)==[(sym,d,s,l['gross'])])
                        g=F(l['gross']);ck('direction',l['direction']==(g>0)-(g<0));counts['late_labels']+=int(m>end(d,s+3))
                        for mode,a in [('HOLD',0),('CHASE',mom),('FADE',-mom)]:
                            for c in PLAN['fees_bps']:
                                pnl=100000*(a*g-F(c,10000)) if a else F(0);nets[f'{mode}_{c}']+=pnl
                                ck('fee_accounting',pnl==(100000*a*g-c*10 if a else 0))
                        if seed==PLAN['seeds'][0] and len(samples)<12:samples.append(dict(case=case,feature=z,label=l))
        report[case]=dict(counts=counts,complete_case_pnl={k:round(float(v),2) for k,v in nets.items()})
    rows=fixture(148000,'complete');idx=validate(rows);z=freeze(rows,5,3);t=z['decision'];
    mutate=[dict(r,close=r['open'],high=r['open']+5,low=r['open']-5) if r['received']>t else r for r in rows]
    ck('future_price_mutation',freeze(mutate,5,3)==z)
    reject('duplicate',lambda:validate(rows+[rows[0]]));reject('lunch_cross',lambda:freeze(rows,5,9));reject('day_end_cross',lambda:freeze(rows,5,29))
    bad=[dict(rows[0],received=0)]+rows[1:];reject('premature_receipt',lambda:validate(bad))
    missing=dict(idx);missing.pop(('X','V1',5,5));ck('missing_middle',label(z,missing,end(8,0))['gross'] is None)
    delayed=dict(idx);k=('X','V1',5,5);delayed[k]=dict(delayed[k],received=end(5,6)+600);l=label(z,delayed,end(8,0));ck('late_middle',l['mature']==end(5,6)+600);ck('late_middle_before',label(z,delayed,l['mature']-1)['gross'] is None)
    return dict(plan=PLAN,plan_sha=digest(PLAN),checks=dict(checks),passed=sum(checks.values()),report=report,samples=samples,limits=['synthetic sessions only; no exchange calendar or CSV loader','future label is next close to third close hypothetical proxy, not an executable fill','complete-case PnL excludes unresolved labels; no overall profitability or cash ledger','variable payoff and flat labels not compatible with old binary fixed payoff without adaptation','no live data or orders'])
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2))
