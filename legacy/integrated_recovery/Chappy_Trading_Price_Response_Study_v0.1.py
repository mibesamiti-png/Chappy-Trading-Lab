"""R68: fixed-window synthetic OHLCV response hypotheses. No market input or orders."""
import argparse, json, hashlib
from fractions import Fraction as F
from itertools import product
from copy import deepcopy

PLAN={'baseline_bars':3,'bar_seconds':300,'volume_ratio':'2','weak_body_max':'1/4','strong_body_min':'3/4','horizon_bars':3,'close_move_threshold':'1/100','target':'future close relative to signal close; not return on executable trade'}

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
PLAN_SHA=digest(PLAN)
def bar(i,o,h,l,c,v,received=None):
    return dict(i=i,open=o,high=h,low=l,close=c,volume=v,received=(i+1)*300 if received is None else received)
def valid(b):
    if set(b)!={'i','open','high','low','close','volume','received'} or any(type(v) is not int for v in b.values()):raise ValueError('schema')
    if not (b['i']>=0 and 0<b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high'] and b['volume']>=0 and b['received']>=(b['i']+1)*300):raise ValueError('bar')
def window(rows,cutoff,start,end):
    if type(cutoff) is not int or cutoff<0 or type(start) is not int or type(end) is not int or not 0<=start<=end:raise ValueError('window')
    seen={}
    for b in rows:
        valid(b)
        if start<=b['i']<=end and b['received']<=cutoff:
            if b['i'] in seen:raise ValueError('duplicate')
            seen[b['i']]=b
    return [seen[i] for i in range(start,end+1)] if len(seen)==end-start+1 else None

def classify(ratio,body):
    if ratio<2:return 'ORDINARY_VOLUME'
    if abs(body)<=F(1,4):return 'HIGH_VOLUME_WEAK_BODY'
    if body>=F(3,4):return 'HIGH_VOLUME_UP_BODY'
    if body<=-F(3,4):return 'HIGH_VOLUME_DOWN_BODY'
    return 'HIGH_VOLUME_INTERMEDIATE'

def freeze(case_id,rows,signal,cutoff):
    if not isinstance(case_id,str) or not case_id or type(signal) is not int or signal<3 or type(cutoff) is not int or not (signal+1)*300<=cutoff<(signal+2)*300:raise ValueError('decision cutoff')
    w=window(rows,cutoff,signal-3,signal)
    out={'case_id':case_id,'signal':signal,'cutoff':cutoff,'plan_sha':PLAN_SHA,'prefix_sha':digest(w) if w is not None else None,'state':'UNKNOWN','feature':None,'signal_close':None,'future_prediction':None}
    if w is None:return out
    base=F(sum(b['volume'] for b in w[:-1]),3); b=w[-1]; span=b['high']-b['low']
    if base==0 or span==0 or b['volume']==0:return dict(out,state='UNDEFINED')
    ratio=F(b['volume'],base);body=F(b['close']-b['open'],span)
    f={'volume_ratio':str(ratio),'body_fraction':str(body),'gap':str(F(b['open']-w[-2]['close'],w[-2]['close'])),'close_change':str(F(b['close']-w[-2]['close'],w[-2]['close'])),'category':classify(ratio,body)}
    return dict(out,state='OBSERVED',feature=f,signal_close=b['close'])

def evaluate(frozen,expected_sha,case_id,rows,cutoff):
    if digest(frozen)!=expected_sha or frozen['case_id']!=case_id or frozen['plan_sha']!=PLAN_SHA:raise ValueError('frozen identity')
    if type(cutoff) is not int or cutoff<frozen['cutoff']:raise ValueError('evaluation cutoff')
    if freeze(case_id,rows,frozen['signal'],frozen['cutoff'])!=frozen:raise ValueError('prefix mismatch')
    out={'case_id':case_id,'category':frozen['feature']['category'] if frozen['feature'] else None,'outcome':'UNKNOWN','close_change':None,'pnl':None}
    if frozen['state']!='OBSERVED':return out
    n=frozen['signal']; w=window(rows,cutoff,n+1,n+3)
    if w is None:return out
    ch=F(w[-1]['close']-frozen['signal_close'],frozen['signal_close'])
    return dict(out,outcome='UP' if ch>=F(1,100) else 'DOWN' if ch<=-F(1,100) else 'FLAT',close_change=str(ch))

def prefix(kind):
    base=[bar(i,100,102,98,100,100) for i in range(3)]
    d={'weak':(100,110,90,101,300),'up':(100,109,99,108,300),'down':(100,101,91,92,300),'ordinary':(100,109,99,108,100),'gap':(110,115,105,110,300)}
    return base+[bar(3,*d[kind])]
def tail(p,direction):
    c=p[-1]['close']; end=c+direction*3
    return [bar(4,c,c+1,c-1,c,100),bar(5,c,max(c,end)+1,min(c,end)-1,end,100),bar(6,end,end+1,end-1,end,100)]
def examples():
    out=[]
    for kind,direction in product(('weak','up','down','ordinary','gap'),(-1,0,1)):
        case=f'{kind}:{direction}';p=prefix(kind);fr=freeze(case,p,3,1200); rows=p+tail(p,direction)
        out.append({'frozen':fr,'frozen_sha':digest(fr),'evaluation':evaluate(fr,digest(fr),case,rows,2100)})
    p=prefix('weak'); fr=freeze('missing',p,3,1200);out.append({'frozen':fr,'frozen_sha':digest(fr),'evaluation':evaluate(fr,digest(fr),'missing',p+tail(p,1)[:-1],2100)})
    return {'synthetic_only':True,'plan':PLAN,'plan_sha':PLAN_SHA,'cases':out,'limits':['bar body is not signed order flow','same prefix paired with deliberately constructed futures; not statistical evidence','close change is not executable return','case identity is supplied by fixture; external trusted anchors required']}

def tests():
    out=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        out.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except ValueError:ck(n,True,True);return
        raise AssertionError(n)
    for kind,direction in product(('weak','up','down','ordinary','gap'),(-1,0,1)):
        p=prefix(kind);case=f'{kind}:{direction}'; rows=p+tail(p,direction); fr=freeze(case,p,3,1200);sha=digest(fr)
        ck(case+':no future',freeze(case,rows,3,1200),fr)
        ck(case+':outcome',evaluate(fr,sha,case,rows,2100)['outcome'],{-1:'DOWN',0:'FLAT',1:'UP'}[direction])
        ck(case+':before deadline',evaluate(fr,sha,case,rows,2099)['outcome'],'UNKNOWN')
        ck(case+':no pnl',evaluate(fr,sha,case,rows,2100)['pnl'],None)
        ck(case+':reverse input',freeze(case,rows[::-1],3,1200),fr)
        scale=[dict(b,**{k:b[k]*5 for k in ('open','high','low','close','volume')}) for b in rows]
        ck(case+':scale',freeze(case,scale,3,1200)['feature'],fr['feature'])
    for kind,cat in [('weak','HIGH_VOLUME_WEAK_BODY'),('up','HIGH_VOLUME_UP_BODY'),('down','HIGH_VOLUME_DOWN_BODY'),('ordinary','ORDINARY_VOLUME'),('gap','HIGH_VOLUME_WEAK_BODY')]:
        ck(kind,freeze(kind,prefix(kind),3,1200)['feature']['category'],cat)
    # Independent integer oracle at boundaries and on both signs.
    for v,n in product(range(1,5),range(-8,9)):
        expected='ORDINARY_VOLUME' if v<2 else 'HIGH_VOLUME_WEAK_BODY' if abs(n)*4<=8 else 'HIGH_VOLUME_UP_BODY' if n*4>=24 else 'HIGH_VOLUME_DOWN_BODY' if n*4<=-24 else 'HIGH_VOLUME_INTERMEDIATE'
        ck(f'boundary:{v}:{n}',classify(F(v),F(n,8)),expected)
    p=prefix('weak'); fr=freeze('x',p,3,1200);sha=digest(fr);rows=p+tail(p,1)
    ck('missing baseline',freeze('x',p[1:],3,1200)['state'],'UNKNOWN')
    ck('late signal',freeze('x',p[:-1]+[dict(p[-1],received=1201)],3,1200)['state'],'UNKNOWN')
    ck('zero baseline',freeze('x',[dict(b,volume=0) for b in p[:3]]+p[3:],3,1200)['state'],'UNDEFINED')
    ck('flat range',freeze('x',p[:3]+[bar(3,100,100,100,100,300)],3,1200)['state'],'UNDEFINED')
    ck('zero volume',freeze('x',p[:3]+[dict(p[-1],volume=0)],3,1200)['state'],'UNDEFINED')
    ck('gap separate',freeze('x',prefix('gap'),3,1200)['feature']['gap'],'1/10')
    ck('missing future middle',evaluate(fr,sha,'x',rows[:5]+rows[6:],2100)['outcome'],'UNKNOWN')
    ck('late future',evaluate(fr,sha,'x',rows[:-1]+[dict(rows[-1],received=2101)],2100)['outcome'],'UNKNOWN')
    reject('early freeze',lambda:freeze('x',p,3,1199));reject('late freeze',lambda:freeze('x',rows,3,1500));reject('wrong case',lambda:evaluate(fr,sha,'y',rows,2100));reject('hash',lambda:evaluate(fr,'0'*64,'x',rows,2100));reject('mutated freeze',lambda:evaluate(dict(fr,signal_close=1),sha,'x',rows,2100));reject('prefix swap',lambda:evaluate(fr,sha,'x',prefix('up')+tail(prefix('up'),1),2100));reject('duplicate',lambda:freeze('x',p+[p[0]],3,1200));reject('bad high',lambda:freeze('x',p[:3]+[dict(p[3],high=99)],3,1200));reject('bad received',lambda:freeze('x',p[:3]+[dict(p[3],received=1199)],3,1200));reject('bool volume',lambda:freeze('x',p[:3]+[dict(p[3],volume=True)],3,1200));reject('early evaluation',lambda:evaluate(fr,sha,'x',rows,1199))
    for delta,expected in [(1,'UP'),(-1,'DOWN'),(0,'FLAT')]:
        p=prefix('gap');p[-1]=bar(3,100,110,90,100,300);f=freeze('edge',p,3,1200);r=p+[bar(i,100,102,98,100+delta,100) for i in (4,5,6)];ck('target edge:'+str(delta),evaluate(f,digest(f),'edge',r,2100)['outcome'],expected)
    return {'passed':len(out),'tests':out}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
