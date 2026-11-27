# -*- coding: utf-8 -*-
"""Known-data opportunity cost experiment; no brokerage or live orders.
python Chappy_Trading_Opportunity_Study_v0.1.py CTRL.zip output_dir
Requires Short Study v0.1 and its dependencies in same folder.
"""
import argparse,csv,hashlib,importlib.util,json,math,sys
from pathlib import Path
P=Path(__file__).with_name('Chappy_Trading_Short_Study_v0.1.py')
spec=importlib.util.spec_from_file_location('short01',P); sh=importlib.util.module_from_spec(spec);sys.modules[spec.name]=sh;spec.loader.exec_module(sh)
ls=sh.ls
RULES=('LONG_ONLY','HOLD','LONG_PRIORITY_ENTRY','EXIT_SHORT_FOR_LONG','SWITCH_SHORT_FOR_LONG','SWITCH_EITHER','SWITCH_EITHER_3BARS','EXIT_SHORT_ON_PEER_UP')
KINDS=('REVERSAL_REL','TREND_REL','WEAK_ACCEL')

def signal(f,kind):
    long=sh.base_choose(f,'LONG_REBOUND');k=sh.short_pick(f,kind)
    return long, ([(k,-1,1)] if k else [])

def decide(rule,long,short,key,age,peer):
    if key is None:
        if rule=='LONG_ONLY':return long,'ENTRY'
        if long and short:return (long,'ENTRY') if rule=='LONG_PRIORITY_ENTRY' else ([],None)
        return long or short,'ENTRY'
    if rule in ('HOLD','LONG_ONLY','LONG_PRIORITY_ENTRY'):return [],None
    if rule=='EXIT_SHORT_ON_PEER_UP' and key[1]==-1 and peer>0:return [],'EXIT_PEER'
    if long and short:return [],None
    if key[1]==-1 and long:
        if rule=='EXIT_SHORT_FOR_LONG':return [],'EXIT_FOR_LONG'
        if rule in ('SWITCH_SHORT_FOR_LONG','SWITCH_EITHER') or (rule=='SWITCH_EITHER_3BARS' and age>=3):return long,'SWITCH'
    if key[1]==1 and short and (rule=='SWITCH_EITHER' or (rule=='SWITCH_EITHER_3BARS' and age>=3)):return short,'SWITCH'
    return [],None

def simulate(cache,dates,kind,rule,mult,delay):
    b=ls.Book(mult);daily=[];events=[];cycles=0;blocked=False;size_skips=0
    for d in dates:
        series,eligible=cache[d];first=next(iter(series.values()));start=b.cash;pending=None;entry=None;end=None;forced=None;nf=len(b.fills)
        for i in range(len(first)):
            px={k:v[i].c for k,v in series.items()};ts=first[i].ts.isoformat()
            if forced==i:
                b.flatten(px,ts,'MARGIN');entry=end=pending=forced=None;blocked=True
            if end==i:
                b.flatten(px,ts,'TIME_EXIT');entry=end=None
            if pending and pending[0]==i:
                _,orders,reason=pending;pending=None
                if reason!='ENTRY':
                    assert b.legs;b.flatten(px,ts,reason+'_CLOSE');entry=end=None
                if orders and b.enter(orders,px,ts,reason+'_OPEN' if reason!='ENTRY' else 'ENTRY'):
                    entry=i;end=i+ls.HOLD;cycles+=1
            eq=b.mark(px)
            if b.margin_breach(px) and forced is None:
                b.margin_calls+=1;pending=None;forced=min(i+1,end)
            if blocked or forced is not None or i not in eligible:continue
            f=eligible[i];long,short=signal(f,kind);key=next(iter(b.legs),None)
            if key and long and key[1]==-1:events.append(dict(day=d,ts=ts,event='LONG_WHILE_SHORT',symbol=key[0],target=long[0][0]))
            if key and short and key[1]==1:events.append(dict(day=d,ts=ts,event='SHORT_WHILE_LONG',symbol=key[0],target=short[0][0]))
            if pending:continue
            chosen,reason=decide(rule,long,short,key,i-entry if entry is not None else 0,f[key[0]][2] if key else 0)
            if not reason:continue
            if key and i+1+delay>=end:continue # do not replace a scheduled exit
            orders=ls.size(chosen,px,eq)
            if chosen and not orders:size_skips+=1;continue
            if orders or reason!='ENTRY':
                pending=(i+1+delay,orders,reason)
                events.append(dict(day=d,ts=ts,event='SCHEDULE_'+reason,symbol=key[0] if key else '',target=chosen[0][0] if chosen else ''))
        assert not b.legs and pending is None and end is None and forced is None
        daily.append(dict(day=d,opening=start,closing=b.cash,net=b.cash-start,fills=len(b.fills)-nf))
    ls.audit(b);closes=[x for x in b.fills if x['action']=='CLOSE'];gross=sum(x['gross'] for x in closes)
    assert math.isclose(b.cash-ls.CAP,sum(x['net'] for x in closes),abs_tol=1e-6)
    return dict(kind=kind,rule=rule,mult=mult,delay=delay,pnl=b.cash-ls.CAP,return_pct=(b.cash/ls.CAP-1)*100,max_dd_pct=b.dd*100,cycles=cycles,closed_legs=len(closes),long_closes=sum(x['side']==1 for x in closes),short_closes=sum(x['side']==-1 for x in closes),wins=sum(x['net']>0 for x in closes),gross=gross,cost=gross-(b.cash-ls.CAP),margin_calls=b.margin_calls,rejections=b.rejections,size_skips=size_skips,blocked_long_signals=sum(x['event']=='LONG_WHILE_SHORT' for x in events),blocked_short_signals=sum(x['event']=='SHORT_WHILE_LONG' for x in events),switches=sum(x['reason']=='SWITCH_OPEN' for x in b.fills),early_exits=sum(x['reason'] in ('SWITCH_CLOSE','EXIT_FOR_LONG_CLOSE','EXIT_PEER_CLOSE') for x in b.fills)),daily,b.fills,events

def selftest():
    l=[('A',1,1)];s=[('B',-1,1)]
    assert decide('HOLD',l,[],('B',-1),4,0)==([],None)
    assert decide('EXIT_SHORT_FOR_LONG',l,[],('B',-1),4,0)==([],'EXIT_FOR_LONG')
    assert decide('SWITCH_SHORT_FOR_LONG',l,[],('B',-1),4,0)==(l,'SWITCH')
    assert decide('SWITCH_EITHER',[],s,('A',1),1,0)==(s,'SWITCH')
    assert decide('SWITCH_EITHER_3BARS',[],s,('A',1),2,0)==([],None)
    assert decide('SWITCH_EITHER_3BARS',[],s,('A',1),3,0)==(s,'SWITCH')
    assert decide('SWITCH_EITHER',l,s,('A',1),4,0)==([],None)
    assert decide('LONG_PRIORITY_ENTRY',l,s,None,0,0)==(l,'ENTRY')
    assert decide('EXIT_SHORT_ON_PEER_UP',[],[],('B',-1),1,.1)==([],'EXIT_PEER')
    # End-to-end: short at bar 1, long signal at bar 2, switch at bar 3. Price is only read at execution.
    from types import SimpleNamespace
    from datetime import datetime,timedelta
    t=datetime(2026,1,5,9,10)
    series={k:[SimpleNamespace(c=1000. if k=='B' else 1000.+i,ts=t+timedelta(minutes=i*5)) for i in range(20)] for k in ('A','B')}
    fshort={'A':(50,0,0,0,0,0),'B':(80,-.01,-1,-1,-2,0)};flong={'A':(20,.01,1,0,1,3),'B':(50,0,0,0,0,0)}
    cache={'test':(series,{0:fshort,2:flong})}
    res,_,fills,_=simulate(cache,['test'],'TREND_REL','SWITCH_SHORT_FOR_LONG',1,0)
    assert res['switches']==1 and res['long_closes']==res['short_closes']==1 and fills[1]['ts']==fills[2]['ts']==series['A'][3].ts.isoformat()
    res,_,fills,_=simulate(cache,['test'],'TREND_REL','EXIT_SHORT_FOR_LONG',1,0)
    assert res['early_exits']==1 and res['long_closes']==0 and fills[-1]['ts']==series['A'][3].ts.isoformat()
    return 11

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('archive',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args();legacy=ls.selftest();tests=selftest();data,dates=ls.port.rel.load(a.archive);cache,checks=ls.port.prepare(data,dates)
    summary=[];daily=[];fills=[];events=[];leave=[]
    ls.choose=sh.choose;matches=0
    for kind in KINDS:
        for rule in RULES:
            for mult in (1,2):
                for delay in (0,1):
                    res,ds,fs,es=simulate(cache,dates,kind,rule,mult,delay);summary.append(res)
                    tag=dict(kind=kind,rule=rule,mult=mult,delay=delay)
                    daily.extend(dict(**tag,**x) for x in ds);fills.extend(dict(**tag,**x) for x in fs);events.extend(dict(**tag,**x) for x in es)
                    if rule in ('HOLD','LONG_ONLY'):
                        old,_,oldfs=ls.simulate(cache,dates,'MIX_'+kind if rule=='HOLD' else 'LONG_REBOUND',mult,delay)
                        assert abs(old['pnl']-res['pnl'])<1e-7 and oldfs==fs;matches+=1
                    if mult==2 and delay==0:
                        for d in dates:
                            other,*_=simulate(cache,[x for x in dates if x!=d],kind,rule,mult,delay);leave.append(dict(kind=kind,rule=rule,omitted=d,pnl=other['pnl']))
    a.output.mkdir(exist_ok=False)
    for name,rows in [('summary.csv',summary),('daily.csv',daily),('fills.csv',fills),('events.csv',events),('leave_one_day.csv',leave)]:sh.write(a.output/name,rows)
    m=dict(mode='KNOWN_EXPLORATION_ONLY',archive_sha256=ls.port.rel.ARCHIVE,pilot_plan_sha256=ls.port.rel.PLAN,dates=dates,rules=RULES,kinds=KINDS,accounts=len(summary),audited_fills=len(fills),legacy_tests=legacy,policy_tests=tests,baseline_matches=matches,prefix_checks=checks,leave_runs=len(leave),notes='Single position; fixed 60-minute hold restarted on switch. Existing eligible decision times only, not all intraday bars. Next-bar or extra bar execution, close then open at same modeled close; failed open leaves cash. Signals while holding are counts of candidate times, not independent opportunities. Hypothetical short access and costs; known data only.')
    (a.output/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8');print(json.dumps(m,indent=2))
if __name__=='__main__':main()
