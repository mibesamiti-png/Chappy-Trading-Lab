"""R120: in-memory admission evidence ledger and read-only replay of R117 traces. Synthetic only."""
import argparse, hashlib, json, runpy
from pathlib import Path
from collections import Counter
from fractions import Fraction
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Requalification_Budget_Study_v0.1.py')
PARENT='556f066754b1ced78d195d550d1846f6eed92d15f60f53b537e8ae05434f5422'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PARENT:raise ValueError('R119 hash')
R=runpy.run_path(str(P)); Q=R['T']; K=R['K']; LOOKS=tuple(K); ROUTES={'initial':('initial',),'refresh':('update_old','update_new'),'recovery1':('restart1_old','restart1_new'),'recovery2':('restart2_one',),'parallel':('parallel',)}
G=R['R']['T']
if not np.array_equal(Q,G):raise ValueError('candidate table mismatch')
# Pin actual integrated source, not just R119's transitive imports.
P2=P.with_name('Chappy_Trading_Qualification_Generation_Study_v0.1.py'); P2HASH='5f417e5ec3d7e523e3c1180d5828ff78b2ca44404c0e7496fd36d60c10203350'
if hashlib.sha256(P2.read_bytes()).hexdigest()!=P2HASH:raise ValueError('R117 hash')
I=runpy.run_path(str(P2)); SEEDS=range(120000,120004)
PLAN=dict(parent=PARENT,integrated=P2HASH,lanes=ROUTES,looks=LOOKS,alpha='1/700',horizon=8192,seed=list(SEEDS),stream='single append-only synthetic stream',batch='one open batch, common observations within batch, nested prefixes within lane, no overlap across batches',second_recovery='first archived candidate, chosen at batch start',scope='in-memory ledger and trace adapter; no live integration')
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
SHA=digest(PLAN)
class Ledger:
    def __init__(self,stream='synthetic'):
        self.stream=stream;self.rows=[];self.entries=[];self.gen=Counter();self.batches=[];self.active=None;self.used=set();self.last_end=0
    def ingest(self,x,y):
        if type(x) is not int or type(y) is not int or not 0<=x<Q.shape[1] or y not in (-1,1) or len(self.rows)>=8192:return False
        self.rows.append((x,y));return True
    def open(self,route,js):
        # Check before mutation. Candidate and proposed generation fixed at opening.
        if route not in ROUTES or route in self.used or self.active is not None or not isinstance(js,(list,tuple)) or not 1<=len(js)<=len(ROUTES[route]) or any(type(j) is not int or not 0<j<len(Q) for j in js) or len(set(js))!=len(js):return False
        if route!='initial' and 'initial' not in self.used:return False
        if route=='recovery2' and 'recovery1' not in self.used:return False
        b=dict(id=len(self.batches),route=route,start=len(self.rows),end=None,lanes={l:dict(j=j,generation=self.gen[j]+1,looks=0,closed=False) for l,j in zip(ROUTES[route],js)})
        self.batches.append(b);self.active=b;self.used.add(route);return True
    def close(self):
        if self.active is None:return False
        self.active['end']=len(self.rows);self.last_end=len(self.rows);self.active=None;return True
    def spend(self,lane,j,generation,n):
        b=self.active
        if b is None or lane not in b['lanes'] or any(type(v) is not int for v in (j,generation,n)):return None
        a=b['lanes'][lane];t=len(self.rows)
        if a['closed'] or j!=a['j'] or generation!=a['generation'] or a['looks']>=len(LOOKS) or n!=LOOKS[a['looks']] or len(self.entries)>=35:return None
        ix=[i for i in range(b['start'],t) if Q[j,self.rows[i][0]]!=0]
        if len(ix)!=n or ix[-1]!=t-1:return None
        w=sum(int(Q[j,self.rows[i][0]]==self.rows[i][1]) for i in ix);ok=w>=K[n]
        ids=[[self.stream,i] for i in ix]; evidence=digest([[self.stream,i,*self.rows[i]] for i in ix])
        e=dict(batch=b['id'],route=b['route'],lane=lane,j=j,generation=generation,n=n,t=t,w=w,passed=ok,indices=ix,evidence_sha=evidence,claim_sha=digest([b['id'],lane,j,generation,n,ids,evidence]))
        # All validation precedes mutation; only successful spend changes the ledger.
        self.entries.append(e);a['looks']+=1;a['closed']=ok or n==LOOKS[-1]
        if ok:self.gen[j]=generation
        return e
    def snapshot(self):return digest(dict(rows=self.rows,entries=self.entries,batches=self.batches,gen=dict(self.gen),used=sorted(self.used)))

def replay(x,y,events):
    L=Ledger();p=0;recovery=0;reject=None;matches=0
    for e in events:
        t=e['t'];kind=e['kind']
        if kind not in ('audit_start','look','stop'):continue
        while p<t:
            if not L.ingest(int(x[p]),int(y[p])):raise ValueError('ingest')
            p+=1
        if kind=='stop':
            if L.active:L.close()
        elif kind=='audit_start':
            if L.active:L.close()
            phase=e['phase'];js=e['js']
            if phase=='recovery':recovery+=1;phase=f'recovery{recovery}'
            if not js:continue
            if not L.open(phase,js):reject=dict(t=t,route=phase,js=js,reason='route capacity or state');break
        else:
            b=L.active
            if b is None:raise ValueError('look without batch')
            lane=next(l for l,a in b['lanes'].items() if a['j']==e['j']);a=b['lanes'][lane]
            z=L.spend(lane,e['j'],a['generation'],e['n'])
            if z is None or (z['w'],z['passed'],z['t'])!=(e['w'],e['passed'],t):raise ValueError(('trace mismatch',e,z))
            matches+=1
    if L.active:L.close()
    return L,matches,reject

def study():
    c=Counter();examples={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def reject(L,fn):
        before=L.snapshot();ck('reject',not fn());ck('nonmutating',before==L.snapshot())
    def ingest(L,x,y,n):
        for _ in range(n):ck('append',L.ingest(x,y))
    def audit(L):
        ck('budget',len(L.entries)<=35 and Fraction(len(L.entries),700)<=Fraction(1,20));seen=set();prev={};used={};last=-1
        for e in L.entries:
            b=L.batches[e['batch']];j=e['j'];ix=[i for i in range(b['start'],e['t']) if Q[j,L.rows[i][0]]!=0]
            ck('evidence_indices',ix==e['indices'] and len(ix)==e['n']);ck('direct_wins',sum(int(Q[j,L.rows[i][0]]==L.rows[i][1]) for i in ix)==e['w']);ck('threshold',e['passed']==(e['w']>=K[e['n']]));ck('chronology',e['t']>=last);last=e['t'];ck('digest',e['evidence_sha']==digest([[L.stream,i,*L.rows[i]] for i in ix]));ck('unique_claim',e['claim_sha'] not in seen);seen.add(e['claim_sha']);key=(e['batch'],e['lane']);old=prev.get(key,[]);ck('nested_prefix',ix[:len(old)]==old);prev[key]=ix
            ck('cross_batch_disjoint',all(i not in used or used[i]==e['batch'] for i in ix));used.update({i:e['batch'] for i in ix})
    # Full 35-spend ledger: balanced outcomes prevent early acceptance; same batch sharing is valid.
    L=Ledger();j1,j2=9,256;xx=7
    for route,lanes in ROUTES.items():
        js=[j1,j2][:len(lanes)];ck('open',L.open(route,js));reject(L,lambda:L.open(route,js));start=len(L.rows);old=0
        for n in LOOKS:
            for i in range(old,n):ck('append',L.ingest(xx,1 if i%2==0 else -1))
            for lane,j in zip(lanes,js):
                a=L.active['lanes'][lane];g=a['generation'];reject(L,lambda:L.spend(lane,j,g+1,n));reject(L,lambda:L.spend(lane,1 if j!=1 else 2,g,n));e=L.spend(lane,j,g,n);ck('consume',e is not None and not e['passed']);reject(L,lambda:L.spend(lane,j,g,n));
            old=n
        ck('close',L.close());reject(L,lambda:L.open(route,js));ck('interval',L.batches[-1]['start']==start)
    ck('full_budget',len(L.entries)==35);audit(L);examples['full_budget']={'looks':len(L.entries),'alpha':str(Fraction(len(L.entries),700)),'batches':[{k:v for k,v in b.items() if k!='lanes'} for b in L.batches]}
    # Fresh generation, identical evidence shared only in a single batch, no fake wins or old rows.
    L=Ledger();ck('open',L.open('initial',[j1]));ingest(L,0,int(Q[j1,0]),16);e=L.spend('initial',j1,1,16);ck('generation_one',e['passed'] and L.gen[j1]==1);reject(L,lambda:L.spend('initial',j1,1,32));L.close();ck('open',L.open('refresh',[j1,j2]));reject(L,lambda:L.spend('update_old',j1,2,16));ingest(L,0,int(Q[j1,0]),16);e=L.spend('update_old',j1,2,16);f=L.spend('update_new',j2,1,16);ck('generation_two',e['passed'] and L.gen[j1]==2);ck('shared_observation',e['indices']==f['indices'] and e['evidence_sha']==f['evidence_sha'] and e['claim_sha']!=f['claim_sha']);L.close();audit(L);examples['generation']={'entries':L.entries}
    # Sparse support: off-support observation cannot inflate sample size.
    L=Ledger();j=257;on=int(np.flatnonzero(Q[j]!=0)[0]);off=int(np.flatnonzero(Q[j]==0)[0]);ck('open',L.open('initial',[j]));ingest(L,off,1,16);reject(L,lambda:L.spend('initial',j,1,16));ingest(L,on,int(Q[j,on]),16);e=L.spend('initial',j,1,16);ck('sparse',e['indices']==list(range(16,32)));L.close();audit(L)
    # Late look after an unrelated observation, missing scheduled look, malformed ingest.
    L=Ledger();reject(L,lambda:L.ingest(-1,1));reject(L,lambda:L.ingest(0,0));reject(L,lambda:L.ingest(True,1));ck('open',L.open('initial',[j]));reject(L,lambda:L.spend('initial',j,1,32));ingest(L,on,1,16);ingest(L,off,1,1);reject(L,lambda:L.spend('initial',j,1,16));L.close();reject(L,lambda:L.spend('initial',j,1,16));audit(L)
    # Second recovery restriction: prior order fixed, not selected using future outcome.
    # Both candidates lose qualification in first recovery (alternating outcome); second window favors one.
    cases={}
    for winner in (j1,j2):
        for policy in ('ONE','TWO_REFERENCE'):
            L=Ledger();ck('open',L.open('initial',[j1]));L.close();ck('open',L.open('recovery1',[j1,j2]));
            old=0
            for n in LOOKS:
                for i in range(old,n):ck('append',L.ingest(7,1 if i%2==0 else -1))
                for lane,j in zip(ROUTES['recovery1'],[j1,j2]):ck('recovery1_fail',not L.spend(lane,j,1,n)['passed'])
                old=n
            L.close();start=len(L.rows);ck('open',L.open('recovery2',[j1]));accepted=None;old=0;refwins={j1:0,j2:0};done=set()
            for n in LOOKS:
                for i in range(old,n):ck('append',L.ingest(7,int(Q[winner,7])))
                if policy=='ONE':
                    e=L.spend('restart2_one',j1,1,n);ck('second_look',e is not None)
                    if e['passed']:accepted=j1;break
                else:
                    # Outside proposed ledger; independently evaluate the two frozen candidates.
                    for j in (j1,j2):
                        if j not in done:
                            w=sum(int(Q[j,x]==y) for x,y in L.rows[start:]);ck('reference_count',0<=w<=n)
                            if w>=K[n]:accepted=j;done.add(j);break
                    if accepted:break
                old=n
            L.close();audit(L);cases[f'{winner}_{policy}']={'accepted':accepted,'observations':len(L.rows)-start}
    ck('restriction_counterexample',cases[f'{j2}_ONE']['accepted'] is None and cases[f'{j2}_TWO_REFERENCE']['accepted']==j2);examples['second_recovery']=cases
    # Read-only adapter of actual R117 event records; reject incompatible second dual-candidate request.
    traces={};total=0;incompatible=0
    def trace(name,x,y):
        nonlocal total,incompatible
        r=I['simulate'](x,y);L,n,err=replay(x,y,r['events']);audit(L);ck('trace_count',n==len(L.entries));total+=n;incompatible+=int(err is not None)
        if err:ck('expected_incompatibility',err['route']=='recovery2' and len(err['js'])==2)
        else:ck('complete_trace',n==r['looks'])
        traces[name]=dict(looks=n,original_looks=r['looks'],rejected=err)
    for name,(x,y) in I['fixtures']().items():trace(name,x,y)
    for case in I['R']['R']['CASES']:
        for seed in SEEDS:
            x,y=I['R']['R']['generate'](seed,case);trace(f'{case}_{seed}',x,y)
    ck('exhaust_detected',traces['exhaust']['rejected'] is not None)
    examples['trace_replay']=traces
    return dict(passed=sum(c.values()),counts=dict(c),traces=len(traces),trace_looks=total,incompatible=incompatible,plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,examples=examples)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,z in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round120_{k}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
