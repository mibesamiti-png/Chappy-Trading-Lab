"""R167 read-only integration audit; synthetic OHLCV only."""
import argparse, hashlib, json, runpy
from collections import Counter
from pathlib import Path
P=Path(__file__).parent
PINS={160:('Market_Context_Adapter','14d2affe89176df07d784780add75d0bf08b91f96759f9d99de0f92973af0677'),161:('Multi_Horizon_Adapter','7aa917e673e3d289c58d2da30c09380d67d70d25e1d3b541b86666c008c0654b'),162:('Multi_Horizon_Learning_Study','4e92b34c34ddbda5fca8bfb77efc43b653f50944e2f16e1e70755d772f57eb49'),163:('Multi_Horizon_CTRL_Evaluation','efb8400db58fd940790b599e10efb7566f4b759bb3b353825399fa85246546a5'),164:('Capital_Diagnostic','03285b821372c0505e3e6b13f63ce3bd5863afcf65b429261f534b16f72bb655'),165:('Capital_Aware_Learning','97b24c62808f609a5cfeac525d1779e179ba71c9d6e10c0b5c6f93486cd2dbce'),166:('Capital_Lifecycle_Study','fe0a70707e9f75fa2974bc9f7c8c61cdbc5282fe079f492ccb1da75b5db9c94b')}
def src(n):return P/f'Chappy_Trading_{PINS[n][0]}_v0.1.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
PLAN=dict(round=167,scope='synthetic OHLCV and saved reports only; no market archive read, no new candidate or threshold',days=19,fees=[20,40],modes=['FROZEN','STOP','REFRESH'],cases=['stable','reversal','missing'],fault='remove one middle bar at day 11, slot 9, first symbol',acceptance='freeze only if data safety authority and integrated input/output acceptance established; report gaps, no modifications')
def run():
 counts=Counter();findings={};cases=[];saved={}
 def ck(k,b):
  if not b:raise AssertionError(k)
  counts[k]+=1
 for n,(_,h) in PINS.items():
  ck('source_hash',sha(src(n))==h);compile(src(n).read_text(),str(src(n)),'exec');ck('source_compile',True)
  p=P/f'Trading_Round{n}_results.json';d=json.loads(p.read_text());ck('stored_count_arithmetic',d['passed']==sum(d['checks'].values()));saved[str(n)]=dict(passed=d['passed'],sha256=sha(p))
 R=runpy.run_path(str(src(166)));L=R['A']['L'];M=R['M'];syms=L['SYMS'];H=19*86400;end=L['END'];common=L['COMMON'];hs=L['HS']
 ck('pool',len(R['C'])==2449);ck('shared_capital',M['INITIAL']==200000 and M['N']==100000)
 def fixture(case):
  out={}
  for j,sym in enumerate(syms):
   p=1000000+10000*j
   for d in range(19):
    for s in range(63):
     o=p;p+=1000 if case=='stable' or d<11 else -1000
     if case=='missing' and (j,d,s)==(0,11,9):continue
     out[sym,d,s]=dict(open=o,high=max(o,p)+10,low=min(o,p)-10,close=p,volume=100,received=end(d,s),actual_start=f'{d}:{s}')
  return out
 for case in PLAN['cases']:
  idx=fixture(case);rows=[]
  for d in range(5,19):
   for s in common:
    for sym in syms:
     t=end(d,s);z,states=L['observe'](idx,sym,d,s);pre={k:v for k,v in idx.items() if v['received']<=t and end(k[1],k[2])<=t};ck('feature_prefix',L['observe'](pre,sym,d,s)==(z,states));ck('clock',z['decision']==t)
     labs={h:M['label'](idx,z,h,H) for h in hs}
     for h,l in labs.items():
      ck('label_oracle',(l['reason'],l['gross'],l['mature'])==M['reference'](idx,z,h,H));ck('session',M['supported'](s,h));ck('maturity',l['mature'] is None or l['mature']>t and not L['ready'](l,l['mature']) and L['ready'](l,l['mature']+1))
     rows.append(dict(key=(d,s,sym),t=t,states=states,labels=labs))
  ck('coverage',len(rows)==672)
  for c in PLAN['fees']:
   for mode in PLAN['modes']:
    z=R['simulate'](rows,c,mode,ck);a=z['account'];q=z['orders'];ev=z['events'];ck('account_oracle',{k:v for k,v in a.items() if k!='events'}==M['cash_ref'](q,c,H-1));ck('authority',ev[0]['admit'] or not q);ck('single_horizon',len({x[0] for x in q})==len(q));ck('unknown_conservation',(a['net'] is None)==bool(a['unresolved']))
    for k,t,v,l in q:ck('order_clock',t==end(k[0],k[1]) and M['supported'](k[1],l['horizon']))
    cases.append(dict(case=case,fee=c,mode=mode,bars=len(idx),features=sum(r['states'] is not None for r in rows),events=ev,intents=len(q),accepted=len(a['accepted']),blocked=len(a['blocked']),unresolved=a['unresolved'],net=a['net'],reviews=z['reviews']))
 z=R['simulate'](R['fixture']('unknown_monitor'),20,'REFRESH',ck);u=[x['day'] for x in z['reviews'] if x['day']>=12 and x['review'] is None];later=[x for x in z['orders'] if x[0][0]>=12];ck('known_gap_reproduced',bool(u) and bool(later) and not any(e['kind']=='stop' for e in z['events']));findings['missing_safety_authority']=dict(status='BLOCKER',unknown_review_days=u,subsequent_intents=len(later),accepted_after_unknown=sum(k[0]>=12 for k in z['account']['accepted']),unresolved=z['account']['unresolved'],note='Economic monitor UNKNOWN is not a data safety stop; orders still emitted. No integrated R132/R133 data authority in R166.')
 idx=fixture('stable');sym=syms[0];d=5;s=common[1];t=end(d,s);idx[sym,d,s]=dict(idx[sym,d,s],received=t-1);z,states=L['observe'](idx,sym,d,s);ck('early_receipt_gap_reproduced',z['decision']==t-1 and states is None);findings['invalid_receipt_boundary']=dict(status='BLOCKER',scheduled=t,actual_returned=z['decision'],states=states,note='Common features reject early receipt but base decision timestamp is not canonical. Need validated input boundary; current pinned archive has ideal receipts.')
 findings['entrypoint']=dict(status='BLOCKER',note='R166 CLI accepts no OHLCV input, only synthetic fixture report. R155 frozen CLI predates R160-166. Audit invokes modules through synthetic adapter, not a packaged runtime.')
 findings['monitor_population']=dict(status='LIMITATION',note='Learning/audit use constrained account; economic monitor uses last four shadow intents. Different estimands.')
 for n,(_,h) in PINS.items():ck('source_unchanged',sha(src(n))==h)
 return dict(plan=PLAN,status='FREEZE_BLOCKED',checks=dict(counts),passed=sum(counts.values()),saved_reports=saved,cases=cases,findings=findings,limits=['audit checks include successful reproduction of blockers, not all acceptance gates passed','synthetic OHLCV only; no market evidence','saved counts checked arithmetically, not all historical regression rerun','no actual orders'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();r=run()
 with open(a.output,'x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
