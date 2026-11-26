"""R75: matched evidence comparison; artificial data only, no orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
from copy import deepcopy
P=Path(__file__).with_name('Chappy_Trading_Expected_Value_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='d2bfc1892be0a1893ddc9e86956c8d9654834728782b08b679dbf71e6ad2fa95': raise ValueError('R74 hash')
R=runpy.run_path(str(P)); digest=R['digest']
PLAN={'window_slots':12,'min_resolved':6,'min_each_sign':2,'hit_margin':2,'clip_bps':150,'costs_bps':[20,40],'notional_yen':100000,'horizon_slots':3,'policies':['HIT','POINT','CLIPPED','SENSITIVE','WAIT'],'market_adoption':False}
SHA=digest(PLAN)

def fixtures():
    # Identical multiset for dispersed/grouped; separate stress, no policy-dependent outcomes.
    base=[100,100,-100,0,100,-100,100,0,-100,100,100,-100]*5
    outlier=base.copy(); outlier[12]=1200
    shifted=base[:30]+[-x for x in base[30:]]
    for name,values in [('dispersed',base),('grouped',sorted(base,reverse=True)),('outlier',outlier),('shift',shifted),('delayed',base)]:
        rows=[{'id':f'R{i:03}','slot':i,'eligible':True,'relative_bps':x,'received':i+3+(4 if name=='delayed' and i%3==0 else 0)} for i,x in enumerate(values)]
        rows.extend([{'id':'R060','slot':60,'eligible':True,'relative_bps':None,'received':None},{'id':'R061','slot':61,'eligible':False,'relative_bps':None,'received':None}])
        yield name,rows

def validate(rows):
    for i,r in enumerate(rows):
        if set(r)!={'id','slot','eligible','relative_bps','received'} or r['id']!=f'R{i:03}' or type(r['slot']) is not int or r['slot']!=i or type(r['eligible']) is not bool: raise ValueError('row binding')
        x,t=r['relative_bps'],r['received']
        if x is None:
            if t is not None: raise ValueError('missing')
        elif not r['eligible'] or type(x) is not int or abs(x)>=10000 or type(t) is not int or t<i+3: raise ValueError('result/time')

def sign(x): return (x>0)-(x<0)
def clip(x): return max(-150,min(150,x))
def choose(xs,cost):
    e=R['estimate'](xs,cost); n=len(xs); h=e['positive']-e['negative']; picks={k:0 for k in PLAN['policies']}; stats={'n':n,'hit_margin':h,'mean_bps':None,'clipped_mean_bps':None,'sensitivity_bps':None}
    if e['net'] is not None:
        mean=F(e['net'])+cost; cm=F(sum(map(clip,xs)),n)
        # HIT intentionally ignores magnitude and cost, other conditions identical.
        picks['HIT']=sign(h) if abs(h)>=2 else 0
        picks['POINT']=sign(mean) if abs(mean)>cost else 0
        picks['CLIPPED']=sign(cm) if abs(cm)>cost else 0
        sens={s:F(R['estimate']([s*x for x in xs],cost)['sensitivity']) for s in (1,-1)}
        picks['SENSITIVE']=next((s for s in (1,-1) if sens[s]>0),0)
        stats.update(mean_bps=str(mean),clipped_mean_bps=str(cm),sensitivity_bps={str(s):str(v) for s,v in sens.items()})
    return picks,stats

def decisions(rows,cost):
    validate(rows)
    if type(cost) is not int or cost not in PLAN['costs_bps']: raise ValueError('cost')
    result=[]
    for i,r in enumerate(rows):
        ev=[{k:a[k] for k in ('id','relative_bps','received')} for a in rows[max(0,i-12):i] if a['eligible'] and a['received'] is not None and a['received']<=i]
        p,s=choose([a['relative_bps'] for a in ev],cost)
        if not r['eligible']: p=dict.fromkeys(p,0)
        result.append({'id':r['id'],'slot':i,'eligible':r['eligible'],'evidence':ev,'stats':s,'picks':p})
    return result

def evaluate(rows,cost,d,h,cutoff):
    if type(cutoff) is not int or cutoff<0 or digest(d)!=h or decisions(rows,cost)!=d: raise ValueError('decision binding')
    result=[]
    for r,a in zip(rows,d):
        if r['slot']>cutoff: break
        x=r['relative_bps'] if r['received'] is not None and r['received']<=cutoff else None
        pay={k:None if not r['eligible'] or (s and x is None) else 0 if not s else (s*x-cost)*10 for k,s in a['picks'].items()}
        result.append(dict(a,result_bps=x,payoff_yen=pay))
    return result

def summarize(rs):
    el=[r for r in rs if r['eligible']]; resolved=sum(r['result_bps'] is not None for r in el); out={}
    for k in PLAN['policies']:
        chosen=[r for r in el if r['picks'][k]]; scored=[r for r in chosen if r['result_bps'] is not None]; vals=[r['payoff_yen'][k] for r in scored]; hits=sum(r['picks'][k]*r['result_bps']>0 for r in scored)
        out[k]={'scored':len(scored),'unresolved':len(chosen)-len(scored),'abstained':len(el)-len(chosen),'hits':hits,'accuracy':str(F(hits,len(scored))) if scored else None,'net_yen':sum(vals),'all_selected_net_yen':sum(vals) if len(scored)==len(chosen) else None,'net_per_resolved_opportunity_yen':str(F(sum(vals),resolved)) if resolved else None}
    return {'eligible':len(el),'resolved':resolved,'policies':out}

def dependence():
    # Zero mean +/-100 bps: 12 independent draws vs 4 independent blocks of 3 identical values.
    # Exact enumerate distribution of the sample mean, threshold strict >20bps.
    from itertools import product
    out={}
    for n,repeat in [(12,1),(4,3)]:
        means=[F(sum(xs)*repeat,12) for xs in product([-100,100],repeat=n)]
        out[str(repeat)]={'variance_bps2':str(sum(x*x for x in means)/len(means)),'abs_mean_gt_20':str(F(sum(abs(x)>20 for x in means),len(means))),'draws':n}
    return out

def examples():
    cases={}
    for name,rows in fixtures():
        for cost in PLAN['costs_bps']:
            d=decisions(rows,cost); h=digest(d); rs=evaluate(rows,cost,d,h,100)
            cases[f'{name}:{cost}']={'decision_sha':h,'summary':summarize(rs),'records':rs}
    samples={}
    for name,xs in [('regular',[100,100,100,100,-100,-100,-100,-100,0,0]),('one_outlier',[1200,100,100,100,-100,-100,-100,-100,0,0])]:
        p,s=choose(xs,20);samples[name]={'values_bps':xs,'picks':p,'stats':s}
    return {'synthetic_only':True,'plan':PLAN,'plan_sha':SHA,'cases':cases,'samples':samples,'dependence':dependence(),'market_adoption':False}

def tests():
    out=[]
    def ck(n,a,b):
        if a!=b: raise AssertionError((n,a,b))
        out.append({'name':n,'pass':True})
    def reject(n,fn):
        try: fn()
        except ValueError: ck(n,True,True); return
        raise AssertionError(n)
    for name,rows in fixtures():
        for cost in PLAN['costs_bps']:
            tag=f'{name}:{cost}'; d=decisions(rows,cost); h=digest(d); rs=evaluate(rows,cost,d,h,100); sm=summarize(rs)
            ck(tag+':denom',(sm['eligible'],sm['resolved']),(61,60))
            for i,a in enumerate(d):
                evidence=[r for r in rows[:i] if i-r['slot']<=12 and r['received'] is not None and r['received']<=i]; xs=[r['relative_bps'] for r in evidence]
                ck(tag+f':ids {i}',[r['id'] for r in a['evidence']],[r['id'] for r in evidence]); ck(tag+f':prefix {i}',decisions(rows[:i+1],cost)[-1],a)
                masked=deepcopy(rows)
                for r in masked:
                    if r['received'] is not None and r['received']>i:r['relative_bps']=r['received']=None
                ck(tag+f':mask {i}',decisions(masked,cost)[i],a)
                expected=dict.fromkeys(PLAN['policies'],0)
                if a['eligible'] and len(xs)>=6 and min(sum(x>0 for x in xs),sum(x<0 for x in xs))>=2:
                    hits=sum((1 if x>0 else -1 if x<0 else 0) for x in xs); mean=F(sum(xs),len(xs)); cm=F(sum(x if abs(x)<=150 else 150*sign(x) for x in xs),len(xs))
                    expected.update(HIT=sign(hits) if abs(hits)>=2 else 0,POINT=sign(mean) if abs(mean)>cost else 0,CLIPPED=sign(cm) if abs(cm)>cost else 0)
                    for s in (1,-1):
                        if all(F(s*sum(xs[:j]+xs[j+1:]),len(xs)-1)>cost+20 for j in range(len(xs))):expected['SENSITIVE']=s
                ck(tag+f':policy {i}',a['picks'],expected)
                for k,s in expected.items():
                    v=rows[i]['relative_bps']; oracle=None if not a['eligible'] or (s and v is None) else 0 if not s else F(100000,10000)*(s*v-cost)
                    ck(tag+f':payoff {i} {k}',rs[i]['payoff_yen'][k],oracle)
            for k,p in sm['policies'].items(): ck(tag+':coverage '+k,p['scored']+p['unresolved']+p['abstained'],61)
            reject(tag+':bad hash',lambda:evaluate(rows,cost,d,'0'*64,100))
            ck(tag+':cutoff',[r['result_bps'] for r in evaluate(rows,cost,d,h,20)],[r['relative_bps'] if r['received'] is not None and r['received']<=20 else None for r in rows[:21]])
    x=examples(); ck('matched multiset',sorted(v['relative_bps'] for v in list(fixtures())[0][1][:60]),sorted(v['relative_bps'] for v in list(fixtures())[1][1][:60])); ck('outlier point',x['samples']['one_outlier']['picks']['POINT'],1); ck('outlier clipped',x['samples']['one_outlier']['picks']['CLIPPED'],0)
    ck('dependent variance ratio',F(x['dependence']['3']['variance_bps2'])/F(x['dependence']['1']['variance_bps2']),3)
    return {'passed':len(out),'tests':out}
if __name__=='__main__':
    p=argparse.ArgumentParser(); g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
