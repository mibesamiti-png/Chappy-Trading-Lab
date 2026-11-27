"""Synthetic-only, fixed-cohort calibration monitor; no order or market-data interface."""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
from fractions import Fraction as F
from dataclasses import dataclass, replace
from math import comb

R53_SHA='9d1e42d1e218a2d9f98bab128cfcebbd205b6629911835620800476d1f6d65be'
MODEL_SHA='30e5dbf2e75ef5cfd0ffaaf2ede34a6213201523dacea1353991c3e33b757ab3'
p=Path(__file__).with_name('Chappy_Trading_Calibration_Study_v0.1.py')
if hashlib.sha256(p.read_bytes()).hexdigest()!=R53_SHA: raise ValueError('R53 source integrity')
spec=importlib.util.spec_from_file_location('r53_monitor',p); r53=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r53;spec.loader.exec_module(r53)
PLAN={'cohort_size':10,'resolved_min':8,'grace':5,'gap':'1/4','bad_to_stop':2,'good_to_ready':2,'bin':4,'start':110,'interval':20,'horizon':10,'model_sha':MODEL_SHA}
PLAN_SHA=r53.digest(PLAN)
@dataclass(frozen=True)
class Forecast:
    id:str; time:int; deadline:int; p:int=8000
@dataclass(frozen=True)
class Outcome:
    id:str; event:int; received:int; label:str

def model():
    train,_,_=r53.fixtures(); m=r53.fit(*train)
    if m['sha256']!=MODEL_SHA: raise ValueError('model integrity')
    return F(m['model']['mapping']['4'])

def validate(fs,rs,approvals,cutoff):
    if type(cutoff) is not int or cutoff<0: raise ValueError('cutoff')
    if any(type(t) is not int or t<0 for t in approvals) or list(approvals)!=sorted(set(approvals)): raise ValueError('approval times')
    by={f.id:f for f in fs}
    if len(by)!=len(fs) or len({r.id for r in rs})!=len(rs): raise ValueError('duplicate')
    for f in fs:
        if not isinstance(f.id,str) or not f.id or any(type(v) is not int for v in (f.time,f.deadline,f.p)) or f.time<PLAN['start'] or (f.time-PLAN['start'])%PLAN['interval'] or f.deadline!=f.time+PLAN['horizon'] or not 8000<=f.p<=10000: raise ValueError('forecast')
    for r in rs:
        f=by.get(r.id)
        if f is None or r.label not in {'CONFIRMED','REFUTED','EXPIRED_UNRESOLVED'} or any(type(v) is not int for v in (r.event,r.received)) or not f.time<r.event<=r.received: raise ValueError('outcome')
        if r.label=='EXPIRED_UNRESOLVED' and r.event!=f.deadline: raise ValueError('expiry')
        if r.label!='EXPIRED_UNRESOLVED' and r.event>f.deadline: raise ValueError('late event')
    groups={}
    for f in fs: groups.setdefault(f.time,[]).append(f)
    groups=[sorted(g,key=lambda f:f.id) for _,g in sorted(groups.items())]
    prev=-1
    for g in groups:
        if len(g)!=PLAN['cohort_size'] or len({f.deadline for f in g})!=1 or g[0].time<=prev: raise ValueError('cohort')
        prev=g[0].deadline+PLAN['grace']
    return groups,{r.id:r for r in rs}

def monitor(fs,rs,cutoff,approvals=(),expected_plan_sha=PLAN_SHA):
    if r53.digest(PLAN)!=expected_plan_sha or expected_plan_sha!=PLAN_SHA: raise ValueError('plan integrity')
    groups,by=validate(fs,rs,approvals,cutoff); expected=model()
    timeline=[]; state='WARMUP'; bad=good=0; ai=0; ready_at=None
    def apply_approvals(t):
        nonlocal ai,state,bad,good,ready_at
        while ai<len(approvals) and approvals[ai]<=t:
            a=approvals[ai]; ai+=1; before=state
            # Approval must be strictly after readiness, not simultaneous or pre-authorized.
            if state=='READY' and a>ready_at:
                state='NORMAL'; bad=good=0; ready_at=None
            timeline.append({'time':a,'type':'approval','before':before,'after':state,'accepted':before=='READY' and state=='NORMAL'})
    scheduled={g[0].time:g for g in groups}
    for start in range(PLAN['start'],cutoff-PLAN['horizon']-PLAN['grace']+1,PLAN['interval']):
        t=start+PLAN['horizon']+PLAN['grace'];g=scheduled.get(start,[])
        apply_approvals(t)
        known=[by[f.id].label for f in g if f.id in by and by[f.id].received<=t]
        c=known.count('CONFIRMED'); n=c+known.count('REFUTED'); missing=PLAN['cohort_size']-len(known)
        rate=F(c,n) if n else None
        # Coverage includes unresolved; unknowns do not become failures.
        verdict='DATA_GAP' if missing>0 or n<PLAN['resolved_min'] else 'BAD' if abs(rate-expected)>=F(PLAN['gap']) else 'GOOD'
        before=state
        if verdict=='DATA_GAP':
            state='HALTED';bad=good=0;ready_at=None
        elif verdict=='BAD':
            good=0;ready_at=None
            if state in {'HALTED','RECOVERING','READY'}: state='HALTED';bad=0
            else:
                bad+=1;state='HALTED' if bad>=PLAN['bad_to_stop'] else 'WARNING'
        else:
            bad=0
            if state in {'HALTED','RECOVERING','READY'}:
                if state!='READY':
                    good+=1;state='READY' if good>=PLAN['good_to_ready'] else 'RECOVERING'
                    if state=='READY': ready_at=t
            else: state='NORMAL';good=0
        timeline.append({'time':t,'type':'cohort','confirmed':c,'resolved':n,'unresolved':known.count('EXPIRED_UNRESOLVED'),'missing':missing,'rate':str(rate) if rate is not None else None,'verdict':verdict,'before':before,'after':state})
    apply_approvals(cutoff)
    return {'state':state,'synthetic_probability_available':state=='NORMAL','live_adoption':False,'timeline':timeline,'plan_sha':PLAN_SHA,'expected':str(expected)}

def fixture(counts,late=None):
    fs=[];rs=[]
    for i,c in enumerate(counts):
        t=110+i*20;d=t+10
        for j in range(10):
            f=Forecast(f'C{i:02}-{j:02}',t,d);fs.append(f)
            label='CONFIRMED' if j<c else 'REFUTED' if j<8 else 'EXPIRED_UNRESOLVED'
            rs.append(Outcome(f.id,d,d+(6 if late==(i,j) else 0),label))
    return fs,rs

def alarm_math():
    # Exact probability under independent Bernoulli resolved labels with constant true rate 13/18;
    # excludes coverage failures, serial dependence and selection effects.
    p=model();n=8
    q=sum((F(comb(n,k))*p**k*(1-p)**(n-k) for k in range(n+1) if abs(F(k,n)-p)>=F(PLAN['gap'])),F(0))
    a,b=F(1),F(0) # no previous bad / previous bad, no halt yet
    out={}
    for k in range(1,21):
        a,b=(a+b)*(1-q),a*q
        if k in (2,5,10,20):out[str(k)]=float(1-a-b)
    return {'one_block_bad':float(q),'two_consecutive_stop_by_blocks':out,'scope':'ideal iid conditional on eight resolved per block; no real-market rate'}

def example():
    out={}
    for name,counts,late,approvals in [('stable',[6,6,5,6,7,6],None,()),('drift_recovery',[6,2,2,6,6,6],None,(205,206)),('isolated_bad',[6,2,6,6],None,()),('late_receipt',[6,6,6,6],(1,0),(205,))]:
        fs,rs=fixture(counts,late);out[name]=monitor(fs,rs,125+20*(len(counts)-1),approvals)
    out['false_alarm_model']=alarm_math(); return out

def self_test():
    tests=[]
    def ck(name,a,b):
        if a!=b: raise AssertionError((name,a,b))
        tests.append({'name':name,'pass':True})
    def reject(name,fn):
        try:fn()
        except ValueError:ck(name,1,1)
        else:raise AssertionError(name)
    ex=example()
    def states(x):return [r['after'] for r in x['timeline'] if r['type']=='cohort']
    ck('model',str(model()),'13/18');ck('stable',states(ex['stable']),['NORMAL']*6)
    ck('drift recovery',states(ex['drift_recovery']),['NORMAL','WARNING','HALTED','RECOVERING','READY','NORMAL'])
    ck('isolated bad',states(ex['isolated_bad']),['NORMAL','WARNING','NORMAL','NORMAL'])
    ck('late data stop',states(ex['late_receipt']),['NORMAL','HALTED','RECOVERING','READY'])
    ck('late never rewrites',ex['late_receipt']['timeline'][1]['missing'],1)
    ck('early approval denied',[x['accepted'] for x in ex['drift_recovery']['timeline'] if x['type']=='approval'],[False,True])
    fs,rs=fixture([6,2,2,6,6,6]);t=monitor(fs,rs,225)
    ck('no auto restart',t['state'],'READY');ck('ready unavailable',t['synthetic_probability_available'],False);ck('no live adoption',t['live_adoption'],False)
    for i in range(6):
        cutoff=125+20*i
        a=monitor(fs,rs,cutoff); f=[f for f in fs if f.time<=cutoff]; ids={f.id for f in f};r=[r for r in rs if r.received<=cutoff and r.id in ids]
        ck('prefix '+str(i),a,monitor(f,r,cutoff))
    ck('before first cutoff',monitor(fs,rs,124)['timeline'],[]);ck('warmup not available',monitor(fs,rs,124)['synthetic_probability_available'],False);ck('missing whole cohort',monitor([],[],125)['state'],'HALTED');ck('cohort omitted after normal',monitor(*fixture([6]),145)['state'],'HALTED')
    ck('warning unavailable',monitor(fs,rs,145)['synthetic_probability_available'],False)
    ck('same-time approval denied',monitor(fs,rs,205,(205,))['state'],'READY')
    ck('after readiness approval',monitor(fs,rs,206,(206,))['state'],'NORMAL')
    ck('future approval invisible',monitor(fs,rs,205,(206,))['state'],'READY')
    f,r=fixture([6]);ck('unresolved separate',monitor(f,r,125)['timeline'][0]['unresolved'],2)
    ck('missing not refuted',monitor(f,r[:-1],125)['timeline'][0]['resolved'],8)
    ck('missing forces stop',monitor(f,r[:-1],125)['state'],'HALTED')
    r2=[replace(x,label='EXPIRED_UNRESOLVED') if j<2 else x for j,x in enumerate(r)]
    ck('insufficient resolved',monitor(f,r2,125)['timeline'][0]['verdict'],'DATA_GAP')
    ck('order invariant',monitor(list(reversed(f)),list(reversed(r)),125),monitor(f,r,125))
    reject('duplicate forecast',lambda:monitor(f+[f[0]],r,125));reject('duplicate result',lambda:monitor(f,r+[r[0]],125));reject('orphan',lambda:monitor(f,r+[replace(r[0],id='x')],125));reject('bad time',lambda:monitor(f,[replace(r[0],received=100)]+r[1:],125));reject('late event',lambda:monitor(f,[replace(r[0],event=121,received=121)]+r[1:],125));reject('bad label',lambda:monitor(f,[replace(r[0],label='WIN')]+r[1:],125));reject('wrong bin',lambda:monitor([replace(f[0],p=6000)]+f[1:],r,125));reject('partial cohort',lambda:monitor(f[:-1],r[:-1],125));reject('bad plan',lambda:monitor(f,r,125,expected_plan_sha='x'));reject('approval duplicate',lambda:monitor(f,r,125,(120,120)));reject('approval reversed',lambda:monitor(f,r,125,(121,120)))
    q=alarm_math(); ck('two blocks equals q squared',abs(q['two_consecutive_stop_by_blocks']['2']-q['one_block_bad']**2)<1e-12,True)
    ck('longer horizon greater risk',q['two_consecutive_stop_by_blocks']['20']>q['two_consecutive_stop_by_blocks']['2'],True)
    return {'test_count':len(tests),'tests':tests}

if __name__=='__main__':
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=ap.parse_args();print(json.dumps(self_test() if a.self_test else example(),sort_keys=True,indent=2))
