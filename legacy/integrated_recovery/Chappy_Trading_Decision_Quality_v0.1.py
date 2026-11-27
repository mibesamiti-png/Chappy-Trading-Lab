"""Synthetic research only. No market feed, order routing or strategy optimization.
Python 3.10+. Run with --self-test. Time values are integer seconds on one clock.
"""
from dataclasses import dataclass, replace
from enum import Enum
import argparse, json
from math import isfinite

class Status(str, Enum):
    OK='OK'; UNKNOWN='UNKNOWN'; STALE='STALE'; UNSUPPORTED='UNSUPPORTED'; INVALID='INVALID'; FUTURE='FUTURE'

@dataclass(frozen=True)
class Observation:
    value: float | None
    event: int | None
    received: int | None

@dataclass(frozen=True)
class Policy:
    requirements: tuple[str,...]
    max_age: int
    # Research assumptions, not calibrated market thresholds.
    max_spread: float=2.0
    min_depth: float=100.0

BAR=Policy(('close','volume'),600)
BOOK=Policy(('close','bid','ask','bid_depth','ask_depth'),10)
TAPE=Policy(('close','trade_volume','trade_price'),10)
FIELD_NAMES=frozenset(('close','volume','bid','ask','bid_depth','ask_depth','trade_volume','trade_price'))
BARS=frozenset(('close','volume'))
ALL=FIELD_NAMES

@dataclass(frozen=True)
class Decision:
    time: int
    action: str
    hypothesis: str
    invalidation: str
    risk_limit: float | None
    reason: str
    requested_qty: float=100.0


def observe(name, obs, supported, now, age):
    if name not in supported: return Status.UNSUPPORTED
    if obs is None or obs.value is None or obs.event is None or obs.received is None: return Status.UNKNOWN
    if (type(obs.event) is not int or type(obs.received) is not int or
        type(now) is not int or obs.event < 0 or obs.received < obs.event): return Status.INVALID
    if obs.received>now or obs.event>now: return Status.FUTURE
    if type(obs.value) not in (int,float) or not isfinite(obs.value): return Status.INVALID
    if obs.value<0 or (name in ('close','bid','ask','trade_price') and obs.value==0): return Status.INVALID
    if now-obs.event>age: return Status.STALE
    return Status.OK


def evaluate(policy, data, supported, decision):
    states={k:observe(k,data.get(k),supported,decision.time,policy.max_age) for k in policy.requirements}
    blockers=[f'{k}:{v.value}' for k,v in states.items() if v!=Status.OK]
    process=[]
    if decision.action not in ('BUY','SELL','WAIT'): process.append('INVALID_ACTION')
    if not decision.reason.strip(): process.append('REASON_MISSING')
    if decision.action in ('BUY','SELL'):
        if not decision.hypothesis.strip(): process.append('HYPOTHESIS_MISSING')
        if not decision.invalidation.strip(): process.append('INVALIDATION_MISSING')
        if type(decision.risk_limit) not in (int,float) or not isfinite(decision.risk_limit) or decision.risk_limit<=0: process.append('RISK_LIMIT_INVALID')
        if type(decision.requested_qty) not in (int,float) or not isfinite(decision.requested_qty) or decision.requested_qty<=0: process.append('QUANTITY_INVALID')
    if all(states.get(k)==Status.OK for k in ('bid','ask')):
        if data['bid'].value>=data['ask'].value: blockers.append('LOCKED_OR_CROSSED_BOOK')
        elif data['ask'].value-data['bid'].value>policy.max_spread: blockers.append('SPREAD_TOO_WIDE')
    if decision.action in ('BUY','SELL') and 'QUANTITY_INVALID' not in process:
        k='ask_depth' if decision.action=='BUY' else 'bid_depth'
        if states.get(k)==Status.OK and data[k].value<max(policy.min_depth,decision.requested_qty): blockers.append('DISPLAYED_DEPTH_INSUFFICIENT')
    if decision.action=='WAIT':
        quality='NONCOMPLIANT' if process else 'PROCEDURE_COMPLIANT_WAIT'
        gate='NO_TRADE'
    else:
        quality='NONCOMPLIANT' if process or blockers else 'PROCEDURE_COMPLIANT'
        gate='BLOCK' if process or blockers else 'RESEARCH_ELIGIBLE'
    return {'states':{k:v.value for k,v in states.items()},'blockers':blockers,'procedure_errors':process,'gate':gate,'quality':quality,
            'execution_proven':False,'reason':decision.reason}


def review(result, pnl):
    if type(pnl) not in (int,float) or not isfinite(pnl): raise ValueError('invalid synthetic pnl')
    if result['gate']=='NO_TRADE' and pnl!=0: raise ValueError('WAIT cannot have trade pnl')
    # Outcome is external synthetic evidence, not an actual fill or an approved trade.
    return {'quality':result['quality'],'outcome':'PROFIT' if pnl>0 else 'LOSS' if pnl<0 else 'FLAT','pnl':pnl}


def self_test():
    d=Decision(1000,'BUY','price recovery','break below low',1000,'synthetic',100)
    good={k:Observation(v,995,997) for k,v in {'close':100,'volume':0,'bid':99,'ask':100,'bid_depth':100,'ask_depth':100,'trade_volume':100,'trade_price':100}.items()}
    cases=[]
    def check(name, value, expected):
        if value!=expected: raise RuntimeError(f'{name}: {value!r} != {expected!r}')
        cases.append({'test':name,'result':'PASS'})
    def ev(p=BOOK,data=good,s=ALL,dec=d): return evaluate(p,data,s,dec)
    def altered(k,o): return {**good,k:o}
    check('book eligible',ev()['gate'],'RESEARCH_ELIGIBLE')
    check('bar eligible with zero volume as observation',ev(BAR,s=BARS)['gate'],'RESEARCH_ELIGIBLE')
    check('zero volume known',ev(BAR,s=BARS)['states']['volume'],'OK')
    check('book unavailable blocks',ev(s=BARS)['gate'],'BLOCK')
    check('unsupported distinct',ev(s=BARS)['states']['bid'],'UNSUPPORTED')
    check('tape unavailable blocks',ev(TAPE,s=BARS)['gate'],'BLOCK')
    check('tape eligible',ev(TAPE)['gate'],'RESEARCH_ELIGIBLE')
    check('absent known field',ev(data={k:v for k,v in good.items() if k!='bid'})['states']['bid'],'UNKNOWN')
    check('null value',ev(data=altered('bid',Observation(None,995,997)))['states']['bid'],'UNKNOWN')
    check('null received',ev(data=altered('bid',Observation(99,995,None)))['states']['bid'],'UNKNOWN')
    check('future received',ev(data=altered('bid',Observation(99,995,1001)))['states']['bid'],'FUTURE')
    check('future event',ev(data=altered('bid',Observation(99,1001,1002)))['states']['bid'],'FUTURE')
    check('reversed time',ev(data=altered('bid',Observation(99,997,995)))['states']['bid'],'INVALID')
    check('stale even recent receipt',ev(data=altered('bid',Observation(99,980,999)))['states']['bid'],'STALE')
    check('age boundary',ev(data=altered('bid',Observation(99,990,999)))['states']['bid'],'OK')
    check('one second stale',ev(data=altered('bid',Observation(99,989,999)))['states']['bid'],'STALE')
    check('negative depth',ev(data=altered('ask_depth',Observation(-1,995,997)))['states']['ask_depth'],'INVALID')
    check('zero depth is known',ev(data=altered('ask_depth',Observation(0,995,997)))['states']['ask_depth'],'OK')
    check('zero depth blocks',ev(data=altered('ask_depth',Observation(0,995,997)))['gate'],'BLOCK')
    check('nan invalid',ev(data=altered('bid',Observation(float('nan'),995,997)))['states']['bid'],'INVALID')
    check('bool invalid',ev(data=altered('bid',Observation(True,995,997)))['states']['bid'],'INVALID')
    check('zero price invalid',ev(data=altered('bid',Observation(0,995,997)))['states']['bid'],'INVALID')
    check('wide spread',ev(data=altered('ask',Observation(103,995,997)))['blockers'],['SPREAD_TOO_WIDE'])
    check('locked book',ev(data=altered('ask',Observation(99,995,997)))['blockers'],['LOCKED_OR_CROSSED_BOOK'])
    check('crossed book',ev(data=altered('ask',Observation(98,995,997)))['gate'],'BLOCK')
    check('buy side depth',ev(data=altered('ask_depth',Observation(99,995,997)))['gate'],'BLOCK')
    check('sell side depth',ev(data=altered('bid_depth',Observation(99,995,997)),dec=replace(d,action='SELL'))['gate'],'BLOCK')
    check('quantity exceeds depth',ev(dec=replace(d,requested_qty=101))['gate'],'BLOCK')
    check('missing hypothesis',ev(dec=replace(d,hypothesis=''))['gate'],'BLOCK')
    check('missing invalidation',ev(dec=replace(d,invalidation=''))['gate'],'BLOCK')
    check('missing risk limit',ev(dec=replace(d,risk_limit=None))['gate'],'BLOCK')
    check('invalid risk nan',ev(dec=replace(d,risk_limit=float('nan')))['gate'],'BLOCK')
    check('missing reason',ev(dec=replace(d,reason=''))['gate'],'BLOCK')
    check('invalid quantity',ev(dec=replace(d,requested_qty=-1))['gate'],'BLOCK')
    check('unknown action',ev(dec=replace(d,action='OTHER'))['gate'],'BLOCK')
    wait=ev(s=BARS,dec=replace(d,action='WAIT',hypothesis='',invalidation='',risk_limit=None,reason='book unavailable'))
    check('wait no trade',wait['gate'],'NO_TRADE')
    check('wait with missing data compliant',wait['quality'],'PROCEDURE_COMPLIANT_WAIT')
    check('wait requires reason',ev(dec=replace(d,action='WAIT',reason=''))['quality'],'NONCOMPLIANT')
    check('profitable violation still violation',review(ev(s=BARS),100)['quality'],'NONCOMPLIANT')
    check('loss does not rewrite compliance',review(ev(),-100)['quality'],'PROCEDURE_COMPLIANT')
    check('profit outcome',review(ev(),100)['outcome'],'PROFIT')
    check('loss outcome',review(ev(),-100)['outcome'],'LOSS')
    check('wait flat',review(wait,0)['outcome'],'FLAT')
    try: review(wait,100)
    except ValueError: check('wait pnl contradiction rejected',True,True)
    else: check('wait pnl contradiction rejected',False,True)
    check('eligibility is not proof of execution',ev()['execution_proven'],False)
    check('bar eligibility is not execution proof',ev(BAR,s=BARS)['execution_proven'],False)
    return {'test_count':len(cases),'tests':cases,'scope':'synthetic only; no market data or live orders'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--self-test',action='store_true'); a=p.parse_args()
    if not a.self_test: p.error('research prototype: use --self-test')
    print(json.dumps(self_test(),ensure_ascii=False,indent=2))
