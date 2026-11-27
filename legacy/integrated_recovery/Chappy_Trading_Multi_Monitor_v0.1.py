"""Synthetic parallel alarm study, no market input or order interface."""
import argparse, hashlib, importlib.util, itertools, json, math
from collections import defaultdict
from pathlib import Path
from fractions import Fraction as F
ROOT=Path(__file__).parent
R55=ROOT/'Chappy_Trading_Alarm_Study_v0.1.py'
R55_SHA='97f2f063d1b74af6f3365b55f34b7df66c257d6eed8ea49cb8cf632e05ab9876'
if hashlib.sha256(R55.read_bytes()).hexdigest()!=R55_SHA: raise ValueError('R55 hash')
spec=importlib.util.spec_from_file_location('alarm55',R55); alarm=importlib.util.module_from_spec(spec);spec.loader.exec_module(alarm)

def bad(p): return sum(q for k,q in enumerate(alarm.pmf(p)) if alarm.flag(k,'two-sided'))

def masks(qs,share):
    if not 1<=len(qs)<=6 or not 0<=share<=1 or any(not 0<=q<=1 for q in qs): raise ValueError('probabilities')
    # Each group: independently sampled binary flags, or one common uniform draw.
    n=len(qs); out=[]
    for m in range(1<<n):
        indep=math.prod(q if m>>i&1 else 1-q for i,q in enumerate(qs))
        upper=min((q for i,q in enumerate(qs) if m>>i&1),default=1)
        lower=max((q for i,q in enumerate(qs) if not m>>i&1),default=0)
        w=(1-share)*indep+share*max(0,upper-lower)
        if w: out.append((m,w))
    return out

def advance(prev,halted,flags,full):
    new=prev&flags&~halted
    h=halted|new
    return flags&(full^h),h

def distribution(qs,share,groups):
    if type(groups) is not int or not 1<=groups<=100: raise ValueError('groups')
    weights=masks(qs,share); full=(1<<len(qs))-1
    states={(0,0):1.0}; rows=[]
    for t in range(1,groups+1):
        nxt=defaultdict(float)
        for (prev,halted),mass in states.items():
            for flags,w in weights: nxt[advance(prev,halted,flags,full)]+=mass*float(w)
        states=nxt
        hist=[0.0]*(len(qs)+1)
        for (_,h),mass in states.items():hist[h.bit_count()]+=mass
        rows.append({'group':t,'any':sum(hist[1:]),'quorum':sum(hist[3:]),'all':hist[-1], 'expected_local':sum(i*x for i,x in enumerate(hist)), 'strategy_0':sum(m for (_,h),m in states.items() if h&1),'other_any':sum(m for (_,h),m in states.items() if h&~1),'hist':hist})
    return rows

def route(states,feed):
    # Inputs are alarm statuses and explicitly verified scope, not inferred causality.
    if not states or any(s not in ('NORMAL','ALARM','GAP') for s in states) or feed not in ('OK','VERIFIED_SHARED_FAILURE','UNKNOWN'):raise ValueError('scope')
    if feed!='OK':return {'global_hold':True,'local_holds':list(range(len(states))),'reason':'SHARED_FAILURE' if feed=='VERIFIED_SHARED_FAILURE' else 'SCOPE_UNKNOWN','cause_inferred':False}
    ids=[i for i,s in enumerate(states) if s!='NORMAL']
    return {'global_hold':False,'local_holds':ids,'reason':'LOCAL_OR_UNATTRIBUTED' if ids else 'NORMAL','cause_inferred':False,'escalate_review':len(ids)>=3}

def example():
    q=bad(F(13,18)); shift=bad(F(9,20)); rows=[]
    for c in (F(0),F(1,4),F(1)):
        for label,qs in [('unchanged',[q]*6),('one_shift',[shift]+[q]*5),('all_shift',[shift]*6)]:
            res=distribution(qs,c,20)
            for t in (5,10,20): rows.append({'case':label,'shared_flag_probability':str(c),**res[t-1]})
    return {'baseline_bad':float(q),'shift_bad':float(shift),'rows':rows,'routing':{k:route(s,f) for k,s,f in [('one_alarm',['NORMAL','ALARM']+['NORMAL']*4,'OK'),('three_alarms',['ALARM']*3+['NORMAL']*3,'OK'),('shared_failure',['NORMAL']*6,'VERIFIED_SHARED_FAILURE'),('unknown_scope',['NORMAL']*6,'UNKNOWN')]},'live_adoption':False}

def self_test():
    tests=[]
    def ck(n,v):
        if not v:raise AssertionError(n)
        tests.append({'name':n,'pass':True})
    def close(a,b):return abs(a-b)<1e-11
    q=bad(F(13,18)); shifted=bad(F(9,20))
    for n in (1,2,3,6):
        for c in (F(0),F(1,4),F(1)):
            qs=[shifted]+[q]*(n-1); w=masks(qs,c)
            ck(f'mass {n} {c}',sum(p for _,p in w)==1)
            for i in range(n):ck(f'marginal {n} {c} {i}',sum(p for m,p in w if m>>i&1)==qs[i])
    for c in (F(0),F(1,4),F(1)):
        qs=[q,shifted];w=masks(qs,c); hist=[F(0)]*3
        for seq in itertools.product(w,repeat=4):
            halted=[False]*2; prev=[False]*2; mass=F(1)
            for m,p in seq:
                mass*=p
                for i in range(2):
                    cur=bool(m>>i&1); halted[i]|=prev[i] and cur;prev[i]=cur
            hist[sum(halted)]+=mass
        r=distribution(qs,c,4)[-1];ck('independent enumeration '+str(c),all(close(float(a),b) for a,b in zip(hist,r['hist'])))
    _,s=alarm.distribution([F(13,18)]*20,F(0),'R54_2_OF_2');p=1-s[-1]
    for n in (1,2,3,6):
        r=distribution([q]*n,F(0),20)[-1];ck('independent any '+str(n),close(r['any'],1-(1-p)**n));ck('independent expected '+str(n),close(r['expected_local'],n*p));ck('independent all '+str(n),close(r['all'],p**n))
        r=distribution([q]*n,F(1),20)[-1];ck('shared any '+str(n),close(r['any'],p));ck('shared all '+str(n),close(r['all'],p))
    for r in example()['rows']:
        ck('mass '+r['case']+r['shared_flag_probability']+str(r['group']),close(sum(r['hist']),1));ck('bounds '+r['case']+r['shared_flag_probability']+str(r['group']),0<=r['all']<=r['quorum']+1e-12<=r['any']+2e-12<=1+3e-12)
    ck('local',route(['NORMAL','ALARM'],'OK')['local_holds']==[1]);ck('quorum not cause',not route(['ALARM']*3,'OK')['global_hold']);ck('escalation',route(['ALARM']*3,'OK')['escalate_review']);ck('shared failure',route(['NORMAL']*6,'VERIFIED_SHARED_FAILURE')['global_hold']);ck('unknown',route(['NORMAL']*6,'UNKNOWN')['global_hold']);ck('gap',route(['GAP','NORMAL'],'OK')['local_holds']==[0])
    return {'test_count':len(tests),'tests':tests}

if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(self_test() if a.self_test else example(),sort_keys=True,indent=2))
