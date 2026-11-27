"""R153: configured offline synthetic lifecycle; no live prices or orders."""
import hashlib,json,runpy,random,tempfile
from pathlib import Path
from fractions import Fraction as F
from collections import Counter,namedtuple
from statistics import median
from datetime import date,timedelta
P=Path(__file__).with_name('Chappy_Trading_CSV_Input_Guard_v0.1.py')
SHA='c4a4ad009a8c4cf87c2fce344525bf8dc1d38971a4d734ac1fa2bdd46d4fe0ec'
if hashlib.sha256(P.read_bytes()).hexdigest()!=SHA:raise ValueError('dependency hash')
G=runpy.run_path(str(P)); L=G['L']; R=L['R']; B=L['B']; V=L['V']; T=L['T']; M=L['M']; end=L['end']; N=100000; INITIAL=200000
class Config(namedtuple('ConfigBase','days symbols train audit')):
 __slots__=()
 def __new__(cls,days,symbols,train=4,audit=3):
  if not all(type(v) is int for v in (days,train,audit)) or min(train,audit)<1 or 5+train+audit>=days:raise ValueError('periods')
  if not isinstance(symbols,tuple) or not symbols or any(not isinstance(s,str) or not s for s in symbols) or tuple(sorted(set(symbols)))!=symbols:raise ValueError('symbols')
  return super().__new__(cls,days,symbols,train,audit)
 @property
 def active(self):return 5+self.train+self.audit
 @property
 def delay(self):return self.train+self.audit
OLD=Config(32,('X','Y')); NEW=Config(19,tuple(G['SYMS']),3,2)
PLAN=dict(dependency=SHA,old=OLD._asdict(),new=NEW._asdict(),regression_seeds=[153000],new_seeds=list(range(153001,153005)),cases=['stable','reversal','null','missing'],fees=[20,40],modes=['FROZEN','STOP','REFRESH'],scope='artificial normalized CSV; shorter train/audit for fixture only, not optimized',capital='fixed 100000/full collateral plus fee, initial 200000, observation fee zero')
def fixture(seed,case,cfg):
 rng=random.Random(seed); rows=[]; vols={}
 for sym in cfg.symbols:
  for d in range(cfg.days):
   c=10000; changes={}
   for lo,hi in R['PLAN']['segments']:
    for s in range(lo,hi+1):
     o=c;c+=rng.choice([-30,-15,0,15,30]);v=100
     if s in R['PLAN']['signals']:
      v=400 if rng.random()<.25 else 100;vols[sym,d,s]=v
      if d>=5:
       bit=v>=2*median([vols[sym,i,s] for i in range(d-5,d)])
       sign=1 if bit else -1
       if case=='reversal' and d>=cfg.active:sign=-sign
       if case=='null':sign=rng.choice([-1,1])
       elif rng.random()<.1:sign=-sign
       changes[s+3]=sign*rng.choice([70,100,150])
     if s in changes:c=entry+changes[s]
     if s-1 in R['PLAN']['signals']:entry=c
     delay=600 if case=='missing' and d>=cfg.active and rng.random()<.10 else 0
     if case=='missing' and d>=cfg.active and rng.random()<.04:continue
     rows.append(B['row'](d,s,v,received=end(d,s)+delay,symbol=sym,o=o,h=max(o,c)+5,l=min(o,c)-5,c=c))
 return rows

def records(rows,cfg):
 idx=R['validate'](rows);out=[]
 if any(not 0<=r['day']<cfg.days or r['symbol'] not in cfg.symbols for r in rows):raise ValueError('record outside config')
 for d in range(5,cfg.days):
  for s in R['PLAN']['signals']:
   for sym in cfg.symbols:
    z=R['freeze'](rows,d,s,sym);out.append((z,R['label'](z,idx,end(cfg.days,0))))
 return out

def ready(l,t):return l['mature'] is not None and l['mature']<t

def choose(rs,start,c,cfg,reference=False):
 a=start+cfg.train;b=a+cfg.audit
 samples=[(d['state'],F(l['gross'])*10000) for d,l in rs if start<=d['day']<a and ready(l,end(a,0))]
 if reference:
  scores=[V['score'](samples,t,c,False) for t in T];j=scores.index(max(scores))
  selected=[(d,l) for d,l in rs if a<=d['day']<b and d['state'] is not None and T[j][d['state']]]
  ok=bool(selected) and all(ready(l,end(b,0)) for d,l in selected) and sum(T[j][d['state']]*F(l['gross'])*10000-c for d,l in selected)>0
 else:
  j=V['select'](samples,c,False); ar=eligible(rs,j,a,b); vals=[v*F(l['gross'])*10000-c for d,l,v in ar if ready(l,end(b,0))];ok=bool(ar and len(vals)==len(ar) and sum(vals)>0)
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

def simulate(rs,c,mode,cfg):
 j,ok=choose(rs,5,c,cfg);events=[('initial',cfg.active,j,ok)];orders=[];reviews=[];start=cfg.active;restart=None;used=False
 for day in range(cfg.active,cfg.days):
  if restart==day:
   j,ok=choose(rs,day-cfg.delay,c,cfg);events.append(('readmit',day,j,ok));start=day
  if ok and mode!='FROZEN':
   z=monitor(rs,j,start,day,c);reviews.append((day,z))
   if z is not None and z[0]:
    ok=False;events.append(('stop',day,j,True))
    if mode=='REFRESH' and not used and day+cfg.delay<cfg.days:restart=day+cfg.delay;used=True;events.append(('refresh',day,j,True))
  if ok:orders.extend(order(d,l,a) for d,l,a in eligible(rs,j,day,day+1))
 return events,orders,reviews

def oracle(rs,c,mode,cfg):
 j,ok=choose(rs,5,c,cfg,True);events=[('initial',cfg.active,j,ok)];orders=[];reviews=[];start=cfg.active
 for gen in range(2):
  if not ok:break
  stop=cfg.days
  if mode!='FROZEN':
   for day in range(start,cfg.days):
    z=monitor(rs,j,start,day,c,True);reviews.append((day,z))
    if z is not None and z[0]:stop=day;break
  orders.extend(order(d,l,a) for d,l,a in eligible(rs,j,start,stop))
  if stop==cfg.days:break
  events.append(('stop',stop,j,True))
  if mode!='REFRESH' or gen or stop+cfg.delay>=cfg.days:break
  events.append(('refresh',stop,j,True));start=stop+cfg.delay;j,ok=choose(rs,stop,c,cfg,True);events.append(('readmit',start,j,ok))
 return events,orders,reviews
def settle(orders,c,cfg,initial=INITIAL):
 fee=F(c*10);cash=F(initial);pending=[];accepted=[];blocked=[];gross=F(0); fees=F(0);events=[]
 def release(t):
  nonlocal cash,gross,pending
  for k,m,g in sorted(pending,key=lambda x:(x[1] is None,x[1] or 0,x[0])):
   if m is not None and m<t:
    cash+=N+g;gross+=g;events.append(('settle',k,m,str(cash)))
  pending=[(k,m,g) for k,m,g in pending if m is None or m>=t]
 for k,t,a,l in sorted(orders,key=lambda z:(z[1],z[0])):
  release(t)
  if cash<N+fee:blocked.append(k);continue
  cash-=N+fee;fees+=fee;accepted.append(k);events.append(('reserve',k,t,str(cash)))
  g=None if l['gross'] is None else a*F(l['gross'])*N
  if g is not None and abs(g)>N:raise ValueError('outside bounded synthetic collateral model')
  pending.append((k,l['mature'],g))
 release(end(cfg.days,0)+1)
 return dict(accepted=accepted,blocked=blocked,cash=str(cash),reserved=len(pending)*N,unresolved=len(pending),gross=str(gross),fees=str(fees),net=None if pending else str(cash-initial),events=events)

def cash_ref(orders,c,cfg,initial=INITIAL):
 taken=[]; blocked=[];fee=F(c*10)
 for k,t,a,l in sorted(orders,key=lambda z:(z[1],z[0])):
  old=[z for z in taken if z[3]['mature'] is not None and z[3]['mature']<t]
  cash=initial-len(taken)*(N+fee)+sum(N+z[2]*F(z[3]['gross'])*N for z in old)
  if cash>=N+fee:taken.append((k,t,a,l))
  else:blocked.append(k)
 old=[z for z in taken if z[3]['mature'] is not None and z[3]['mature']<=end(cfg.days,0)]
 gross=sum((z[2]*F(z[3]['gross'])*N for z in old),F(0));un=len(taken)-len(old);fees=fee*len(taken);cash=initial-un*N+gross-fees
 return dict(accepted=[z[0] for z in taken],blocked=blocked,cash=str(cash),reserved=un*N,unresolved=un,gross=str(gross),fees=str(fees),net=None if un else str(cash-initial))

def study():
 checks=Counter();report={}; dates=[str(date(2026,10,26)+timedelta(days=i)) for i in range(30) if (date(2026,10,26)+timedelta(days=i)).weekday()<5 and str(date(2026,10,26)+timedelta(days=i)) not in ('2026-11-06','2026-11-03','2026-11-23')]
 def ck(k,x):
  if not x:raise AssertionError(k)
  checks[k]+=1
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp)/'artificial.csv'
  for case in PLAN['cases']:
   for seed in PLAN['regression_seeds']:
    rows=fixture(seed,case,OLD);ck('old_fixture',rows==L['fixture'](seed,case));rs=records(rows,OLD);ck('old_records',rs==L['records'](rows))
    for c in PLAN['fees']:
     for mode in PLAN['modes']:
      z=simulate(rs,c,mode,OLD);ck('old_lifecycle',z==L['simulate'](rs,c,mode));ck('old_capital',settle(z[1],c,OLD)==L['settle'](z[1],c))
   totals={(c,m):Counter() for c in PLAN['fees'] for m in PLAN['modes']};nets={k:F(0) for k in totals};coverage=Counter()
   for seed in PLAN['new_seeds']:
    rows=fixture(seed,case,NEW);raw=G['encode'](rows,dates);p.write_bytes(raw);m=G['manifest'](raw,dates,list(NEW.symbols),'known_development');m['source']='SYNTHETIC VALUES ONLY; historical schema test';rr,q=G['load'](p,m);coverage.update(rows=q['rows'],missing=q['missing']);ck('csv_coverage',q['rows']+q['missing']==NEW.days*len(NEW.symbols)*24)
    rs=records(rr,NEW);original=records(rows,NEW);ck('record_count',len(rs)==(NEW.days-5)*4*len(NEW.symbols));
    for (d,l),(a,b) in zip(rs,original):
     ck('csv_record',{k:v for k,v in d.items() if k!='feature_sha'}=={k:v for k,v in a.items() if k!='feature_sha'} and l==b)
     x,mom,g=R['oracle'](rr,d['day'],d['slot'],d['symbol'],end(NEW.days,0));ck('input_oracle',x==d['state'] and (x is None or mom==d['momentum']) and g==(None if l['gross'] is None else (l['gross'],l['mature'])))
    for c in PLAN['fees']:
     for mode in PLAN['modes']:
      ev,o,re=simulate(rs,c,mode,NEW);ck('lifecycle_oracle',(ev,o,re)==oracle(rs,c,mode,NEW));z=settle(o,c,NEW);ck('cash_oracle',{k:v for k,v in z.items() if k!='events'}==cash_ref(o,c,NEW));ck('conservation',F(z['cash'])+z['reserved']==INITIAL+F(z['gross'])-F(z['fees']));ck('partition',len(o)==len(z['accepted'])+len(z['blocked']));ck('nonnegative',all(F(e[3])>=0 for e in z['events']));ck('refresh_bound',sum(e[0]=='refresh' for e in ev)<=1)
      cut=end(NEW.active+3,0);masked=[(d,dict(l,gross=None,mature=None)) if not ready(l,cut) else (d,l) for d,l in rs];ee,oo,_=simulate(masked,c,mode,NEW);ck('event_prefix',[e for e in ev if end(e[1],0)<cut]==[e for e in ee if end(e[1],0)<cut]);ck('intent_prefix',[(k,t,a) for k,t,a,l in o if t<cut]==[(k,t,a) for k,t,a,l in oo if t<cut]);zz=settle(oo,c,NEW);ck('cash_prefix',[e for e in z['events'] if e[2]<cut]==[e for e in zz['events'] if e[2]<cut]);
      totals[c,mode].update(initial_admit=int(ev[0][3]),stops=sum(e[0]=='stop' for e in ev),refreshes=sum(e[0]=='refresh' for e in ev),readmits=sum(e[0]=='readmit' and e[3] for e in ev),accepted=len(z['accepted']),blocked=len(z['blocked']),unresolved=z['unresolved'],complete=int(z['net'] is not None));nets[c,mode]+=F(z['gross'])-F(z['fees'])
   report[case]=dict(coverage=coverage,modes={f'{c}:{mode}':dict(q,mean_net=round(float(nets[c,mode]/len(PLAN['new_seeds'])),2) if q['complete']==len(PLAN['new_seeds']) else None) for (c,mode),q in totals.items()})
 for cfg in (OLD,NEW):
  t=end(cfg.days-1,3);k=(cfg.days-1,3,cfg.symbols[0]);cut=end(cfg.days,0)
  for delay in (0,1):
   o=[(k,t,1,dict(gross='1/100',mature=cut+delay))];z=settle(o,20,cfg);ck('terminal_cutoff',z['unresolved']==delay and (z['net'] is None)==bool(delay));ck('terminal_oracle',{k:v for k,v in z.items() if k!='events'}==cash_ref(o,20,cfg))
 for args in [(10,('X',),3,2),(19,('X','X'),3,2),(19,(),3,2),(19,('X',),0,2)]:
  try:Config(*args)
  except ValueError:ck('invalid_config',True)
  else:raise AssertionError('invalid config')
 return dict(plan=PLAN,plan_sha=R['digest'](PLAN),checks=dict(checks),passed=sum(checks.values()),report=report,limits=['synthetic 19-day six-symbol historical schema only; not real prices or authentic calendar','3/2-day training/audit for fixture only, no statistical guarantee','same synthetic slots and 5-day volume history, fixed collateral; no observation fee','no broker CSV conversion, full regression, live orders or real data'])
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2))
