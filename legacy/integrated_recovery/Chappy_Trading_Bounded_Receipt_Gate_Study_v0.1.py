"""R136: fixed-window partial receipt gate. Synthetic data only; no orders."""
import argparse, hashlib, json, runpy, bisect, itertools
from collections import Counter, defaultdict
from pathlib import Path
ROOT=Path(__file__).parent
P=ROOT/'Chappy_Trading_Receipt_Bias_Study_v0.1.py'
PIN='d75313a76c65fcc16e158d38c146ce656318d0cd56b7fcd4b7fc4013fa574999'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PIN:raise ValueError('R135 hash')
R=runpy.run_path(str(P)); M=R['R']; B=R['B']; D=R['D']
MODES=('REASON','STRICT','MATURE16','FIXED16','BOUNDS','FIXED16_BOUNDS')
SEEDS=range(136000,136016); DIRECT=range(136100,136164)
CASES=dict(R['CASES']); CASES.update({'good_unbiased_holes':(90,75,75,0,0),'weak_unbiased_holes':(45,75,75,0,0)})
PLAN=dict(parent=PIN,cases=CASES,seeds=list(SEEDS),direct_seeds=list(DIRECT),modes=MODES,rule='R135 parent authority unchanged; latest four consecutive eligible after DATA resume, or fixed t-17 window; allow iff >=3 received wins strictly before action, no adaptive window search; missing result unknown not assumed loss; existing 3/4 rule; no new admission looks; no claim of next-win probability; same fees as parent',direct='512 slots, authority fixed after 32, stationary iid',integrated='2048 slots, parent R135 generate and R132 REASON gate initial34')
def classify(v):
    lo=v.count(1);hi=lo+v.count(None)
    return 'ALLOW' if lo>=3 else 'DENY' if hi<3 else 'UNKNOWN'
def bounded(e,ev,a,m):
    resume=next((t for t,k,v in a['log'] if (k,v)==('RESUME','DATA')),None)
    out=list(a['actions']); proof={}; status=Counter()
    if resume is None:return out,proof,status
    by=defaultdict(list)
    for t,i,r,v in ev:by[t].append((i,v))
    slots=[];received={}
    for t in range(resume+1,len(e)+1):
        if out[t-1]:
            j=len(slots) if m=='BOUNDS' else bisect.bisect_right(slots,t-17)
            w=slots[j-4:j] if j>=4 else []
            v=[received.get(i) for i in w];s=classify(v) if len(w)==4 else 'INSUFFICIENT'
            status[s]+=1
            if s=='ALLOW':proof[t]=tuple(w)
            else:out[t-1]=0
        if e[t-1]:slots.append(t)
        for i,v in by[t]:
            if i>resume:received[i]=v
    return out,proof,status
def oracle(e,ev,a,m):
    resume=next((t for t,k,v in a['log'] if (k,v)==('RESUME','DATA')),None)
    out=list(a['actions']);proof={};status=Counter()
    if resume is None:return out,proof,status
    slots=[i for i,x in enumerate(e,1) if x and i>resume];by=defaultdict(list)
    for t,i,r,v in ev:by[i].append((t,r,v))
    for j,t in enumerate(slots):
        if not out[t-1]:continue
        k=j if m=='BOUNDS' else bisect.bisect_right(slots,t-17)
        w=slots[max(0,k-4):k]
        if len(w)<4:s='INSUFFICIENT'
        else:
            v=[max((x for x in by[i] if x[0]<t),default=(0,0,None))[2] for i in w]
            possible=[sum(z) for z in itertools.product(*[(0,1) if x is None else (x,) for x in v])]
            s='ALLOW' if min(possible)>=3 else 'DENY' if max(possible)<3 else 'UNKNOWN'
        status[s]+=1
        if s=='ALLOW':proof[t]=tuple(w)
        else:out[t-1]=0
    return out,proof,status
def study():
    c=Counter();cases={};fixtures={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    for v in itertools.product((0,1,None),repeat=4):
        p=[sum(x)>=3 for x in itertools.product(*[(0,1) if z is None else (z,) for z in v])]
        ck('exhaustive_ternary',classify(v)==('ALLOW' if all(p) else 'DENY' if not any(p) else 'UNKNOWN'))
    def check(e,y,ev,a,m):
        if m in ('BOUNDS','FIXED16_BOUNDS'):
            x,p,s=bounded(e,ev,a,m);ck('bounds_oracle',(x,p,s)==oracle(e,ev,a,m))
        else:
            x,p=M['filter_actions'](e,ev,a,m);s=Counter();ck('old_oracle',(x,p)==M['oracle'](e,ev,a,m))
        ck('authority',all(v<=b for v,b in zip(x,a['actions'])));ck('support',all(not v or e[i] for i,v in enumerate(x)));ck('budget',a['used']<=35)
        net=sum((800 if w else -1200)*v for w,v in zip(y,x))-len(e)-a['fees']
        ck('account',net==a['net']+sum((800 if w else -1200)*(v-b) for w,v,b in zip(y,x,a['actions'])))
        return x,p,s,net
    for direct,seeds in ((True,DIRECT),(False,SEEDS)):
        for name,case in CASES.items():
            agg={m:Counter() for m in MODES}
            for seed in seeds:
                e,y,ev=R['generate'](seed,case,direct)
                if direct:a=R['direct_base'](e,y)
                else:
                    d=D['run'](e,ev,'WAIT_HOLD');a=B['gate'](e,y,d,'REASON',34)
                res={}
                for m in MODES:
                    x,p,s,net=check(e,y,ev,a,m);res[m]=x,p
                    z=agg[m];z.update(s);z['net']+=net;z['trades']+=sum(x);start=32 if direct else 1024;z['post_trades']+=sum(x[start:]);z['post_wins']+=sum(int(w)*v for w,v in zip(y[start:],x[start:]));z['resumes']+=sum((k,v)==('RESUME','DATA') for t,k,v in a['log'])
                    if m in ('BOUNDS','FIXED16_BOUNDS'):
                        by=defaultdict(list)
                        for t,i,r,v in ev:by[i].append((t,r,v))
                        for t,w in p.items():
                            vals=[max((q for q in by[i] if q[0]<t),default=(0,0,None))[2] for i in w]
                            ck('known_wins',vals.count(1)>=3);ck('strict_causality',all(i<t for i in w));z['partial_permits']+=int(None in vals)
                    if seed==seeds[0]:
                        cut=256 if direct else 1536
                        b=R['direct_base'](e[:cut],y[:cut]) if direct else B['gate'](e[:cut],y[:cut],D['run'](e[:cut],ev,'WAIT_HOLD'),'REASON',34)
                        q,pr,*_=check(e[:cut],y[:cut],ev,b,m);ck('future_prefix',q==x[:cut] and pr=={t:w for t,w in p.items() if t<=cut})
                for new,old in [('BOUNDS','STRICT'),('FIXED16_BOUNDS','FIXED16')]:ck('superset',all(v>=u for v,u in zip(res[new][0],res[old][0])))
            cases[('direct_' if direct else 'integrated_')+name]={m:dict(z,mean_net=z['net']/len(seeds),mean_post_trades=z['post_trades']/len(seeds),trade_rate=z['post_wins']/max(1,z['post_trades'])) for m,z in agg.items()}
    # isolate fixed window: same truth, different reception; exact boundary correction.
    e=[True]*64;y=[1]*36+[0]*28;a=R['direct_base'](e,y)
    for name,ev in [('one_missing',[(i,i,1,w) for i,w in enumerate(y,1) if i!=36]),('losses_missing',[(i,i,1,w) for i,w in enumerate(y,1) if w]),('correction',sorted([(i,i,1,w) for i,w in enumerate(y,1)]+[(37,34,2,0),(38,35,2,0)]))]:
        fixtures[name]={}
        for m in MODES:
            x,p,s,n=check(e,y,ev,a,m);fixtures[name][m]=dict(action37=x[36],action38=x[37],action39=x[38],action41=x[40],trades=sum(x),net=n)
    ck('partial_fixture',fixtures['one_missing']['BOUNDS']['action37']==1 and fixtures['one_missing']['STRICT']['action37']==0)
    ck('stale_fixture',fixtures['losses_missing']['BOUNDS']['action41']==0 and fixtures['losses_missing']['MATURE16']['action41']==1)
    ck('revision_boundary',fixtures['correction']['BOUNDS']['action37']==1 and fixtures['correction']['BOUNDS']['action38']==0)
    return dict(passed=sum(c.values()),checks=dict(c)),dict(plan=PLAN,plan_sha=B['digest'](PLAN),cases=cases,fixtures=fixtures)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='.');a=p.parse_args();t,e=study();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for n,z in [('tests',t),('examples',e)]:(out/f'Trading_Round136_{n}.json').write_text(json.dumps(z,sort_keys=True,indent=2)+'\n')
    print(t)
