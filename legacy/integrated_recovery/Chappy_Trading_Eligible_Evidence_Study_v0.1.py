"""R128: eligible observation clocks and sparse audit windows. Synthetic batch prototype.
Run with prior R120 and R127 files in the same directory. No market data or orders.
"""
import argparse,hashlib,json,runpy
from collections import Counter
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parent
PARENTS={'Evidence_Ledger':'798ee9a2ebf9199064d9fb8d502396aea3798fe0f837a119a457243997953d63','Ledger_Integration':'5b9a8366135cc06aa98497a56864e6cd6255f20032b1be33b165f836a2d30ad6'}
for name,h in PARENTS.items():
    if hashlib.sha256((ROOT/f'Chappy_Trading_Admission_{name}_Study_v0.1.py').read_bytes()).hexdigest()!=h:raise ValueError(name)
R=runpy.run_path(str(ROOT/'Chappy_Trading_Admission_Evidence_Ledger_Study_v0.1.py'));Q,K=R['Q'],R['K']
SCHEDULES={'FULL':tuple((n,n) for n in K),'SPREAD':((16,16),(256,256)),'FRESH128':((16,16),(256,128)),'FRESH64':((16,16),(256,64)),'LATE':((256,256),)}
SEEDS=range(128000,128064); H=2048
CASES={'dense':((9,256),(0,0,0,0,0,0,0,100),70),'mixed':((9,260),(8,2,0,0,0,0,0,90),70),'disjoint':((260,264),(5,5,20,20,0,0,0,50),70),'overlap':((257,260),(5,5,0,0,0,0,0,90),70),'rare':((260,264),(1,0,5,0,0,0,0,94),80),'absent':((260,264),(0,0,0,0,0,0,0,100),90),'null':((260,264),(10,10,10,10,0,0,0,60),50)}
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
PLAN=dict(parents=PARENTS,seeds=list(SEEDS),horizon=H,cases=CASES,schedules=SCHEDULES,scope='one open batch, eligible count per lane, fixed schedule, first passing boundary after all due looks, no final-boundary qualification, unused reservations released',cap=35,alpha='1/700',thresholds=K)
class Ledger:
    def __init__(self,h,spent=0):
        if type(h)!=int or h<1 or type(spent)!=int or not 0<=spent<=35:raise ValueError('init')
        self.h=h;self.spent=spent;self.rows=[];self.gen={};self.batches=[];self.entries=[];self.active=None
    def snapshot(self):return digest([self.h,self.spent,self.rows,self.gen,self.batches,self.entries,self.active])
    def open(self,js,mode):
        if self.active is not None or len(self.rows)>=self.h or mode not in SCHEDULES or not isinstance(js,(tuple,list)) or not 1<=len(js)<=2 or any(type(j)!=int or not 0<j<len(Q) for j in js) or len(set(js))!=len(js):return False
        sch=SCHEDULES[mode];reserve=len(js)*len(sch)
        if self.spent+reserve>35:return False
        b=dict(id=len(self.batches),start=len(self.rows),end=None,mode=mode,js=tuple(js),schedule=sch,before=self.spent,reserved=reserve,lanes={j:dict(ix=[],k=0,g=self.gen.get(j,0)+1,passed=False) for j in js},winner=None)
        self.batches.append(b);self.active=b;return True
    def pending(self):
        b=self.active
        if b is None or len(self.rows)==self.h:return []
        return [j for j,a in b['lanes'].items() if not a['passed'] and a['k']<len(b['schedule']) and len(a['ix'])==b['schedule'][a['k']][0]]
    def done(self):
        b=self.active
        return b is not None and not self.pending() and (len(self.rows)==self.h or any(a['passed'] for a in b['lanes'].values()) or all(a['k']==len(b['schedule']) for a in b['lanes'].values()))
    def ingest(self,x,y):
        if type(x)!=int or type(y)!=int or not 0<=x<Q.shape[1] or y not in (-1,1) or len(self.rows)>=self.h or self.pending() or self.done():return False
        i=len(self.rows);self.rows.append((x,y));b=self.active
        if b:
            for j,a in b['lanes'].items():
                if Q[j,x]!=0 and a['k']<len(b['schedule']) and not a['passed']:a['ix'].append(i)
        return True
    def spend(self,j,g,n,w):
        b=self.active
        if b is None or any(type(v)!=int for v in (j,g,n,w)) or j not in self.pending() or self.spent>=35:return None
        a=b['lanes'][j]
        if g!=a['g'] or (n,w)!=b['schedule'][a['k']]:return None
        ix=a['ix'][-w:];wins=sum(Q[j,self.rows[i][0]]==self.rows[i][1] for i in ix);wins=int(wins);ok=wins>=K[w]
        ev=digest([[i,*self.rows[i]] for i in ix]);e=dict(batch=b['id'],j=j,g=g,n=n,window=w,t=len(self.rows),indices=ix,wins=wins,passed=ok,evidence=ev,claim=digest([b['id'],j,g,n,w,ev]))
        self.entries.append(e);self.spent+=1;a['k']+=1;a['passed']=ok
        if ok:self.gen[j]=g
        return e
    def close(self):
        if not self.done():return False
        b=self.active;b['end']=len(self.rows);b['after']=self.spent;b['winner']=next((j for j in b['js'] if b['lanes'][j]['passed']),None);self.active=None;return True

def oracle(x,y,js,mode,h):
    # Offline independent checkpoint enumeration, not the incremental ledger.
    events=[]
    for j in js:
        ix=np.flatnonzero(Q[j,x]!=0)
        for n,w in SCHEDULES[mode]:
            if len(ix)<n or ix[n-1]+1>=h:continue
            ids=ix[n-w:n];t=int(ix[n-1]+1);wins=int(np.count_nonzero(Q[j,x[ids]]==y[ids]));events.append((t,js.index(j),j,n,w,wins,wins>=K[w],ids.tolist()))
    events.sort();accepted=next((e[0] for e in events if e[6]),None)
    if accepted is not None:events=[e for e in events if e[0]<=accepted];end=accepted
    elif all(sum(e[2]==j for e in events)==len(SCHEDULES[mode]) for j in js):end=max(e[0] for e in events)
    else:end=h
    return events,end,next((e[2] for e in events if e[6]),None)

def drive(x,y,js,mode,ck):
    l=Ledger(len(x));ck('open',l.open(js,mode));b=l.active
    for a,v in zip(x,y):
        ck('ingest',l.ingest(int(a),int(v)))
        for j in l.pending():
            z=b['lanes'][j];n,w=b['schedule'][z['k']];ck('spend',l.spend(j,z['g'],n,w) is not None)
        if l.done():break
    ck('close',l.close());events,end,winner=oracle(x,y,js,mode,len(x));got=[(e['t'],js.index(e['j']),e['j'],e['n'],e['window'],e['wins'],e['passed'],e['indices']) for e in l.entries]
    ck('oracle',got==events and b['end']==end and b['winner']==winner);ck('budget',l.spent==len(events)<=b['reserved']<=35);ck('claims',len({e['claim'] for e in l.entries})==len(l.entries))
    for e in l.entries:
        ck('eligible',all(Q[e['j'],x[i]]!=0 for i in e['indices']));ck('digest',e['evidence']==digest([[i,int(x[i]),int(y[i])] for i in e['indices']]));ck('boundary',e['indices'][-1]+1==e['t']<len(x));ck('window',len(e['indices'])==e['window'])
    return l

def study():
    c=Counter();summary={};examples={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def reject(l,fn):
        before=l.snapshot();ck('reject',not fn());ck('atomic',before==l.snapshot())
    for name,(js,weights,p) in CASES.items():
        for mode in SCHEDULES:
            counts=Counter();ends=[]
            for seed in SEEDS:
                rng=np.random.default_rng(seed);x=rng.choice(8,H,p=np.array(weights)/100);y=np.where(rng.random(H)<p/100,1,-1);l=drive(x,y,js,mode,ck);b=l.batches[0];counts['looks']+=l.spent;counts['admitted']+=b['winner'] is not None;counts['deadline']+=b['end']==H;counts['unused']+=b['reserved']-l.spent;ends.append(b['end']);counts['suffix']+=sum(e['window']<e['n'] for e in l.entries)
                if seed==SEEDS[0]:
                    # Future changes cannot change a completed prefix: truncate strictly after end.
                    if b['end']<H:
                        yy=y.copy();yy[b['end']:]*=-1;other=drive(x,yy,js,mode,ck);ck('future_prefix',other.entries==l.entries and other.batches[0]['winner']==b['winner'])
            summary[name+'_'+mode]=dict(counts,mean_end=sum(ends)/len(ends),trials=len(SEEDS))
    # Dedicated asynchronous support: A every 4 slots, B every 8; A passes at 64, B not yet due.
    x=np.full(300,7);x[3::4]=0;x[7::8]=2;y=np.ones(300,dtype=int)
    # A at slots 4,12,... actually every 8; B at 8,16,... also every 8. Make A every 4 without overlap by assigning B at 8k+1.
    x[:]=7;x[3::4]=0;x[0::8]=2
    l=drive(x,y,(260,264),'SPREAD',ck);ck('async_fixture',l.entries[0]['j']==260 and l.entries[0]['t']==64 and l.batches[0]['winner']==260 and len(l.entries)==1);examples['asynchronous']=l.entries
    # 256 eligible samples separated by arbitrary off-support data; suffix contains exactly last 128 eligible.
    x=np.full(1100,7);x[3::4]=0;y=np.ones(1100,dtype=int);y[3:64:8]=-1
    l=drive(x,y,(260,),'FRESH128',ck);e=l.entries[-1];ck('suffix_fixture',e['n']==256 and e['window']==128 and e['t']==1024 and e['indices'][0]==515 and e['passed']);examples['suffix']=[{k:v for k,v in z.items() if k!='indices'} for z in l.entries]
    # No support and exact final boundary: no look, no qualification, no cost.
    for xx in (np.full(64,7),np.zeros(16,dtype=int)):
        l=drive(xx,np.ones(len(xx),dtype=int),(260,),'SPREAD',ck);ck('deadline_fixture',l.spent==0 and l.batches[0]['winner'] is None);examples['deadline_'+str(len(xx))]=dict(end=l.batches[0]['end'],spent=l.spent)
    # Shared simultaneous observations: all due looks processed even when first passes; first in fixed order wins.
    x=np.zeros(32,dtype=int);y=np.ones(32,dtype=int);l=drive(x,y,(9,260),'SPREAD',ck);ck('same_time',len(l.entries)==2 and all(e['passed'] for e in l.entries) and l.batches[0]['winner']==9);examples['shared']=l.entries
    # Reject wrong candidate, generation, skipped look, malformed input, pending advancement, premature close.
    l=Ledger(600,31);reject(l,lambda:l.open((9,260),'FULL'));ck('api_open',l.open((9,260),'SPREAD'));reject(l,lambda:l.close());reject(l,lambda:l.ingest(True,1));reject(l,lambda:l.spend(9,1,16,16))
    for _ in range(16):ck('api_ingest',l.ingest(0,1))
    reject(l,lambda:l.ingest(7,1));reject(l,lambda:l.spend(9,2,16,16));reject(l,lambda:l.spend(9,1,256,256));reject(l,lambda:l.spend(264,1,16,16));ck('api_spend',l.spend(9,1,16,16)['passed']);reject(l,lambda:l.spend(9,1,16,16));reject(l,lambda:l.close());ck('api_spend',l.spend(260,1,16,16)['passed']);ck('api_close',l.close());ck('release',l.spent==33);reject(l,lambda:l.open((9,260),'SPREAD'));ck('next_batch',l.open((9,),'SPREAD'))
    for _ in range(16):ck('api_ingest',l.ingest(0,1))
    reject(l,lambda:l.spend(9,1,16,16));ck('api_spend',l.spend(9,2,16,16)['passed']);ck('api_close',l.close());ck('disjoint',set(l.entries[0]['indices']).isdisjoint(l.entries[-1]['indices']) and l.spent==34);examples['budget']={'spent':l.spent,'generations':l.gen,'batch_ends':[b['end'] for b in l.batches]}
    return dict(passed=sum(c.values()),counts=dict(c),plan_sha=digest(PLAN),random_trials=len(CASES)*len(SCHEDULES)*len(SEEDS)),dict(plan=PLAN,summary=summary,examples=examples)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,v in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round128_{k}.json').write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
