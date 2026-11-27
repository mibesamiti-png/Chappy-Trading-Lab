"""R52 synthetic stress and score uncertainty. No market data or orders.
Place beside the unchanged R51 portfolio module. New long allocations only.
Money: hundredths of yen; score: hypothetical yen benefit; prices: whole yen.
"""
import argparse, hashlib, importlib.util, itertools, json, sys
from pathlib import Path
from dataclasses import replace
from fractions import Fraction
P=Path(__file__).with_name('Chappy_Trading_Portfolio_Decision_v0.1.py')
EXPECTED='c33f248e8122b7a59b6e663e5c009d2988780878d38fbf0f07f3081f0608456c'
if hashlib.sha256(P.read_bytes()).hexdigest()!=EXPECTED: raise RuntimeError('R51 hash mismatch')
spec=importlib.util.spec_from_file_location('r51_verified',P); r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)

def plan(rows, now, cash, budget, scenarios, uncertainty, stress_cap=None, bps=10, max_positions=2, robust=False):
    r.need(all(r.integer(x) and x>=0 for x in (cash,budget)) and (stress_cap is None or r.integer(stress_cap) and stress_cap>=0),'budget')
    r.need(bps in (10,20) and r.integer(max_positions) and 1<=max_positions<=12 and type(robust) is bool,'settings')
    qs=r.snapshot(rows,now); keys=set(qs)
    r.need(type(scenarios) is dict and bool(scenarios),'missing stress set')
    for name, prices in scenarios.items():
        r.need(type(name) is str and bool(name) and type(prices) is dict and set(prices)==keys,'incomplete stress scenario')
        r.need(all(r.integer(p) and p>=0 for p in prices.values()),'invalid stress price')
    r.need(type(uncertainty) is dict and set(uncertainty)==keys and all(r.integer(x) and x>=0 for x in uncertainty.values()),'uncertainty')
    eligible=sorted(s for s,q in qs.items() if q.gate=='OK' and now-q.received<=10 and q.available>=q.qty and q.score>0)
    options=[]
    for n in range(min(len(eligible),max_positions)+1):
        for sy in itertools.combinations(eligible,n):
            entry=sum(r.cost(qs[s],bps) for s in sy); stop=sum(r.risk(qs[s],bps,True) for s in sy)
            if entry>cash or stop>budget: continue
            losses={name:entry-sum(prices[s]*qs[s].qty*100-r.fee(prices[s],qs[s].qty,bps) for s in sy) for name,prices in scenarios.items()}
            worst=max(0,*losses.values())
            nominal=sum(qs[s].score*100-r.fee(qs[s].price,qs[s].qty,bps) for s in sy)
            lower=nominal-sum(uncertainty[s]*100 for s in sy)
            options.append(dict(held=list(sy),cash=cash-entry,stop_risk=stop,scenario_losses=losses,worst_loss=worst,nominal=nominal,lower=lower,eligible=stress_cap is None or worst<=stress_cap))
    chosen=min((v for v in options if v['eligible']),key=lambda v:(-v['lower' if robust else 'nominal'],v['worst_loss'],len(v['held']),v['held']))
    return dict(chosen=chosen,options=options,stress_cap=stress_cap,robust=robust,execution_proven=False,adoption=False)

def fixture():
    rows=tuple(r.Quote(s,4000,3960,100,score,100,bid=4000) for s,score in [('A',12000),('B',11000),('C',9000),('D',7500)])
    scenarios={'auto_shock':{'A':3600,'B':3600,'C':3960,'D':3960},'market_shock':dict.fromkeys('ABCD',3760),'other_shock':{'A':3960,'B':3960,'C':3600,'D':3600}}
    uncertainty={'A':8500,'B':5000,'C':1500,'D':1000}
    return rows,scenarios,uncertainty

def example():
    rows,scenarios,u=fixture(); out={}
    for bps in (10,20):
        out[str(bps)]={k:plan(rows,100,100_000_000,2_000_000,scenarios,u,cap,bps,robust=rob) for k,cap,rob in [('nominal',None,False),('stress',5_500_000,False),('robust',5_500_000,True)]}
    return {'units':'hundredths of yen','synthetic':True,'scenarios':scenarios,'score_uncertainty_yen':u,'results':out,'r51_sha256':EXPECTED}

def self_test():
    rows,sc,u=fixture(); tests=[]
    def ck(name,a,b):
        if a!=b: raise RuntimeError(f'{name}: {a!r} != {b!r}')
        tests.append({'name':name,'pass':True})
    def reject(name,fn):
        try: fn()
        except ValueError: ck(name,True,True)
        else: ck(name,False,True)
    def p(rows=rows,scenarios=sc,uncertainty=u,**kw):
        args=dict(now=100,cash=100_000_000,budget=2_000_000,scenarios=scenarios,uncertainty=uncertainty);args.update(kw);return plan(rows,**args)
    a=p()['chosen']; b=p(stress_cap=5_500_000)['chosen']; c=p(stress_cap=5_500_000,robust=True)['chosen']
    ck('nominal A+B',a['held'],['A','B']);ck('stress A+C',b['held'],['A','C']);ck('robust B+C',c['held'],['B','C'])
    ck('nominal sector shock',a['worst_loss'],8_152_000);ck('diversified market shock',b['worst_loss'],4_955_200)
    ck('same standalone stop risks',a['stop_risk'],b['stop_risk']);ck('cap exact passes',p(stress_cap=b['worst_loss'])['chosen']['held'],['A','C'])
    ck('cap below pair switches to single',len(p(stress_cap=b['worst_loss']-1)['chosen']['held']),1)
    ck('cap zero cash',p(stress_cap=0)['chosen']['held'],[]);ck('cash zero',p(cash=0)['chosen']['held'],[]);ck('stop budget zero',p(budget=0)['chosen']['held'],[])
    ck('all lower scores negative',p(uncertainty=dict.fromkeys('ABCD',50000),robust=True)['chosen']['held'],[])
    ck('one position',p(max_positions=1)['chosen']['held'],['A']);ck('input order',p(rows=rows[::-1]),p());ck('no uncertainty matches nominal',p(uncertainty=dict.fromkeys('ABCD',0),robust=True),p(uncertainty=dict.fromkeys('ABCD',0))|{'robust':True})
    for gate in ['UNKNOWN','STALE','CONFLICT','UNSUPPORTED']:
        ck('gate '+gate,p(rows=(replace(rows[0],gate=gate),*rows[1:]))['chosen']['held'],['B','C'])
    ck('stale clock',p(rows=(replace(rows[0],received=89),*rows[1:]))['chosen']['held'],['B','C'])
    ck('size',p(rows=(replace(rows[0],available=99),*rows[1:]))['chosen']['held'],['B','C'])
    reject('future',lambda:p(rows=(replace(rows[0],received=101),*rows[1:])))
    reject('missing scenario price',lambda:p(scenarios={'x':{'A':3000}}));reject('missing scenarios',lambda:p(scenarios={}))
    reject('extra symbol',lambda:p(scenarios={'x':dict.fromkeys('ABCDE',3000)}));reject('negative price',lambda:p(scenarios={'x':dict.fromkeys('ABCD',-1)}))
    reject('bool price',lambda:p(scenarios={'x':dict.fromkeys('ABCD',True)}));reject('uncertainty missing',lambda:p(uncertainty={'A':0}));reject('uncertainty negative',lambda:p(uncertainty=dict.fromkeys('ABCD',-1)))
    reject('negative cap',lambda:p(stress_cap=-1));reject('bad bps',lambda:p(bps=5));reject('bad positions',lambda:p(max_positions=0));reject('duplicate',lambda:p(rows=(rows[0],*rows)))
    ck('zero exit valid as total loss stress',p(scenarios={'zero':dict.fromkeys('ABCD',0)})['chosen']['worst_loss'],80_080_000)
    ck('upside stress loss floored at zero',p(scenarios={'up':dict.fromkeys('ABCD',4500)})['chosen']['worst_loss'],0)
    # Independent Fraction arithmetic for every feasible option and each scenario, both fee assumptions.
    for bps in (10,20):
        result=p(bps=bps); base=r.plan(rows,100,100_000_000,budget=2_000_000,bps=bps,policy='PACK')
        ck('R51 matching nominal '+str(bps),result['chosen']['held'],base['held'])
        for v in result['options']:
            q=[x for x in rows if x.symbol in v['held']]; mult=Fraction(bps,10000)
            entry=sum(x.price*x.qty*100*(1+mult) for x in q)
            ck(f'cash {bps} {v["held"]}',v['cash'],100_000_000-entry)
            for name,prices in sc.items():
                expected=entry-sum(prices[x.symbol]*x.qty*100*(1-mult) for x in q)
                ck(f'stress {bps} {v["held"]} {name}',v['scenario_losses'][name],expected)
        ck('all options '+str(bps),len(result['options']),11)
    return {'test_count':len(tests),'tests':tests}

if __name__=='__main__':
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=ap.parse_args();print(json.dumps(self_test() if a.self_test else example(),sort_keys=True,indent=2))
