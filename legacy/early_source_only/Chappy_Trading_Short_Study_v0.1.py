# -*- coding: utf-8 -*-
"""Exploratory short-side comparison on frozen known archive. No live orders.
Usage: python Chappy_Trading_Short_Study_v0.1.py CTRL.zip output_dir
Requires LongShort Study v0.1 and its dependencies alongside.
"""
import argparse,csv,hashlib,importlib.util,json,sys,math
from pathlib import Path
P=Path(__file__).with_name('Chappy_Trading_LongShort_Study_v0.1.py')
spec=importlib.util.spec_from_file_location('longshort01',P);ls=importlib.util.module_from_spec(spec);sys.modules[spec.name]=ls;spec.loader.exec_module(ls)
base_choose=ls.choose
SHORTS=('REVERSAL','REVERSAL_PEER','REVERSAL_REL','TREND','TREND_PEER','TREND_REL','WEAK','WEAK_PEER','WEAK_ACCEL')
RULES=('NO_TRADE','LONG_REBOUND','SHORT_REVERSAL','DIRECTION')+tuple('S_'+x for x in SHORTS)+('MIX_REVERSAL_REL','MIX_TREND_REL','MIX_WEAK_ACCEL')
# Features: previous RSI, last-bar fractional return, other five 30-min mean %,
# relative excess %, own 30-min return %, other five positive count.
def short_pick(f,kind):
    picks=[]
    for k,(r,ch,peer,rel,mom,breadth) in f.items():
        reversal=r>70 and ch<0
        trend=mom<-.3 and ch<0
        weak=rel<-.2 and ch<0
        flags={'REVERSAL':reversal,'REVERSAL_PEER':reversal and peer<0 and breadth<=2,'REVERSAL_REL':reversal and rel<0,
               'TREND':trend,'TREND_PEER':trend and peer<0 and breadth<=2,'TREND_REL':trend and rel<-.2,
               'WEAK':weak,'WEAK_PEER':weak and peer<0,'WEAK_ACCEL':weak and mom<0 and ch*100<mom/6}
        if flags[kind]:picks.append(k)
    if not picks:return None
    idx=0 if kind.startswith('REVERSAL') else 4 if kind.startswith('TREND') else 3
    return min(picks,key=lambda k:((-f[k][idx] if idx==0 else f[k][idx]),k))
def choose(f,rule):
    if rule in ('NO_TRADE','LONG_REBOUND','SHORT_REVERSAL','DIRECTION'):return base_choose(f,rule)
    kind=rule.split('_',1)[1];k=short_pick(f,kind)
    if rule.startswith('S_'):return [(k,-1,1)] if k else []
    if rule.startswith('MIX_'):
        long=base_choose(f,'LONG_REBOUND')
        return [] if k and long else [(k,-1,1)] if k else long
    raise ValueError(rule)
def write(p,rows):
    with p.open('x',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('archive',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
    # First validate untouched legacy engine, then install this research-only policy.
    tests=ls.selftest();data,dates=ls.port.rel.load(a.archive);cache,checks=ls.port.prepare(data,dates)
    assert all(short_pick({'X':(80,-.01,-1.,-1.,-2.,0)},s)=='X' for s in SHORTS)
    assert all(short_pick({'X':(20,.01,1.,1.,2.,5)},s) is None for s in SHORTS)
    assert choose({'X':(80,-.01,-1.,-1.,-2.,0),'Y':(20,.01,1.,1.,2.,5)},'MIX_TREND_REL')==[]
    ls.choose=choose
    summary=[];daily=[];fills=[];leave=[];signals=[]
    for rule in RULES:
        for d in dates:
            eligible=cache[d][1];orders=[choose(f,rule) for f in eligible.values()];signals.append(dict(rule=rule,day=d,eligible=len(eligible),long_signals=sum(any(s==1 for k,s,w in x) for x in orders),short_signals=sum(any(s==-1 for k,s,w in x) for x in orders)))
        for mult in (1,2):
            for delay in (0,1):
                res,ds,fs=ls.simulate(cache,dates,rule,mult,delay)
                assert all(f['side']==-1 for f in fs) if rule.startswith('S_') else True
                summary.append(dict(**res,long_closes=sum(f['action']=='CLOSE' and f['side']==1 for f in fs),short_closes=sum(f['action']=='CLOSE' and f['side']==-1 for f in fs)))
                daily.extend(dict(rule=rule,mult=mult,delay=delay,**x) for x in ds);fills.extend(dict(rule=rule,mult=mult,delay=delay,**x) for x in fs)
                if mult==2 and delay==0:
                    for d in dates:
                        other,_,_=ls.simulate(cache,[x for x in dates if x!=d],rule,mult,delay);leave.append(dict(rule=rule,omitted=d,pnl=other['pnl']))
    assert all(math.isclose(x['pnl'],x['gross']-x['cost'],abs_tol=1e-7) for x in summary)
    assert all(x['pnl']==0 for x in summary if x['rule']=='NO_TRADE')
    a.output.mkdir(exist_ok=False)
    for name,rows in [('summary.csv',summary),('daily.csv',daily),('fills.csv',fills),('leave_one_day.csv',leave),('signals.csv',signals)]:write(a.output/name,rows)
    m=dict(mode='KNOWN_EXPLORATION_ONLY',archive_sha256=ls.port.rel.ARCHIVE,pilot_plan_sha256=ls.port.rel.PLAN,engine_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),dates=dates,rules=RULES,capital=ls.CAP,lot=ls.LOT,gross_limit=ls.GROSS,maintenance=ls.MAINT,borrow_per_open=.0001,holding_bars=ls.HOLD,prefix_checks=checks,legacy_synthetic_tests=tests,policy_synthetic_assertions=19,accounts=len(summary),audited_fills=len(fills),leave_one_day_runs=len(leave),notes='Same known data; exploratory only; no actual borrow access, regulation, execution or real-time latency modeled. Conflict between long and short is skipped. Same fixed horizon and sizing as Round9.')
    (a.output/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8');print(json.dumps(m,indent=2))
if __name__=='__main__':main()
