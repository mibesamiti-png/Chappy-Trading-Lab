"""R129: synthetic eligible observation lifecycle. No market data or orders."""
import argparse, hashlib, json, runpy
from pathlib import Path
from collections import Counter
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Eligible_Evidence_Study_v0.1.py')
PH='c2ea6f1db1fca40a8bc74c1acda3bcd223815e86c1b9743aa4060177c4d6c346'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PH:raise ValueError('parent')
R=runpy.run_path(str(P));Q,K,Ledger=R['Q'],R['K'],R['Ledger'];digest=R['digest']
H=4096;SEEDS=range(129000,129016);COOL=256
CASES={'dense_stable':((50,50),((0,90),)), 'mixed_temporary':((25,10),((0,90),(1024,10),(1536,90))), 'mixed_permanent':((25,10),((0,90),(1024,10))), 'rare_temporary':((5,1),((0,90),(1024,10),(1536,90))), 'rare_permanent':((5,1),((0,90),(1024,10))), 'absent':((0,0),((0,90),)), 'mixed_relapse':((25,10),((0,90),(1024,10),(1536,90),(3072,10)))}
PLAN=dict(parent=PH,horizon=H,seeds=list(SEEDS),cases=CASES,js=[260,264],modes=['FULL','SPREAD'],policies=['STOP','RESTART'],prior_spent=20,cap=35,cool_calendar=COOL,monitor=[32,8],restart='same winner once; FULL >=5, SPREAD >=2, LATE 1; next slot only',fees=[1,200],payoffs=[800,-1200])
def schedule(left):return 'FULL' if left>=5 else 'SPREAD' if left>=2 else 'LATE' if left==1 else None

def simulate(x,y,js,mode,policy,spent=20):
    h=len(x);l=Ledger(h,spent);actions=np.zeros(h,dtype=int);events=[];groups=[];obs=fee=0;j=g=stop=None;block=[];restart=False;phase='audit'
    if not l.open(js,mode):raise ValueError('initial budget')
    for i,(a,v) in enumerate(zip(x,y)):
        t=i+1
        if phase=='cool' and i==stop+COOL:
            if not l.open((j,),schedule(35-l.spent)):raise RuntimeError('restart open')
            phase='audit';restart=True;events.append(('restart_audit',i,j,g))
        if phase=='terminal':break
        if phase=='live' and Q[j,a]!=0:actions[i]=j
        if not l.ingest(int(a),int(v)):raise RuntimeError('ingest')
        obs+=1
        if phase=='audit':
            for k in l.pending():
                b=l.active;lane=b['lanes'][k];n,w=b['schedule'][lane['k']]
                if l.spend(k,lane['g'],n,w) is None:raise RuntimeError('spend')
            if l.done():
                b=l.active
                if not l.close():raise RuntimeError('close')
                j=b['winner']
                if j is None:phase='terminal';continue
                g=l.gen[j];phase='live';block=[];fee+=200;events.append(('resume' if restart else 'admit',t,j,g))
        elif phase=='live' and Q[j,a]!=0:
            block.append(i)
            if len(block)==32:
                wins=sum(int(Q[j,x[k]]==y[k]) for k in block);groups.append((j,g,t,wins,tuple(block)));block=[]
                if wins<=8:
                    events.append(('stop',t,j,g));stop=t
                    phase='cool' if policy=='RESTART' and not restart and l.spent<35 and t+COOL<h else 'terminal'
    gross=int(np.where(actions==0,0,np.where(Q[actions,x]==y,800,-1200)).sum())
    return dict(events=events,groups=groups,entries=l.entries,spent=l.spent,actions=actions,obs=obs,fee=fee,gross=gross,net=gross-obs-fee)

def oracle(x,y,js,mode,policy,spent):
    h=len(x);events=[];groups=[];entries=[];actions=np.zeros(h,dtype=int);g={};fee=0
    def audit(start,js,mode):
        nonlocal spent
        ev,end,winner=R['oracle'](x[start:],y[start:],js,mode,h-start)
        gens={j:g.get(j,0)+1 for j in js}
        for t,_,j,n,w,wins,ok,ids in ev:
            entries.append((j,gens[j],t+start,n,w,wins,ok,tuple(i+start for i in ids)));spent+=1
            if ok:g[j]=gens[j]
        return start+end,winner
    t,j=audit(0,js,mode);end=t
    for epoch in range(2):
        if j is None:break
        events.append(('admit' if epoch==0 else 'resume',t,j,g[j]));fee+=200
        ids=np.flatnonzero(Q[j,x[t:]]!=0)+t;end=h;alarm=False
        for k in range(0,len(ids)-31,32):
            ix=ids[k:k+32];wins=int(np.count_nonzero(Q[j,x[ix]]==y[ix]));e=int(ix[-1])+1;groups.append((j,g[j],e,wins,tuple(map(int,ix))))
            if wins<=8:end=e;alarm=True;events.append(('stop',e,j,g[j]));break
        actions[ids[ids<end]]=j
        if not alarm or epoch or policy=='STOP' or spent==35 or end+COOL>=h:break
        start=end+COOL;events.append(('restart_audit',start,j,g[j]));t,j=audit(start,(j,),schedule(35-spent));end=t
    gross=int(np.where(actions==0,0,np.where(Q[actions,x]==y,800,-1200)).sum())
    return dict(events=events,groups=groups,entries=entries,spent=spent,actions=actions,obs=end,fee=fee,gross=gross,net=gross-end-fee)

def study():
    c=Counter();summary={};examples={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    def check(x,y,js,mode,policy,spent=20):
        z=simulate(x,y,js,mode,policy,spent);o=oracle(x,y,js,mode,policy,spent)
        es=[(e['j'],e['g'],e['t'],e['n'],e['window'],e['wins'],e['passed'],tuple(e['indices'])) for e in z['entries']]
        ck('audit_oracle',es==o['entries']);ck('state_oracle',all(z[k]==o[k] for k in ('events','groups','spent','obs','fee','gross','net')));ck('action_oracle',np.array_equal(z['actions'],o['actions']));ck('budget',z['spent']==spent+len(es)<=35);ck('support',np.all((z['actions']==0)|(Q[z['actions'],x]!=0)));ck('accounting',z['net']==z['gross']-z['obs']-z['fee'])
        used=set()
        for j,g,t,w,ix in z['groups']:
            ck('group_evidence',len(ix)==32 and ix[-1]+1==t and all(Q[j,x[i]]!=0 for i in ix) and w==sum(Q[j,x[i]]==y[i] for i in ix));ck('group_unique',not used.intersection(ix));used.update(ix)
        for e in z['entries']:
            ck('audit_evidence',all(Q[e['j'],x[i]]!=0 for i in e['indices']) and e['evidence']==digest([[i,int(x[i]),int(y[i])] for i in e['indices']]));ck('audit_monitor_disjoint',not used.intersection(e['indices']))
        for kind,t,j,g in z['events']:
            if kind=='stop':
                resume=next((e[1] for e in z['events'] if e[0]=='resume' and e[1]>t),len(x));ck('stop_authority',not np.any(z['actions'][t:resume]))
        return z
    for name,((a,b),phases) in CASES.items():
        for mode in PLAN['modes']:
            for policy in PLAN['policies']:
                total=Counter()
                for seed in SEEDS:
                    rng=np.random.default_rng(seed);x=rng.choice([0,2,7],H,p=[a/100,b/100,1-(a+b)/100]);p=np.zeros(H)
                    for t,v in phases:p[t:]=v/100
                    y=np.where(rng.random(H)<p,1,-1);z=check(x,y,(260,264),mode,policy)
                    for k,t,j,g in z['events']:total[k]+=1
                    total['net']+=z['net'];total['looks']+=z['spent']-20;total['trades']+=int(np.count_nonzero(z['actions']))
                    if seed==SEEDS[0]:
                        for cut in {t for k,t,j,g in z['events']}:
                            yy=y.copy();yy[cut:]*=-1;q=simulate(x,yy,(260,264),mode,policy);ck('future_prefix',np.array_equal(z['actions'][:cut],q['actions'][:cut]) and [e for e in z['events'] if e[1]<=cut]==[e for e in q['events'] if e[1]<=cut] and [e for e in z['entries'] if e['t']<=cut]==[e for e in q['entries'] if e['t']<=cut])
                summary[name+'_'+mode+'_'+policy]=dict(total,mean_net=total['net']/len(SEEDS))
    x=np.full(2200,7);x[3::4]=0;y=np.ones(len(x),dtype=int);y[64:192]=-1
    for name,xx,yy,spent,mode in [('sparse',x,y,20,'SPREAD'),('one_left',x,y,33,'SPREAD'),('final_boundary',x[:512],y[:512],20,'SPREAD')]:
        z=check(xx,yy,(260,),mode,'RESTART',spent);examples[name]=dict(events=z['events'],spent=z['spent'],fee=z['fee'],net=z['net'],groups=[g[:4] for g in z['groups']])
    ck('sparse_times',examples['sparse']['events'][:4]==[('admit',64,260,1),('stop',192,260,1),('restart_audit',448,260,1),('resume',512,260,2)])
    ck('final_no_resume',not any(e[0]=='resume' for e in examples['final_boundary']['events']));ck('one_left',examples['one_left']['spent']==35 and any(e[0]=='resume' for e in examples['one_left']['events']))
    xx=np.zeros(1024,dtype=int);yy=np.ones(1024,dtype=int);yy[256:]=-1;z=check(xx,yy,(260,),'LATE','RESTART',34);ck('exhaustion',z['events']==[('admit',256,260,1),('stop',288,260,1)] and z['spent']==35);examples['exhaustion']=dict(events=z['events'],spent=z['spent'],net=z['net'])
    return dict(passed=sum(c.values()),counts=dict(c),random_trials=len(CASES)*2*2*len(SEEDS),fixture_trials=4,plan_sha=digest(PLAN)),dict(plan=PLAN,summary=summary,examples=examples)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();a.outdir.mkdir(exist_ok=True);t,e=study()
    for k,v in [('tests',t),('examples',e)]:(a.outdir/f'Trading_Round129_{k}.json').write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
