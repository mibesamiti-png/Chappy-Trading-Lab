"""R86: one-shot conditional binomial screening on synthetic data only."""
import argparse, hashlib, json, random, runpy, math
from fractions import Fraction as F
from itertools import product
from pathlib import Path
P=Path(__file__).with_name('Chappy_Trading_Random_Market_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='f51883f82afac45140b2cf1b6ffbbe4ec8f77a1ecf935e19eb8c749f04e7f63f':raise ValueError('R85 hash')
R=runpy.run_path(str(P)); MODES=R['MODES']; B=256; N=256; SEEDS=range(86000,86256); OFFSET=100000; POL=('UNGATED','GATE50','GATE60','WAIT'); C=20
PLAN=dict(calibration_blocks=B,block_length=5,evaluation_slots=N,seeds=list(SEEDS),evaluation_seed_offset=OFFSET,delay=1,window=4,cost_bps=C,alpha='1/20',gates={'GATE50':'P(hit)<=1/2','GATE60':'P(hit)<=3/5'},candidate='R85 SYMMETRIC',modes=MODES,one_shot=True,synthetic_only=True,irregular='stress only; independence assumption not guaranteed',evaluation='separate seeded stream, no updates')
def gen(mode,seed,n):
    r=random.Random(seed);x=r.choice((-100,100));out=[]
    if mode=='irregular_bias':
        left=0
        for _ in range(n):
            if left==0:x=-x;left=r.randint(8,40)
            out.append(x if r.randrange(100)<80 else -x);left-=1
    else:
        out.append(x)
        for _ in range(n-1):
            if r.randrange(100)>=MODES[mode]:x=-x
            out.append(x)
    return out
# Exact integer binomial tails; minimal rejection count.
def thresholds(a,b):
    out=[]
    for n in range(B+1):
        tail=0; cutoff=n+1; denom=b**n
        for k in range(n,-1,-1):
            tail+=math.comb(n,k)*a**k*(b-a)**(n-k)
            if 20*tail<=denom:cutoff=k
            else:break
        out.append(cutoff)
    return tuple(out)
TH={50:thresholds(1,2),60:thresholds(3,5)}
def calibration(vs):
    n=k=0
    for i in range(4,len(vs),5):
        a=R['action']('SYMMETRIC',4,1,vs[i-4:i+1]); n+=bool(a); k+=a*vs[i]>0
    return n,k

def decisions(n,k):return dict(UNGATED=True,GATE50=k>=TH[50][n],GATE60=k>=TH[60][n],WAIT=False)
def exact(mode):
    if mode=='irregular_bias':return None
    p=F(MODES[mode],100); t=h=F(0)
    for bits in product((0,1),repeat=4):
        vs=[100];w=p**sum(bits)*(1-p)**(4-sum(bits))
        for z in bits:vs.append(vs[-1] if z else -vs[-1])
        a=R['action']('SYMMETRIC',4,1,vs);t+=w*bool(a);h+=w*(a*vs[-1]>0)
    q=h/t
    def power(g):
        return math.fsum(math.comb(B,n)*float(t)**n*float(1-t)**(B-n)*math.fsum(math.comb(n,k)*float(q)**k*float(1-q)**(n-k) for k in range(TH[g][n],n+1)) for n in range(B+1))
    return dict(trade_probability=str(t),accuracy=str(q),expected_yen_per_mature_slot=str(1000*(2*h-t)-200*t),gate50_power=min(1.0,max(0.0,power(50))),gate60_power=min(1.0,max(0.0,power(60))))
def run(mode,s):
    n,k=calibration(gen(mode,s,B*5)); gates=decisions(n,k)
    v=gen(mode,s+OFFSET,N); z=R['simulate'](v,1,'SYMMETRIC')
    return dict(seed=s,calibration_trades=n,calibration_hits=k,admitted=gates,evaluation=z)
def examples():
    agg={};runs={}
    for m in MODES:
        rows=[run(m,s) for s in SEEDS];runs[m]=rows;agg[m]={}
        for p in POL:
            accepted=[r for r in rows if r['admitted'][p]];values=[r['evaluation']['net_yen'] if r['admitted'][p] else 0 for r in rows]
            agg[m][p]=dict(admitted=len(accepted),mean_yen=sum(values)/len(rows),positive_runs=sum(v>0 for v in values),negative_runs=sum(v<0 for v in values),trades=sum(r['evaluation']['trades'] for r in accepted),conditional_mean_yen=sum(values)/len(accepted) if accepted else None)
    return dict(plan=PLAN,plan_sha=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest(),aggregate=agg,theory={m:exact(m) for m in MODES},runs=runs)
def tests():
    counts={}
    def ck(n,a,b):
        if a!=b:raise AssertionError((n,a,b))
        counts[n]=counts.get(n,0)+1
    for g,a,b in [(50,1,2),(60,3,5)]:
        for n,k in enumerate(TH[g]):
            tail=lambda j:sum(math.comb(n,i)*a**i*(b-a)**(n-i) for i in range(j,n+1))
            ck('threshold_valid',20*tail(k)<=b**n,True);ck('threshold_minimal',20*tail(k-1)>b**n,True)
    for n in range(B+1):ck('economic_gate_nested',TH[60][n]>=TH[50][n],True)
    for vs in product((-100,100),repeat=5):
        m=sum(vs[:4]);a=1 if m>80 else -1 if m< -80 else 0
        ck('block',calibration(vs),(int(bool(a)),int(a*vs[4]>0)))
        ck('sign_symmetry',calibration(vs),calibration(tuple(-v for v in vs)))
    for mode,s in product(MODES,SEEDS):
        cv=gen(mode,s,B*5); ev=gen(mode,s+OFFSET,N);r=run(mode,s)
        ck('generator_equivalence',cv[:N],R['series'](mode,s));ck('evaluation_generator',ev,R['series'](mode,s+OFFSET));ck('seed_disjoint',s+OFFSET not in SEEDS,True)
        n=k=0
        for i in range(4,len(cv),5):
            m=sum(cv[i-4:i]);a=1 if m>80 else -1 if m< -80 else 0;n+=bool(a);k+=a*cv[i]>0
        ck('calibration_counts',(n,k),(r['calibration_trades'],r['calibration_hits']));ck('gate50',r['admitted']['GATE50'],k>=TH[50][n]);ck('gate60',r['admitted']['GATE60'],k>=TH[60][n]);ck('gate_recompute',decisions(*calibration(cv)),r['admitted'])
        actions=[0 if i<4 else (1 if sum(ev[i-4:i])>80 else -1 if sum(ev[i-4:i])< -80 else 0) for i in range(N)]
        gs=[10*(a*v-C) if a else 0 for a,v in zip(actions,ev)];ck('eval_net',r['evaluation']['net_yen'],sum(gs));ck('eval_trades',r['evaluation']['trades'],sum(bool(a) for a in actions));ck('eval_hits',r['evaluation']['correct'],sum(a*v>0 for a,v in zip(actions,ev)))
    q=exact('iid');ck('null_accuracy',q['accuracy'],'1/2');ck('null_selection',q['trade_probability'],'5/8');ck('null_size',q['gate50_power']<=.05,True);ck('null_economic_size',q['gate60_power']<=.05,True)
    return dict(passed=sum(counts.values()),counts=counts)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(tests() if a.self_test else examples(),indent=2,sort_keys=True))
