"""R143: attribution of R142 core results, synthetic only; no changes to trading policy."""
import hashlib,json,runpy,math
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Capital_Comparison_v0.1.py')
assert_sha='9bcae09e6015b1885f69bb771f8f8493e759c1c8d5c4f55e4914efa7659b69f1'
if hashlib.sha256(P.read_bytes()).hexdigest()!=assert_sha:raise ValueError('R142 hash')
R=runpy.run_path(str(P)); C=R['R']; G=C['R']['R']['R']; T=C['T']; H=G['H']; SHIFT=G['SHIFT']; TRAIN=G['TRAIN']; S=G['S']; K=C['K']; LIMIT=C['R']['LIMITS']['BLOCK_SPEND']; CASES=('rare','rare_disappears','rare_boundary','null','strong'); SEEDS={'replay':list(range(142000,142016)),'fresh':list(range(143000,143032))}
PLAN=dict(source_sha=assert_sha,seeds=SEEDS,cases=CASES,costs=[200,400],diagnostic_only=True,split=SHIFT,block=32,alarm=LIMIT,truth='evaluation only; no policy changes',methods=['B_LEARN','C_AUDIT','E_REFRESH'])
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest()
def inspect(x,y,case,cost,ck):
    z={m:C['simulate'](x,y,m) for m in PLAN['methods']}; a={m:R['settle'](y,[(i,d) for i,d,_ in q['trades']],cost) for m,q in z.items()}
    e=z['E_REFRESH']['epochs'][0]; j=e['candidate']; admit=e['admit']; d=T[j,x]; ix=np.flatnonzero(d[TRAIN:])+TRAIN; hit=d[ix]==y[ix]; before=ix[ix<SHIFT]; after=ix[ix>=SHIFT]
    b={i:g-cost for i,_,g,_ in a['B_LEARN']['fills']}; c={i:g-cost for i,_,g,_ in a['C_AUDIT']['fills']}
    ck('same_candidate',j==z['B_LEARN']['epochs'][0]['candidate']==z['C_AUDIT']['epochs'][0]['candidate']); ck('same_audit',e['looks']==z['C_AUDIT']['epochs'][0]['looks'] and admit==z['C_AUDIT']['epochs'][0]['admit'])
    ck('audit_oracle',e['looks']==[[int(ix[n-1])+1,n,int(hit[:n].sum())] for n in K if n<=len(ix) and (not e['looks'] or n<=e['looks'][-1][1])] if j else not e['looks'])
    rejected=sum(v for i,v in b.items() if i not in c and admit is None); wait=sum(v for i,v in b.items() if i not in c and admit is not None and i<admit); later=sum(v for i,v in b.items() if i not in c and admit is not None and i>=admit); c_only=sum(v for i,v in c.items() if i not in b)
    ck('paired_accounting',a['B_LEARN']['net']-a['C_AUDIT']['net']==rejected+wait+later-c_only);ck('shared_fill',all(v==c[i] for i,v in b.items() if i in c))
    live=ix[ix>=admit] if admit is not None else ix[:0]; stop=e['stop']; live=live[live<stop] if stop is not None else live; h=(d[live]==y[live]); groups=[live[k:k+32] for k in range(0,len(live)-31,32)]; wins=[int((d[g]==y[g]).sum()) for g in groups]; alarms=[int(g[-1])+1 for g,w in zip(groups,wins) if w<=LIMIT]
    ck('monitor_oracle',stop==(alarms[0] if alarms else None));ck('monitor_support',sum(len(g) for g in groups)+len(live)%32==len(live));ck('monitor_causal',all(g[0]>=admit for g in groups))
    # Model truth is computed only after fixed actions. Cost 400 reduces each eligible expected payoff by 200.
    weights=np.array([S['WEIGHTS']['skewed'][k] for k in S['MASK']]); support=float((np.abs(T[j])@weights)/200)
    pre,post=G['CASES'][case]; ev=[float(S['theory'](m,G['W'])[j]/20000-(cost-200)*support) for m in (pre,post)]
    post_live=live[live>=SHIFT]; post_full=sum(g[0]>=SHIFT for g in groups);post_mix=sum(g[0]<SHIFT<=g[-1] for g in groups)
    return dict(candidate=j,support=support,pre_ev=ev[0],post_ev=ev[1],selected=int(j!=0),admit=admit,admitted=int(admit is not None),admitted_pre=int(admit is not None and admit<=SHIFT),audit_n=e['looks'][-1][1] if e['looks'] else 0,audit_w=e['looks'][-1][2] if e['looks'] else 0,pre_eligible=len(before),post_eligible=len(after),post_live=len(post_live),post_full_blocks=post_full,mixed_blocks=post_mix,live_blocks=len(groups),min_block_wins=min(wins) if wins else None,stop=stop,stopped=int(stop is not None),b_net=a['B_LEARN']['net'],c_net=a['C_AUDIT']['net'],e_net=a['E_REFRESH']['net'],b_minus_c=a['B_LEARN']['net']-a['C_AUDIT']['net'],rejected_pnl=rejected,waiting_pnl=wait,later_b_only_pnl=later,c_only_pnl=c_only,post_e_pnl=sum(g-cost for i,_,g,_ in a['E_REFRESH']['fills'] if i>=SHIFT),b_blocked=len(a['B_LEARN']['blocked']),c_blocked=len(a['C_AUDIT']['blocked']))
def study():
    counts={}; rows={}; summary={}
    def ck(k,v):
        if not v:raise AssertionError(k)
        counts[k]=counts.get(k,0)+1
    for cohort,seeds in SEEDS.items():
        rows[cohort]={};summary[cohort]={}
        for case in CASES:
            rows[cohort][case]={};summary[cohort][case]={}
            for cost in PLAN['costs']:
                rr=[]
                for seed in seeds:
                    x,y=G['series'](seed,case); r=inspect(x,y,case,cost,ck);r['seed']=seed;rr.append(r)
                rows[cohort][case][str(cost)]=rr
                aa=[r for r in rr if r['admitted']]; keys=['b_net','c_net','e_net','b_minus_c','rejected_pnl','waiting_pnl','later_b_only_pnl','c_only_pnl','pre_ev','post_ev','post_e_pnl','support']
                summary[cohort][case][str(cost)]={**{k:sum(r[k] for r in rr)/len(rr) for k in keys},'admitted':len(aa),'stopped':sum(r['stopped'] for r in rr),'selected':sum(r['selected'] for r in rr),'admit_pre':sum(r['admitted_pre'] for r in rr),'admitted_mean_slot':sum(r['admit'] for r in aa)/len(aa) if aa else None,'admitted_mean_post_live':sum(r['post_live'] for r in aa)/len(aa) if aa else None,'admitted_mean_post_full_blocks':sum(r['post_full_blocks'] for r in aa)/len(aa) if aa else None,'admitted_min_block_wins':min((r['min_block_wins'] for r in aa if r['min_block_wins'] is not None),default=None),'admitted_post_negative':sum(r['post_ev']<0 for r in aa),'audit_no_final_look':sum(r['candidate']!=0 and not r['admitted'] and r['audit_n']<256 for r in rr)}
    old=json.loads(P.with_name('Trading_Round142_examples.json').read_text())
    for case in CASES:
        for cost in PLAN['costs']:
            for key,mode in [('b_net','B_LEARN'),('c_net','C_AUDIT'),('e_net','E_REFRESH')]:ck('R142_replay',summary['replay'][case][str(cost)][key]==old['summary'][case][str(cost)][mode]['mean_net'])
    theory={}
    for p in (.5,.6,.9):
        q=sum(math.comb(32,k)*p**k*(1-p)**(32-k) for k in range(LIMIT+1));theory[str(p)]={'one_block':q,'one_full_block':q,'two_full_blocks':-math.expm1(2*math.log1p(-q)),'four_full_blocks':-math.expm1(4*math.log1p(-q))}
    ck('limit',LIMIT==8)
    return dict(plan=PLAN,plan_sha=SHA,summary=summary,rows=rows,theory=theory,checks=counts,passed=sum(counts.values()))
if __name__=='__main__':print(json.dumps(study(),sort_keys=True,indent=2,default=lambda x: x.item()))
