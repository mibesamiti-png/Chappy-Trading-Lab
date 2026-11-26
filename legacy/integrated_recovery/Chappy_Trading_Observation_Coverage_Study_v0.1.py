"""R79: artificial observation coverage and generalization. No market data or execution."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
P=Path(__file__).with_name('Chappy_Trading_Opportunity_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='f4628d5b6b93c12199bbade62f5423ee6421373ecfc1c52ab9e649b783dd8f9c':raise ValueError('R78 hash')
R=runpy.run_path(str(P)); digest=R['digest']
PLAN={'strata':['A','B'],'training_cutoff':30,'minimum_observed':6,'minimum_coverage':'3/4','cost_bps':20,'notional_yen':100000,'policies':['POOLED','STRATIFIED','COVERAGE','WAIT'],'scope':'artificial fixed opportunity population; no inference of missing outcomes'}
SHA=digest(PLAN)
def st(v):return None if v is None else str(v)
def fit(schedule,observations,cutoff=30):
    ids={}
    for o in schedule:
        if o['id'] in ids or o['group'] not in PLAN['strata'] or type(o['due']) is not int or o['due']<0:raise ValueError('schedule')
        ids[o['id']]=o
    due={k:o for k,o in ids.items() if o['due']<=cutoff}; seen=set(); values={k:set() for k in due}
    for r in observations:
        if type(r['received']) is not int:raise ValueError('receipt')
        if r['received']>cutoff:continue
        if r['id'] in seen or r['opportunity'] not in ids or r['received']<ids[r['opportunity']]['due'] or type(r['bps']) is not int:raise ValueError('observation')
        seen.add(r['id'])
        if r['opportunity'] in values:values[r['opportunity']].add(r['bps'])
    def summarize(keys):
        vals=[next(iter(values[k])) for k in keys if len(values[k])==1]; n=len(keys); m=len(vals); mean=F(sum(vals),m) if m else None
        pick=(int(mean>20)-int(mean< -20)) if m>=6 else 0
        return {'planned':n,'observed':m,'coverage':st(F(m,n)) if n else None,'mean_bps':st(mean),'conflicts':sum(len(values[k])>1 for k in keys),'pick':pick}
    pooled=summarize(list(due)); groups={g:summarize([k for k,o in due.items() if o['group']==g]) for g in PLAN['strata']}
    picks={g:{'POOLED':pooled['pick'],'STRATIFIED':s['pick'],'COVERAGE':s['pick'] if s['coverage'] is not None and F(s['coverage'])>=F(3,4) else 0,'WAIT':0} for g,s in groups.items()}
    return {'pooled':pooled,'groups':groups,'picks':picks}
NAMES=['complete_heterogeneous','complete_homogeneous','selective_B','unseen_B_negative','unseen_B_positive','selective_A']
def fixture(name):
    a=[100]*16+[-100]*4; b=([100]*16+[-100]*4 if name in ('complete_homogeneous','unseen_B_positive') else [100]*4+[-100]*16)
    if name=='selective_A':a=[100]*4+[-100]*16
    schedule=[];obs=[];test=[]
    for g,vs in [('A',a),('B',b)]:
        for i,v in enumerate(vs):
            k=f'TRAIN:{g}:{i:02}'; due=i+3; schedule.append({'id':k,'group':g,'due':due})
            seen=not ((g=='B' and name.startswith('unseen_B')) or (g=='B' and name=='selective_B' and i>=6) or (g=='A' and name=='selective_A' and i>=6))
            if seen:obs.append({'id':'R:'+k,'opportunity':k,'received':due,'bps':v})
            test.append({'id':f'TEST:{g}:{i:02}','group':g,'truth_bps':v,'observable':seen})
    return schedule,obs,test

def evaluate(name):
    schedule,obs,test=fixture(name); model=fit(schedule,obs); rows=[]
    for t in test:
        picks=model['picks'][t['group']]; rows.append(dict(t,picks=picks,payoff={k:(10*(p*t['truth_bps']-20) if p else 0) for k,p in picks.items()}))
    summaries={}
    for k in PLAN['policies']:
        summaries[k]={}
        for g in ['ALL']+PLAN['strata']:
            rs=[r for r in rows if g=='ALL' or r['group']==g]; selected=[r for r in rs if r['picks'][k]]; visible=[r for r in selected if r['observable']]; unseen=len(selected)-len(visible)
            summaries[k][g]={'opportunities':len(rs),'observed_opportunities':sum(r['observable'] for r in rs),'selected':len(selected),'visible_selected':len(visible),'unobserved_selected':unseen,'visible_net_yen':sum(r['payoff'][k] for r in visible),'observable_all_selected_net_yen':sum(r['payoff'][k] for r in visible) if not unseen else None,'artificial_oracle_net_yen':sum(r['payoff'][k] for r in selected)}
    return {'fit':model,'summary':summaries,'records':rows}
def examples():return {'synthetic_only':True,'plan':PLAN,'plan_sha':SHA,'cases':{n:evaluate(n) for n in NAMES}}
def tests():
    checks=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        checks.append({'name':n,'pass':True})
    for n in NAMES:
        s,o,t=fixture(n); e=evaluate(n); m=e['fit']; ck(n+':reverse',m,fit(s[::-1],o[::-1]));ck(n+':future masking',m,fit(s,o+[{'id':'future','opportunity':s[0]['id'],'received':31,'bps':-999}]))
        for g in ['ALL','A','B']:
            keys={r['id'] for r in s if g=='ALL' or r['group']==g}; vals=[r['bps'] for r in o if r['opportunity'] in keys]; mm=m['pooled'] if g=='ALL' else m['groups'][g]
            ck(n+g+':n',mm['planned'],len(keys));ck(n+g+':m',mm['observed'],len(vals));ck(n+g+':coverage',mm['coverage'],str(F(len(vals),len(keys))));ck(n+g+':mean',mm['mean_bps'],str(F(sum(vals),len(vals))) if vals else None)
            pick=int(sum(vals)>20*len(vals))-int(sum(vals)<-20*len(vals)) if len(vals)>=6 else 0;ck(n+g+':pick',mm['pick'],pick)
            if g!='ALL':ck(n+g+':coverage gate',m['picks'][g]['COVERAGE'],pick if 4*len(vals)>=3*len(keys) else 0)
        for r in e['records']:
            for k,p in r['picks'].items():ck(n+r['id']+k+':pay',r['payoff'][k],(p*r['truth_bps']-20)*10 if p else 0)
        for k,ss in e['summary'].items():
            for g,z in ss.items():
                rows=[r for r in t if g=='ALL' or r['group']==g]; chosen=[r for r in rows if m['picks'][r['group']][k]]; vv=[r for r in chosen if r['observable']]; pay=lambda r:10*(m['picks'][r['group']][k]*r['truth_bps']-20)
                ck(n+k+g+':denom',z['opportunities'],len(rows));ck(n+k+g+':selected',z['selected'],len(chosen));ck(n+k+g+':visible',z['visible_selected'],len(vv));ck(n+k+g+':unseen',z['unobserved_selected'],len(chosen)-len(vv));ck(n+k+g+':oracle',z['artificial_oracle_net_yen'],sum(map(pay,chosen)));ck(n+k+g+':observed',z['visible_net_yen'],sum(map(pay,vv)));ck(n+k+g+':unknown',z['observable_all_selected_net_yen'],sum(map(pay,vv)) if len(vv)==len(chosen) else None)
    a=evaluate('unseen_B_negative');b=evaluate('unseen_B_positive');ck('identical training evidence',a['fit'],b['fit']);ck('identical visible evaluation',[(r['id'],r['truth_bps']) for r in a['records'] if r['observable']],[(r['id'],r['truth_bps']) for r in b['records'] if r['observable']]);ck('opposite hidden payoff',a['summary']['POOLED']['ALL']['artificial_oracle_net_yen']<0<b['summary']['POOLED']['ALL']['artificial_oracle_net_yen'],True)
    # Coverage threshold and mean selection independently exercised over synthetic counts.
    s=[{'id':str(i),'group':'A','due':0} for i in range(20)]
    for n in range(21):
        for p in range(n+1):
            o=[{'id':str(i),'opportunity':str(i),'received':0,'bps':100 if i<p else -100} for i in range(n)]; m=fit(s,o); expected=(int(100*(2*p-n)>20*n)-int(100*(2*p-n)<-20*n)) if n>=6 else 0
            ck(f'grid:{n}:{p}:point',m['picks']['A']['STRATIFIED'],expected);ck(f'grid:{n}:{p}:coverage',m['picks']['A']['COVERAGE'],expected if n>=15 else 0)
    s,o,_=fixture('complete_heterogeneous');r=dict(o[0],id='copy');ck('identical repeat',fit(s,o+[r]),fit(s,o));r['bps']=-r['bps'];ck('conflict unknown',fit(s,o+[r])['groups']['A']['observed'],19)
    for bad in [dict(o[0],id='new',opportunity='absent'),dict(o[0],id='new',received=0),o[0]]:
        try:fit(s,o+[bad])
        except ValueError:ck('invalid:'+str(bad),True,True)
        else:raise AssertionError('accepted invalid')
    return {'passed':len(checks),'tests':checks}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
