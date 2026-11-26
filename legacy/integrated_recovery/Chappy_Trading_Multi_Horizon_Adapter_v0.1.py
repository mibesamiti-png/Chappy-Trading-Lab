"""R161: synthetic multi-horizon contract. No market archive access or strategy selection."""
import argparse, hashlib, json, runpy, random
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
P=Path(__file__).parent
DEP='14d2affe89176df07d784780add75d0bf08b91f96759f9d99de0f92973af0677'
src=P/'Chappy_Trading_Market_Context_Adapter_v0.1.py'
if hashlib.sha256(src.read_bytes()).hexdigest()!=DEP:raise ValueError('dependency hash')
A=runpy.run_path(str(src)); R=A['R']; C=R['C']; END=A['end']; SYMS=A['SYMS']; SEGS=A['SEGS']; HS=(10,30,60); N=100000; INITIAL=200000
SCHEDULE=tuple(R['signals']); COMMON=tuple(s for s in SCHEDULE if any(a<=s-3 and s+13<b for a,b in SEGS))
PLAN=dict(round=161,dependency=DEP,horizons=HS,schedule=SCHEDULE,common=COMMON,days=8,seeds=list(range(161000,161004)),cases=['complete','delay','missing','zero'],fees=[20,40],entry='next close',exit='entry + horizon minutes',maturity='max path receipt; learning and cash release strictly after maturity',capital=INITIAL,notional=N,scope='artificial fixture only; no candidate search',allocation='one active contract per symbol; same-time symbol sort; full collateral plus fee; no observation fee')
def supported(s,h):
 if h not in HS or s not in SCHEDULE:raise ValueError('unsupported request')
 return any(a<=s-3 and s+1+h//5<b for a,b in SEGS)
def label(idx,z,h,cut):
 sym,d,s=z['symbol'],z['day'],z['slot']; out=dict(horizon=h,gross=None,direction=None,mature=None,reason='session_boundary')
 if not supported(s,h):return out
 if z['state'] is None:return dict(out,reason='feature_unavailable')
 w=[idx.get((sym,d,j)) for j in range(s+1,s+2+h//5)]
 if any(x is None or not END(d,j)<=x['received']<=cut for j,x in zip(range(s+1,s+2+h//5),w)):return dict(out,reason='unresolved')
 if any(x['volume']<=0 or x['close']<=0 for x in w):return dict(out,reason='invalid_path')
 g=F(w[-1]['close'],w[0]['close'])-1
 return dict(horizon=h,gross=str(g),direction=(g>0)-(g<0),mature=max(x['received'] for x in w),reason='mature')
def reference(idx,z,h,cut):
 sym,d,s=z['symbol'],z['day'],z['slot']; e=s+1+h//5
 if e>=(28 if s<28 else 63):return ('session_boundary',None,None)
 if z['state'] is None:return ('feature_unavailable',None,None)
 rec=[]
 for j in range(s+1,e+1):
  x=idx.get((sym,d,j))
  if x is None or x['received']>cut or x['received']<END(d,j):return ('unresolved',None,None)
  rec.append(x)
 if min(x['volume'] for x in rec)<=0 or min(x['close'] for x in rec)<=0:return ('invalid_path',None,None)
 return ('mature',str(F(rec[-1]['close']-rec[0]['close'],rec[0]['close'])),max(x['received'] for x in rec))
def settle(orders,c,terminal,initial=INITIAL):
 fee=F(N*c,10000);cash=F(initial);pending={};seen=set();accepted=[];blocked=[];events=[];gross=F(0)
 def release(t):
  nonlocal cash,gross
  for sym,(k,m,g) in sorted(list(pending.items()),key=lambda x:(x[1][1] is None,x[1][1] or 0,x[1][0])):
   if m is not None and m<t:
    cash+=N+g;gross+=g;events.append(('settle',k,m,str(cash)));del pending[sym]
 for k,t,a,l in sorted(orders,key=lambda x:(x[1],x[0])):
  if k in seen or a not in (-1,1) or t>=terminal:raise ValueError('invalid order')
  seen.add(k);sym=k[2];release(t)
  if sym in pending or cash<N+fee:blocked.append((k,'symbol_busy' if sym in pending else 'cash'));continue
  g=None if l['gross'] is None else a*F(l['gross'])*N;m=l['mature']
  if (g is None)!=(m is None) or (m is not None and (m<=t or abs(g)>N)):raise ValueError('invalid label')
  cash-=N+fee;accepted.append(k);events.append(('reserve',k,t,str(cash)));pending[sym]=(k,m,g)
 release(terminal+1);fees=fee*len(accepted)
 return dict(accepted=accepted,blocked=blocked,cash=str(cash),reserved=N*len(pending),gross=str(gross),fees=str(fees),net=None if pending else str(cash-initial),unresolved=len(pending),events=events)
def cash_ref(orders,c,terminal,initial=INITIAL):
 fee=F(N*c,10000);taken=[];blocked=[]
 for q in sorted(orders,key=lambda x:(x[1],x[0])):
  k,t,a,l=q;done=[x for x in taken if x[3]['mature'] is not None and x[3]['mature']<t];active=[x for x in taken if x not in done]
  bal=initial-len(taken)*(N+fee)+sum(N+x[2]*F(x[3]['gross'])*N for x in done)
  if any(x[0][2]==k[2] for x in active):blocked.append((k,'symbol_busy'))
  elif bal<N+fee:blocked.append((k,'cash'))
  else:taken.append(q)
 done=[x for x in taken if x[3]['mature'] is not None and x[3]['mature']<=terminal];g=sum((x[2]*F(x[3]['gross'])*N for x in done),F(0));un=len(taken)-len(done);fees=fee*len(taken);cash=initial-un*N+g-fees
 return dict(accepted=[x[0] for x in taken],blocked=blocked,cash=str(cash),reserved=N*un,gross=str(g),fees=str(fees),net=None if un else str(cash-initial),unresolved=un)
def fixture(seed,case):
 rng=random.Random(seed);idx={}
 for sym in SYMS:
  p=100000
  for d in range(PLAN['days']):
   for s in range(63):
    o=p;p+=rng.choice([-200,-100,0,100,200]);v=rng.choice([100,200,400]);t=END(d,s)
    if d>=5 and case=='missing' and rng.random()<.035:continue
    if d>=5 and case=='zero' and rng.random()<.035:v=0
    if d>=5 and case=='delay' and rng.random()<.10:t+=rng.choice([300,1200,3600])
    idx[sym,d,s]=dict(open=o,high=max(o,p)+1,low=min(o,p)-1,close=p,volume=v,received=t,actual_start=f'{d}:{s}')
 return idx
def report():
 checks=Counter();summary={};terminal=PLAN['days']*86400
 def ck(k,b):
  if not b:raise AssertionError(k)
  checks[k]+=1
 for case in PLAN['cases']:
  cov={str(h):Counter() for h in HS};accounts={f'{c}:{h}':Counter() for c in PLAN['fees'] for h in HS}
  for seed in PLAN['seeds']:
   idx=fixture(seed,case);orders={h:[] for h in HS}
   for d in range(5,PLAN['days']):
    for s in SCHEDULE:
     for sym in SYMS:
      t=END(d,s)
      # R157 requires current row; gate it and use only received prefix with scheduled clock.
      pre={k:v for k,v in idx.items() if v['received']<=t and END(k[1],k[2])<=t} if (sym,d,s) in idx and idx[sym,d,s]['received']<=t else {}
      z=R['freeze'](pre,sym,d,s) if (sym,d,s) in pre else dict(symbol=sym,day=d,slot=s,decision=t,state=None,momentum=0)
      ck('decision_clock',z['decision']==t)
      for h in HS:
       l=label(idx,z,h,terminal);ck('label_oracle',(l['reason'],l['gross'],l['mature'])==reference(idx,z,h,terminal));ck('schedule',supported(s,h)==(l['reason']!='session_boundary'))
       if h==10 and z['state'] is not None:
        old=R['label'](idx,z,terminal);ck('old_label',(old['gross'],old['mature'])==(l['gross'],l['mature']))
       if l['mature'] is not None:
        m=l['mature'];ck('before_receipt',label(idx,z,h,m-1)['gross'] is None);ck('at_receipt',label(idx,z,h,m)==l);ck('strict_learning',not C['ready'](l,m) and C['ready'](l,m+1));ck('duration',END(d,s+1+h//5)-END(d,s+1)==h*60)
       if s in COMMON:
        cov[str(h)][l['reason']]+=1
        if z['state'] is not None and z['momentum']:
         orders[h].append(((d,s,sym),t,z['momentum'],l))
   ck('common_intent_identity',all([q[:3] for q in orders[h]]==[q[:3] for q in orders[10]] for h in HS))
   for c in PLAN['fees']:
    for h in HS:
     q=orders[h];z=settle(q,c,terminal);ck('cash_oracle',{k:v for k,v in z.items() if k!='events'}==cash_ref(q,c,terminal));ck('accounting',F(z['cash'])+z['reserved']==INITIAL+F(z['gross'])-F(z['fees']));ck('partition',len(q)==len(z['accepted'])+len(z['blocked']));ck('nonnegative',all(F(x[3])>=0 for x in z['events']))
     cut=6*86400+10*3600;masked=[(k,t,a,dict(l,gross=None,mature=None)) if l['mature'] is not None and l['mature']>=cut else (k,t,a,l) for k,t,a,l in q if t<cut];p=settle(masked,c,cut);ck('cash_prefix',[x for x in z['events'] if x[2]<cut]==[x for x in p['events'] if x[2]<cut]);ck('acceptance_prefix',p['accepted']==[x for x in z['accepted'] if any(k==x and t<cut for k,t,a,l in q)])
     a=accounts[f'{c}:{h}'];a['intents']+=len(q);a['accepted']+=len(z['accepted']);a['cash_blocked']+=sum(r=='cash' for k,r in z['blocked']);a['symbol_busy']+=sum(r=='symbol_busy' for k,r in z['blocked']);a['unresolved']+=z['unresolved'];a['known_accounts']+=z['net'] is not None
  summary[case]=dict(coverage={k:dict(v) for k,v in cov.items()},accounts={k:dict(v) for k,v in accounts.items()})
 # Explicit path and exact-time capital fixtures.
 idx=fixture(161000,'complete');sym=SYMS[0];d=5;s=COMMON[0];z=dict(symbol=sym,day=d,slot=s,state=1);base=[label(idx,z,h,terminal) for h in HS];q=dict(idx);del q[sym,d,s+10];ck('short_survives_long_missing',label(q,z,10,terminal)==base[0] and label(q,z,60,terminal)['gross'] is None)
 q=dict(idx);q[sym,d,s+2]=dict(q[sym,d,s+2],received=END(d,s+13)+600);ck('late_middle_receipt',label(q,z,60,terminal)['mature']==END(d,s+13)+600)
 l=dict(gross='0',mature=20);u=dict(gross=None,mature=None);o=[((0,0,sym),10,1,l),((0,1,sym),20,1,l|{'mature':30}),((0,2,SYMS[1]),20,1,l|{'mature':30}),((0,3,SYMS[1]),21,1,u)]
 a=settle(o,20,100);ck('same_receipt_no_release',a['blocked']==[(o[1][0],'symbol_busy'),(o[2][0],'cash')]);ck('unknown_reserved',a['reserved']==N and a['net'] is None);ck('dedicated_oracle',{k:v for k,v in a.items() if k!='events'}==cash_ref(o,20,100))
 # Unchanged existing settlement on a fixture where symbol locking never changes outcome.
 cfg=C['cfg'] if 'cfg' in C else R['cfg'];o=[((5,0,sym),END(5,0),1,dict(gross='1/100',mature=END(5,3))),((5,4,SYMS[1]),END(5,4),-1,dict(gross='-1/100',mature=END(5,7)))];a=settle(o,20,terminal);b=C['settle'](o,20,cfg);ck('legacy_cash',all(a[k]==b[k] for k in ('accepted','cash','reserved','gross','fees','net','unresolved')))
 return dict(plan=PLAN,plan_sha=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest(),checks=dict(checks),passed=sum(checks.values()),summary=summary,limits=['artificial prices only; no profit comparison or candidate search','common structural schedule does not depend on future data','label requires complete positive-volume path; unknown capital remains reserved','full collateral proxy at decision, no actual fills, no observation fee','same-symbol lock is explicit conservative addition; no portfolio optimization'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--plan-only',action='store_true');a=p.parse_args();r=PLAN if a.plan_only else report()
 with open(a.output,'x') as f:json.dump(r,f,sort_keys=True,indent=2);f.write('\n')
