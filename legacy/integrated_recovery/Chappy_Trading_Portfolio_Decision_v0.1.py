"""R51 synthetic portfolio decision study. Not connected to orders or market data."""
import argparse, hashlib, itertools, json
from dataclasses import dataclass, replace

def need(ok, msg):
    if not ok: raise ValueError(msg)
def integer(x): return type(x) is int
@dataclass(frozen=True)
class Quote:
    symbol: str
    price: int  # whole yen per share
    stop: int
    qty: int
    score: int  # hypothetical remaining benefit, yen, not calibrated
    received: int
    gate: str = 'OK'
    available: int = 100
    bid: int = 0  # explicit bid; 0 means unavailable
    bid_available: int = 100

# All money internally in hundredths of yen; exact for the assumed fee rates.
def fee(price,qty,bps):
    n=price*qty*100*bps
    need(n%10000==0,'fractional cent')
    return n//10000

def cost(q,bps): return q.price*q.qty*100+fee(q.price,q.qty,bps)
def proceeds(q,bps): return q.bid*q.qty*100-fee(q.bid,q.qty,bps)
def risk(q,bps,new):
    # stress price = stop; this is not a loss bound
    return (q.price-q.stop)*q.qty*100+fee(q.stop,q.qty,bps)+(fee(q.price,q.qty,bps) if new else 0)
def snapshot(rows, now):
    need(integer(now) and now>=0,'time')
    need(len(rows)<=12,'too many candidates')
    out={}
    for q in rows:
        need(type(q) is Quote and isinstance(q.symbol,str) and bool(q.symbol) and q.symbol not in out,'symbol duplicate/invalid')
        need(all(integer(x) for x in (q.price,q.stop,q.qty,q.score,q.received,q.available,q.bid,q.bid_available)),'integer fields')
        need(q.price>q.stop>0 and q.qty>0 and q.qty%100==0 and q.available>=0 and q.bid_available>=0 and 0<=q.bid<=q.price,'quote shape')
        need(q.gate in ('OK','UNKNOWN','STALE','CONFLICT','UNSUPPORTED'),'gate')
        need(0<=q.received<=now,'future or invalid receipt')
        out[q.symbol]=q
    return out

def plan(rows, now, cash, held=None, budget=2_000_000, bps=10, policy='PACK', max_positions=2):
    need(all(integer(x) and x>=0 for x in (cash,budget)) and bps in (10,20) and integer(max_positions) and 1<=max_positions<=12,'account inputs')
    need(policy in ('GREEDY','PACK','HOLD','SWITCH','SWITCH_RAW'),'policy')
    qs=snapshot(rows,now); held={} if held is None else held
    need(type(held) is dict and all(integer(v) and v>0 for v in held.values()),'held quantities')
    h=set(held)
    need(h<=qs.keys(),'missing held quote')
    need(all(qs[s].qty==held[s] for s in h),'held quantity mismatch')
    need(len(h)<=max_positions,'existing position limit')
    def fresh(q): return q.gate=='OK' and now-q.received<=10
    # Missing held data freezes all new allocation; not an automatic liquidation.
    if any(not fresh(qs[s]) or not qs[s].bid for s in h):
        return {'status':'FROZEN_HELD_DATA','buy':[],'sell':[],'held':sorted(h),'cash':cash,'risk':None,'objective':None}
    eligible={s for s,q in qs.items() if s not in h and fresh(q) and q.available>=q.qty and q.score>0}
    def evaluate(target):
        buys=target-h; sells=h-target
        if sells and policy not in ('SWITCH','SWITCH_RAW'): return None
        if any(qs[s].bid_available<qs[s].qty for s in sells): return None
        if len(target)>max_positions or not buys<=eligible: return None
        c=cash+sum(proceeds(qs[s],bps) for s in sells)-sum(cost(qs[s],bps) for s in buys)
        r=sum(risk(qs[s],bps,s in buys) for s in target)
        if c<0 or r>budget: return None
        friction=sum(fee(qs[s].price,qs[s].qty,bps) for s in buys)+sum(fee(qs[s].bid,qs[s].qty,bps)+(qs[s].price-qs[s].bid)*qs[s].qty*100 for s in sells)
        objective=sum(qs[s].score*100 for s in target)-(0 if policy=='SWITCH_RAW' else friction)
        return {'status':'OK','buy':sorted(buys),'sell':sorted(sells),'held':sorted(target),'cash':c,'risk':r,'objective':objective,'friction':friction}
    if policy=='GREEDY':
        target=h.copy(); best=evaluate(target)
        if best is not None:
            for s in sorted(eligible,key=lambda s:(-qs[s].score,s)):
                nxt=evaluate(target|{s})
                if nxt is not None and nxt['objective']>best['objective']: target.add(s);best=nxt
            return best
    else:
        pool=sorted(h|eligible); options=[]
        for n in range(min(len(pool),max_positions)+1):
            for comb in itertools.combinations(pool,n):
                v=evaluate(set(comb))
                if v is not None: options.append(v)
        if options:
            # prefer fewer changes on ties; stable symbol order
            return min(options,key=lambda v:(-v['objective'],len(v['buy'])+len(v['sell']),v['held']))
    return {'status':'NO_FEASIBLE_PLAN','buy':[],'sell':[],'held':sorted(h),'cash':cash,'risk':None,'objective':None}

def terminal(p,quotes,outcomes,bps):
    # separate post-decision artificial exit price; missing is never zero
    if p['status']!='OK' or any(s not in outcomes or outcomes[s] is None for s in p['held']): return None
    q={v.symbol:v for v in quotes}; cash=p['cash']
    for s in p['held']:
        px=outcomes[s];need(integer(px) and px>0,'bad terminal price')
        cash+=px*q[s].qty*100-fee(px,q[s].qty,bps)
    return cash

def fixtures():
    a=Quote('A',6000,5940,100,10000,100, bid=6000)
    b=Quote('B',5000,4950,100,9000,100,bid=5000)
    c=Quote('C',4000,3960,100,8000,100,bid=4000)
    x=Quote('A',6000,5940,100,4000,200,bid=5999)
    y=Quote('B',6000,5940,100,5000,200,bid=5999)
    return (a,b,c),(x,y)

def example():
    pack,sw=fixtures(); initial=100_000_000; out={}
    for bps in (10,20):
        p={k:plan(pack,100,initial,bps=bps,policy=k) for k in ('GREEDY','PACK')}
        # first holding was opened in a separate, earlier synthetic batch
        entry=plan((pack[0],),100,initial,bps=bps,policy='PACK')
        h={k:plan(sw,200,entry['cash'],{'A':pack[0].qty},bps=bps,policy=k,max_positions=1) for k in ('HOLD','SWITCH','SWITCH_RAW')}
        high=(sw[0],replace(sw[1],score=8000))
        highp=plan(high,200,entry['cash'],{'A':pack[0].qty},bps=bps,policy='SWITCH',max_positions=1)
        # Freeze plans before looking at future outcome fixtures.
        out[str(bps)]={'allocation':{k:{'plan':v,'terminal':terminal(v,pack,{'A':6100,'B':5100,'C':4080},bps)} for k,v in p.items()},'switch':{k:{'plan':v,'terminal':terminal(v,sw,{'A':6100,'B':5900},bps)} for k,v in h.items()},'high_score_switch':{'plan':highp,'terminal':terminal(highp,high,{'A':6100,'B':5900},bps)}}
    return {'units':'1/100 yen; score is artificial remaining yen benefit','initial':initial,'cases':out,'execution_proven':False,'adoption':False}

def self_test():
    tests=[]
    def ck(name,actual,expected):
        if actual!=expected: raise RuntimeError(f'{name}: {actual!r} != {expected!r}')
        tests.append({'name':name,'pass':True})
    def reject(name,fn):
        try: fn()
        except ValueError: ck(name,True,True)
        else: ck(name,False,True)
    a,b,c=fixtures()[0]; x,y=fixtures()[1]; money=100_000_000
    def p(rows=(a,b,c),**kw): return plan(rows,100,money,**kw)
    def s(rows=(x,y),**kw): return plan(rows,200,39_940_000,{'A':100},max_positions=1,**kw)
    ck('greedy chooses A',p(policy='GREEDY')['held'],['A']);ck('pack chooses B+C',p()['held'],['B','C'])
    ck('pack exact cash',p()['cash'],9_910_000);ck('pack risk',p()['risk'],1_079_100)
    ck('input order invariant',p((c,b,a)),p());ck('one position',p(max_positions=1)['held'],['A']);ck('risk cap',p(budget=800_000)['held'],['A'])
    ck('no risk capacity',p(budget=0)['held'],[]);ck('two cost capacity',p(bps=20)['cash'],9_820_000)
    for state in ('UNKNOWN','STALE','CONFLICT','UNSUPPORTED'): ck('blocks '+state,p((replace(a,gate=state),))['held'],[])
    ck('stale clock',p((replace(a,received=89),))['held'],[]);ck('fresh boundary',p((replace(a,received=90),))['held'],['A'])
    ck('size insufficient',p((replace(a,available=99),))['held'],[]);ck('zero depth',p((replace(a,available=0),))['held'],[])
    ck('zero score',p((replace(a,score=0),))['held'],[]);ck('negative score',p((replace(a,score=-1),))['held'],[])
    ck('hold',s(policy='HOLD')['held'],['A']);ck('cost aware no switch',s(policy='SWITCH')['held'],['A']);ck('raw switch',s(policy='SWITCH_RAW')['held'],['B'])
    ck('high score switch',s((x,replace(y,score=8000)),policy='SWITCH')['held'],['B']);ck('exit size insufficient',s((replace(x,bid_available=99),replace(y,score=8000)),policy='SWITCH')['held'],['A'])
    ck('held missing quote freezes',s((replace(x,bid=0),y),policy='SWITCH')['status'],'FROZEN_HELD_DATA');ck('held conflict freezes',s((replace(x,gate='CONFLICT'),y),policy='SWITCH')['status'],'FROZEN_HELD_DATA')
    ck('existing risk above budget no feasible',s(policy='HOLD',budget=1)['status'],'NO_FEASIBLE_PLAN')
    reject('duplicate',lambda:p((a,a)));reject('future receipt',lambda:p((replace(a,received=101),)));reject('bad stop',lambda:p((replace(a,stop=6000),)));reject('bad qty',lambda:p((replace(a,qty=99),)));reject('bool numeric',lambda:p((replace(a,score=True),)));reject('crossed quote',lambda:p((replace(a,bid=6001),)));reject('unknown gate',lambda:p((replace(a,gate='MAGIC'),)));reject('missing held row',lambda:s((y,),policy='SWITCH'));reject('held quantity mismatch',lambda:s((replace(x,qty=200),y),policy='SWITCH'));reject('too many rows',lambda:p(tuple(replace(a,symbol=str(i)) for i in range(13))));reject('bad cost',lambda:p(bps=1));reject('bad max positions',lambda:p(max_positions=0))
    e=example()['cases']['10'];ck('pack terminal',e['allocation']['PACK']['terminal'],101_618_200);ck('greedy terminal',e['allocation']['GREEDY']['terminal'],100_879_000)
    ck('switch cost aware better in constructed case',e['switch']['SWITCH']['terminal']>e['switch']['SWITCH_RAW']['terminal'],True);ck('high score switch worse ex post',e['high_score_switch']['terminal']<e['switch']['HOLD']['terminal'],True)
    ck('missing terminal unknown',terminal(p(),(a,b,c),{'B':5100},10),None);reject('bad terminal',lambda:terminal(p(),(a,b,c),{'B':5100,'C':0},10));ck('no trade cash',terminal(p(budget=0),(a,b,c),{},10),money)
    # Independent integer cash reconciliation of every output (fee exact for 100-share lots).
    for bps in (10,20):
        ex=example()['cases'][str(bps)]
        for k,v in ex['allocation'].items():
            sy=v['plan']['held']; expected=money+sum(({'A':6100,'B':5100,'C':4080}[q.symbol]-q.price)*q.qty*100-(q.price+{'A':6100,'B':5100,'C':4080}[q.symbol])*q.qty*bps//100 for q in (a,b,c) if q.symbol in sy)
            ck(f'independent allocation {bps} {k}',v['terminal'],expected)
        for k,v in ex['switch'].items():
            if v['plan']['held']==['A']:
                expected=money+(6100-6000)*100*100-(6000+6100)*100*bps//100
            else:
                expected=money+(5999-6000+5900-6000)*100*100-(6000+5999+6000+5900)*100*bps//100
            ck(f'independent switch {bps} {k}',v['terminal'],expected)
        ck(f'independent high score {bps}',ex['high_score_switch']['terminal'],money+(5999-6000+5900-6000)*100*100-(6000+5999+6000+5900)*100*bps//100)
    return {'test_count':len(tests),'tests':tests}
if __name__=='__main__':
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=ap.parse_args();print(json.dumps(self_test() if a.self_test else example(),sort_keys=True,indent=2))
