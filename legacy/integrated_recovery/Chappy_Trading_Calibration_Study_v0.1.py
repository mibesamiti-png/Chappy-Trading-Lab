"""Synthetic-only calibration of observed hypothesis outcomes, not trade returns."""
import argparse, hashlib, json
from fractions import Fraction as F
from dataclasses import dataclass, replace, asdict

BINS=5
MIN_RESOLVED=10
FIT_CUTOFF=100
OUTCOMES={'CONFIRMED','REFUTED','EXPIRED_UNRESOLVED','UNKNOWN'}

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

@dataclass(frozen=True)
class Forecast:
    id:str
    time:int
    deadline:int
    p:int # basis points: confirmation conditional on resolved
    regime:str

@dataclass(frozen=True)
class Result:
    id:str
    observed:int
    label:str

def integer(x): return type(x) is int

def validate(fs,rs):
    if len({f.id for f in fs})!=len(fs) or len({r.id for r in rs})!=len(rs): raise ValueError('duplicate id')
    by={f.id:f for f in fs}
    for f in fs:
        if not isinstance(f.id,str) or not f.id or not isinstance(f.regime,str) or not f.regime or not all(map(integer,(f.time,f.deadline,f.p))) or not 0<=f.p<=10000 or not 0<=f.time<f.deadline: raise ValueError('forecast')
    for r in rs:
        if r.id not in by or r.label not in OUTCOMES or not integer(r.observed) or r.observed<=by[r.id].time: raise ValueError('result')
        if r.label=='EXPIRED_UNRESOLVED' and r.observed<by[r.id].deadline: raise ValueError('early expiry')
        if r.label in {'CONFIRMED','REFUTED'} and r.observed>by[r.id].deadline: raise ValueError('late decisive outcome')
    return {r.id:r for r in rs}

def binid(p): return min(BINS-1,p*BINS//10000)
def label(f,by,cutoff):
    if f.time>cutoff: raise ValueError('future forecast')
    r=by.get(f.id)
    if r is None or r.observed>cutoff: return 'OPEN' if cutoff<f.deadline else 'UNKNOWN'
    return r.label

def fit(fs,rs,cutoff=FIT_CUTOFF):
    by=validate(fs,rs)
    if any(f.deadline>cutoff for f in fs): raise ValueError('fit not mature')
    groups={str(i):[0,0] for i in range(BINS)}
    for f in fs:
        y=label(f,by,cutoff)
        if y in {'CONFIRMED','REFUTED'}:
            g=groups[str(binid(f.p))];g[0]+=1;g[1]+=int(y=='CONFIRMED')
    # Laplace smoothing is a fixed design choice, not a confidence interval.
    probs={k:str(F(c+1,n+2)) if n>=MIN_RESOLVED else None for k,(n,c) in groups.items()}
    obj={'cutoff':cutoff,'bins':BINS,'min_resolved':MIN_RESOLVED,'ids':sorted(f.id for f in fs),'groups':groups,'mapping':probs,'forecasts_sha':digest([asdict(f) for f in sorted(fs,key=lambda x:x.id)]),'known_results_sha':digest([asdict(r) for r in sorted(rs,key=lambda x:x.id) if r.observed<=cutoff])}
    return {'model':obj,'sha256':digest(obj)}

def ratio(a,b): return str(F(a,b)) if b else None

def mean(xs): return str(sum(xs,F(0))/len(xs)) if xs else None

def evaluate(fs,rs,frozen,expected_sha,cutoff):
    by=validate(fs,rs); m=frozen['model']
    if digest(m)!=frozen['sha256'] or frozen['sha256']!=expected_sha: raise ValueError('model integrity')
    if m['bins']!=BINS or m['min_resolved']!=MIN_RESOLVED: raise ValueError('model schema')
    if any(f.time<=m['cutoff'] or f.id in m['ids'] for f in fs): raise ValueError('split overlap')
    rows=[]
    for f in sorted(fs,key=lambda x:(x.time,x.id)):
        y=label(f,by,cutoff);p=F(f.p,10000);v=m['mapping'][str(binid(f.p))]
        rows.append({'id':f.id,'regime':f.regime,'bin':binid(f.p),'p':str(p),'calibrated':v,'outcome':y})
    def summarize(rr):
        counts={k:sum(r['outcome']==k for r in rr) for k in sorted(OUTCOMES|{'OPEN'})}
        resolved=[r for r in rr if r['outcome'] in {'CONFIRMED','REFUTED'}]
        paired=[r for r in resolved if r['calibrated'] is not None]
        def score(r,key): return (F(r[key])-int(r['outcome']=='CONFIRMED'))**2
        known=counts['CONFIRMED']+counts['REFUTED']+counts['EXPIRED_UNRESOLVED']; n=len(rr)
        return {'n':n,'counts':counts,'resolved':len(resolved),'confirmed_over_resolved':ratio(counts['CONFIRMED'],len(resolved)),'resolved_over_all':ratio(len(resolved),n),'confirmed_over_all_observed_lower':ratio(counts['CONFIRMED'],n),'confirmed_over_all_observed_upper':ratio(counts['CONFIRMED']+n-known,n),'mean_p_resolved':mean([F(r['p']) for r in resolved]),'raw_brier_resolved':mean([score(r,'p') for r in resolved]),'paired_n':len(paired),'paired_raw_brier':mean([score(r,'p') for r in paired]),'paired_calibrated_brier':mean([score(r,'calibrated') for r in paired]),'calibration_abstained':sum(r['calibrated'] is None for r in rr)}
    return {'overall':summarize(rows),'by_regime':{g:summarize([r for r in rows if r['regime']==g]) for g in sorted({r['regime'] for r in rows})},'by_bin':{str(i):summarize([r for r in rows if r['bin']==i]) for i in range(BINS)},'rows':rows,'scope':'synthetic; confirmation conditional on resolution; no PnL or adoption','live_adoption':False}

def fixtures():
    def group(prefix,t,p,c,r,u,regime,unknown=0):
        labs=['CONFIRMED']*c+['REFUTED']*r+['EXPIRED_UNRESOLVED']*u+['UNKNOWN']*unknown
        fs=[Forecast(f'{prefix}{i:02}',t,t+10,p,regime) for i in range(len(labs))]
        rs=[Result(f.id,t+10,y) for f,y in zip(fs,labs) if y!='UNKNOWN']
        return fs,rs
    def join(*gs): return [f for g in gs for f in g[0]],[r for g in gs for r in g[1]]
    train=join(group('T_H',10,8000,12,4,4,'train'),group('T_L',30,4000,6,10,4,'train'),group('T_S',50,6000,2,1,1,'train'))
    stable=join(group('S_H',110,8000,12,4,4,'stable'),group('S_L',130,4000,6,10,4,'stable'),group('S_S',150,6000,1,2,1,'stable'))
    drift=join(group('D_H',210,8000,4,12,4,'drift'),group('D_L',230,4000,6,10,4,'drift'),group('D_S',250,6000,1,1,1,'drift',1))
    return train,stable,drift

def example():
    train,stable,drift=fixtures(); frozen=fit(*train)
    return {'frozen':frozen,'stable':evaluate(*stable,frozen,frozen['sha256'],300),'drift':evaluate(*drift,frozen,frozen['sha256'],300)}

def self_test():
    import copy
    tests=[]
    def ck(name,a,b):
        if a!=b: raise AssertionError((name,a,b))
        tests.append({'name':name,'pass':True})
    def reject(name,fn):
        try: fn()
        except ValueError: ck(name,True,True)
        else: raise AssertionError(name)
    train,stable,drift=fixtures(); f=fit(*train); h=f['sha256']; ex=example()
    ck('train high',f['model']['mapping']['4'],'13/18');ck('train low',f['model']['mapping']['2'],'7/18');ck('small bin abstain',f['model']['mapping']['3'],None)
    ck('train deterministic order',fit(list(reversed(train[0])),list(reversed(train[1]))),f)
    for p,b in [(0,0),(1999,0),(2000,1),(3999,1),(4000,2),(6000,3),(8000,4),(10000,4)]: ck('bin '+str(p),binid(p),b)
    for name,n,conf in [('stable',16,12),('drift',16,4)]:
        v=ex[name]['by_bin']['4'];ck(name+' high count',v['resolved'],n);ck(name+' high observed',v['confirmed_over_resolved'],ratio(conf,n));ck(name+' unresolved',v['counts']['EXPIRED_UNRESOLVED'],4);ck(name+' denominator',v['resolved_over_all'],'4/5');ck(name+' high raw exact',v['raw_brier_resolved'],str((conf*F(1,5)**2+(n-conf)*F(4,5)**2)/n));ck(name+' high calibrated exact',v['paired_calibrated_brier'],str((conf*F(5,18)**2+(n-conf)*F(13,18)**2)/n));ck(name+' no adoption',ex[name]['live_adoption'],False)
    ck('stable small abstains',ex['stable']['overall']['calibration_abstained'],4);ck('drift unknown',ex['drift']['overall']['counts']['UNKNOWN'],1);ck('unknown not refuted',ex['drift']['by_bin']['3']['counts']['REFUTED'],1);ck('unknown bounds lower',ex['drift']['by_bin']['3']['confirmed_over_all_observed_lower'],'1/4');ck('unknown bounds upper',ex['drift']['by_bin']['3']['confirmed_over_all_observed_upper'],'1/2')
    s=stable[0][0]; r=stable[1][0]
    def ev(fs,rs,cut=300,model=f,sha=h): return evaluate(fs,rs,model,sha,cut)
    reject('duplicate forecast',lambda:ev([s,s],[r]));reject('duplicate label',lambda:ev([s],[r,r]));reject('orphan result',lambda:ev([],[r]));reject('bad probability',lambda:ev([replace(s,p=10001)],[r]));reject('bool probability',lambda:ev([replace(s,p=True)],[r]));reject('invalid label',lambda:ev([s],[replace(r,label='WIN')]));reject('event at forecast',lambda:ev([s],[replace(r,observed=s.time)]));reject('late confirmation',lambda:ev([s],[replace(r,observed=s.deadline+1)]));reject('early expiry',lambda:ev([s],[replace(r,label='EXPIRED_UNRESOLVED',observed=s.deadline-1)]));reject('future forecast',lambda:ev([s],[r],s.time-1));reject('train overlap',lambda:ev(*train));reject('immature fit',lambda:fit(*stable));reject('bad model hash',lambda:ev([s],[r],sha='0'*64))
    bad=copy.deepcopy(f);bad['model']['mapping']['4']='1';reject('model tamper',lambda:ev([s],[r],model=bad));bad['sha256']=digest(bad['model']);reject('rehashed model tamper',lambda:ev([s],[r],model=bad))
    ck('future result hidden',ev([s],[r],s.time+1)['overall']['counts']['OPEN'],1);ck('missing after deadline unknown',ev([s],[])['overall']['counts']['UNKNOWN'],1);ck('missing brier null',ev([s],[])['overall']['raw_brier_resolved'],None);ck('empty ratio null',ev([],[])['overall']['confirmed_over_resolved'],None);ck('empty paired score null',ev([],[])['overall']['paired_calibrated_brier'],None)
    ck('stable paired improves',F(ex['stable']['overall']['paired_calibrated_brier'])<F(ex['stable']['overall']['paired_raw_brier']),True)
    # Drift can make both the raw and calibrated probability badly wrong, even when correction improves Brier.
    ck('drift high overconfident',F(ex['drift']['by_bin']['4']['confirmed_over_resolved'])<F(f['model']['mapping']['4']),True)
    ck('model independent of eval',fit(*train),f)
    return {'test_count':len(tests),'tests':tests}

if __name__=='__main__':
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=ap.parse_args();print(json.dumps(self_test() if a.self_test else example(),sort_keys=True,indent=2))
