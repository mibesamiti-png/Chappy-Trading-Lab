"""R80 synthetic support and shift study; no market data, no orders."""
import argparse, hashlib, json, runpy
from fractions import Fraction as F
from pathlib import Path
P=Path(__file__).with_name('Chappy_Trading_Observation_Coverage_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='7b99b2893770cabee0d84b02c6a9d0f700fce72587554ca41e33e2f141f872db':raise ValueError('R79 hash')
digest=runpy.run_path(str(P))['digest']
PLAN={'train_cells':[[0,0],[1,1]],'train_n_per_cell':20,'cutoff':30,'cost_bps':20,'notional_yen':100000,'minimum_n':6,'probe_count':6,'probe_delay':3,'probe_cost_yen':[0,100],'policies':['GLOBAL','MARGINAL','JOINT','PROBE','WAIT'],'features':'two artificial ordinal categories, not real market features'}
SHA=digest(PLAN)
NAMES={'known_stable':((0,0),1),'joint_unknown_positive':((0,1),1),'joint_unknown_negative':((0,1),-1),'outside_negative':((2,2),-1),'hidden_shift':((0,0),-1),'joint_unknown_flat':((0,1),0)}
def pick(vals):
    return (int(sum(vals)>20*len(vals))-int(sum(vals)<-20*len(vals))) if len(vals)>=6 else 0

def fit(rows,cutoff=30):
    seen=set(); cells={}
    for r in rows:
        if type(r['received']) is not int:raise ValueError('clock')
        if r['received']>cutoff:continue
        k=r['id']; x=tuple(r['x']); v=r['bps']
        if k in seen or len(x)!=2 or any(type(i) is not int for i in x) or type(v) is not int:raise ValueError('record')
        seen.add(k);cells.setdefault(x,[]).append(v)
    allv=[v for vals in cells.values() for v in vals]
    return {'global':pick(allv),'cells':{x:tuple(sorted(v)) for x,v in cells.items()},'margins':tuple(frozenset(x[i] for x in cells) for i in range(2))}
def decide(m,x,i,receipts):
    # Only first six scheduled probes in the unknown cell can be used; no future truth input.
    local=m['cells'].get(x,()); joint=len(local)>=6; marginal=all(x[j] in m['margins'][j] for j in range(2)); g=m['global']
    vals=[]; ids=[]
    for r in receipts:
        if r['received']>i:continue
        if r['x']!=x or not 0<=r['index']<6 or r['received']<r['index']+3 or r['index']>=i or r['index'] in ids:raise ValueError('probe receipt')
        ids.append(r['index']); vals.append(r['bps'])
    return {'joint':joint,'marginal':marginal,'probe_evidence':sorted(ids),'observe':not joint and i<6,'picks':{'GLOBAL':g,'MARGINAL':g if marginal else 0,'JOINT':pick(local) if joint else 0,'PROBE':pick(local) if joint else pick(vals),'WAIT':0}}
def training():return [{'id':f'{j}:{i}','x':(j,j),'bps':100 if i%5!=4 else -100,'received':i+3} for j in range(2) for i in range(20)]
def evaluate(name,fee):
    x,s=NAMES[name]; m=fit(training()); receipts=[]; rows=[]
    for i in range(20):
        d=decide(m,x,i,receipts);v=s*(100 if i%5!=4 else -100)
        net={k:(10*(p*v-20) if p else 0)-(fee if k=='PROBE' and d['observe'] else 0) for k,p in d['picks'].items()}
        rows.append(dict(index=i,x=x,truth_bps=v,**d,net_yen=net))
        if d['observe']:receipts.append({'index':i,'received':i+3,'x':x,'bps':v})
    return {'records':rows,'summary':{k:{'selected':sum(bool(r['picks'][k]) for r in rows),'observations':sum(r['observe'] for r in rows) if k=='PROBE' else 0,'net_yen':sum(r['net_yen'][k] for r in rows)} for k in PLAN['policies']}}
def examples():return {'synthetic_only':True,'plan':PLAN,'plan_sha':SHA,'cases':{f'{n}:{fee}':evaluate(n,fee) for n in NAMES for fee in PLAN['probe_cost_yen']}}
def tests():
    checks=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        checks.append({'name':n,'pass':True})
    t=training();m=fit(t);ck('full coverage',sum(map(len,m['cells'].values())),40);ck('training order',m,fit(t[::-1]));ck('future mask',m,fit(t+[dict(t[0],received=31,bps=-999)]));ck('global',m['global'],1)
    for n,(x,s) in NAMES.items():
        for fee in PLAN['probe_cost_yen']:
            e=evaluate(n,fee);label=f'{n}:{fee}';joint=x in [(0,0),(1,1)];marginal=all(j in [0,1] for j in x)
            for r in e['records']:
                i=r['index']; expect={'GLOBAL':1,'MARGINAL':int(marginal),'JOINT':int(joint),'PROBE':1 if joint else s if i>=8 else 0,'WAIT':0}; ck(label+str(i)+'picks',r['picks'],expect);ck(label+str(i)+'probe',r['observe'],not joint and i<6);ck(label+str(i)+'ids',r['probe_evidence'],list(range(min(6,max(0,i-2)))) if not joint else []);ck(label+str(i)+'support',(r['joint'],r['marginal']),(joint,marginal))
                for k,p in expect.items():ck(label+str(i)+k+'net',r['net_yen'][k],(10*(p*r['truth_bps']-20) if p else 0)-(fee if k=='PROBE' and not joint and i<6 else 0))
            for k,z in e['summary'].items():
                ck(label+k+'sum',z['net_yen'],sum(r['net_yen'][k] for r in e['records']));ck(label+k+'selected',z['selected'],sum(r['picks'][k]!=0 for r in e['records']))
    for a in range(-1,4):
        for b in range(-1,4):
            x=(a,b);d=decide(m,x,0,[]);ck(f'{x}joint',d['joint'],x in [(0,0),(1,1)]);ck(f'{x}margin',d['marginal'],a in [0,1] and b in [0,1])
    from itertools import product
    for vs in product([-100,0,100],repeat=6):
        rec=[{'index':i,'received':i+3,'x':(0,1),'bps':v} for i,v in enumerate(vs)];d=decide(m,(0,1),8,rec);ck('probe'+str(vs),d['picks']['PROBE'],int(sum(vs)>120)-int(sum(vs)<-120));ck('before last'+str(vs),decide(m,(0,1),7,rec)['picks']['PROBE'],0)
    a=evaluate('known_stable',100);b=evaluate('hidden_shift',100);ck('same decisions under hidden shift',[r['picks'] for r in a['records']],[r['picks'] for r in b['records']]);ck('opposite profit',(a['summary']['JOINT']['net_yen'],b['summary']['JOINT']['net_yen']),(8000,-16000))
    return {'passed':len(checks),'tests':checks}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
