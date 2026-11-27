"""R57 synthetic dependency routing. No order interface or market data."""
import argparse, json, hashlib, itertools
from pathlib import Path
ROOT=Path(__file__).parent
R56_SHA='ba1b7346676f5c46ae4ebfe22da6500c74b89004315fd59d38bc0fbafcada893'
if hashlib.sha256((ROOT/'Chappy_Trading_Multi_Monitor_v0.1.py').read_bytes()).hexdigest()!=R56_SHA: raise ValueError('R56 hash mismatch')
# All parents required. Explicit separation of entry, monitoring and exit pathways.
GRAPH={'price':(), 'news':(), 'account':(), 'risk':('account',), 'technical':('price',), 'event':('news',), 'quote':(), 'exit_channel':(), 'alarm_A':(), 'alarm_B':(), 'alarm_C':(), 'strategy_A':('technical','alarm_A'), 'strategy_B':('technical','event','alarm_B'), 'strategy_C':('event','alarm_C'), 'monitor':('quote','account'), 'exit':('monitor','exit_channel'), **{'entry_'+s:('strategy_'+s,'risk','exit') for s in 'ABC'}}
ROOTS=tuple(k for k,v in GRAPH.items() if not v)
# Artificial health status validity, not an actual data latency limit.
TTL=10

def validate(graph):
    seen=set(); active=set()
    def visit(n):
        if n not in graph: raise ValueError('unknown dependency')
        if n in active: raise ValueError('cycle')
        if n in seen:return
        active.add(n)
        for p in graph[n]:visit(p)
        active.remove(n);seen.add(n)
    for n in graph:visit(n)

def health(events, now, graph=GRAPH):
    validate(graph)
    if type(now) is not int or now<0:raise ValueError('now')
    roots={n for n,p in graph.items() if not p}; known={n:[] for n in roots}
    for e in events:
        if set(e)!={'node','event','received','status'} or e['node'] not in roots or e['status'] not in ('OK','FAILED','UNKNOWN') or type(e['event']) is not int or type(e['received']) is not int or not 0<=e['event']<=e['received']:raise ValueError('health event')
        if e['received']<=now:known[e['node']].append(e)
    states={}; reasons={}
    def visit(n):
        if n in states:return
        if n in roots:
            rows=known[n]
            if not rows:status='MISSING'
            else:
                latest=max(r['event'] for r in rows); vals={r['status'] for r in rows if r['event']==latest}
                if len(vals)>1:status='CONFLICT'
                elif now-latest>TTL:status='STALE'
                else:status=next(iter(vals))
            states[n]=status; reasons[n]=[] if status=='OK' else [n+':'+status]
        else:
            for p in graph[n]:visit(p)
            reasons[n]=sorted({r for p in graph[n] for r in reasons[p]});states[n]='BLOCKED' if reasons[n] else 'OK'
    for n in graph:visit(n)
    return states,reasons

def route(events, now, holdings, exit_requested=()):
    if set(holdings)!=set('ABC') or any(type(v) is not int or v<0 for v in holdings.values()):raise ValueError('holdings')
    if not set(exit_requested)<=set('ABC'):raise ValueError('exit requests')
    states,reasons=health(events,now)
    out={}
    for s in 'ABC':
        entry=states['entry_'+s]=='OK'; held=holdings[s]>0; requested=s in exit_requested
        # A blocked strategy is not an automatic liquidation signal. Exit intent must be explicit.
        # If holdings are unverified, never assume a zero supplied balance is authoritative.
        verified=states['account']=='OK'
        monitor='NOT_REQUIRED' if not held and verified else ('AVAILABLE' if states['monitor']=='OK' else ('ESCALATE_UNVERIFIED_EXPOSURE' if not verified else 'MONITOR_BLOCKED_ESCALATE'))
        exit_state='NOT_REQUESTED' if not requested else ('UNVERIFIED_POSITION_ESCALATE' if not verified else ('NO_POSITION' if not held else ('SIMULATED_EXIT_ELIGIBLE' if states['exit']=='OK' else 'EXIT_BLOCKED_ESCALATE')))
        out[s]={'new_entry':'ELIGIBLE' if entry else 'BLOCKED','entry_reasons':reasons['entry_'+s],'monitor':monitor,'exit':exit_state,'exit_reasons':reasons['exit'] if requested else [],'reported_holdings':holdings[s],'holdings_verified':verified}
    return {'as_of':now,'strategies':out,'health':states,'root_reasons':reasons,'actual_orders':False,'cause_inferred':False}

def feed(changes=None,t=100):
    changes=changes or {}; return [{'node':n,'event':t,'received':t,'status':changes.get(n,'OK')} for n in ROOTS]

def example():
    cases={'normal':{},'news_down':{'news':'FAILED'},'price_down':{'price':'FAILED'},'A_alarm':{'alarm_A':'FAILED'},'quote_down':{'quote':'FAILED'},'exit_channel_down':{'exit_channel':'FAILED'},'account_unknown':{'account':'UNKNOWN'},'both_feeds_down':{'price':'FAILED','news':'FAILED'}}
    return {k:route(feed(v),100,{'A':100,'B':100,'C':0},('A','B')) for k,v in cases.items()}

def self_test():
    tests=[]
    def ck(n,v):
        if not v:raise AssertionError(n)
        tests.append({'name':n,'pass':True})
    def rejects(n,fn):
        try:fn()
        except ValueError:ck(n,True)
        else:ck(n,False)
    # Independent explicit dependency sets, exhaustive root-failure combinations.
    required={'A':{'price','alarm_A','account','quote','exit_channel'},'B':{'price','news','alarm_B','account','quote','exit_channel'},'C':{'news','alarm_C','account','quote','exit_channel'}}
    ncases=0
    for bits in itertools.product((False,True),repeat=len(ROOTS)):
        failed={n for n,b in zip(ROOTS,bits) if b}; r=route(feed({n:'FAILED' for n in failed}),100,{'A':100,'B':100,'C':0},('A','B'))['strategies']
        for s in 'ABC':
            if (r[s]['new_entry']=='ELIGIBLE') != (not bool(failed&required[s])):raise AssertionError(('entry',failed,s))
            if set(r[s]['entry_reasons'])!={n+':FAILED' for n in failed&required[s]}:raise AssertionError(('reason',failed,s))
        for s in 'AB':
            expected='UNVERIFIED_POSITION_ESCALATE' if 'account' in failed else 'EXIT_BLOCKED_ESCALATE' if failed&{'quote','exit_channel'} else 'SIMULATED_EXIT_ELIGIBLE'
            if r[s]['exit']!=expected:raise AssertionError(('exit',failed,s))
        ncases+=1
    ck('exhaustive failure masks '+str(ncases),ncases==2**len(ROOTS))
    for n in ROOTS:
        for status in ('FAILED','UNKNOWN'):
            r=route(feed({n:status}),100,{'A':100,'B':100,'C':0})
            ck(n+' '+status,all((r['strategies'][s]['new_entry']=='BLOCKED')==(n in required[s]) for s in 'ABC'))
        e=[x for x in feed() if x['node']!=n]
        ck(n+' missing',health(e,100)[0][n]=='MISSING')
        e=feed(); e.append({'node':n,'event':101,'received':102,'status':'FAILED'})
        ck(n+' future excluded',health(e,101)[0][n]=='OK')
        ck(n+' future now received',health(e,102)[0][n]=='FAILED')
        e=feed(); e.append({'node':n,'event':100,'received':101,'status':'FAILED'})
        ck(n+' conflict',health(e,101)[0][n]=='CONFLICT')
        ck(n+' stale',health(feed(),111)[0][n]=='STALE')
    ck('ttl boundary',health(feed(),110)[0]['price']=='OK')
    e=feed({'news':'FAILED'})+[{'node':'news','event':101,'received':102,'status':'OK'}]
    ck('recovery not before receive',health(e,101)[0]['news']=='FAILED');ck('recovery observed',health(e,102)[0]['news']=='OK')
    e=feed()+[{'node':'news','event':99,'received':101,'status':'FAILED'}]
    ck('late older sample cannot replace newer',health(e,101)[0]['news']=='OK')
    ck('input permutation invariant',route(e,101,dict.fromkeys('ABC',100))==route(e[::-1],101,dict.fromkeys('ABC',100)))
    cases=example();ck('news only entry B,C', [s for s,v in cases['news_down']['strategies'].items() if v['new_entry']=='BLOCKED']==['B','C'])
    ck('news failure preserves exit',cases['news_down']['strategies']['B']['exit']=='SIMULATED_EXIT_ELIGIBLE')
    ck('exit channel failure preserves monitor',cases['exit_channel_down']['strategies']['A']['monitor']=='AVAILABLE')
    ck('quote failure blocks monitor and exit, preserves known holdings',cases['quote_down']['strategies']['A']['exit']=='EXIT_BLOCKED_ESCALATE' and cases['quote_down']['strategies']['A']['monitor']=='MONITOR_BLOCKED_ESCALATE' and cases['quote_down']['strategies']['A']['holdings_verified'])
    ck('unknown account zero not authoritative',cases['account_unknown']['strategies']['C']['monitor']=='ESCALATE_UNVERIFIED_EXPOSURE')
    ck('no automatic liquidation',route(feed({'alarm_A':'FAILED'}),100,dict.fromkeys('ABC',100))['strategies']['A']['exit']=='NOT_REQUESTED')
    ck('no position exit',route(feed(),100,dict.fromkeys('ABC',0),('A',))['strategies']['A']['exit']=='NO_POSITION')
    ck('no real orders',all(not v['actual_orders'] and not v['cause_inferred'] for v in cases.values()))
    rejects('cycle',lambda:validate({'a':('b',),'b':('a',)}));rejects('dangling',lambda:validate({'a':('b',)}));rejects('invalid time',lambda:health(feed(),True));rejects('invalid holding',lambda:route(feed(),100,{'A':-1,'B':0,'C':0}));rejects('unknown request',lambda:route(feed(),100,dict.fromkeys('ABC',0),('D',)));rejects('time reversal',lambda:health(feed()+[{'node':'price','event':105,'received':104,'status':'OK'}],110))
    return {'test_count':len(tests),'exhaustive_failure_masks':ncases,'tests':tests}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(self_test() if a.self_test else example(),sort_keys=True,indent=2))
