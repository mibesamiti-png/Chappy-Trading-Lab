"""R160 causal market context adapter. Features only, no strategy or labels."""
import argparse, hashlib, json, runpy, math
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
P=Path(__file__).parent
DEP='cfbd00bfcefa91ec9bbdcf5fae9ec2f81b7d8daa1fc96a3df0255ad14fb7a589'
source=P/'Chappy_Trading_Known_Market_Diagnostic_v0.1.py'
if hashlib.sha256(source.read_bytes()).hexdigest()!=DEP: raise ValueError('dependency hash')
D=runpy.run_path(str(source)); R=D['R']; SYMS=tuple(R['symbols']); SEGS=R['segments']; DAYS=R['days']
PLAN=dict(round=160,dependency=DEP,archive_sha=R['I']['SHA'],schedule=list(R['signals']),days=[5,19],features={'rsi':'R158 Wilder14 continuous observed prefix from first available day; previous RSI<30 and current close rises','peer':'other five same-session 30min returns; full contiguous seven observed positive-volume bars per symbol; mean>0 and at least three strictly rising','relative':'target 30min return minus other-five equal-weight mean'},clock='scheduled bar end, receive <= cutoff; no waiting or future fill',unknown='missing/late/invalid history -> null for affected component; no imputation',scope='features only; existing known development archive; no candidate selection, labels, profitability or reserved dates')
def end(d,s):
 h,m,*rest=map(int,R['slots'][s].split(':'));return d*86400+h*3600+m*60+(rest[0] if rest else 0)+300

def usable(idx,sym,d,s,t):
 x=idx.get((sym,d,s));return x if x is not None and end(d,s)<=x['received']<=t and x['close']>0 and x['volume']>0 else None

def ret(idx,sym,d,s,t):
 if not any(a<=s-6 and s<b for a,b in SEGS):return None
 w=[usable(idx,sym,d,j,t) for j in range(s-6,s+1)]
 return None if any(x is None for x in w) else F(w[-1]['close']-w[0]['close'],w[0]['close'])

def observe(idx,sym,d,s,t):
 if sym not in SYMS or not 0<=d<len(DAYS) or not 0<=s<63 or t!=end(d,s):raise ValueError('invalid decision')
 # Require the complete chronological observed prefix for R158's continuous RSI definition.
 keys=[(i,j) for i in range(d+1) for j in range(63 if i<d else s+1)]
 xs=[usable(idx,sym,i,j,t) for i,j in keys]
 r=prev=rebound=None
 if len(xs)>=16 and all(x is not None for x in xs):
  closes=[x['close'] for x in xs]; rr=D['rsi'](closes);r,prev=rr[-1],rr[-2];rebound=prev<30 and closes[-1]>closes[-2]
 peers={p:ret(idx,p,d,s,t) for p in SYMS if p!=sym};own=ret(idx,sym,d,s,t)
 mean=up=condition=relative=None
 if all(x is not None for x in peers.values()):
  mean=sum(peers.values(),F(0))/len(peers);up=sum(x>0 for x in peers.values());condition=mean>0 and up>=3
  if own is not None:relative=own-mean
 return dict(symbol=sym,day=d,slot=s,cutoff=t,rsi=r,previous_rsi=prev,rebound=rebound,own30=None if own is None else str(own),peer30={p:None if v is None else str(v) for p,v in peers.items()},peer_mean=None if mean is None else str(mean),peer_up=up,peer_condition=condition,relative=None if relative is None else str(relative))

def reference(idx,sym,d,s,t):
 # Independent direct return and RSI oracle. No call to adapter helpers or R158 RSI.
 def valid(p,i,j):
  x=idx.get((p,i,j));return x is not None and end(i,j)<=x['received']<=t and x['close']>0 and x['volume']>0
 seq=[(i,j) for i in range(d+1) for j in range(63) if (i,j)<=(d,s)]
 r=pr=reb=None
 if len(seq)>=16 and all(valid(sym,i,j) for i,j in seq):
  c=[idx[sym,i,j]['close'] for i,j in seq];ds=[b-a for a,b in zip(c,c[1:])];g=sum(max(0,x) for x in ds[:14])/14;l=sum(max(0,-x) for x in ds[:14])/14
  def value(g,l):return 50. if g==l==0 else 100. if l==0 else 100-100/(1+g/l)
  r=value(g,l)
  for v in ds[14:]:
   pr=r;g=g*13/14+max(0,v)/14;l=l*13/14+max(0,-v)/14;r=value(g,l)
  reb=pr<30 and c[-1]>c[-2]
 returns={}
 for p in SYMS:
  ok=(s>=6 if s<28 else s>=34) and all(valid(p,d,j) for j in range(s-6,s+1))
  returns[p]=None if not ok else F(idx[p,d,s]['close'],idx[p,d,s-6]['close'])-1
 own=returns.pop(sym);v=list(returns.values());m=u=cond=rel=None
 if None not in v:
  m=sum(v,F(0))/5;u=len([x for x in v if x>0]);cond=m>0 and u>=3;rel=None if own is None else own-m
 return r,pr,reb,own,returns,m,u,cond,rel

def fixture():
 idx={}
 for p,sym in enumerate(SYMS):
  for d in range(2):
   for s in range(63):
    i=d*63+s;c=100000+100*p+(p-2)*i*3+(i%7)*11
    idx[sym,d,s]=dict(close=c,volume=100,received=end(d,s))
 return idx

def report(path):
 checks=Counter()
 def ck(k,v):
  if not v:raise AssertionError(k)
  checks[k]+=1
 def compare(idx,sym,d,s):
  t=end(d,s);a=observe(idx,sym,d,s,t);r,pr,reb,own,ps,m,u,cond,rel=reference(idx,sym,d,s,t)
  close=lambda x,y: x is y if x is None or y is None else math.isclose(x,y,abs_tol=1e-9)
  ck('rsi_oracle',close(a['rsi'],r) and close(a['previous_rsi'],pr) and a['rebound']==reb)
  enc=lambda x:None if x is None else str(x)
  ck('peer_oracle',a['own30']==enc(own) and a['peer30']=={p:enc(v) for p,v in ps.items()} and a['peer_mean']==enc(m) and a['peer_up']==u and a['peer_condition']==cond and a['relative']==enc(rel))
  ck('target_exclusion',set(a['peer30'])==set(SYMS)-{sym})
  ck('causal_prefix',observe({k:v for k,v in idx.items() if v['received']<=t and end(k[1],k[2])<=t},sym,d,s,t)==a)
  if a['relative'] is not None:ck('relative_identity',F(a['relative'])==F(a['own30'])-F(a['peer_mean']))
  return a
 f=fixture();sym=SYMS[0];peer=SYMS[1];d=1;s=12;t=end(d,s);base=compare(f,sym,d,s)
 ck('fixture_ready',base['relative'] is not None and base['rsi'] is not None)
 for j in (s-6,s-3,s):
  q=dict(f);del q[peer,d,j];z=compare(q,sym,d,s);ck('missing_peer',z['peer_mean'] is None and z['rsi']==base['rsi'] and z['relative'] is None)
  q=dict(f);q[peer,d,j]=dict(q[peer,d,j],received=t+1);z=compare(q,sym,d,s);ck('late_peer',z['peer_mean'] is None and z['rsi']==base['rsi'])
 q=dict(f);q[sym,0,1]=dict(q[sym,0,1],received=t+1);z=compare(q,sym,d,s);ck('late_history',z['rsi'] is None and z['peer_mean']==base['peer_mean'])
 q=dict(f);del q[sym,d,s-2];z=compare(q,sym,d,s);ck('missing_own',z['rsi'] is None and z['relative'] is None and z['peer_mean']==base['peer_mean'])
 q=dict(f);q[peer,d,s]=dict(q[peer,d,s],volume=0);z=compare(q,sym,d,s);ck('zero_volume',z['peer_mean'] is None)
 q=dict(f);q[sym,d,s+1]=dict(q[sym,d,s+1],close=1);q[peer,d,s+1]=dict(q[peer,d,s+1],close=999999);ck('future_mutation',compare(q,sym,d,s)==base)
 for j in (3,28,31,34):
  z=compare(f,sym,d,j);ck('session_boundary',(z['peer_mean'] is not None)==(j==34))
 # Target price change cannot alter peer aggregates; a valid observed target changes only own features.
 q=dict(f);q[sym,d,s]=dict(q[sym,d,s],close=f[sym,d,s]['close']+999);z=compare(q,sym,d,s);ck('peer_invariance',z['peer_mean']==base['peer_mean'] and z['peer_up']==base['peer_up'] and z['relative']!=base['relative'])
 idx,meta=R['load'](path);rows=[]
 for d in range(5,19):
  for s in R['signals']:
   for sym in SYMS:rows.append(compare(idx,sym,d,s))
 coverage={}
 for name,lo,hi in [('train',5,8),('audit',8,10),('evaluation',10,19)]:
  a=[x for x in rows if lo<=x['day']<hi];coverage[name]=dict(n=len(a),rsi_ready=sum(x['rsi'] is not None for x in a),rebound=sum(x['rebound'] is True for x in a),peer_ready=sum(x['peer_mean'] is not None for x in a),peer_condition=sum(x['peer_condition'] is True for x in a),relative_ready=sum(x['relative'] is not None for x in a),both=sum(x['rebound'] is True and x['peer_condition'] is True for x in a),relative_positive=sum(x['relative'] is not None and F(x['relative'])>0 for x in a))
  ck('coverage_partition',coverage[name]['peer_ready']+sum(x['peer_mean'] is None for x in a)==len(a))
 ck('archive_unchanged',hashlib.sha256(Path(path).read_bytes()).hexdigest()==PLAN['archive_sha'])
 return dict(plan=PLAN,normalized_sha=meta['normalized_sha256'],coverage=coverage,checks=dict(checks),passed=sum(checks.values()),observations=rows,limits=['features only, no profit evaluation or candidate changes','known 19 days; ideal bar-end receipt','continuous RSI strict full prefix; missing history not recovered','other five stocks not market index; no order book inference'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('--output',required=True);p.add_argument('--plan-only',action='store_true');a=p.parse_args();z=PLAN if a.plan_only else report(a.archive)
 with open(a.output,'x') as f:json.dump(z,f,indent=2,sort_keys=True);f.write('\n')
