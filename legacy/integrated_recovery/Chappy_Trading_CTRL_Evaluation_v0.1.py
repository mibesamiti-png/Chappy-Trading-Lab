"""R157 known-development replay only. No network, order placement or unknown period access."""
import argparse,runpy,json,hashlib,zipfile,io
from collections import Counter
from pathlib import Path
from datetime import datetime
from fractions import Fraction as F
from statistics import median
P=Path(__file__).parent
DEPS={'Chappy_Trading_CTRL_Intake_v0.1.py':'51a72c0dd6b961a654fbc67438dcf123aa5c9a22221229aee55ed7e69c505ad5','Chappy_Trading_Configured_Lifecycle_Study_v0.1.py':'8279536d239361f54e9f0e167af1105caa0c56b7159011b2d8a1bf4188735b09'}
for n,h in DEPS.items():
 if hashlib.sha256((P/n).read_bytes()).hexdigest()!=h:raise ValueError('dependency hash')
I=runpy.run_path(str(P/'Chappy_Trading_CTRL_Intake_v0.1.py'));C=runpy.run_path(str(P/'Chappy_Trading_Configured_Lifecycle_Study_v0.1.py'))
R=C['R']['R']; B=C['R']['B']; cfg=C['NEW']; days=I['DAYS']; symbols=I['SYMS']; slots=I['SLOTS']; segments=((0,28),(28,63)); signals=tuple(s for a,b in segments for s in range(a+3,b-3,4))
PLAN=dict(dependencies=DEPS,archive_sha=I['SHA'],dates=days,symbols=symbols,segments=segments,signals=signals,config=cfg._asdict(),fees=[20,40],modes=['HOLD','CHASE','FADE','FROZEN','STOP','REFRESH'],clock='logical trading day ordinal plus original JST seconds, ideal bar end; no actual receipt',entry='next bar close',exit='third bar close',capital=200000,notional=100000,observation_fee=0,scope='known development only; fixed before replay; no statistical or execution guarantee')
PLAN_SHA=R['digest'](PLAN)
def load(path):
 meta=I['intake'](path);rows=[]
 raw=Path(path).read_bytes()
 if I['sha'](raw)!=I['SHA']:raise ValueError('archive changed')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  for e in meta['symbols']:
   name=next(n for n in z.namelist() if n.rsplit('/',1)[-1].startswith(e+'_') and n.endswith('.csv'))
   rr,_=I['parse'](z.read(name),e,Counter());rows+=rr
 rows.sort(key=lambda a:(a[1],a[0]))
 if I['sha'](json.dumps(rows,separators=(',',':')).encode())!=meta['normalized_sha256']:raise ValueError('normalized hash')
 idx={}
 for sym,t,close,o,h,l,c,v in rows:
  d=days.index(t[:10]);s=slots.index(t[11:]);q=datetime.fromisoformat(close);sec=q.hour*3600+q.minute*60+q.second
  idx[sym,d,s]=dict(open=o,high=h,low=l,close=c,volume=v,received=d*86400+sec,actual_start=t,actual_end=close)
 return idx,meta

def freeze(idx,sym,d,s):
 if d<5 or s not in signals:raise ValueError('unscheduled')
 t=idx[sym,d,s]['received']; a=[idx.get((sym,d,j)) for j in range(s-3,s+1)];hist=[idx.get((sym,i,s)) for i in range(d-5,d)]
 out=dict(symbol=sym,day=d,slot=s,decision=t,state=None,momentum=0,reason='unknown',feature_sha=None)
 if any(x is None or x['received']>t for x in a+hist):return out
 if any(x['volume']==0 for x in a):return dict(out,reason='zero_volume')
 # Reuse R68 and R69 with a local four-bar window and five same-time observations.
 # Receipt gating is performed on original clock above; the normalized local clock is not an execution timestamp.
 def vals(x):return [x[k] for k in ('open','high','low','close','volume')]
 bars=[R['bar'](j,*vals(x)) for j,x in enumerate(a)]
 fr=R['freeze'](f'{sym}:{d}:{s}',bars,3,1200)
 def volrow(day,slot,x):return B['row'](day,slot,x['volume'],symbol=sym,o=x['open'],h=x['high'],l=x['low'],c=x['close'])
 vr=[volrow(i,6,x) for i,x in zip(range(d-5,d),hist)]+[volrow(d,j,x) for j,x in zip(range(3,7),a)]
 vol=B['measure'](vr,d,6,B['end'](d,6),sym)['same_slot_median']
 if fr['state']!='OBSERVED' or vol['state']!='OBSERVED':return dict(out,reason='undefined_or_history')
 delta=F(fr['feature']['close_change']);body=F(fr['feature']['body_fraction']);ratio=F(vol['ratio']);state=4*int(delta>0)+2*int(body>0)+int(ratio>=2)
 return dict(out,state=state,momentum=int(delta>0)-int(delta<0),reason='ready',feature_sha=R['digest']([fr,vol,[x['actual_start'] for x in a+hist]]))

def label(idx,z,cut):
 out=dict(gross=None,direction=None,mature=None,reason='feature_unavailable')
 if z['state'] is None:return out
 d,s,sym=z['day'],z['slot'],z['symbol'];w=[idx.get((sym,d,j)) for j in range(s+1,s+4)]
 if not any(a<=s-3 and s+3<b for a,b in segments):raise ValueError('session boundary')
 if any(x is None or x['received']>cut for x in w):return dict(out,reason='unresolved')
 if any(x['volume']==0 for x in w):return dict(out,reason='zero_volume_path')
 g=F(w[-1]['close']-w[0]['close'],w[0]['close']);return dict(gross=str(g),direction=int(g>0)-int(g<0),mature=max(x['received'] for x in w),reason='mature')

def evaluate(path):
 idx,meta=load(path);checks=Counter();rs=[]
 def ck(k,b):
  if not b:raise AssertionError(k)
  checks[k]+=1
 for d in range(5,len(days)):
  for s in signals:
   for sym in symbols:
    z=freeze(idx,sym,d,s);l=label(idx,z,len(days)*86400);rs.append((z,l));t=z['decision'];a=[idx[sym,d,j] for j in range(s-3,s+1)];h=[idx[sym,i,s] for i in range(d-5,d)];w=[idx[sym,d,j] for j in range(s+1,s+4)];b=a[-1];v=median([x['volume'] for x in h]);delta=b['close']-a[-2]['close']
    state=None if any(x['volume']==0 for x in a) or not v or b['high']==b['low'] else 4*int(delta>0)+2*int(b['close']>b['open'])+int(b['volume']>=2*v)
    ck('feature_oracle',state==z['state'] and (state is None or z['momentum']==int(delta>0)-int(delta<0)))
    g=None if state is None or any(x['volume']==0 for x in w) else str(F(w[-1]['close']-w[0]['close'],w[0]['close']))
    ck('label_oracle',l['gross']==g and (g is None or l['mature']==w[-1]['received']))
    prefix={(sym,d,j):idx[sym,d,j] for j in range(s-3,s+1)};prefix.update({(sym,i,s):idx[sym,i,s] for i in range(d-5,d)})
    ck('feature_prefix',freeze(prefix,sym,d,s)==z and all(x['received']<=t for x in prefix.values()))
    ck('same_session',any(lo<=s-3 and s+3<hi for lo,hi in segments));ck('strict_future',all(x['received']>t for x in w))
    if l['mature'] is not None:
     ck('not_mature_before',label(idx,z,l['mature']-1)['gross'] is None);ck('mature_at_receipt',label(idx,z,l['mature'])==l);ck('learning_boundary',not C['ready'](l,l['mature']) and C['ready'](l,l['mature']+1))
 coverage={}
 for name,lo,hi in [('train',5,8),('audit',8,10),('evaluation',10,19)]:
  part=[(d,l) for d,l in rs if lo<=d['day']<hi];coverage[name]=dict(opportunities=len(part),features=sum(d['state'] is not None for d,l in part),mature=sum(l['mature'] is not None for d,l in part),flat=sum(l['direction']==0 for d,l in part),states=dict(Counter(str(d['state']) for d,l in part)))
 results={}
 for cost in PLAN['fees']:
  for mode in PLAN['modes']:
   if mode in ('HOLD','CHASE','FADE'):
    ev=[];rv=[];orders=[] if mode=='HOLD' else [C['order'](d,l,d['momentum']*(1 if mode=='CHASE' else -1)) for d,l in rs if d['day']>=cfg.active and d['state'] is not None and d['momentum']]
   else:
    ev,orders,rv=C['simulate'](rs,cost,mode,cfg);ck('lifecycle_oracle',(ev,orders,rv)==C['oracle'](rs,cost,mode,cfg))
   z=C['settle'](orders,cost,cfg);ref=C['cash_ref'](orders,cost,cfg);ck('cash_oracle',{k:v for k,v in z.items() if k!='events'}==ref);ck('conservation',F(z['cash'])+z['reserved']==200000+F(z['gross'])-F(z['fees']));ck('nonnegative',all(F(e[3])>=0 for e in z['events']));ck('partition',len(orders)==len(z['accepted'])+len(z['blocked']));ck('unknown', (z['net'] is None)==bool(z['unresolved']))
   # Freeze all decisions before evaluation start, independently from evaluation labels.
   if mode not in ('HOLD','CHASE','FADE'):
    masked=[(d,dict(l,gross=None,mature=None,direction=None)) if d['day']>=cfg.active else (d,l) for d,l in rs];ck('initial_no_eval',C['simulate'](masked,cost,mode,cfg)[0][0]==ev[0])
   results[f'{cost}:{mode}']=dict(lifecycle=ev,reviews=rv,intents=len(orders),accepted_count=len(z['accepted']),blocked_count=len(z['blocked']),net_yen=None if z['net'] is None else round(float(F(z['net'])),2),**z)
   # retain full accepted and blocked keys (not counts under those keys)
 return dict(status='KNOWN_DEVELOPMENT_ONLY',plan=PLAN,plan_sha=PLAN_SHA,normalized_sha=meta['normalized_sha256'],coverage=coverage,results=results,checks=dict(checks),passed=sum(checks.values()),limits=['already studied 19 days; not unknown validation','ideal bar-end receipt, next close proxy; no executable fill','fixed 100k yen notional, no lot or borrow constraints; both directions hypothetical','point audit/monitor no statistical guarantee','calendar ordinal compresses gaps, original timestamps preserved in intake','no observation fee or live orders'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('--output',required=True);p.add_argument('--plan-only',action='store_true');a=p.parse_args();r=dict(plan=PLAN,plan_sha=PLAN_SHA) if a.plan_only else evaluate(a.archive)
 with open(a.output,'x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
