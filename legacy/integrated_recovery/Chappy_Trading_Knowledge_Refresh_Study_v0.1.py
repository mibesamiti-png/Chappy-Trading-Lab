"""R81 synthetic knowledge refresh; no live data or orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from itertools import product
P=Path(__file__).with_name('Chappy_Trading_Applicability_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='a68f670dcc6e13ab0d54f7de34f1908c41878dc7ecf1318aa94a6caa1de759c3': raise ValueError('R80 hash')
R80=runpy.run_path(str(P)); pick=R80['pick']; digest=R80['digest']
PLAN={'slots':60,'initial_direction':1,'cost_bps':20,'notional_yen':100000,'delay':3,'audit_n':6,'audit_timeout':10,'periodic_starts':[12,32,48],'reactive_window':4,'reactive_trigger_signed_sum_bps':-200,'retry_wait':12,'audit_fees':[0,100], 'policies':['FROZEN','PERIODIC','REACTIVE','WAIT']}
NAMES=['stable','persistent_shift','temporary_shift','flat_shift','rapid_shift','missing_audit']
def truth(name,i):
    base=100 if i%5!=4 else -100
    if name=='stable':return base
    if name=='flat_shift':return base if i<20 else 0
    if name=='temporary_shift':return -base if 20<=i<30 else base
    if name=='rapid_shift':return base if (i//5)%2==0 else -base
    return base if i<20 else -base

def decide(policy,i,history,receipts):
    # history contains previous decisions only; receipts are masked before use.
    visible={r['index']:r['bps'] for r in receipts if r['received']<=i and r['index']<i}
    prev=history[-1] if history else {'direction':1,'audit_start':None,'epoch':0,'retry_at':None}
    direction,start,epoch,retry=(prev[k] for k in ('direction','audit_start','epoch','retry_at'))
    d={'direction':direction,'audit_start':start,'epoch':epoch,'retry_at':retry,'action':'WAIT','p':0,'evidence':[],'reason':'WAIT'}
    if policy=='WAIT':return d
    if policy=='FROZEN':return dict(d,action='TRADE',p=1,reason='FROZEN')
    if start is not None:
        ids=[j for j in range(start,start+6) if j in visible]
        if len(ids)==6 or i>=start+10:
            direction=pick([visible[j] for j in ids]) if len(ids)==6 else 0
            d.update(direction=direction,audit_start=None,epoch=i,retry_at=i+12 if not direction else None,evidence=ids,reason='REFRESH' if len(ids)==6 else 'TIMEOUT')
            if direction:d.update(action='TRADE',p=direction)
            return d
        return dict(d,action='PROBE' if i<start+6 else 'WAIT',evidence=ids,reason='AUDIT')
    trigger=False; ids=[]
    if policy=='PERIODIC':trigger=i in PLAN['periodic_starts']
    else:
        ids=[r['index'] for r in history if r['index']>=epoch and r['action']=='TRADE' and r['index'] in visible][-4:]
        trigger=(direction!=0 and len(ids)==4 and sum(direction*visible[j] for j in ids)<=-200) or (direction==0 and retry is not None and i>=retry)
    if trigger:return dict(d,audit_start=i,action='PROBE',reason='TRIGGER',evidence=ids)
    if direction:return dict(d,action='TRADE',p=direction,reason='ACTIVE',evidence=ids)
    return d

def simulate(name,policy,fee):
    history=[];receipts=[]
    for i in range(60):
        d=decide(policy,i,history,receipts); v=truth(name,i)
        net=(10*(d['p']*v-20) if d['p'] else 0)-(fee if d['action']=='PROBE' else 0)
        history.append(dict(d,index=i,truth_bps=v,net_yen=net))
        if d['action'] in ('TRADE','PROBE') and not (name=='missing_audit' and d['action']=='PROBE' and i%3==0):
            receipts.append(dict(index=i,received=i+3,bps=v))
    return {'records':history,'receipts':receipts,'summary':{'net_yen':sum(r['net_yen'] for r in history),'trades':sum(r['action']=='TRADE' for r in history),'probes':sum(r['action']=='PROBE' for r in history),'waits':sum(r['action']=='WAIT' for r in history),'audit_starts':[r['index'] for r in history if r['reason']=='TRIGGER'],'refreshes':[[r['index'],r['direction'],r['reason']] for r in history if r['reason'] in ('REFRESH','TIMEOUT')]}}
def examples():return {'synthetic_only':True,'plan':PLAN,'plan_sha':digest(PLAN),'cases':{f'{n}:{fee}':{p:simulate(n,p,fee) for p in PLAN['policies']} for n in NAMES for fee in PLAN['audit_fees']}}
def tests():
    checks=[]
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        checks.append({'name':n,'pass':True})
    for n in NAMES:
        for p in PLAN['policies']:
            a=simulate(n,p,100);b=simulate(n,p,0); rows=a['records']; rec=a['receipts']; tag=n+':'+p
            ck(tag+'fee changes no decisions',[{k:v for k,v in r.items() if k!='net_yen'} for r in rows],[{k:v for k,v in r.items() if k!='net_yen'} for r in b['records']]);ck(tag+'fee accounting',a['summary']['net_yen'],b['summary']['net_yen']-100*a['summary']['probes']);ck(tag+'partition',sum(a['summary'][k] for k in ('trades','probes','waits')),60)
            for i,r in enumerate(rows):
                prefix=[q for q in rec if q['received']<=i]; future=[q for q in rec if q['received']>i]; d=decide(p,i,rows[:i],prefix)
                ck(tag+str(i)+'prefix',d,{k:v for k,v in r.items() if k not in ('index','truth_bps','net_yen')});ck(tag+str(i)+'future mask',d,decide(p,i,rows[:i],prefix+[{**q,'bps':99999} for q in future]));ck(tag+str(i)+'order',d,decide(p,i,rows[:i],prefix[::-1]));ck(tag+str(i)+'action',bool(r['p']),r['action']=='TRADE');ck(tag+str(i)+'evidence received',all(any(q['index']==j for q in prefix) for j in r['evidence']),True)
                expected=(100000*(r['p']*truth(n,i)-20)//10000 if r['action']=='TRADE' else -100 if r['action']=='PROBE' else 0);ck(tag+str(i)+'net',r['net_yen'],expected)
                if r['reason']=='REFRESH':
                    vs=[q['bps'] for q in prefix if q['index'] in r['evidence']];ck(tag+str(i)+'refresh count',len(vs),6);ck(tag+str(i)+'refresh pick',r['direction'],1 if sum(vs)>120 else -1 if sum(vs)<-120 else 0)
                if r['reason']=='TIMEOUT':ck(tag+str(i)+'timeout wait',(r['p'],r['direction']),(0,0))
                if r['reason']=='TRIGGER' and p=='REACTIVE' and r['direction']:
                    ck(tag+str(i)+'trigger',len(r['evidence'])==4 and sum(r['direction']*q['bps'] for q in prefix if q['index'] in r['evidence'])<=-200,True)
            ck(tag+'summary',a['summary']['net_yen'],sum(r['net_yen'] for r in rows))
    for vs in product((-100,0,100),repeat=6):
        h=[{'direction':1,'audit_start':0,'epoch':0,'retry_at':None}]*8;rec=[dict(index=j,received=j+3,bps=v) for j,v in enumerate(vs)]
        ck('all six '+str(vs),decide('REACTIVE',8,h,rec)['direction'],int(sum(vs)>120)-int(sum(vs)<-120));ck('before six '+str(vs),decide('REACTIVE',7,h[:7],rec)['p'],0)
    return {'passed':len(checks),'tests':checks}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
