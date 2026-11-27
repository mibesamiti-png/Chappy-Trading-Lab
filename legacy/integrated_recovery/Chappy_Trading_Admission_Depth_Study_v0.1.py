"""R122: exact finite-budget admission depth, synthetic two opposite candidates."""
import argparse, hashlib, json, runpy, math
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
P=Path(__file__).with_name('Chappy_Trading_Admission_Allocation_Study_v0.1.py')
HASH='af6ee2c9beb5b76b3c8d0c7cc933181f5dccc54dd061b9dd07ce90e67432d2dc'
if hashlib.sha256(P.read_bytes()).hexdigest()!=HASH:raise ValueError('parent hash')
R=runpy.run_path(str(P)); K=R['K']; LOOKS=tuple(K)
S={
 'A_DEEP':(5,LOOKS,()),
 'PREFIX_2_2':(5,(16,32),(16,32)),
 'SPREAD_2_2':(5,(16,256),(16,256)),
 'SPREAD_3_2':(5,(16,64,256),(16,256)),
 'LATE_1_1':(5,(256,),(256,)),
 'PREFIX_4_4':(9,(16,32,64,128),(16,32,64,128)),
 'SPREAD_4_4':(9,(16,32,64,256),(16,32,64,256)),
 'FULL_5_5':(10,LOOKS,LOOKS)}
PS=(0,10,20,25,30,35,40,45,50,55,60,65,70,75,80,90,100); HS=(512,2048)
PLAN=dict(parent=HASH,thresholds=K,schedules=S,p_up_percent=PS,horizons=HS,alpha='1/700',prior_spend=15,maximum_total=35,cost=1,fee=200,payoffs=[800,-1200],scope='frozen opposite candidates; stationary iid Bernoulli; fixed schedules; first passing candidate wins; no monitoring; no trades until admission; unspent budget not valued')
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()

def exact(p,a,b):
    """Each integer state at n has mass numerator over 100**n."""
    active=[1]; events=[]; schedule=sorted(set(a+b)); spent=F(0)
    for n in range(1,schedule[-1]+1):
        nxt=[0]*(n+1)
        for w,v in enumerate(active):
            nxt[w]+=v*(100-p);nxt[w+1]+=v*p
        active=nxt
        if n not in schedule:continue
        den=100**n; lanes=int(n in a)+int(n in b); before=sum(active)
        spent+=F(before*lanes,den)
        pa=pb=0
        for w,v in enumerate(active):
            qa=n in a and w>=K[n];qb=n in b and n-w>=K[n]
            if qa and qb:raise ValueError('tie impossible')
            if qa:pa+=v;active[w]=0
            if qb:pb+=v;active[w]=0
        events.append((n,F(pa,den),F(pb,den),F(sum(active),den)))
    return events,spent

def oracle(p,a,b):
    """Independent checkpoint convolution with binomial increments."""
    old={0:1};prev=0;events=[];spent=F(0)
    for n in sorted(set(a+b)):
        d=n-prev; coeff=[math.comb(d,k)*p**k*(100-p)**(d-k) for k in range(d+1)]
        dist={}
        for w,v in old.items():
            for k,c in enumerate(coeff):
                if v and c:dist[w+k]=dist.get(w+k,0)+v*c
        den=100**n;spent+=F(sum(dist.values())*(int(n in a)+int(n in b)),den)
        groups=[0,0,0];old={}
        for w,v in dist.items():
            j=0 if n in a and w>=K[n] else 1 if n in b and n-w>=K[n] else 2
            groups[j]+=v
            if j==2:old[w]=v
        events.append((n,*[F(x,den) for x in groups]));prev=n
    return events,spent

def metrics(p,events,spent,H):
    pa=sum((a for _,a,_,_ in events),F(0));pb=sum((b for _,_,b,_ in events),F(0)); miss=1-pa-pb
    wait=sum((n*(a+b) for n,a,b,_ in events),F(0))+events[-1][0]*miss
    ga=20*p-1200;gb=800-20*p
    gross=sum(((H-n)*(ga*a+gb*b) for n,a,b,_ in events),F(0))
    net=gross-wait-200*(pa+pb)
    return dict(pass_A=pa,pass_B=pb,miss=miss,beneficial_pass=(pa if ga>0 else F(0))+(pb if gb>0 else F(0)),nonpositive_pass=(pa if ga<=0 else F(0))+(pb if gb<=0 else F(0)),expected_wait=wait,expected_looks=spent,expected_gross=gross,expected_net=net)

def study():
    c=Counter();out={}; stored={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        c[k]+=1
    for name,(cap,a,b) in S.items():
        ck('budget_plan',len(a)+len(b)<=cap and 15+10+cap<=35)
        ck('schedule_valid',all(tuple(sorted(set(x)))==x and set(x)<=set(K) for x in (a,b)))
        for p in PS:
            e,s=exact(p,a,b);o,so=oracle(p,a,b);ck('exact_oracle',e==o);ck('look_cost_oracle',s==so);stored[name,p]=(e,s)
            survival=F(1)
            for n,pa,pb,rem in e:
                ck('mass_conservation',pa+pb+rem==survival);ck('nonnegative',min(pa,pb,rem)>=0);ck('lane_A',n in a or pa==0);ck('lane_B',n in b or pb==0);survival=rem
            ck('expected_budget',0<=s<=len(a)+len(b));ck('probability',sum((x+y for _,x,y,_ in e),F(0))+e[-1][3]==1)
            if 40<=p<=60:ck('null_union_bound',1-e[-1][3]<=F(len(a)+len(b),700))
            for H in HS:
                m=metrics(p,e,s,H);ck('partition',m['beneficial_pass']+m['nonpositive_pass']+m['miss']==1);ck('wait_bound',0<=m['expected_wait']<=e[-1][0]);ck('net_identity',m['expected_net']==m['expected_gross']-m['expected_wait']-200*(1-m['miss']))
                out.setdefault(str(p),{}).setdefault(str(H),{})[name]={k:float(v) for k,v in m.items()}
    for name,(_,a,b) in S.items():
        if a==b:
            for p in PS:
                e,s=stored[name,p];f,t=stored[name,100-p];ck('symmetry',s==t and [(n,y,x,r) for n,x,y,r in e]==f)
        for p in (0,100):
            e,s=stored[name,p];m=metrics(p,e,s,2048);sched=a if p==100 else b
            ck('deterministic',m['beneficial_pass']==int(bool(sched)) and m['expected_wait']==(sched[0] if sched else e[-1][0]))
    for p in PS:
        e,_=stored['LATE_1_1',p];n,pa,pb,rem=e[0]
        ck('closed_form_A',pa==F(sum(math.comb(n,w)*p**w*(100-p)**(n-w) for w in range(K[n],n+1)),100**n))
        ck('closed_form_B',pb==F(sum(math.comb(n,w)*(100-p)**w*p**(n-w) for w in range(K[n],n+1)),100**n))
    return dict(passed=sum(c.values()),counts=dict(c),exact_schedules=len(S)*len(PS),economic_cases=len(S)*len(PS)*len(HS),plan_sha=SHA),dict(plan=PLAN,plan_sha=SHA,results=out)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',type=Path,required=True);args=ap.parse_args();args.outdir.mkdir(exist_ok=True);t,e=study()
    for kind,obj in [('tests',t),('examples',e)]:(args.outdir/f'Trading_Round122_{kind}.json').write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')
    print(json.dumps(t))
