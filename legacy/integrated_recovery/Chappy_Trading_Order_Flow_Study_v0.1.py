"""R67: artificial best quote observation study; no market input or trading.
OFI definition from Cont, Kukanov, Stoikov (2014), doi:10.1093/jjfinec/nbt003.
A snapshot transition is an event-level OFI only for a complete event feed.
"""
import argparse,json
from fractions import Fraction as F
from itertools import product

def q(seq,bid,ask,bq,aq,event=None,received=None):
    return dict(seq=seq,bid=bid,ask=ask,bq=bq,aq=aq,event=seq if event is None else event,received=seq if received is None else received)

def valid(s):
    if set(s)!= {'seq','bid','ask','bq','aq','event','received'} or any(type(v) is not int for v in s.values()):raise ValueError('schema')
    if not(0<s['bid']<s['ask'] and s['bq']>0 and s['aq']>0 and s['seq']>=0 and 0<=s['event']<=s['received']):raise ValueError('quote')

def ofi(p,n):
    return ((n['bq'] if n['bid']>=p['bid'] else 0)-(p['bq'] if n['bid']<=p['bid'] else 0)-(n['aq'] if n['ask']<=p['ask'] else 0)+(p['aq'] if n['ask']>=p['ask'] else 0))

def f(x):return str(x)

def analyze(rows,cutoff,start_seq,end_seq,*,event_complete):
    if type(cutoff) is not int or type(start_seq) is not int or type(end_seq) is not int or not 0<=start_seq<end_seq or cutoff<0 or type(event_complete) is not bool:raise ValueError('contract')
    seen={}
    for s in rows:
        valid(s)
        if s['received']>cutoff or not start_seq<=s['seq']<=end_seq:continue
        if s['seq'] in seen:raise ValueError('duplicate')
        seen[s['seq']]=s
    if not event_complete:return {'state':'UNSUPPORTED','ofi':None}
    if set(seen)!=set(range(start_seq,end_seq+1)):return {'state':'UNKNOWN','ofi':None}
    a=[seen[i] for i in range(start_seq,end_seq+1)]
    if any(y['event']<x['event'] for x,y in zip(a,a[1:])):raise ValueError('event order')
    terms=[ofi(x,y) for x,y in zip(a,a[1:])];flow=sum(terms)
    depth=sum((F(x['bq']+x['aq'],2) for x in a[:-1]),F(0))/len(terms)
    mid=lambda x:F(x['bid']+x['ask'],2)
    return {'state':'OBSERVED','ofi':flow,'terms':terms,'mean_pre_depth':f(depth),'normalized_ofi':f(flow/depth),'mid_change':f(mid(a[-1])-mid(a[0])),'spread_end':a[-1]['ask']-a[-1]['bid'],'queue_imbalance_end':f(F(a[-1]['bq']-a[-1]['aq'],a[-1]['bq']+a[-1]['aq'])),'interpretation':'DESCRIPTIVE_ONLY','future_prediction':None}

def fixture():
    # Quote-only examples; one common artificial trade stream can occur at the shared best ask before these changes.
    # Different depths and price responses are constructed, not drawn from a stochastic market.
    return {'flat_positive':[q(0,99,101,500,500),q(1,99,101,800,500),q(2,99,101,800,300)],'flat_negative':[q(0,99,101,500,500),q(1,99,101,200,500),q(2,99,101,200,700)],'thin':[q(0,99,101,200,300),q(1,100,102,200,300)],'deep':[q(0,99,101,2000,300),q(1,100,102,200,300)],'positive_no_move':[q(0,99,101,200,500),q(1,99,101,700,500)]}

def examples():
    cases={k:analyze(v,10,0,len(v)-1,event_complete=True) for k,v in fixture().items()}
    return {'synthetic_only':True,'common_bar_example':{'open':101,'high':101,'low':101,'close':101,'volume':100,'note':'same hypothetical trade at shared initial ask, before quote-only sequences; initial snapshots are after that trade'},'cases':cases,'limits':['feed completeness is a declared fixture condition, not independently proven','same-window response is not forecast','order causes, hidden liquidity and future returns are not inferred','OHLCV cannot reconstruct these quote events']}

def tests():
    out=[]
    def ck(name,a,b):
        if a!=b:raise AssertionError((name,a,b))
        out.append({'name':name,'pass':True})
    def reject(name,fn):
        try:fn()
        except ValueError:ck(name,True,True);return
        raise AssertionError(name)
    # Independent piecewise sign oracle, exhaustive price changes and quantities.
    for db,da,b0,a0,b1,a1 in product((-1,0,1),(-1,0,1),(1,7),(2,9),(1,7),(2,9)):
        p=q(0,99,103,b0,a0);n=q(1,99+db,103+da,b1,a1)
        bid={-1:-b0,0:b1-b0,1:b1}[db];ask={-1:-a1,0:a0-a1,1:a0}[da]
        ck('ofi:'+str((db,da,b0,a0,b1,a1)),ofi(p,n),bid+ask)
        # Mirroring book around a fixed price negates OFI.
        def mirror(s):return q(s['seq'],202-s['ask'],202-s['bid'],s['aq'],s['bq'])
        ck('mirror:'+str((db,da,b0,a0,b1,a1)),ofi(mirror(p),mirror(n)),-ofi(p,n))
    ex=examples()['cases'];ck('positive',ex['flat_positive']['ofi'],500);ck('negative',ex['flat_negative']['ofi'],-500)
    ck('flat price',ex['flat_positive']['mid_change'],'0');ck('flat price neg',ex['flat_negative']['mid_change'],'0')
    ck('thin flow',ex['thin']['ofi'],500);ck('deep flow',ex['deep']['ofi'],500);ck('thin norm',ex['thin']['normalized_ofi'],'2');ck('deep norm',ex['deep']['normalized_ofi'],'10/23');ck('thin move',ex['thin']['mid_change'],'1');ck('no move',ex['positive_no_move']['mid_change'],'0')
    rows=fixture()['flat_positive'];run=lambda r,t=10,complete=True:analyze(r,t,0,2,event_complete=complete)
    ck('missing',run(rows[:2])['state'],'UNKNOWN');ck('unsupported',run(rows,complete=False)['state'],'UNSUPPORTED');ck('future hidden',run(rows,1)['state'],'UNKNOWN');ck('arrival reorder',run(rows[::-1]),run(rows));ck('late arrival',run(rows[:2]+[dict(rows[2],received=11)])['state'],'UNKNOWN');ck('late visible',run(rows[:2]+[dict(rows[2],received=11)],11),run(rows));ck('zero not missing',run([q(0,99,101,5,5),q(1,99,101,5,5),q(2,99,101,5,5)])['ofi'],0)
    reject('duplicate',lambda:run(rows+[rows[1]]));reject('crossed',lambda:run([dict(rows[0],ask=98)]+rows[1:]));reject('zero qty',lambda:run([dict(rows[0],aq=0)]+rows[1:]));reject('bool qty',lambda:run([dict(rows[0],aq=True)]+rows[1:]));reject('negative latency',lambda:run(rows[:2]+[dict(rows[2],received=1)]));reject('event reversal',lambda:run(rows[:2]+[dict(rows[2],event=0)]))
    ck('no forecast',ex['thin']['future_prediction'],None)
    return {'passed':len(out),'tests':out}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
