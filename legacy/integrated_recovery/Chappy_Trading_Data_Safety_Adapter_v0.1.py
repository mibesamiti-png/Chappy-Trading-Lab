"""R168: terminal data authority adapter, synthetic tests only. No archive read."""
import argparse, hashlib, json, runpy
from pathlib import Path
from collections import Counter
from fractions import Fraction as F
P=Path(__file__).parent
PIN='fe0a70707e9f75fa2974bc9f7c8c61cdbc5282fe079f492ccb1da75b5db9c94b'
SRC=P/'Chappy_Trading_Capital_Lifecycle_Study_v0.1.py'
if hashlib.sha256(SRC.read_bytes()).hexdigest()!=PIN:raise ValueError('R166 dependency')
R=runpy.run_path(str(SRC)); L=R['A']['L']; M=R['M']; D=R['D']; END=L['END']; SYMS=L['SYMS']; COMMON=L['COMMON']; HS=L['HS']; H=19*D
PLAN=dict(round=168,scope='synthetic only, no market archive',parent=PIN,authority='terminal DATA stop for this run; no auto resume; repair and independently requalify before new run',timing='validate entire structural input before replay; canonical scheduled decisions; no early receipt',monitor='R166 economics unchanged; prior accepted contracts unresolved at next day boundary or full four shadow intents missing mature labels is DATA, not economic loss; fewer than four is insufficient',sync='at structurally supported common slot all six feature states required; first slot in each session excluded by existing cohort',capital='R161 unchanged; stop new orders, retain and settle existing contracts as evidence arrives',fees=[20,40],modes=['FROZEN','STOP','REFRESH'])
def validate(idx):
 for k,x in idx.items():
  if not isinstance(k,tuple) or len(k)!=3:raise ValueError('key')
  sym,d,s=k
  if sym not in SYMS or type(d)!=int or not 0<=d<19 or type(s)!=int or not 0<=s<63:raise ValueError('key')
  if any(type(x.get(n))!=int for n in ('open','high','low','close','volume','received')):raise ValueError('numeric')
  if x['received']<END(d,s):raise ValueError('early receipt')
  if min(x['open'],x['close'],x['low'])<=0 or x['low']>min(x['open'],x['close']) or x['high']<max(x['open'],x['close']) or x['volume']<0:raise ValueError('OHLCV')

def rows_from(idx):
 validate(idx);rows=[]
 for d in range(5,19):
  for s in COMMON:
   for sym in SYMS:
    t=END(d,s);z,states=L['observe'](idx,sym,d,s)
    if z['decision']!=t:raise ValueError('noncanonical clock')
    rows.append(dict(key=(d,s,sym),t=t,states=states,labels={h:M['label'](idx,z,h,H) for h in HS}))
 return rows

def simulate(rows,c,mode,ck,ohlcv=False):
 q=[];shadow=[];reviews=[];events=[];decision=R['select'](rows,c,5,ck);i=decision['candidate'];ok=decision['admit'];events.append(dict(kind='initial',day=10,**decision));restart=None;used=False;data_stop=None
 for day in range(10,19):
  if data_stop is not None:continue
  # Every accepted intraday contract is due before the next day, including older contracts outside the shadow window.
  if q and M['settle'](q,c,day*D-1)['unresolved']:
   data_stop=day*D;events.append(dict(kind='data_stop',day=day,t=data_stop,reason='accepted_contract_unresolved'));continue
  # Full shadow window expected to be mature by next day. Insufficient observations are distinct.
  if ok and len(shadow)>=4 and not all(R['ready'](l,day*D) for _,_,_,l in shadow[-4:]):
   data_stop=day*D;events.append(dict(kind='data_stop',day=day,t=data_stop,reason='shadow_unresolved'));continue
  if restart==day:
   decision=R['select'](rows,c,day-5,ck);i=decision['candidate'];ok=decision['admit'];shadow=[];events.append(dict(kind='readmit',day=day,**decision))
  if ok and mode!='FROZEN':
   review=R['monitor'](shadow,c,day,ck);reviews.append(dict(day=day,review=review))
   if review is not None and review['stop']:
    ok=False;events.append(dict(kind='stop',day=day,candidate=i))
    if mode=='REFRESH' and not used and day+5<19:
     used=True;restart=day+5;events.append(dict(kind='refresh',day=day,restart=restart))
  if ok or ohlcv:
   batch=R['window'](rows,day,day+1)
   for t in sorted({r['t'] for r in batch}):
    group=[r for r in batch if r['t']==t]
    # Structurally ineligible common slots (first in each session) are not an outage.
    if ohlcv and group[0]['key'][1] not in (COMMON[0],next(s for s in COMMON if s>=28)) and (len(group)!=len(SYMS) or {r['key'][2] for r in group}!=set(SYMS) or any(r['states'] is None for r in group)):
     data_stop=t;events.append(dict(kind='data_stop',day=day,t=t,reason='synchronized_features_unavailable'));break
    if ok:
     new=R['orders'](group,i);q.extend(new);shadow.extend(new)
 z=R['account'](q,c,H-1,ck);ck('authority',data_stop is None or all(t<data_stop for _,t,_,_ in q));return dict(events=events,reviews=reviews,account=z,orders=q,data_stop=data_stop)

def fixture(case):
 out={}
 for j,sym in enumerate(SYMS):
  p=1000000+10000*j
  for d in range(19):
   for s in range(63):
    o=p;p+=1000 if case=='stable' or d<11 else -1000
    if case=='missing' and (j,d,s)==(0,11,9):continue
    out[sym,d,s]=dict(open=o,high=max(o,p)+10,low=min(o,p)-10,close=p,volume=100,received=END(d,s),actual_start=f'{d}:{s}')
 return out

def run():
 checks=Counter();results=[]
 def ck(k,v):
  if not v:raise AssertionError(k)
  checks[k]+=1
 for case in ('stable','reversal','missing'):
  idx=fixture(case);rows=rows_from(idx)
  for c in PLAN['fees']:
   for mode in PLAN['modes']:
    z=simulate(rows,c,mode,ck,True);old=R['simulate'](rows,c,mode,ck);a=z['account'];q=z['orders'];ck('oracle',{k:v for k,v in a.items() if k!='events'}==M['cash_ref'](q,c,H-1))
    if case!='missing':ck('unchanged',z['data_stop'] is None and all(z[k]==old[k] for k in ('events','reviews','account','orders')))
    else:
     ck('missing_stops',z['data_stop'] is not None);ck('no_future_orders',all(t<z['data_stop'] for _,t,_,_ in q));ck('prefix_orders',q==[x for x in old['orders'] if x[1]<z['data_stop']]);ck('collateral_preserved',a['reserved']==M['N']*a['unresolved'])
    results.append(dict(case=case,fee=c,mode=mode,data_stop=z['data_stop'],events=z['events'],intents=len(q),accepted=len(a['accepted']),unresolved=a['unresolved'],reserved=a['reserved'],net=a['net']))
 # R167 exact unknown-monitor gap reproduction, now terminal for every mode.
 rows=R['fixture']('unknown_monitor')
 for mode in PLAN['modes']:
  z=simulate(rows,20,mode,ck);old=R['simulate'](rows,20,mode,ck);ck('unknown_stop',z['data_stop']==12*D);ck('unknown_no_orders',all(k[0]<12 for k,*_ in z['orders']));ck('unknown_not_economic',not any(e['kind']=='stop' for e in z['events']));ck('unknown_hold',z['account']['reserved']==100000 and z['account']['net'] is None);results.append(dict(case='unknown_monitor',fee=20,mode=mode,data_stop=z['data_stop'],old_later=sum(k[0]>=12 for k,*_ in old['orders']),later=sum(k[0]>=12 for k,*_ in z['orders']),reserved=z['account']['reserved'],net=z['account']['net']))
 # Older accepted unresolved contract outside the four-intent shadow window.
 rows=R['fixture']('stable');first=next(r for r in rows if r['key'][:2]==(11,0));first['labels'][60]=dict(horizon=60,gross=None,mature=None)
 last=next(r for r in rows if r['key'][:2]==(11,3));extra=dict(last,key=(11,4,last['key'][2]),t=last['t']+60,labels={h:dict(l,mature=l['mature']+60) for h,l in last['labels'].items()});rows.append(extra);rows.sort(key=lambda r:r['t'])
 z=simulate(rows,20,'REFRESH',ck);ck('older_unresolved_stop',z['data_stop']==12*D and z['events'][-1]['reason']=='accepted_contract_unresolved');ck('older_hold',z['account']['reserved']==100000);ck('older_no_orders',all(k[0]<12 for k,*_ in z['orders']));ck('older_outside_shadow',all(R['ready'](l,12*D) for _,_,_,l in z['orders'][-4:]));results.append(dict(case='older_unresolved',fee=20,mode='REFRESH',data_stop=z['data_stop'],reason=z['events'][-1]['reason'],reserved=z['account']['reserved'],net=z['account']['net']))
 # Structural corruption rejected before features, even in a future input row.
 key=(SYMS[0],5,COMMON[1]);v=fixture('stable')[key]
 for bad in [dict(v,received=v['received']-1),dict(v,received=True),dict(v,high=0),dict(v,volume=-1),dict(v,close=0)]:
  try:validate({key:bad})
  except ValueError:ck('invalid_rejected',True)
  else:ck('invalid_rejected',False)
 ck('source_unchanged',hashlib.sha256(SRC.read_bytes()).hexdigest()==PIN)
 return dict(plan=PLAN,checks=dict(checks),passed=sum(checks.values()),cases=results,status='ENTRYPOINT_AND_FULL_REGRESSION_PENDING')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();z=run()
 with open(a.output,'x') as f:json.dump(z,f,indent=2,sort_keys=True);f.write('\n')
