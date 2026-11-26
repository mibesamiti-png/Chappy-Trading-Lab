"""R76: artificial evidence overlap / duplication sensitivity, no market data or orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
from copy import deepcopy
from itertools import product
P=Path(__file__).with_name('Chappy_Trading_Estimation_Comparison_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='fda9901b247bfc5cb0cb0935458a8ec722cf39a40c5e5a0b75a974a07bd7e1e7': raise ValueError('R75 hash')
R=runpy.run_path(str(P)); digest=R['digest']
PLAN={'window_slots':12,'min_units':6,'min_each_sign':2,'cost_bps':20,'policies':['ROW','SOURCE','OVERLAP','WAIT'],'interval':'[start,end)','market_adoption':False}
SHA=digest(PLAN)
def validate(rows):
    ids=set()
    for r in rows:
        if set(r)!={'id','slot','start','end','received','source','bps'} or not isinstance(r['id'],str) or not r['id'] or r['id'] in ids: raise ValueError('id')
        ids.add(r['id'])
        if not isinstance(r['source'],str) or not r['source'] or any(type(r[k]) is not int for k in ('slot','start','end','received','bps')) or not 0<=r['slot'] or not 0<=r['start']<r['end']<=r['received'] or abs(r['bps'])>=10000: raise ValueError('row')

def groups(rows,mode):
    if mode not in PLAN['policies'][:3]: raise ValueError('mode')
    rows=sorted(rows,key=lambda r:r['id']); n=len(rows); parent=list(range(n))
    def root(i):
        while parent[i]!=i:i=parent[i]
        return i
    for i in range(n):
        for j in range(i):
            a,b=rows[i],rows[j]
            if mode!='ROW' and (a['source']==b['source'] or (mode=='OVERLAP' and max(a['start'],b['start'])<min(a['end'],b['end']))): parent[root(i)]=root(j)
    result={}
    for i,r in enumerate(rows):result.setdefault(root(i),[]).append(r)
    return sorted(result.values(),key=lambda g:g[0]['id'])

def decision(rows,slot,now):
    validate(rows)
    if type(slot) is not int or type(now) is not int or min(slot,now)<0: raise ValueError('clock')
    ev=[r for r in rows if max(0,slot-12)<=r['slot']<slot and r['received']<=now]; out={}
    for mode in PLAN['policies'][:3]:
        gs=groups(ev,mode); vals=[F(sum(r['bps'] for r in g),len(g)) for g in gs]; n=len(vals)
        pos=sum(v>0 for v in vals); neg=sum(v<0 for v in vals); mean=sum(vals,F(0))/n if n else None
        pick=R['sign'](mean) if n>=6 and min(pos,neg)>=2 and abs(mean)>20 else 0
        out[mode]={'units':n,'members':[[r['id'] for r in g] for g in gs],'mean_bps':str(mean) if mean is not None else None,'pick':pick}
    out['WAIT']={'pick':0}
    return {'slot':slot,'now':now,'rows':len(ev),'evidence_ids':sorted(r['id'] for r in ev),'policies':out}

def fixtures():
    base=[100,100,-100,0,100,-100,100,0,-100,100,100,-100]*4
    balanced=[100,-100]*24
    for name,values,spacing in [('balanced',balanced,4),('skew_copy',balanced,4),('equal_copy',base,4),('overlap',base,1),('delayed',base,4)]:
        rows=[]; targets=[]
        for i,v in enumerate(values):
            t=i*spacing; end=t+3; received=end+(8 if name=='delayed' and i%3==0 else 0)
            n=(5 if v>0 else 1) if name=='skew_copy' else 3 if name=='equal_copy' else 1
            for j in range(n):rows.append({'id':f'E{i:03}-{j}','slot':i,'start':t,'end':end,'received':received,'source':f'S{i:03}','bps':v})
            targets.append({'slot':i,'now':t,'bps':v,'received':received})
        # Unknown target; no fabricated evidence.
        targets.append({'slot':48,'now':48*spacing,'bps':None,'received':None})
        yield name,rows,targets

def evaluate(rows,targets,cutoff):
    result=[]
    for t in targets:
        if t['now']>cutoff:break
        d=decision(rows,t['slot'],t['now']); x=t['bps'] if t['received'] is not None and t['received']<=cutoff else None
        p={k:None if v['pick'] and x is None else (v['pick']*x-20)*10 if v['pick'] else 0 for k,v in d['policies'].items()}
        result.append(dict(d,result_bps=x,payoff_yen=p))
    return result

def summary(rs):
    out={}
    for k in PLAN['policies']:
        chosen=[r for r in rs if r['policies'][k]['pick']]; scored=[r for r in chosen if r['result_bps'] is not None]; vals=[r['payoff_yen'][k] for r in scored]
        out[k]={'selected':len(chosen),'scored':len(scored),'unresolved':len(chosen)-len(scored),'wait':len(rs)-len(chosen),'net_yen':sum(vals),'all_selected_net_yen':sum(vals) if len(scored)==len(chosen) else None}
    return out

def static():
    rows=[]
    for i,v in enumerate([100,-100]*3):
        for j in range(5 if v>0 else 1):rows.append({'id':f'S{i}-{j}','slot':i,'start':4*i,'end':4*i+3,'received':4*i+3,'source':str(i),'bps':v})
    return decision(rows,6,24)

def examples():
    cases={}
    for name,rows,targets in fixtures():
        rs=evaluate(rows,targets,1000);cases[name]={'summary':summary(rs),'records':rs,'evidence_rows':len(rows),'decisions_sha':digest([{k:v for k,v in r.items() if k not in ('result_bps','payoff_yen')} for r in rs])}
    return {'plan':PLAN,'plan_sha':SHA,'synthetic_only':True,'market_adoption':False,'static':static(),'cases':cases}

def tests():
    out=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        out.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except ValueError:ck(n,True,True);return
        raise AssertionError(n)
    def oracle(ev,mode):
        # Independent graph reachability via expansion of vertex sets.
        left=set(range(len(ev))); comps=[]
        while left:
            seen={min(left)}
            while True:
                expanded=seen|{j for j in left for i in seen if mode!='ROW' and (ev[i]['source']==ev[j]['source'] or (mode=='OVERLAP' and ev[i]['start']<ev[j]['end'] and ev[j]['start']<ev[i]['end']))}
                if expanded==seen:break
                seen=expanded
            left-=seen;comps.append(sorted(ev[i]['id'] for i in seen))
        return sorted(comps)
    for name,rows,targets in fixtures():
        rs=evaluate(rows,targets,1000); sm=summary(rs)
        for t,r in zip(targets,rs):
            i=t['slot']; now=t['now']; tag=f'{name}:{i}'
            ev=[a for a in rows if 0<i-a['slot']<=12 and a['received']<=now]; d=decision(rows,i,now)
            ck(tag+':evidence',d['evidence_ids'],sorted(a['id'] for a in ev));ck(tag+':prefix',decision(ev,i,now),d);ck(tag+':order',decision(list(reversed(rows)),i,now),d)
            for k in PLAN['policies'][:3]:
                p=d['policies'][k]; gs=oracle(ev,k); vals=[F(sum(a['bps'] for a in ev if a['id'] in g),len(g)) for g in gs]; mean=sum(vals,F(0))/len(vals) if vals else None
                ck(tag+k+':components',p['members'],gs);ck(tag+k+':mean',p['mean_bps'],str(mean) if mean is not None else None)
                pick=(1 if mean>20 else -1 if mean< -20 else 0) if len(vals)>=6 and sum(x>0 for x in vals)>=2 and sum(x<0 for x in vals)>=2 else 0
                ck(tag+k+':choice',p['pick'],pick);ck(tag+k+':payoff',r['payoff_yen'][k],None if pick and t['bps'] is None else 10*(pick*t['bps']-20) if pick else 0)
        for k,v in sm.items():ck(name+k+':denom',v['wait']+v['scored']+v['unresolved'],49)
        ck(name+':cutoff', [x['result_bps'] for x in evaluate(rows,targets,20)],[t['bps'] if t['received'] is not None and t['received']<=20 else None for t in targets if t['now']<=20])
    s=static();ck('static rows',s['rows'],18);ck('static row mean',s['policies']['ROW']['mean_bps'],'200/3');ck('static source mean',s['policies']['SOURCE']['mean_bps'],'0');ck('static choice',[s['policies'][k]['pick'] for k in PLAN['policies']],[1,0,0,0]);ck('static groups',s['policies']['OVERLAP']['units'],6)
    # Exhaust all 3-interval start combinations and source assignments (transitive overlap included).
    for starts in product(range(4),repeat=3):
        for labels in product('AB',repeat=3):
            ev=[{'id':str(i),'slot':i,'start':x,'end':x+2,'received':x+2,'source':labels[i],'bps':100} for i,x in enumerate(starts)]
            ck(f'graph:{starts}:{labels}',[[a['id'] for a in g] for g in groups(ev,'OVERLAP')],oracle(ev,'OVERLAP'))
    rows=list(fixtures())[0][1];reject('duplicate',lambda:decision(rows+[rows[0]],12,48)); bad=deepcopy(rows);bad[0]['received']=0;reject('early received',lambda:decision(bad,12,48));reject('invalid clock',lambda:decision(rows,12,-1))
    return {'passed':len(out),'tests':out}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
