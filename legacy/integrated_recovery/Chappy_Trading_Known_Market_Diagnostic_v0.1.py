'''R158: known development diagnostics only; no new strategy selection or live orders.'''
import argparse,hashlib,json,runpy
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
P=Path(__file__).parent
DEP='ec13774a49d1cf106df85ab04bbe01977d32c5058b497daacc33cb35a9eaf41d'
R157=P/'Chappy_Trading_CTRL_Evaluation_v0.1.py'
if hashlib.sha256(R157.read_bytes()).hexdigest()!=DEP:raise ValueError('dependency')
R=runpy.run_path(str(R157)); C=R['C']; T=C['T']; days=R['days']; syms=R['symbols']
PLAN=dict(dependency=DEP,archive_sha=R['I']['SHA'],split={'train':[5,8],'audit':[8,10],'evaluation':[10,19]},diagnostic_costs=[0,20,40],candidate_scope='existing 273; training scores only, no selection for deployment',reference='previously recorded RSI14 rebound: preceding RSI<30 and current close rises; Wilder smoothing, continuous observed bars including session gaps; fixed diagnostic only, not old full strategy reproduction',horizons_minutes=[10,30,60],cohorts=['R157 fixed signal schedule for 10min','all same-session decisions supporting all 3 horizons, common cohort'],notional=100000,scope='known development only; no new threshold search; event returns not capital returns')
def rsi(xs):
 out=[None]*len(xs);g=l=0.
 for i in range(1,len(xs)):
  d=xs[i]-xs[i-1];a=max(d,0);b=max(-d,0)
  if i<=14:
   g+=a/14;l+=b/14
  else:g=(13*g+a)/14;l=(13*l+b)/14
  if i>=14:out[i]=50. if g==l==0 else 100. if l==0 else 100*g/(g+l)
 return out

def report(path):
 idx,meta=R['load'](path);checks=Counter()
 def ck(k,v):
  if not v:raise AssertionError(k)
  checks[k]+=1
 rs=[]
 for d in range(5,19):
  for s in R['signals']:
   for sym in syms:
    z=R['freeze'](idx,sym,d,s);l=R['label'](idx,z,19*86400);ck('complete',z['state'] is not None and l['gross'] is not None);rs.append((z,l))
 train=[(z['state'],F(l['gross'])*10000) for z,l in rs if 5<=z['day']<8]
 states=[]
 for s in range(8):
  v=[g for x,g in train if x==s];states.append(dict(state=s,count=len(v),gross_mean_bps=None if not v else float(sum(v)/len(v)),abs_mean_bps=None if not v else float(sum(map(abs,v))/len(v)),up=sum(g>0 for g in v),down=sum(g<0 for g in v),flat=sum(g==0 for g in v)))
 score={};previous=None
 for c in PLAN['diagnostic_costs']:
  a=[]
  for j,t in enumerate(T):
   vals=[t[x]*g for x,g in train if t[x]];gross=sum(vals,F(0));net=gross-c*len(vals);ck('score_oracle',C['V']['score'](train,t,c,False)==net);a.append((net,j,len(vals),gross))
  ck('cost_monotonic',previous is None or all(x[0]<=y[0] for x,y in zip(a,previous)));previous=a
  best=max(a,key=lambda x:x[0]);trading=[q for q in a if q[2]];bt=max(trading,key=lambda x:x[0]);score[str(c)]=dict(positive=sum(q[0]>0 for q in a),zero=sum(q[0]==0 for q in a),active_candidates=len(trading),best_id=best[1],best_net_yen=float(best[0]*10),best_active_id=bt[1],best_active_count=bt[2],best_active_gross_yen=float(bt[3]*10),best_active_net_yen=float(bt[0]*10),selected=C['V']['select'](train,c,False))
  ck('selection',score[str(c)]['selected']==best[1])
  if c in (20,40):ck('r157_wait',C['choose'](rs,5,c,R['cfg'])==(0,False))
 # Fixed historical signal, calculate from every bar in chronological order, never future data.
 rv={}
 for sym in syms:
  xs=[idx[sym,d,s]['close'] for d in range(19) for s in range(63)];v=rsi(xs)
  for i,x in enumerate(v):
   if i>=14:
    # Prefix re-run for every scheduled or common-cohort decision below.
    ck('rsi_range',0<=x<=100)
   rv[sym,i//63,i%63]=(x,v[i-1] if i else None,xs[i]>xs[i-1] if i else False)
  for d in range(5,19):
   for s in range(63):
    i=d*63+s;ck('rsi_prefix',rsi(xs[:i+1])[-1]==v[i])
 events=[]
 for cohort,hs in [('matched',[2]),('common',[2,6,12])]:
  for d in range(5,19):
   for a,b in R['segments']:
    for s in range(a+3,b-1-max(hs)):
     if cohort=='matched' and s not in R['signals']:continue
     for sym in syms:
      cur,prev,up=rv[sym,d,s];rebound=prev is not None and prev<30 and up
      for h in hs:
       entry=idx[sym,d,s+1];exit=idx[sym,d,s+1+h];t=idx[sym,d,s]['received'];ck('causal_horizon',t<entry['received']<exit['received'] and s+1+h<b and exit['received']-entry['received']==h*300)
       g=F(exit['close']-entry['close'],entry['close'])*10000;events.append((cohort,d,sym,s,h*5,rebound,g))
 ck('matched_count',sum(e[0]=='matched' for e in events)==len(rs))
 def stats(es,c):
  if not es:return dict(n=0,mean_net_bps=None,mean_gross_bps=None,positive_days=0,days=0)
  vs=[e[-1] for e in es];by={}
  for e in es:by.setdefault(e[1],[]).append(e[-1]-c)
  return dict(n=len(es),mean_net_bps=float(sum(vs)/len(vs)-c),mean_gross_bps=float(sum(vs)/len(vs)),positive_days=sum(sum(v)>0 for v in by.values()),days=len(by))
 tables={}
 for cohort,hs in [('matched',[10]),('common',[10,30,60])]:
  for h in hs:
   for phase,(lo,hi) in PLAN['split'].items():
    es=[e for e in events if e[0]==cohort and e[4]==h and lo<=e[1]<hi];sub=[e for e in es if e[5]]
    for c in [20,40]:tables[f'{cohort}:{h}:{phase}:{c}']=dict(all=stats(es,c),rebound=stats(sub,c))
 # Exact reconciliation of the new R157 state data with stored coverage, no old performance re-selection.
 old=json.loads((P/'Trading_Round157_results.json').read_text())
 for name,(lo,hi) in PLAN['split'].items():
  part=[(z,l) for z,l in rs if lo<=z['day']<hi];ck('stored_coverage',len(part)==old['coverage'][name]['opportunities'] and dict(Counter(str(z['state']) for z,l in part))==old['coverage'][name]['states'])
 return dict(plan=PLAN,normalized_sha=meta['normalized_sha256'],states=states,scores=score,events=len(events),tables=tables,checks=dict(checks),passed=sum(checks.values()),limits=['already known data; no independent profitability evidence','RSI diagnostic definition explicit; earlier implementation unavailable, no exact old strategy reproduction','overlapping events, no shared capital or executable fills; costs fixed','no real order, no reserved dates, no new threshold search'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('--output',required=True);p.add_argument('--plan-only',action='store_true');a=p.parse_args()
 z=PLAN if a.plan_only else report(a.archive)
 with open(a.output,'x') as f:json.dump(z,f,indent=2,sort_keys=True);f.write('\n')
