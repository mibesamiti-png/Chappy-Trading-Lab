"""R166: fixed capital-aware candidates + R153 shadow monitor, synthetic labels only."""
import argparse,hashlib,json,runpy
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
P=Path(__file__).parent
DEPS={'Chappy_Trading_Capital_Aware_Learning_v0.1.py':'97b24c62808f609a5cfeac525d1779e179ba71c9d6e10c0b5c6f93486cd2dbce','Chappy_Trading_Configured_Lifecycle_Study_v0.1.py':'8279536d239361f54e9f0e167af1105caa0c56b7159011b2d8a1bf4188735b09'}
for p,sha in DEPS.items():
 if hashlib.sha256((P/p).read_bytes()).hexdigest()!=sha:raise ValueError(p)
A=runpy.run_path(str(P/next(iter(DEPS))));R=runpy.run_path(str(P/list(DEPS)[1]));M=A['M'];C=A['C'];HS=A['HS'];IDS=A['IDS'];orders=A['orders'];ready=A['ready'];masked=A['masked'];N=M['N'];INITIAL=M['INITIAL'];D=86400
PLAN=dict(round=166,dependencies=DEPS,scope='synthetic label fixtures only, no price archive',days=19,prep=5,train=3,audit=2,active=10,fees=[20,40],modes=['FROZEN','STOP','REFRESH'],cases=['stable','reversal','failed_readmit','second_stop','unknown_monitor','null'],pool=len(C),monitor='R153/R82 NET last four eligible shadow intents, strict maturity at day boundary; nonpositive net stops',refresh='max one, 3 train + 2 audit days, no orders during pause, no retry',capital='R161 fixed 100000/full collateral plus fee; 200000 initial; independent training/audit accounts; one continuous evaluation account; fixed symbol order',limits='point audit, artificial labels, no statistical or actual execution guarantee')
def window(rows,a,b):return [r for r in rows if a<=r['key'][0]<b]
def account(q,c,t,ck):
 z=M['settle'](q,c,t);ck('cash_oracle',{k:v for k,v in z.items() if k!='events'}==M['cash_ref'](q,c,t));ck('conservation',F(z['cash'])+z['reserved']==INITIAL+F(z['gross'])-F(z['fees']));return z

def select(rows,c,start,ck):
 a=start+3;b=a+2;tr=[r for r in window(rows,start,a) if r['states'] is not None and all(ready(l,a*D) for l in r['labels'].values())];cache={};sc=[]
 for i in range(len(C)):
  q=orders(tr,i);k=tuple((k,t,v,l['horizon'],l['gross'],l['mature']) for k,t,v,l in q)
  if k not in cache:
   z=account(q,c,a*D-1,ck);ck('training_mature',z['net'] is not None);cache[k]=F(z['net'])
  sc.append(cache[k])
 i=max(IDS['ALL_MULTI'],key=sc.__getitem__);ck('wait_tie',sc[i]>0 or i==0)
 q=orders(window(rows,a,b),i);known=all(ready(l,b*D) for _,_,_,l in q);z=account(masked(q,b*D),c,b*D-1,ck);ok=bool(q) and known and z['net'] is not None and F(z['net'])>0
 return dict(candidate=i,admit=ok,train_n=len(tr),train_net=str(sc[i]),audit_net=z['net'],audit_n=len(q),audit_known=known,unique_streams=len(cache))

def monitor(q,c,day,ck):
 w=q[-4:];t=day*D
 if len(w)!=4 or not all(ready(l,t) for _,_,_,l in w):return None
 vals=[v*F(l['gross'])*10000 for _,_,v,l in w];net=sum(vals)-4*c
 z=R['M']['decide']('NET',6,c,[dict(index=i,received=i+3,bps=v) for i,v in enumerate(vals)])
 stop=z['action']=='WAIT';ck('monitor_r82',stop==(net<=0));return dict(stop=stop,keys=[x[0] for x in w],net_bps=str(net))

def simulate(rows,c,mode,ck):
 q=[];shadow=[];reviews=[];events=[];decision=select(rows,c,5,ck);i=decision['candidate'];ok=decision['admit'];events.append(dict(kind='initial',day=10,**decision));restart=None;used=False
 for day in range(10,19):
  if restart==day:
   decision=select(rows,c,day-5,ck);i=decision['candidate'];ok=decision['admit'];shadow=[];events.append(dict(kind='readmit',day=day,**decision))
  if ok and mode!='FROZEN':
   review=monitor(shadow,c,day,ck);reviews.append(dict(day=day,review=review))
   if review is not None and review['stop']:
    ok=False;events.append(dict(kind='stop',day=day,candidate=i))
    if mode=='REFRESH' and not used and day+5<19:
     used=True;restart=day+5;events.append(dict(kind='refresh',day=day,restart=restart))
  if ok:
   new=orders(window(rows,day,day+1),i);q.extend(new);shadow.extend(new)
 z=account(q,c,19*D-1,ck);ck('partition',len(q)==len(z['accepted'])+len(z['blocked']));ck('nonnegative',all(F(x[3])>=0 for x in z['events']));return dict(events=events,reviews=reviews,account=z,orders=q)

def fixture(case):
 rows=[]
 for day in range(5,19):
  for j in range(4):
   x=7*(j%2);t=day*D+[9*3600,11*3600,13*3600,15*3600][j];sign=1 if x else -1
   if case in ('reversal','failed_readmit','second_stop','unknown_monitor') and day>=11:sign=-sign
   if case=='failed_readmit' and day>=15:sign=-sign
   if case=='second_stop' and day>=17:sign=-sign
   labels={h:dict(horizon=h,gross=str(F(sign*80,10000) if h==60 and case!='null' else F(0)),mature=t+300+h*60) for h in HS}
   if case=='unknown_monitor' and day>=11 and j==3:labels[60]=dict(horizon=60,gross=None,mature=None)
   rows.append(dict(key=(day,j,A['SYMS'][0]),t=t,states=dict(base=0,context=x,hybrid=0),labels=labels))
 return rows

def run():
 checks=Counter();out=[]
 def ck(k,b):
  if not b:raise AssertionError(k)
  checks[k]+=1
 for case in PLAN['cases']:
  rows=fixture(case)
  for c in PLAN['fees']:
   for mode in PLAN['modes']:
    z=simulate(rows,c,mode,ck);ev=z['events'];q=z['orders'];ac=z['account'];stops=[e['day'] for e in ev if e['kind']=='stop'];refresh=[e for e in ev if e['kind']=='refresh'];readmit=[e for e in ev if e['kind']=='readmit'];ck('one_refresh',len(refresh)<=1 and len(readmit)<=1);ck('pause',all(not e['day']<=k[0]<e['restart'] for e in refresh for k,*_ in q));ck('no_orders_after_terminal_stop',all(k[0]<stops[-1] for k,*_ in q) if stops and (not refresh or stops[-1]!=refresh[0]['day']) else True)
    # At each day boundary redact every not-yet-received label, then replay only the past.
    for day in range(10,19):
     cut=day*D;pre=[dict(r,labels={h:l if ready(l,cut) else dict(l,gross=None,mature=None) for h,l in r['labels'].items()}) for r in rows if r['key'][0]<day]
     # No future features: current day's action is intentionally excluded from this comparison.
     v=simulate(pre,c,mode,ck);ck('decision_prefix',[e for e in ev if e['day']<=day]==[e for e in v['events'] if e['day']<=day]);ck('monitor_prefix',[e for e in z['reviews'] if e['day']<=day]==[e for e in v['reviews'] if e['day']<=day]);ck('cash_prefix',[e for e in ac['events'] if e[2]<cut]==[e for e in v['account']['events'] if e[2]<cut])
    ck('initial_expected',ev[0]['admit']==(case!='null'));ck('stable_no_stop',not stops if case in ('stable','null') or mode=='FROZEN' else True)
    if case=='reversal' and mode=='REFRESH':ck('reversal_requal',stops==[12] and readmit[0]['day']==17 and readmit[0]['admit'] and readmit[0]['candidate']!=ev[0]['candidate'])
    if case=='failed_readmit' and mode=='REFRESH':ck('failed_readmit',len(readmit)==1 and not readmit[0]['admit'] and all(k[0]<12 for k,*_ in q))
    if case=='second_stop' and mode=='REFRESH':ck('second_terminal',stops==[12,18] and len(refresh)==1)
    if case=='unknown_monitor' and mode!='FROZEN':ck('unknown_not_negative',not stops and ac['unresolved']>0 and ac['net'] is None)
    out.append(dict(case=case,fee=c,mode=mode,events=ev,reviews=z['reviews'],intents=len(q),accepted=len(ac['accepted']),blocked=len(ac['blocked']),net=ac['net'],unresolved=ac['unresolved'],reserved=ac['reserved']))
 return dict(plan=PLAN,checks=dict(checks),passed=sum(checks.values()),cases=out)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan-only',action='store_true');p.add_argument('--output',required=True);a=p.parse_args();z=PLAN if a.plan_only else run()
 with open(a.output,'x') as f:json.dump(z,f,indent=2,sort_keys=True);f.write('\n')
