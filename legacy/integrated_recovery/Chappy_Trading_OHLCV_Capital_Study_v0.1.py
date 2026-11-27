"""R150: regression of learned rules through OHLCV and reserved cash; synthetic only."""
import hashlib,json,runpy,random
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
from statistics import median
P=Path(__file__).with_name('Chappy_Trading_Variable_Payoff_Core_Study_v0.1.py')
SHA='a5a4d5189f338382e67c1ff572daf4dfabc9a8ca308cdfdec78937a459492103'
if hashlib.sha256(P.read_bytes()).hexdigest()!=SHA:raise ValueError('R149 hash')
V=runpy.run_path(str(P)); R=V['R']; B=R['B']; T=V['T']; end=R['end']; N=100000; INITIAL=200000
PLAN=dict(dependency=SHA,synthetic_only=True,seeds=list(range(150000,150012)),cases=['stable','reversal','null','missing'],days=16,train=[5,9],audit=[9,12],evaluation=[12,16],cost_bps=[20,40],modes=list(V['MODES']),notional=N,initial=INITIAL,observation_cost=0,capital='reserve full notional plus fee at intent; settle after result receipt; unknown remains reserved; canonical symbol order for ties',rule='volume bit determines future signed variable magnitude; reversal only evaluation; null independent sign; hidden from learner')
def fixture(seed,case):
 rng=random.Random(seed); rows=[]; vols={}
 for sym in R['PLAN']['symbols']:
  for d in range(16):
   c=10000; changes={}
   for lo,hi in R['PLAN']['segments']:
    for s in range(lo,hi+1):
     o=c;c+=rng.choice([-30,-15,0,15,30]);v=100
     if s in R['PLAN']['signals']:
      v=400 if rng.random()<.25 else 100
      vols[sym,d,s]=v
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
 idx=R['validate'](rows); out=[]
 for d in range(5,16):
  for s in R['PLAN']['signals']:
   for sym in R['PLAN']['symbols']:
    z=R['freeze'](rows,d,s,sym);out.append((z,R['label'](z,idx,end(16,0))))
 return out

def actions(rs,c):
 samples=[(d['state'],F(l['gross'])*10000) for d,l in rs if d['day']<9 and l['mature'] is not None and l['mature']<end(9,0)]
 h=V['select'](samples,c,True);p=V['select'](samples,c,False)
 # R149's fixed audit-day interface: remap day field only, retaining absolute timestamps.
 ar=[(dict(d,day=6),l) for d,l in rs if 9<=d['day']<12]
 a=V['audit'](ar,p,c,end(12,0));out={m:[] for m in V['MODES']}
 for d,l in rs:
  if d['day']<12:continue
  x=d['state']; mom=d['momentum'] if x is not None else 0
  vals=[0,mom,-mom,T[h][x] if x is not None else 0,T[p][x] if x is not None else 0,T[p][x] if x is not None and a['pass_point'] else 0]
  for m,v in zip(V['MODES'],vals):
   if v:out[m].append(((d['day'],d['slot'],d['symbol']),d['decision'],v,l))
 return h,p,a,samples,out

def settle(orders,c,initial=INITIAL):
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
 release(end(16,0)+1)
 return dict(accepted=accepted,blocked=blocked,cash=str(cash),reserved=len(pending)*N,unresolved=len(pending),gross=str(gross),fees=str(fees),net=None if pending else str(cash-initial),events=events)

def oracle(orders,c,initial=INITIAL):
 taken=[]; blocked=[];fee=F(c*10)
 for k,t,a,l in sorted(orders,key=lambda z:(z[1],z[0])):
  old=[z for z in taken if z[3]['mature'] is not None and z[3]['mature']<t]
  cash=initial-len(taken)*(N+fee)+sum(N+z[2]*F(z[3]['gross'])*N for z in old)
  if cash>=N+fee:taken.append((k,t,a,l))
  else:blocked.append(k)
 old=[z for z in taken if z[3]['mature'] is not None and z[3]['mature']<=end(16,0)]
 gross=sum((z[2]*F(z[3]['gross'])*N for z in old),F(0));un=len(taken)-len(old);fees=fee*len(taken);cash=initial-un*N+gross-fees
 return dict(accepted=[z[0] for z in taken],blocked=blocked,cash=str(cash),reserved=un*N,unresolved=un,gross=str(gross),fees=str(fees),net=None if un else str(cash-initial))

def study():
 checks=Counter();report={}
 def ck(k,ok):
  if not ok:raise AssertionError(k)
  checks[k]+=1
 for case in PLAN['cases']:
  totals={str(c):{m:Counter() for m in V['MODES']} for c in PLAN['cost_bps']}; sums={str(c):{m:F(0) for m in V['MODES']} for c in PLAN['cost_bps']}; diag=Counter()
  for seed in PLAN['seeds']:
   rows=fixture(seed,case);rs=records(rows)
   for d,l in rs:
    state,mom,g=R['oracle'](rows,d['day'],d['slot'],d['symbol'],end(16,0));ck('input_oracle',d['state']==state and (state is None or d['momentum']==mom) and g==(None if l['gross'] is None else (l['gross'],l['mature'])))
   for c in PLAN['cost_bps']:
    h,p,a,samples,acts=actions(rs,c);diag[f'{c}_audit_pass']+=a['pass_point'];diag[f'{c}_train_n']+=len(samples)
    for hit,j in [(True,h),(False,p)]:
     vals=[V['score'](samples,t,c,hit) for t in T];ck('selection_oracle',j==vals.index(max(vals)))
    masked=[(d,dict(l,gross=None,mature=None)) if d['day']>=12 else (d,l) for d,l in rs];hh,pp,aa,_,ac=actions(masked,c);ck('evaluation_blind',(h,p,a)==(hh,pp,aa) and all([(k,t,v) for k,t,v,l in acts[m]]==[(k,t,v) for k,t,v,l in ac[m]] for m in acts))
    for m,orders in acts.items():
     z=settle(orders,c);q=oracle(orders,c);ck('cash_oracle',{k:v for k,v in z.items() if k!='events'}==q);ck('conservation',F(z['cash'])+z['reserved']==INITIAL+F(z['gross'])-F(z['fees']));ck('nonnegative',all(F(e[3])>=0 for e in z['events']));ck('partition',len(z['accepted'])+len(z['blocked'])==len(orders));ck('audit_authority',m!='PAY_AUDIT' or a['pass_point'] or not orders)
     cut=end(14,0);future=[(k,t,v,dict(l,gross=None,mature=None)) if l['mature'] is None or l['mature']>=cut else (k,t,v,l) for k,t,v,l in orders];zz=settle(future,c);ck('capital_prefix',[e for e in z['events'] if e[2]<cut]==[e for e in zz['events'] if e[2]<cut]);
     cc=totals[str(c)][m];cc.update(dict(intents=len(orders),accepted=len(z['accepted']),blocked=len(z['blocked']),unresolved=z['unresolved'],complete_runs=int(z['net'] is not None)));sums[str(c)][m]+=F(z['gross'])-F(z['fees'])
  report[case]=dict(diag=dict(diag),modes={c:{m:dict(totals[c][m],recognized_net_yen=round(float(sums[c][m]),2),mean_final_net_yen=round(float(sums[c][m]/len(PLAN['seeds'])),2) if totals[c][m]['complete_runs']==len(PLAN['seeds']) else None) for m in V['MODES']} for c in totals})
 # Same time, one collateral; unknown result keeps capital locked; later receipt not used before arrival.
 t=end(12,3);l=dict(gross='1/100',mature=t+900);u=dict(gross=None,mature=None);orders=[((12,3,'X'),t,1,l),((12,3,'Y'),t,1,l),((12,6,'X'),t+900,1,u),((12,23,'X'),t+6000,1,l|{'mature':t+6900})]
 z=settle(orders,20);ck('same_time_capacity',z['blocked']==[(12,3,'Y'),(12,6,'X')]);ck('boundary_oracle',{k:v for k,v in z.items() if k!='events'}==oracle(orders,20));z2=settle([((12,3,'X'),t,1,u),((12,23,'X'),t+6000,1,l|{'mature':t+6900})],20);ck('unknown_locked',z2['net'] is None and z2['reserved']==N and len(z2['blocked'])==1)
 return dict(plan=PLAN,plan_sha=R['digest'](PLAN),checks=dict(checks),passed=sum(checks.values()),report=report,limits=['synthetic price paths with designed conditional returns; no real market or order execution','full collateral for either direction, fee paid at commitment, reserve at decision not actual fill','complete case realized component not total PnL when pending; no mark to market','fixed descriptive audit, not statistical certification; no refresh or observation costs'])
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2))
