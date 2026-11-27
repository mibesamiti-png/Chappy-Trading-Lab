"""R50: synthetic-only paired policy evaluation. No market data or orders.
Illustrative fixtures are engineered, not statistical out-of-sample evidence.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

PLAN = {
    'id': 'R50-SYNTHETIC-01', 'baseline': 'BASE',
    'policies': {'BASE': {'min_signal': 1, 'agreement': False},
                 'STRICT': {'min_signal': 2, 'agreement': False},
                 'AGREE': {'min_signal': 1, 'agreement': True}},
    'discovery_ids': ['D01','D02','D03','D04','D05','D06'],
    'evaluation_ids': ['E01','E02','E03','E04','E05','E06','E07','E08'],
    'costs_bps': [10,20], 'min_selected': 2,
    'criterion': 'complete paired scores, positive delta at both costs, at least two selections',
    'scope': 'engineered synthetic scenario; no fills or live adoption'
}
def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
PLAN_SHA = '488fa4cc417083e57b36d8c3ed33265c650f067a10740f2d7a3990adfce88119'

def require(ok,msg):
    if not ok: raise ValueError(msg)

# Decision-time evidence intentionally excludes subsequent price movement.
def row(i,signal,agree,gate='OK'):
    return {'id':i,'signal':signal,'agree':agree,'gate':gate,'decision_tick':10,'received_tick':9}

def fixture():
    d=[row('D01',2,True),row('D02',3,True),row('D03',1,False),row('D04',1,True),row('D05',0,False),row('D06',3,True,'STALE')]
    e=[row('E01',1,True),row('E02',1,True),row('E03',2,True),row('E04',3,False),row('E05',1,False),row('E06',0,True),row('E07',3,True,'CONFLICT'),row('E08',2,True,'UNKNOWN')]
    moves=dict(zip([x['id'] for x in d+e],[100,80,-90,-60,150,300,100,90,-50,-70,-20,200,400,None]))
    outcomes={i: {'move_bps':m,'observed_tick':20} for i,m in moves.items()}
    return d,e,outcomes

def validate_plan(plan):
    require(digest(plan)==PLAN_SHA,'fixed plan mismatch')

def decide(policy, x):
    require(set(x)=={'id','signal','agree','gate','decision_tick','received_tick'},'decision schema (no future fields)')
    require(type(x['signal']) is int and 0<=x['signal']<=3 and type(x['agree']) is bool,'signal invalid')
    require(type(x['decision_tick']) is int and type(x['received_tick']) is int and 0<=x['received_tick']<=x['decision_tick'],'time invalid')
    require(x['gate'] in {'OK','STALE','CONFLICT','UNKNOWN','UNSUPPORTED','INVALID'},'gate invalid')
    if x['gate']!='OK': return 'BLOCK_'+x['gate']
    if x['signal']<policy['min_signal']: return 'WAIT_SIGNAL'
    if policy['agreement'] and not x['agree']: return 'WAIT_AGREEMENT'
    return 'SELECT'

def freeze_decisions(plan, inputs, split):
    validate_plan(plan)
    require(split in ('discovery','evaluation'),'split invalid')
    ids=[x['id'] for x in inputs]
    require(ids==plan[split+'_ids'] and len(set(ids))==len(ids),'fixed split mismatch')
    decisions={p:{x['id']:decide(rule,x) for x in inputs} for p,rule in plan['policies'].items()}
    return {'split':split,'plan_sha':PLAN_SHA,'inputs_sha':digest(inputs),'decisions':decisions}

def score(plan, inputs, frozen, outcomes):
    validate_plan(plan)
    require(frozen==freeze_decisions(plan,inputs,frozen['split']),'decision tamper')
    require(set(outcomes)==set(x['id'] for x in inputs),'outcome set mismatch')
    for x in inputs:
        y=outcomes[x['id']]
        require(set(y)=={'move_bps','observed_tick'} and type(y['observed_tick']) is int and y['observed_tick']>x['decision_tick'],'outcome timing/schema')
        require(y['move_bps'] is None or type(y['move_bps']) is int,'outcome invalid')
    result={}
    for cost in plan['costs_bps']:
        by={}
        for p,decisions in frozen['decisions'].items():
            counts=Counter(decisions.values()); scores={}; shadows={}
            for i,a in decisions.items():
                m=outcomes[i]['move_bps']
                # Only an eligible, voluntarily skipped opportunity gets a shadow score.
                scores[i]=(None if m is None else m-cost) if a=='SELECT' else 0
                if a.startswith('WAIT_'): shadows[i]=None if m is None else m-cost
            by[p]={'selected':counts['SELECT'],'actions':dict(counts),'selected_unknown':sum(v is None for v in scores.values()),
                   'score_bps_sum':None if any(v is None for v in scores.values()) else sum(scores.values()),
                   'scores':scores,'wait_shadow':shadows,'wait_unknown':sum(v is None for v in shadows.values()),
                   'wait_positive':sum(v is not None and v>0 for v in shadows.values()),'wait_negative':sum(v is not None and v<0 for v in shadows.values())}
        base=by[plan['baseline']]['scores']
        for p,v in by.items():
            pairs={i:(None if base[i] is None or s is None else s-base[i]) for i,s in v['scores'].items()}
            v['paired_delta']=None if any(x is None for x in pairs.values()) else sum(pairs.values())
            v['paired_unknown']=sum(x is None for x in pairs.values())
        result[str(cost)]=by
    return result

def study():
    d,e,all_out=fixture()
    # Freeze both sets of actions before the outcome mapping enters score().
    fd=freeze_decisions(PLAN,d,'discovery'); fe=freeze_decisions(PLAN,e,'evaluation')
    ds=score(PLAN,d,fd,{x['id']:all_out[x['id']] for x in d})
    es=score(PLAN,e,fe,{x['id']:all_out[x['id']] for x in e})
    verdict={}
    for p in ('STRICT','AGREE'):
        def passes(s):
            return all(v[p]['selected']>=PLAN['min_selected'] and v[p]['paired_delta'] is not None and v[p]['paired_delta']>0 for v in s.values())
        verdict[p]={'discovery_pass':passes(ds),'evaluation_pass':passes(es),'live_adoption':False,
                    'status':'SYNTHETIC_PASS_ONLY' if passes(ds) and passes(es) else 'REJECT_OR_UNPROVEN'}
    return {'plan':PLAN,'plan_sha':PLAN_SHA,'discovery_frozen':fd,'evaluation_frozen':fe,'discovery':ds,'evaluation':es,'verdict':verdict,'execution_proven':False}

def self_test():
    import copy
    tests=[]
    def check(name,a,b):
        if a!=b: raise RuntimeError(f'{name}: {a!r} != {b!r}')
        tests.append({'test':name,'result':'PASS'})
    def reject(name,f):
        try: f()
        except (ValueError,KeyError,TypeError): tests.append({'test':name,'result':'PASS'});return
        raise RuntimeError(name+' accepted')
    d,e,o=fixture(); s=study(); fd=s['discovery_frozen'];fe=s['evaluation_frozen']; eo={x['id']:o[x['id']] for x in e}
    check('plan hash',digest(PLAN),PLAN_SHA);check('disjoint splits',bool(set(PLAN['discovery_ids'])&set(PLAN['evaluation_ids'])),False)
    p=copy.deepcopy(PLAN);p['policies']['STRICT']['min_signal']=1;reject('rule tamper',lambda:freeze_decisions(p,e,'evaluation'))
    reject('discovery as evaluation',lambda:freeze_decisions(PLAN,d,'evaluation'));reject('duplicate ids',lambda:freeze_decisions(PLAN,e[:-1]+[e[0]],'evaluation'));reject('missing id',lambda:freeze_decisions(PLAN,e[:-1],'evaluation'));reject('reorder',lambda:freeze_decisions(PLAN,e[::-1],'evaluation'))
    reject('future column',lambda:decide(PLAN['policies']['BASE'],dict(e[0],move_bps=100)));reject('future receipt',lambda:decide(PLAN['policies']['BASE'],dict(e[0],received_tick=11)));reject('bool signal',lambda:decide(PLAN['policies']['BASE'],dict(e[0],signal=True)))
    reject('invalid gate',lambda:decide(PLAN['policies']['BASE'],dict(e[0],gate='MAGIC')))
    for p in PLAN['policies']:
        check(p+' blocks conflict',fe['decisions'][p]['E07'],'BLOCK_CONFLICT');check(p+' blocks unknown',fe['decisions'][p]['E08'],'BLOCK_UNKNOWN');check(p+' blocks stale',fd['decisions'][p]['D06'],'BLOCK_STALE')
    check('base discovery score',s['discovery']['10']['BASE']['score_bps_sum'],-10);check('strict discovery score',s['discovery']['10']['STRICT']['score_bps_sum'],160);check('strict discovery delta',s['discovery']['10']['STRICT']['paired_delta'],170)
    check('base evaluation score',s['evaluation']['10']['BASE']['score_bps_sum'],0);check('strict evaluation score',s['evaluation']['10']['STRICT']['score_bps_sum'],-140);check('strict evaluation delta',s['evaluation']['10']['STRICT']['paired_delta'],-140)
    check('agree eval delta',s['evaluation']['10']['AGREE']['paired_delta'],110);check('strict discovery pass',s['verdict']['STRICT']['discovery_pass'],True);check('strict evaluation fail',s['verdict']['STRICT']['evaluation_pass'],False);check('agree evaluation pass',s['verdict']['AGREE']['evaluation_pass'],True);check('no adoption',any(x['live_adoption'] for x in s['verdict'].values()),False)
    check('shadow positive',s['evaluation']['10']['STRICT']['wait_positive'],3);check('shadow negative',s['evaluation']['10']['STRICT']['wait_negative'],1);check('blocked not shadow', 'E07' in s['evaluation']['10']['STRICT']['wait_shadow'],False)
    bad=copy.deepcopy(fe);bad['decisions']['STRICT']['E01']='SELECT';reject('decision tamper',lambda:score(PLAN,e,bad,eo))
    bad=copy.deepcopy(eo);bad['E01']['observed_tick']=10;reject('outcome at decision',lambda:score(PLAN,e,fe,bad))
    bad=copy.deepcopy(eo);bad.pop('E01');reject('missing outcome record',lambda:score(PLAN,e,fe,bad))
    missing=copy.deepcopy(eo);missing['E01']['move_bps']=None;v=score(PLAN,e,fe,missing)['10'];check('missing select no zero',v['BASE']['score_bps_sum'],None);check('missing pair no zero',v['STRICT']['paired_delta'],None);check('missing wait shadow',v['STRICT']['wait_shadow']['E01'],None)
    check('unknown blocked not selected',s['evaluation']['10']['BASE']['selected_unknown'],0);check('frozen decision outcome independent',freeze_decisions(PLAN,e,'evaluation'),fe)
    check('two cost delta strict',s['evaluation']['20']['STRICT']['paired_delta'],-110);check('two cost delta agree',s['evaluation']['20']['AGREE']['paired_delta'],130)
    check('scope not execution',s['execution_proven'],False)
    return {'test_count':len(tests),'tests':tests}

if __name__=='__main__':
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=ap.parse_args();print(json.dumps(self_test() if a.self_test else study(),sort_keys=True,indent=2))
