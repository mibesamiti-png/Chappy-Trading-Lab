"""R154: normalized synthetic CSV to offline evaluation report; real inputs locked."""
import argparse, hashlib, json, runpy, tempfile, os
from pathlib import Path
from datetime import date,timedelta
from collections import Counter
from fractions import Fraction as F
P=Path(__file__).with_name('Chappy_Trading_Configured_Lifecycle_Study_v0.1.py')
SHA='8279536d239361f54e9f0e167af1105caa0c56b7159011b2d8a1bf4188735b09'
if hashlib.sha256(P.read_bytes()).hexdigest()!=SHA:raise ValueError('dependency hash')
C=runpy.run_path(str(P)); G=C['G']; R=C['R']; MODES=('HOLD','CHASE','FADE','FROZEN','STOP','REFRESH'); COSTS=(20,40)
MARKER='SYNTHETIC VALUES ONLY; historical schema test'
PLAN=dict(dependency=SHA,seed=154000,cases=['stable','reversal','null','missing'],profiles=['19x6','32x2'],modes=MODES,costs=COSTS,real_input='locked until provenance and original format checked',scope='offline synthetic normalized subset only',capital=200000,notional=100000,observation_fee=0)
def config(m, historical=False):
 G['preflight'](m)
 if m['purpose']=='known_development':
  if not historical or m['source']!=MARKER:raise ValueError('real historical input locked')
  return C['NEW']
 if historical:raise ValueError('historical schema flag mismatch')
 if m['source']!='artificial fixture':raise ValueError('synthetic source marker required')
 return C['OLD']
def baseline(rs,mode,cfg):
 if mode=='HOLD':return []
 return [C['order'](d,l,d['momentum']*(1 if mode=='CHASE' else -1)) for d,l in rs if d['day']>=cfg.active and d['state'] is not None and d['momentum']]
def evaluate(path,m,historical=False):
 cfg=config(m,historical); rows,q=G['load'](path,m); rs=C['records'](rows,cfg)
 coverage={}
 for phase,lo,hi in [('train',5,5+cfg.train),('audit',5+cfg.train,cfg.active),('evaluation',cfg.active,cfg.days)]:
  part=[(d,l) for d,l in rs if lo<=d['day']<hi]; coverage[phase]=dict(opportunities=len(part),features=sum(d['state'] is not None for d,l in part),mature=sum(l['mature'] is not None for d,l in part),feature_reasons=dict(Counter(d['reason'] for d,l in part)),result_reasons=dict(Counter(l['reason'] for d,l in part)))
 results={}
 for cost in COSTS:
  for mode in MODES:
   if mode in ('HOLD','CHASE','FADE'):ev=[];reviews=[];orders=baseline(rs,mode,cfg)
   else:ev,orders,reviews=C['simulate'](rs,cost,mode,cfg)
   z=C['settle'](orders,cost,cfg)
   results[f'{cost}:{mode}']=dict(lifecycle=ev,reviews=reviews,intents=len(orders),accepted=len(z['accepted']),blocked=len(z['blocked']),unresolved=z['unresolved'],cash=z['cash'],reserved=z['reserved'],known_gross=z['gross'],fees=z['fees'],net=z['net'],status='INCOMPLETE_UNRESOLVED' if z['unresolved'] else 'COMPLETE_SYNTHETIC',ledger=z['events'])
 return dict(schema='R154-v1',status='SYNTHETIC_OFFLINE_ONLY',input=dict(q,source=m['source'],dates=m['dates'],symbols=m['symbols'],clock=m['clock'],provenance='declared synthetic; not authenticated'),config=cfg._asdict(),coverage=coverage,results=results,limits=['real historical inputs locked; no broker conversion or authentic calendar','24 logical bars and 4 decision slots/day; not actual exchange schedule','point audit/monitor not statistical guarantees','fixed full collateral plus fee; no observation fee; alphabetical priority','unresolved results not zero; reported cash excludes reserved collateral','no live orders; no real-price evaluation'])
def demo_fixture(path,case,profile,seed=154000):
 cfg=C['NEW'] if profile=='19x6' else C['OLD']; historical=profile=='19x6'
 if historical:
  ds=[str(date(2026,10,26)+timedelta(days=i)) for i in range(30) if (date(2026,10,26)+timedelta(days=i)).weekday()<5 and str(date(2026,10,26)+timedelta(days=i)) not in ('2026-11-06','2026-11-03','2026-11-23')]
 else:ds=[str(date(2025,1,1)+timedelta(days=i)) for i in range(32)]
 rows=C['fixture'](seed,case,cfg);raw=G['encode'](rows,ds);path.write_bytes(raw);m=G['manifest'](raw,ds,list(cfg.symbols),'known_development' if historical else 'synthetic')
 if historical:m['source']=MARKER
 return m,historical

def exclusive_json(path,obj):
 # Create only; refuse existing file including a symlink. On write failure remove only our new file.
 raw=(json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 try:
  with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 except BaseException:
  Path(path).unlink(missing_ok=True);raise

def study():
 checks=Counter();summary={}
 def ck(k,b):
  if not b:raise AssertionError(k)
  checks[k]+=1
 def reject(k,fn,match):
  try:fn()
  except (ValueError,FileExistsError) as e:ck(k,match in str(e));return
  raise AssertionError(k)
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp)/'fixture.csv';out=Path(tmp)/'report.json';absent=Path(tmp)/'absent.csv'
  for profile in PLAN['profiles']:
   for case in PLAN['cases']:
    m,h=demo_fixture(p,case,profile);r=evaluate(p,m,h);cfg=config(m,h);rr,q=G['load'](p,m);rs=C['records'](rr,cfg)
    ck('coverage',sum(x['opportunities'] for x in r['coverage'].values())==len(rs));ck('input_hash',r['input']['sha256']==hashlib.sha256(p.read_bytes()).hexdigest());ck('bar_coverage',q['rows']+q['missing']==cfg.days*len(cfg.symbols)*24)
    for fee in COSTS:
     for mode in MODES:
      z=r['results'][f'{fee}:{mode}'];key=f'{fee}:{mode}'
      if mode in ('HOLD','CHASE','FADE'):
       o=[] if mode=='HOLD' else [((d['day'],d['slot'],d['symbol']),d['decision'],d['momentum']*(1 if mode=='CHASE' else -1),l) for d,l in rs if d['day']>=cfg.active and d['state'] is not None and d['momentum']!=0];e=[];v=[]
      else:e,o,v=C['oracle'](rs,fee,mode,cfg)
      ref=C['cash_ref'](o,fee,cfg)
      ck('decision_oracle',z['lifecycle']==e and z['reviews']==v and z['intents']==len(o));ck('cash_oracle',all(z[a]==ref[b] for a,b in [('cash','cash'),('reserved','reserved'),('unresolved','unresolved'),('known_gross','gross'),('fees','fees'),('net','net')]) and z['accepted']==len(ref['accepted']) and z['blocked']==len(ref['blocked']));ck('conservation',F(z['cash'])+z['reserved']==200000+F(z['known_gross'])-F(z['fees']));ck('partition',z['accepted']+z['blocked']==z['intents']);ck('unknown', (z['net'] is None)==bool(z['unresolved']));ck('nonnegative',all(F(x[3])>=0 for x in z['ledger']));ck('status',(z['status']=='INCOMPLETE_UNRESOLVED')==bool(z['unresolved']))
    summary[profile+':'+case]=dict(rows=q['rows'],missing=q['missing'],coverage=r['coverage'],results={k:{x:v[x] for x in ('intents','accepted','blocked','unresolved','net','status')} for k,v in r['results'].items()})
    if out.exists():out.unlink()
    exclusive_json(out,r);ck('report_roundtrip',json.loads(out.read_text())==json.loads(json.dumps(r)));old=out.read_bytes();reject('overwrite',lambda:exclusive_json(out,{}),'File exists');ck('preserve_report',out.read_bytes()==old)
  m,h=demo_fixture(p,'stable','19x6');reject('real_lock',lambda:evaluate(absent,dict(m,source='historical source'),True),'real historical input locked');reject('explicit_flag',lambda:evaluate(absent,m,False),'real historical input locked');reject('protected_preopen',lambda:evaluate(absent,dict(m,dates=m['dates'][:-1]+['2026-11-26']),True),'protected or later date');reject('hash',lambda:evaluate(p,dict(m,sha256='0'*64),True),'hash mismatch');reject('source_marker',lambda:evaluate(absent,dict(m,source='real source'),True),'real historical input locked')
 return dict(plan=PLAN,plan_sha=R['digest'](PLAN),checks=dict(checks),passed=sum(checks.values()),summary=summary)
def main():
 a=argparse.ArgumentParser(description=__doc__);g=a.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--demo',choices=PLAN['cases']);g.add_argument('--csv');a.add_argument('--manifest');a.add_argument('--synthetic-historical-schema',action='store_true');a.add_argument('--profile',choices=PLAN['profiles'],default='19x6');a.add_argument('--output',required=True);x=a.parse_args()
 if x.self_test:r=study()
 elif x.demo:
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'demo.csv';m,h=demo_fixture(p,x.demo,x.profile);r=evaluate(p,m,h)
 else:
  if not x.manifest:a.error('--manifest required')
  r=evaluate(x.csv,json.loads(Path(x.manifest).read_text(encoding='utf-8')),x.synthetic_historical_schema)
 exclusive_json(x.output,r)
if __name__=='__main__':main()
