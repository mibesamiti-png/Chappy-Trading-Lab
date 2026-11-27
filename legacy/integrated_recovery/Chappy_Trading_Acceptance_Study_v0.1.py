"""R66 acceptance harness: offline, known synthetic scenarios only. No live trading.
Does not add a unified trading engine or authorize any market execution.
"""
import argparse, copy, hashlib, importlib.util, json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).parent
P=ROOT/'Chappy_Trading_Integrated_Monitor_v0.1.py'
PIN='66d52f6f177f006a674f184d2d3ce00f31358efd158d81e25d03d61a4d97c982'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PIN:raise RuntimeError('R65 integrity')
spec=importlib.util.spec_from_file_location('r65',P);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
c=m.cal;i=c.i;a=c.a;e=c.e;d=a.d

def run():
 tests=[]
 def ck(name,x,y=True):
  if x!=y:raise AssertionError((name,x,y))
  tests.append({'name':name,'pass':True})
 def reject(name,fn):
  try:fn()
  except (ValueError,RuntimeError):ck(name,True);return
  raise AssertionError(name+' accepted')
 train,*_=c.c.fixtures();model=c.c.fit(*train);frozen=c.freeze(c.CASES,c.PROBS,model['sha256']);h=model['sha256'];fh=frozen['sha256']
 # Test fixture anchors are computed from known intended events, not the database under test.
 # These are not externally authenticated independent records.
 allstreams={}; auds={}; anchors={};cases=[];total=0
 policy=i.study()
 with tempfile.TemporaryDirectory() as tmp:
  for name,action in [('BASE','SELECT'),('STRICT','WAIT_SIGNAL')]:
   streams={};reviewed={};anchor={}
   for case in c.CASES:
    ev=i.branch(action,i.OUTCOMES[case]);expected=e.seal(ev);path=Path(tmp)/(name+'-'+case+'.sqlite');s=d.Store(path,create=True)
    try:
     s.authorize(e.Z,[]);v=s.inspect()
     for k,event in enumerate(ev):
      v=s.append(event,v['head']);total+=1
      ck(name+':'+case+':prefix:'+str(k+1),v['records'],expected['records'][:k+1])
    finally:s.close()
    s=d.Store(path)
    try:
     v=s.inspect();ck(name+':'+case+':reopened',v,expected)
     reject(name+':'+case+':no restart append',lambda:s.append(ev[-1],v['head']))
     s.authorize(expected['head'],expected['result']['pending'])
     reject(name+':'+case+':duplicate',lambda:s.append(ev[-1],v['head']))
     ck(name+':'+case+':rollback',s.inspect(),expected)
    finally:s.close()
    cutoff=i.PLAN['cutoffs'][case];aud=a.from_store(path,expected['head'],cutoff);split='discovery' if case.startswith('D') else 'evaluation';old=next(x for x in policy['results'][split]['cases'] if x['id']==case)['policies'][name]['audit'];ck(name+':'+case+':review',aud,old)
    streams[case]=(v['records'],v['head']);reviewed[case]=aud;anchor[case]=expected['head'];cases.append({'policy':name,'case':case,'events':len(ev),'head':v['head'],'review_cutoff':cutoff,'realized_pnl_cents':aud['execution_summary']['realized_pnl_cents'],'held':aud['execution_summary']['held']})
   allstreams[name]=streams;auds[name]=reviewed;anchors[name]=anchor
  pools={};calibrations={}
  for name,streams in allstreams.items():
   # Ensure intended case identity before passing records to the existing audit.
   ck(name+':case anchor map',{k:v[1] for k,v in streams.items()},anchors[name]);z=c.evaluate(frozen,fh,model,h,streams,145);p=m.pool(frozen,fh,model,h,streams,145);ck(name+':pool source',p['source_rows'],z['trace']);ck(name+':pool state',p['monitor']['state'],'NORMAL');calibrations[name]=z;pools[name]=p
  ck('policy remains rejected',policy['candidate'],'REJECT_OR_UNPROVEN');ck('same calibration',calibrations['BASE']['calibration'],calibrations['STRICT']['calibration'])
  # Reproduce case aliasing with same decision prefix but different final outcomes.
  swapped=dict(allstreams['BASE']);swapped['D01'],swapped['E01']=swapped['E01'],swapped['D01'];z=c.evaluate(frozen,fh,model,h,swapped,145)
  before=calibrations['BASE'];ck('legacy accepts swapped streams',z['eligible'],before['eligible']);ck('swapping preserves aggregate',z['calibration']['overall'],before['calibration']['overall']);ck('swapping changes regime report',z['calibration']['by_regime']!=before['calibration']['by_regime']);ck('swapping changes per-case labels',z['trace']!=before['trace']);ck('fixture anchor map detects swap',{k:v[1] for k,v in swapped.items()}!=anchors['BASE'])
  # Verify existing replay entry is independent of the pooled monitoring result.
  pre=c.prefix();p=e.seal(pre);ck('legacy allocation exists',bool(p['result']['plans']));g=m.rec.Gate();route=m.route_tick(g,125,{'A':'WARMUP','B':'NORMAL','C':'NORMAL'});ck('monitor refuses new activity',route['new_entry_allowed'],[])
  # At original entry time no outcome was yet available; do not feed later pool backwards.
  early=c.evaluate(frozen,fh,model,h,allstreams['BASE'],115);ck('all early unresolved',all(x['calibration_label']=='OPEN' for x in early['trace']));reject('no early pool',lambda:m.pool(frozen,fh,model,h,allstreams['BASE'],115))
  for key in ['BASE','STRICT']:
   ck(key+':all streams offline',all(not v['live_adoption'] for v in auds[key].values()))
  ck('monitor recovery fixture',next(x for x in m.example()['parallel'] if x['at']==225)['recovery']['state'],'NORMAL')
 gates=[{'name':'known synthetic offline analysis','status':'PASS','scope':'10 stored case-policy streams, review, improvement, calibration, pooled monitor; no market data'}, {'name':'single live-equivalent pre-entry monitor/recovery gate','status':'BLOCKED','reason':'legacy replay accepts allocation at 115 without monitoring state; earliest pooled result requires source cutoff 145; logical clock is separate'}, {'name':'case identity across streams','status':'BLOCKED','reason':'legacy calibration accepts swapped case streams with matching prefix; harness catches by fixture-specific head map only'}, {'name':'durable monitoring/forecast/recovery state','status':'NOT_TESTED','reason':'SQLite persists R60 events, not R64 sidecar or R65 monitor state; restart gate not unified'}, {'name':'actual market execution and returns','status':'OUT_OF_SCOPE','reason':'synthetic evidence only; reserved prospective plan unchanged'}]
 return {'test_count':len(tests),'tests':tests,'examples':{'streams':cases,'event_appends':total,'stream_count':len(cases),'gates':gates,'research_disposition':'OFFLINE_RESEARCH_ONLY','execution_disposition':'BLOCKED','forecast_manifest_sha':fh,'fixture_anchors':anchors,'legacy_case_swap_reproduced':True,'legacy_entry_monitor_bypass_reproduced':True,'candidate':policy['candidate'],'live_adoption':False}}
if __name__=='__main__':
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');args=p.parse_args();v=run();print(json.dumps(v['examples'] if args.example else {k:v[k] for k in ('test_count','tests')},sort_keys=True,indent=2))
