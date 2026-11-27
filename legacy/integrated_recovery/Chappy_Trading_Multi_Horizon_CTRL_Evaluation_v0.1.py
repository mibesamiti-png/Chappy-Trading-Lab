"""R163 fixed known-development comparison, no live trading."""
import argparse,hashlib,json,runpy,types
from pathlib import Path
from collections import Counter
from fractions import Fraction as F
P=Path(__file__).parent
DEP='4e92b34c34ddbda5fca8bfb77efc43b653f50944e2f16e1e70755d772f57eb49'
p=P/'Chappy_Trading_Multi_Horizon_Learning_Study_v0.1.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if sha(p)!=DEP:raise ValueError('dependency')
L=runpy.run_path(str(p));M=L['M'];R=L['R'];HS=L['HS'];CANDS=L['CANDS'];IDS=L['IDS'];MODES=L['MODES'];COMMON=L['COMMON'];END=L['END'];SYMS=L['SYMS'];H=19*86400
PLAN=dict(round=163,dependency=DEP,archive_sha=R['I']['SHA'],dates=R['days'],symbols=SYMS,train=[5,8],audit=[8,10],evaluation=[10,19],schedule=COMMON,horizons=HS,fees=[20,40],modes=MODES,candidates=len(CANDS),cohort='R162 all panels present and all three train labels matured strictly before audit; fixed selected horizon audit all matured before evaluation; WAIT tie priority',capital='R161 unchanged, 200000 initial,100000 fixed notional, one symbol lock, no observation fee',scope='known development only, one split, no optimization or unknown data')
def train(rows):return [r for r in rows if 5<=r['key'][0]<8 and r['states'] is not None and all(L['ready'](v,8*86400) for v in r['labels'].values())]
def adapt(name):
 f=L[name];return types.FunctionType(f.__code__,dict(f.__globals__,training=train),f.__name__)
scores=adapt('scores');ref_scores=adapt('ref_scores');action=L['action']
def decide(rows,c,m,sc):
 i=max(IDS[m],key=sc.__getitem__);p,h,j=CANDS[i];a=[r for r in rows if 8<=r['key'][0]<10 and action(r,i)];known=[r for r in a if L['ready'](r['labels'][h],10*86400)];net=sum((action(r,i)*F(r['labels'][h]['gross'])*10000-c for r in known),F(0));ok=bool(a) and len(a)==len(known) and net>0
 orders=[(r['key'],r['t'],action(r,i),r['labels'][h]) for r in rows if r['key'][0]>=10 and ok and action(r,i)]
 return dict(candidate=i,audit_count=len(a),audit_mature=len(known),audit_net=str(net),admit=ok,orders=orders)
def run(path):
 idx,meta=R['load'](path);checks=Counter();rows=[]
 def ck(k,v):
  if not v:raise AssertionError(k)
  checks[k]+=1
 for d in range(5,19):
  for s in COMMON:
   for sym in SYMS:
    z,states=L['observe'](idx,sym,d,s);t=END(d,s);pre={k:v for k,v in idx.items() if v['received']<=t and END(k[1],k[2])<=t};ck('feature_prefix',L['observe'](pre,sym,d,s)==(z,states));ck('clock',t==z['decision']);labs={h:M['label'](idx,z,h,H) for h in HS}
    for h,l in labs.items():
     ck('label_oracle',(l['reason'],l['gross'],l['mature'])==M['reference'](idx,z,h,H));ck('session',M['supported'](s,h));ck('maturity',l['mature'] is None or (l['mature']>t and not L['ready'](l,l['mature']) and L['ready'](l,l['mature']+1)))
    rows.append(dict(key=(d,s,sym),t=t,states=states,labels=labs))
 coverage={}
 for n,(lo,hi) in [('train',(5,8)),('audit',(8,10)),('evaluation',(10,19))]:
  q=[r for r in rows if lo<=r['key'][0]<hi];coverage[n]=dict(opportunities=len(q),common_features=sum(r['states'] is not None for r in q),all_mature=sum(r['states'] is not None and all(L['ready'](v,hi*86400) for v in r['labels'].values()) for r in q),state_counts={p:dict(Counter(str(r['states'][p]) for r in q if r['states'] is not None)) for p in L['PANELS']})
 results={};diag={}
 blank=lambda r:dict(r,labels={h:dict(v,gross=None,mature=None) for h,v in r['labels'].items()})
 evmask=[blank(r) if r['key'][0]>=10 else r for r in rows];trmask=[blank(r) if r['key'][0]>=8 else r for r in rows]
 for c in PLAN['fees']:
  sc=scores(rows,c);ref=ref_scores(rows,c);ck('score_oracle',sc==ref);ck('train_mask',scores(trmask,c)==sc);ck('eval_mask',scores(evmask,c)==sc)
  diag[str(c)]={f'{p}:{h}':sum(sc[i]>0 for i,(pp,hh,j) in enumerate(CANDS) if pp==p and hh==h) for p in L['PANELS'] for h in HS}
  for m in MODES:
   z=decide(rows,c,m,sc);i=z['candidate'];p,h,j=CANDS[i];ck('selection',i==max(IDS[m],key=ref.__getitem__));a=[r for r in rows if 8<=r['key'][0]<10 and action(r,i)];ck('audit',z['admit']==(bool(a) and all(L['ready'](r['labels'][h],10*86400) for r in a) and sum((action(r,i)*F(r['labels'][h]['gross'])*10000-c for r in a),F(0))>0));ck('eval_blind',L['identity'](z)==L['identity'](decide(evmask,c,m,sc)))
   o=z.pop('orders');b=M['settle'](o,c,H);ck('cash_oracle',{k:v for k,v in b.items() if k!='events'}==M['cash_ref'](o,c,H));ck('accounting',F(b['cash'])+b['reserved']==M['INITIAL']+F(b['gross'])-F(b['fees']));ck('partition',len(o)==len(b['accepted'])+len(b['blocked']));ck('nonnegative',all(F(x[3])>=0 for x in b['events']));ck('single_horizon',len({q[0] for q in o})==len(o) and all(q[3]['horizon']==h for q in o));ck('authority',z['admit'] or not o)
   results[f'{c}:{m}']=dict(**z,panel=p,horizon=h,table=j,training_net_yen=round(float(sc[i]*10),2),training_intents=sum(bool(action(r,i)) for r in train(rows)),positive_candidates=sum(sc[k]>0 for k in IDS[m]),audit_net_yen=round(float(F(z['audit_net'])*10),2),intents=len(o),accepted_count=len(b['accepted']),blocked_count=len(b['blocked']),net_yen=None if b['net'] is None else round(float(F(b['net'])),2),account=b)
 ck('archive_unchanged',sha(path)==PLAN['archive_sha']);ck('coverage',len(rows)==14*8*6)
 return dict(plan=PLAN,normalized_sha=meta['normalized_sha256'],coverage=coverage,positive_by_panel_horizon=diag,results=results,checks=dict(checks),passed=sum(checks.values()),limits=['known development only','common cohort excludes valid shorter opportunities','point audit no statistical guarantee','training ignores capital contention','no refresh, actual receipt, actual fills or borrow constraints'])
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('archive',type=Path);a.add_argument('--plan-only',action='store_true');a.add_argument('--output',required=True);q=a.parse_args();z=PLAN if q.plan_only else run(q.archive)
 with open(q.output,'x') as f:json.dump(z,f,indent=2,sort_keys=True);f.write('\n')
