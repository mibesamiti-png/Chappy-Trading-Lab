"""R77: row-weighted estimand, deletion sensitivity on artificial dependency groups.
No market inputs, investment recommendations, or execution.
"""
import argparse, hashlib, json, runpy
from pathlib import Path
from fractions import Fraction as F
from itertools import product
P=Path(__file__).with_name('Chappy_Trading_Evidence_Dependency_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='bb4f109e58221bffef69cee86c8508c87ea6cfd43f1cf3402a5e4276fdb34c67': raise ValueError('R76 hash')
R=runpy.run_path(str(P)); digest=R['digest']
PLAN={'window_slots':12,'min_rows':6,'min_each_sign':2,'min_deletion_groups':6,'cost_bps':20,'policies':['POINT','ROW_DELETE','SOURCE_DELETE','OVERLAP_DELETE','WAIT'],'estimand':'equal weight per observed row','market_adoption':False}
SHA=digest(PLAN)
def stats(ev):
    n=len(ev); total=sum(r['bps'] for r in ev); mean=F(total,n) if n else None
    eligible=n>=6 and sum(r['bps']>0 for r in ev)>=2 and sum(r['bps']<0 for r in ev)>=2
    pick=(1 if mean>20 else -1 if mean< -20 else 0) if eligible else 0
    out={'POINT':{'pick':pick},'WAIT':{'pick':0}}
    for mode in ('ROW','SOURCE','OVERLAP'):
        gs=R['groups'](ev,mode)
        deleted=[F(total-sum(r['bps'] for r in g),n-len(g)) for g in gs if len(g)<n]
        lo=min([mean]+deleted) if mean is not None else None; hi=max([mean]+deleted) if mean is not None else None
        complete=bool(gs) and len(deleted)==len(gs)
        p=pick if complete and len(gs)>=6 and ((pick==1 and lo>20) or (pick==-1 and hi< -20)) else 0
        out[mode+'_DELETE']={'pick':p,'groups':len(gs),'complete':complete,'lower_bps':str(lo) if complete else None,'upper_bps':str(hi) if complete else None,'largest_group':max(map(len,gs),default=0),'members':[[r['id'] for r in g] for g in gs]}
    return {'rows':n,'mean_bps':str(mean) if mean is not None else None,'eligible':eligible,'evidence_ids':sorted(r['id'] for r in ev),'policies':out}
def decision(rows,slot,now):
    R['validate'](rows)
    if type(slot) is not int or type(now) is not int or min(slot,now)<0:raise ValueError('clock')
    ev=[r for r in rows if 0<slot-r['slot']<=12 and r['received']<=now]
    return dict(stats(ev),slot=slot,now=now)
def evaluate(rows,targets,cutoff):
    if type(cutoff) is not int or cutoff<0:raise ValueError('cutoff')
    records=[]
    for t in targets:
        if t['now']>cutoff:continue
        d=decision(rows,t['slot'],t['now']); x=t['bps'] if t['received'] is not None and t['received']<=cutoff else None
        records.append(dict(d,result_bps=x,payoff_yen={k:None if p['pick'] and x is None else (p['pick']*x-20)*10 if p['pick'] else 0 for k,p in d['policies'].items()}))
    return records
def summary(rs):
    out={}
    for k in PLAN['policies']:
        selected=[r for r in rs if r['policies'][k]['pick']]; vals=[r['payoff_yen'][k] for r in selected if r['result_bps'] is not None]
        out[k]={'scored':len(vals),'unresolved':len(selected)-len(vals),'wait':len(rs)-len(selected),'net_yen':sum(vals),'all_selected_net_yen':sum(vals) if len(vals)==len(selected) else None}
    return out
def static(sizes,values):
    return stats([{'id':f'{i}:{j:02}','slot':i,'start':i*4,'end':i*4+3,'received':i*4+3,'source':str(i),'bps':x} for i,(n,x) in enumerate(zip(sizes,values)) for j in range(n)])
def variance_model(sizes):
    # Equal variance, perfectly identical within groups, independent across groups. No estimated correlation.
    n=sum(sizes); ss=sum(x*x for x in sizes)
    return {'rows':n,'groups':len(sizes),'variance_multiplier_vs_independent_rows':str(F(ss,n)),'effective_n_under_model':str(F(n*n,ss)),'row_mean_variance_if_sigma_squared_10000':str(F(10000*ss,n*n))}
def examples():
    cases={}
    for name,rows,targets in R['fixtures']():
        rs=evaluate(rows,targets,1000); cases[name]={'summary':summary(rs),'records':rs}
    return {'plan':PLAN,'plan_sha':SHA,'synthetic_only':True,'concentrated':static([10,1,1,1,1,1,1,1],[100,100,100,-100,-100,-100,-100,-100]),'skew':static([5,1]*3,[100,-100]*3),'variance_model':variance_model([5,1]*3),'cases':cases}
def tests():
    out=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        out.append({'name':n,'pass':True})
    for name,rows,targets in R['fixtures']():
        rs=evaluate(rows,targets,1000); sm=summary(rs)
        for t,d in zip(targets,rs):
            i=t['slot']; now=t['now']; tag=f'{name}:{i}'; ev=[r for r in rows if 0<i-r['slot']<=12 and r['received']<=now]
            pure=decision(rows,i,now);ck(tag+':prefix',pure,decision(ev,i,now));ck(tag+':reverse',pure,decision(list(reversed(rows)),i,now))
            mean=F(sum(r['bps'] for r in ev),len(ev)) if ev else None
            ck(tag+':mean',d['mean_bps'],str(mean) if mean is not None else None)
            old=R['decision'](rows,i,now);ck(tag+':point',d['policies']['POINT']['pick'],old['policies']['ROW']['pick'])
            for mode in ('ROW','SOURCE','OVERLAP'):
                p=d['policies'][mode+'_DELETE']; gs=old['policies'][mode]['members'];ck(tag+mode+':members',p['members'],gs)
                vals=[]
                for g in gs:
                    left=[r['bps'] for r in ev if r['id'] not in g]
                    if left:vals.append(F(sum(left),len(left)))
                complete=bool(gs) and len(vals)==len(gs)
                ck(tag+mode+':complete',p['complete'],complete)
                ck(tag+mode+':lo',p['lower_bps'],str(min(vals+[mean])) if complete else None);ck(tag+mode+':hi',p['upper_bps'],str(max(vals+[mean])) if complete else None)
                pick=d['policies']['POINT']['pick']; expected=pick if len(gs)>=6 and complete and all(pick*x>20 for x in vals+[mean]) else 0
                ck(tag+mode+':pick',p['pick'],expected)
                ck(tag+mode+':payoff',d['payoff_yen'][mode+'_DELETE'],None if expected and t['bps'] is None else 10*(expected*t['bps']-20) if expected else 0)
        for k,v in sm.items():ck(name+k+':denom',v['wait']+v['scored']+v['unresolved'],49)
        cut=evaluate(rows,targets,20);ck(name+':cutoff',[d['result_bps'] for d in cut],[t['bps'] if t['received'] is not None and t['received']<=20 else None for t in targets if t['now']<=20])
    ex=examples(); a=ex['concentrated']; b=ex['skew'];ck('concentrated mean',a['mean_bps'],'700/17');ck('concentrated row lower',a['policies']['ROW_DELETE']['lower_bps'],'75/2');ck('concentrated source lower',a['policies']['SOURCE_DELETE']['lower_bps'],'-300/7');ck('concentrated picks',[a['policies'][k]['pick'] for k in PLAN['policies']],[1,1,0,0,0]);ck('skew source retains mean',b['mean_bps'],'200/3');ck('skew source still passes',b['policies']['SOURCE_DELETE']['pick'],1)
    # Exact exhaustive check of the variance formula under the stated independent-group model.
    for sizes in ([5,1]*3,[1]*6,[3]*4,[8,1,1]):
        vals=[F(sum(s*x for s,x in zip(sizes,signs)),sum(sizes)) for signs in product((-100,100),repeat=len(sizes))]
        ck('variance:'+str(sizes),sum(x*x for x in vals)/len(vals),F(variance_model(sizes)['row_mean_variance_if_sigma_squared_10000']))
    return {'passed':len(out),'tests':out}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
