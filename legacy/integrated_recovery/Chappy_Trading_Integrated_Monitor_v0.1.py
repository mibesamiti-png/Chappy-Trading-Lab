"""R65: synthetic monitoring bridge, no market input or trading interface."""
import argparse, json, copy, itertools
from pathlib import Path
from fractions import Fraction
import hashlib, importlib.util, sys
ROOT=Path(__file__).parent

def load(name,filename,pin):
    p=ROOT/filename
    if hashlib.sha256(p.read_bytes()).hexdigest()!=pin: raise ValueError(name+' source integrity')
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
cal=load('r64','Chappy_Trading_Integrated_Calibration_v0.1.py','c37b86847e3465b1a7532f0c1a4e4bcc21d6a9d56cad8b9cc040ab7bdfb66c54')
seq=load('r54','Chappy_Trading_Sequential_Monitor_v0.1.py','8a5213b3869ad5686b3fe8d22f0318d01ac7a90ada03cdee7ad1c7a4521e37f2')
multi=load('r56','Chappy_Trading_Multi_Monitor_v0.1.py','ba1b7346676f5c46ae4ebfe22da6500c74b89004315fd59d38bc0fbafcada893')
rec=load('r58','Chappy_Trading_Recovery_Study_v0.1.py','17b61371aef926a5ddea0fd894059f90d6d2b3022c252a12057c5d3edd07d70b')
SYMBOLS='ABC'; STATES=('WARMUP','NORMAL','WARNING','HALTED','RECOVERING','READY')

def pool(frozen,manifest_sha,model,model_sha,streams,source_cutoff):
    # A completed source audit is transformed into ONE artificial logical cohort.
    # Logical times are NOT original forecast, event, or reception timestamps.
    z=cal.evaluate(frozen,manifest_sha,model,model_sha,streams,source_cutoff)
    rows=z['trace']; selected=[x for x in rows if x['p'] is not None and 8000<=x['p']<=10000]
    if len(selected)!=10 or any(source_cutoff<x['deadline'] for x in selected):raise ValueError('closed high-bin cohort required')
    if len({x['forecast_id'] for x in selected})!=10:raise ValueError('duplicate source')
    fs=[];rs=[]
    for x in selected:
        fs.append(seq.Forecast(x['forecast_id'],110,120,x['p']))
        # No coverage claim: UNKNOWN and OPEN never become known expiry or failure.
        if x['calibration_label'] in ('CONFIRMED','REFUTED'):
            if x['decisive_at'] is None or not x['time']<x['decisive_at']<=min(x['deadline'],source_cutoff):raise ValueError('source time')
            rs.append(seq.Outcome(x['forecast_id'],120,125,x['calibration_label']))
    return {'source_cutoff':source_cutoff,'source_manifest':manifest_sha,'source_model':model_sha,'source_trace_sha':cal.digest(rows),'source_rows':rows,'excluded':[x['forecast_id'] for x in rows if x not in selected],'monitor':seq.monitor(fs,rs,125),'scope':'one pooled high-bin synthetic cohort; logical replay clock; no per-strategy or real-time calibration claim'}

def route_tick(g,t,states,feed='OK',changes=None,approval=None,holdings=None):
    if set(states)!=set(SYMBOLS) or any(s not in STATES for s in states.values()):raise ValueError('monitor states')
    mapped=['NORMAL' if states[s]=='NORMAL' else 'GAP' if states[s]=='WARMUP' else 'ALARM' for s in SYMBOLS]
    routing=multi.route(mapped,feed); health=dict(changes or {})
    if any(k not in rec.dep.ROOTS or k.startswith('alarm_') for k in health):raise ValueError('alarm override or unknown node')
    # Scope unknown/shared failure is a separate externally supplied claim.
    if routing['global_hold']:health['price']='UNKNOWN' if feed=='UNKNOWN' else 'FAILED'
    for k,s in enumerate(SYMBOLS):health['alarm_'+s]='OK' if k not in routing['local_holds'] else 'UNKNOWN' if mapped[k]=='GAP' else 'FAILED'
    l=rec.snapshot(t,holdings=holdings); external=copy.deepcopy(l)
    x=rec.tick(g,t,health,local=l,external=external,approval=approval,exit_requested=('A',) if holdings and holdings['A'] else ())
    return {'at':t,'monitor_states':dict(states),'local_policy':routing,'recovery':x,'new_entry_allowed':[s for s in SYMBOLS if x['routing'][s]['restart_gate']=='ELIGIBLE'],'live_adoption':False}

def parallel(counts, approvals=None, late=None, feed_at=None, end=245):
    if set(counts)!=set(SYMBOLS):raise ValueError('channels')
    approvals=approvals or {};late=late or {};feed_at=feed_at or {};g=rec.Gate();out=[]
    inputs={s:seq.fixture(counts[s],late.get(s)) for s in SYMBOLS}
    for t in range(125,end+1,5):
        states={}
        for s,(fs,rs) in inputs.items():
            # R54 receives only already visible inputs; all fixture data are synthetic.
            f=[x for x in fs if x.time<=t];ids={x.id for x in f};r=[x for x in rs if x.id in ids and x.received<=t]
            states[s]=seq.monitor(f,r,t,tuple(a for a in approvals.get(s,()) if a<=t))['state']
        token=out[-1]['recovery']['ready_token'] if out and out[-1]['recovery']['state']=='READY' else None
        out.append(route_tick(g,t,states,feed_at.get(t,'OK'),approval=token,holdings={'A':100,'B':0,'C':0}))
    return out

def example():
    train,*_=cal.c.fixtures();m=cal.c.fit(*train);f=cal.freeze(cal.CASES,cal.PROBS,m['sha256']);b=cal.inputs();s=cal.inputs('WAIT_SIGNAL')
    p=pool(f,f['sha256'],m,m['sha256'],b,145);q=pool(f,f['sha256'],m,m['sha256'],s,145)
    # A has no usable calibrated cohort. B/C share the same pooled evidence, not independent estimates.
    pooled_route=route_tick(rec.Gate(),125,{'A':'WARMUP','B':p['monitor']['state'],'C':p['monitor']['state']})
    counts={'A':[6]*7,'B':[6,2,2,6,6,6,6],'C':[6]*7}
    return {'pool':p,'strict_pool':q,'pooled_route':pooled_route,'parallel':parallel(counts,{'B':(205,206)}),'late':parallel({s:[6]*7 for s in SYMBOLS},late={'B':(1,0)},end=165),'shared':parallel({s:[6]*7 for s in SYMBOLS},feed_at={145:'VERIFIED_SHARED_FAILURE',150:'UNKNOWN'},end=165),'scope':'synthetic only; all-channel R58 latch intentionally conservative; approval times/auto token in harness are scripted, not authorization'}

def self_test():
    tests=[]
    def ck(n,x,y=True):
        if x!=y:raise AssertionError((n,x,y))
        tests.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except (ValueError,KeyError,TypeError):ck(n,True)
        else:ck(n,False)
    z=example();p=z['pool'];q=z['strict_pool'];g=p['monitor']['timeline'][0];ck('pooled count',g['resolved'],10);ck('pooled confirmed',g['confirmed'],8);ck('pooled normal',p['monitor']['state'],'NORMAL');ck('five excluded',len(p['excluded']),5);ck('trade independent',p['monitor'],q['monitor']);ck('A unavailable',z['pooled_route']['monitor_states']['A'],'WARMUP');ck('pooled insufficient globally',z['pooled_route']['new_entry_allowed'],[])
    by={x['at']:x for x in z['parallel']}
    for t,ms,rs in [(125,'NORMAL','RECONCILED'),(130,'NORMAL','SHADOW'),(135,'NORMAL','READY'),(140,'NORMAL','NORMAL'),(145,'WARNING','HALTED'),(165,'HALTED','HALTED'),(185,'RECOVERING','HALTED'),(205,'READY','HALTED'),(210,'NORMAL','RECONCILED'),(215,'NORMAL','SHADOW'),(220,'NORMAL','READY'),(225,'NORMAL','NORMAL')]:
        x=by[t];ck(f'monitor {t}',x['monitor_states']['B'],ms);ck(f'recovery {t}',x['recovery']['state'],rs);ck(f'entry {t}',x['new_entry_allowed'],list(SYMBOLS) if rs=='NORMAL' else []);ck(f'exit {t}',x['recovery']['routing']['A']['exit'],'SIMULATED_EXIT_ELIGIBLE')
    ck('local hold B',by[145]['local_policy']['local_holds'],[1]);ck('no cause inferred',by[165]['local_policy']['cause_inferred'],False);ck('ready still blocks',by[205]['new_entry_allowed'],[]);ck('late gap',next(x for x in z['late'] if x['at']==145)['monitor_states']['B'],'HALTED');ck('late no rewrite',next(x for x in z['late'] if x['at']==150)['monitor_states']['B'],'HALTED');ck('shared global',next(x for x in z['shared'] if x['at']==145)['local_policy']['global_hold']);ck('unknown global',next(x for x in z['shared'] if x['at']==150)['local_policy']['global_hold'])
    # Cross product of all monitor state combinations and independently supplied scope.
    for vals in itertools.product(STATES,repeat=3):
        states=dict(zip(SYMBOLS,vals));expected=[i for i,s in enumerate(vals) if s!='NORMAL']
        for feed in ('OK','UNKNOWN','VERIFIED_SHARED_FAILURE'):
            gate=rec.Gate();x=route_tick(gate,125,states,feed);actual=x['local_policy']['local_holds'];want=expected if feed=='OK' else [0,1,2]
            if actual!=want or x['new_entry_allowed'] or x['recovery']['state']!=('RECONCILED' if not want else 'HALTED'):raise AssertionError((states,feed,x))
    ck('648 combinations',True)
    reject('override',lambda:route_tick(rec.Gate(),125,dict.fromkeys(SYMBOLS,'NORMAL'),changes={'alarm_A':'OK'}));reject('missing state',lambda:route_tick(rec.Gate(),125,{'A':'NORMAL'}));reject('unknown state',lambda:route_tick(rec.Gate(),125,dict.fromkeys(SYMBOLS,'OK')))
    train,*_=cal.c.fixtures();m=cal.c.fit(*train);f=cal.freeze(cal.CASES,cal.PROBS,m['sha256']);b=cal.inputs()
    reject('pre-deadline source',lambda:pool(f,f['sha256'],m,m['sha256'],b,120));reject('bad manifest',lambda:pool(f,'0'*64,m,m['sha256'],b,145));missing=cal.freeze(cal.CASES,{'B':8000},m['sha256']);reject('missing forecast cohort',lambda:pool(missing,missing['sha256'],m,m['sha256'],b,145))
    # R54 gap with a missing result: no imputed expiry; history cannot become normal automatically.
    fs,rs=seq.fixture([6,6]);ck('missing outcome stops',seq.monitor(fs,rs[:-1],145)['state'],'HALTED')
    return {'test_count':len(tests),'exhaustive_route_combinations':648,'tests':tests}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(self_test() if a.self_test else example(),sort_keys=True,indent=2))
