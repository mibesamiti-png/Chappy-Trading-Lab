"""R151: synthetic variable-payoff lifecycle adapter; no market prices or orders."""
import hashlib,json,runpy,random,types
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
from statistics import median
ROOT=Path(__file__).parent
DEPS={'OHLCV_Capital_Study':'4583053b7c6a1cd82f9537372a43eb77adc6bce91c6b13f085446b3842108a61','Economic_Monitor_Study':'e3e830034f1e13382232ebe6d5658ff38722e36570ab0e34210ab294abe919d4'}
def load(k):
 p=ROOT/f'Chappy_Trading_{k}_v0.1.py'
 if hashlib.sha256(p.read_bytes()).hexdigest()!=DEPS[k]:raise ValueError(k+' hash')
 return runpy.run_path(str(p))
C=load('OHLCV_Capital_Study'); M=load('Economic_Monitor_Study'); V=C['V']; R=C['R']; B=C['B']; T=C['T']; end=C['end']; H=32
PLAN=dict(dependencies=DEPS,synthetic_only=True,seeds=list(range(151000,151008)),cases=['stable','reversal','null','missing'],days=H,train_days=4,audit_days=3,first_active=12,costs=[20,40],modes=['FROZEN','STOP','REFRESH'],monitor='day boundary, latest 4 eligible shadow outcomes of current active generation; all matured strictly before boundary, net<=0 stops; no statistical guarantee',refresh='one attempt: next 4 days train + 3 audit, then resume only if point audit passes; later stop terminal',capital=C['PLAN']['capital'],notional=100000,initial=200000,observation_cost=0)
# Extend R150 synthetic fixture verbatim in spirit; only horizon differs.
def fixture(seed,case):
 rng=random.Random(seed); rows=[]; vols={}
 for sym in R['PLAN']['symbols']:
  for d in range(H):
   c=10000; changes={}
   for lo,hi in R['PLAN']['segments']:
    for s in range(lo,hi+1):
     o=c;c+=rng.choice([-30,-15,0,15,30]);v=100
     if s in R['PLAN']['signals']:
      v=400 if rng.random()<.25 else 100;vols[sym,d,s]=v
      if d>=5:
       bit=v>=2*median([vols[sym,i,s] for i in range(d-5,d)])
       sign=1 if bit else -1
       if case=='reversal' and d>=12:sign=-sign
       if case=='null':sign=rng.choice([-1,1])
       elif rng.random()<.1:sign=-sign
       changes[s+3]=sign*rng.choice([70,100,150])
     if s in changes:c=entry+changes[s]
     if s-1 in R['PLAN']['signals']:entry=c
     delay=600 if case=='missing' and d>=12 and rng.random()<.10 else 0
     if case=='missing' and d>=12 and rng.random()<.04:continue
     rows.append(B['row'](d,s,v,received=end(d,s)+delay,symbol=sym,o=o,h=max(o,c)+5,l=min(o,c)-5,c=c))
 return rows

def records(rows):
 idx=R['validate'](rows);out=[]
 for d in range(5,H):
  for s in R['PLAN']['signals']:
   for sym in R['PLAN']['symbols']:
    z=R['freeze'](rows,d,s,sym);out.append((z,R['label'](z,idx,end(H,0))))
 return out

def ready(l,t):return l['mature'] is not None and l['mature']<t

def choose(rs,start,c,reference=False):
 a=start+4;b=a+3
 samples=[(d['state'],F(l['gross'])*10000) for d,l in rs if start<=d['day']<a and ready(l,end(a,0))]
 if reference:
  scores=[V['score'](samples,t,c,False) for t in T];j=scores.index(max(scores))
  selected=[(d,l) for d,l in rs if a<=d['day']<b and d['state'] is not None and T[j][d['state']]]
  ok=bool(selected) and all(ready(l,end(b,0)) for d,l in selected) and sum(T[j][d['state']]*F(l['gross'])*10000-c for d,l in selected)>0
 else:
  j=V['select'](samples,c,False); ar=[(dict(d,day=6),l) for d,l in rs if a<=d['day']<b];ok=V['audit'](ar,j,c,end(b,0))['pass_point']
 return j,bool(ok)

def eligible(rs,j,start,stop):return [(d,l,T[j][d['state']]) for d,l in rs if start<=d['day']<stop and d['state'] is not None and T[j][d['state']]]
def order(d,l,a):return ((d['day'],d['slot'],d['symbol']),d['decision'],a,l)
def monitor(rs,j,start,day,c,reference=False):
 w=eligible(rs,j,start,day)[-4:];t=end(day,0)
 if len(w)!=4 or not all(ready(l,t) for d,l,a in w):return None
 vals=[a*F(l['gross'])*10000 for d,l,a in w]
 if reference:stop=sum(vals)<=4*c
 else:
  # R82 NET formula: present four already matured eligible observations in its local clock.
  z=M['decide']('NET',6,c,[dict(index=i,received=i+3,bps=v) for i,v in enumerate(vals)])
  stop=z['action']=='WAIT'
 return (stop,tuple((d['day'],d['slot'],d['symbol']) for d,l,a in w),str(sum(vals)-4*c))

def simulate(rs,c,mode):
 j,ok=choose(rs,5,c);events=[('initial',12,j,ok)];orders=[];reviews=[];start=12;restart=None;used=False
 for day in range(12,H):
  if restart==day:
   j,ok=choose(rs,day-7,c);events.append(('readmit',day,j,ok));start=day
  if ok and mode!='FROZEN':
   z=monitor(rs,j,start,day,c);reviews.append((day,z))
   if z is not None and z[0]:
    ok=False;events.append(('stop',day,j,True))
    if mode=='REFRESH' and not used and day+7<H:restart=day+7;used=True;events.append(('refresh',day,j,True))
  if ok:orders.extend(order(d,l,a) for d,l,a in eligible(rs,j,day,day+1))
 return events,orders,reviews

def oracle(rs,c,mode):
 j,ok=choose(rs,5,c,True);events=[('initial',12,j,ok)];orders=[];reviews=[];start=12
 for gen in range(2):
  if not ok:break
  stop=H
  if mode!='FROZEN':
   for day in range(start,H):
    z=monitor(rs,j,start,day,c,True);reviews.append((day,z))
    if z is not None and z[0]:stop=day;break
  orders.extend(order(d,l,a) for d,l,a in eligible(rs,j,start,stop))
  if stop==H:break
  events.append(('stop',stop,j,True))
  if mode!='REFRESH' or gen or stop+7>=H:break
  events.append(('refresh',stop,j,True));start=stop+7;j,ok=choose(rs,stop,c,True);events.append(('readmit',start,j,ok))
 return events,orders,reviews
# Reuse the R150 cash functions; its hard-coded day-16 horizon is replaced only for the terminal cutoff.
def adapt(fn):
 g=dict(fn.__globals__);g['end']=lambda day,slot:end(H if day==16 else day,slot)
 return types.FunctionType(fn.__code__,g,fn.__name__,fn.__defaults__,fn.__closure__)
settle=adapt(C['settle']); cash_oracle=adapt(C['oracle'])
def study():
 checks=Counter();report={}
 def ck(k,x):
  if not x:raise AssertionError(k)
  checks[k]+=1
 for case in PLAN['cases']:
  totals={(c,m):Counter() for c in PLAN['costs'] for m in PLAN['modes']};nets={k:F(0) for k in totals}
  for seed in PLAN['seeds']:
   rows=fixture(seed,case);rs=records(rows)
   for d,l in rs:
    x,m,g=R['oracle'](rows,d['day'],d['slot'],d['symbol'],end(H,0));ck('input_oracle',x==d['state'] and (x is None or m==d['momentum']) and g==(None if l['gross'] is None else (l['gross'],l['mature'])))
   for c in PLAN['costs']:
    for m in PLAN['modes']:
     ev,o,re=simulate(rs,c,m);ck('lifecycle_oracle',(ev,o,re)==oracle(rs,c,m));z=settle(o,c);ck('capital_oracle',{k:v for k,v in z.items() if k!='events'}==cash_oracle(o,c));ck('conservation',F(z['cash'])+z['reserved']==C['INITIAL']+F(z['gross'])-F(z['fees']));ck('nonnegative',all(F(e[3])>=0 for e in z['events']));ck('partition',len(o)==len(z['accepted'])+len(z['blocked']));ck('one_refresh',sum(e[0]=='refresh' for e in ev)<=1)
     cut=end(20,0);masked=[(d,dict(l,gross=None,mature=None)) if not ready(l,cut) else (d,l) for d,l in rs];ee,oo,rr=simulate(masked,c,m);ck('future_events',[e for e in ev if e[1]<20]==[e for e in ee if e[1]<20]);ck('future_intents',[(k,t,a) for k,t,a,l in o if t<cut]==[(k,t,a) for k,t,a,l in oo if t<cut]);zz=settle(oo,c);ck('future_cash',[e for e in z['events'] if e[2]<cut]==[e for e in zz['events'] if e[2]<cut]);
     for day,r in re:
      if r is not None:
       ids=r[1];idx={(d['day'],d['slot'],d['symbol']):l for d,l in rs};ck('monitor_causal',len(set(ids))==4 and all(ready(idx[k],end(day,0)) for k in ids));ck('monitor_net',r[0]==(F(r[2])<=0))
     q=totals[c,m];q.update(initial_admit=int(ev[0][3]),stops=sum(e[0]=='stop' for e in ev),refreshes=sum(e[0]=='refresh' for e in ev),readmits=sum(e[0]=='readmit' and e[3] for e in ev),intents=len(o),accepted=len(z['accepted']),blocked=len(z['blocked']),unresolved=z['unresolved'],complete=int(z['net'] is not None));nets[c,m]+=F(z['gross'])-F(z['fees'])
  report[case]={f'{c}:{m}':dict(q,mean_net=round(float(nets[c,m]/len(PLAN['seeds'])),2) if q['complete']==len(PLAN['seeds']) else None,recognized_net=round(float(nets[c,m]),2)) for (c,m),q in totals.items()}
 return dict(plan=PLAN,plan_sha=R['digest'](PLAN),checks=dict(checks),passed=sum(checks.values()),report=report,limits=['point audit and four-observation net stop are descriptive, not statistically calibrated','daily boundaries and synthetic fixed horizon, one refresh; no extra fees beyond existing trades','shadow outcomes independent of fills; unknown collateral persists; no real data or orders'])
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2))
