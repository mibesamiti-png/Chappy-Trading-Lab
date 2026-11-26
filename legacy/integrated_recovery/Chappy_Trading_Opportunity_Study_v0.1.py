"""R78 artificial opportunity ledger: distinguish observations, opportunities, and sources.
No market input or execution. Bounded missing-result interval is a fixture assumption, not a confidence interval.
"""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
from itertools import product
P=Path(__file__).with_name('Chappy_Trading_Evidence_Sensitivity_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='51dfa84a968c4b87d91a44939d50ca552d28898d572518109b4f9b65eb075e71':raise ValueError('R77 hash')
R=runpy.run_path(str(P)); digest=R['digest']
PLAN={'window':12,'cost_bps':20,'min_observed':6,'min_each_sign':2,'artificial_bound_bps':100,'policies':['ROW','OPPORTUNITY','BOUNDED','WAIT'],'scope':'synthetic fixed planned opportunities only'}
SHA=digest(PLAN)
def st(x):return None if x is None else str(x)
def decision(schedule,obs,slot,now):
    if type(slot) is not int or type(now) is not int or min(slot,now)<0:raise ValueError('clock')
    ids={}
    for o in schedule:
        if o['id'] in ids or type(o['slot']) is not int or o['slot']<0 or type(o['due']) is not int or o['due']<o['slot']+3:raise ValueError('schedule')
        ids[o['id']]=o
    # Only received observations can affect a decision, including conflicts.
    ev={k:[] for k,o in ids.items() if 0<slot-o['slot']<=12 and o['due']<=now}
    seen=set()
    for r in obs:
        if type(r['received']) is not int:raise ValueError('receipt clock')
        if r['received']>now:continue
        if r['id'] in seen or r['opportunity'] not in ids or r['received']<ids[r['opportunity']]['due'] or type(r['bps']) is not int or abs(r['bps'])>100:raise ValueError('observation')
        seen.add(r['id'])
        if r['opportunity'] in ev:ev[r['opportunity']].append(r)
    observed=[]; raw=[]; conflicts=[]; missing=[]
    for k,rs in sorted(ev.items()):
        vals={r['bps'] for r in rs}
        if len(vals)==1:observed.append(next(iter(vals)));raw.extend(r['bps'] for r in rs)
        elif len(vals)>1:conflicts.append(k)
        else:missing.append(k)
    n=len(ev); m=len(observed); unknown=n-m; total=sum(observed)
    mean=F(total,m) if m else None; row=F(sum(raw),len(raw)) if raw else None
    lo=F(total-100*unknown,n) if n else None; hi=F(total+100*unknown,n) if n else None
    def choose(xs,x):return (1 if x>20 else -1 if x< -20 else 0) if len(xs)>=6 and sum(v>0 for v in xs)>=2 and sum(v<0 for v in xs)>=2 else 0
    p=choose(observed,mean); b=p if p and (lo>20 if p==1 else hi< -20) else 0
    return {'slot':slot,'due_opportunities':n,'observed_opportunities':m,'observations':len(raw),'missing':missing,'conflicts':conflicts,'row_mean_bps':st(row),'opportunity_mean_bps':st(mean),'planned_mean_lower_bps':st(lo),'planned_mean_upper_bps':st(hi),'picks':{'ROW':choose(raw,row),'OPPORTUNITY':p,'BOUNDED':b,'WAIT':0}}
def fixture(name):
    # One distinct artificial decision opportunity per slot; three-slot result delay.
    values=([100,-100]*24 if name!='persistent' else [100,100,100,-100]*12)
    schedule=[{'id':f'O{i:02}','slot':i,'due':i+3} for i in range(49)]; obs=[]
    for i,v in enumerate(values):
        if name=='missing_negative' and v<0 and i%4==1:continue
        copies=5 if name=='positive_copies' and v>0 else 1
        delay=4 if name=='late_negative' and v<0 else 0
        for j in range(copies):obs.append({'id':f'R{i:02}:{j}','opportunity':f'O{i:02}','received':i+3+delay,'bps':v})
    return schedule,obs,values
NAMES=['balanced','positive_copies','missing_negative','late_negative','persistent']
def evaluate(name):
    schedule,obs,values=fixture(name); rows=[]
    for i in range(49):
        d=decision(schedule,obs,i,i); x=values[i] if i<len(values) else None
        rows.append(dict(d,truth_bps=x,payoff_yen={k:0 if not p else None if x is None else 10*(p*x-20) for k,p in d['picks'].items()}))
    sm={}
    for k in PLAN['policies']:
        selected=[r for r in rows if r['picks'][k]]; vals=[r['payoff_yen'][k] for r in selected if r['truth_bps'] is not None]
        sm[k]={'scored':len(vals),'unresolved':len(selected)-len(vals),'wait':49-len(selected),'net_yen':sum(vals),'all_selected_net_yen':sum(vals) if len(vals)==len(selected) else None}
    return {'summary':sm,'records':rows}
def examples():return {'plan':PLAN,'plan_sha':SHA,'synthetic_only':True,'cases':{n:evaluate(n) for n in NAMES}}
def tests():
    checks=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        checks.append({'name':n,'pass':True})
    for name in NAMES:
        s,obs,vs=fixture(name); ex=evaluate(name)
        for i,r in enumerate(ex['records']):
            tag=f'{name}:{i}'; due=[o for o in s if i-12<=o['slot']<=i-3]; raw=[]; unique=[]
            for o in due:
                found=[x['bps'] for x in obs if x['opportunity']==o['id'] and x['received']<=i]
                if found:raw+=found;unique.append(found[0])
            d=decision(s,obs,i,i); ck(tag+':prefix',d,decision(s,[x for x in obs if x['received']<=i],i,i));ck(tag+':order',d,decision(s[::-1],obs[::-1],i,i));ck(tag+':due',d['due_opportunities'],len(due));ck(tag+':observed',d['observed_opportunities'],len(unique));ck(tag+':raw',d['observations'],len(raw));ck(tag+':mean',d['opportunity_mean_bps'],st(F(sum(unique),len(unique)) if unique else None));ck(tag+':rawmean',d['row_mean_bps'],st(F(sum(raw),len(raw)) if raw else None))
            # Enumerate all extreme completions (linear mean extrema attained at endpoints).
            if due:
                vals=[F(sum(unique)+sum(z),len(due)) for z in product((-100,100),repeat=len(due)-len(unique))]
                ck(tag+':lower',d['planned_mean_lower_bps'],str(min(vals)));ck(tag+':upper',d['planned_mean_upper_bps'],str(max(vals)))
                truth=F(sum(vs[o['slot']] for o in due),len(due));ck(tag+':contains_truth',min(vals)<=truth<=max(vals),True)
            def oracle(xs):
                if len(xs)<6 or len([v for v in xs if v>0])<2 or len([v for v in xs if v<0])<2:return 0
                return int(sum(xs)>20*len(xs))-int(sum(xs)<-20*len(xs))
            u=oracle(unique); bounded=u if due and u and all(u*v>20 for v in vals) else 0
            ck(tag+':picks',d['picks'],{'ROW':oracle(raw),'OPPORTUNITY':u,'BOUNDED':bounded,'WAIT':0})
            for k,p in d['picks'].items():ck(tag+':payoff:'+k,r['payoff_yen'][k],0 if not p else None if i==48 else (p*vs[i]-20)*10)
        for k,v in ex['summary'].items():ck(name+':denominator:'+k,v['scored']+v['unresolved']+v['wait'],49)
    a=examples()['cases'];ck('copies do not change opportunity decisions',[r['picks']['OPPORTUNITY'] for r in a['balanced']['records']],[r['picks']['OPPORTUNITY'] for r in a['positive_copies']['records']]);ck('missing true bound no false selection',a['missing_negative']['summary']['BOUNDED']['scored'],0)
    s,obs,_=fixture('balanced'); c={'id':'conflict','opportunity':'O00','received':5,'bps':-100};ck('conflict not visible early',decision(s,obs+[c],4,4),decision(s,obs,4,4));ck('conflict visible',decision(s,obs+[c],5,5)['conflicts'],['O00']);ck('conflict removes unique',decision(s,obs+[c],5,5)['observed_opportunities'],2)
    for bad in [dict(obs[0],id='bad',opportunity='unknown'),dict(obs[0],id='bad',received=0),dict(obs[0],id='bad',bps=101),obs[0]]:
        try:decision(s,obs+[bad],10,10)
        except ValueError:ck('reject:'+str(bad),True,True)
        else:raise AssertionError('accepted bad observation')
    return {'passed':len(checks),'tests':checks}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
