"""R104: unchanged R103 policies under prespecified synthetic phase schedules."""
import argparse, hashlib, json, runpy
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('Chappy_Trading_Refresh_Trigger_Study_v0.1.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='cb4d0570492b17d7e4fb963cba0191572463e67d96adb805d44af5fbb9d244ca':raise ValueError('R103 hash')
R=runpy.run_path(str(P)); T=R['T']; H=R['H']; SHIFT=R['SHIFT']; METHODS=R['METHODS']; inputs=R['R']['R']['inputs']; SEEDS=range(104000,104064)
W=(70,20,9,1); W5=(70,20,5,5)
def strong(p):return (p,100-p,100-p,p)
def rare(p):return (50,50,50,p)
# phase records (exclusive end, frequency weights, continuation probabilities)
CASES={
 'stable':[(H,W,strong(75))],
 'gradual':[(4096,W,strong(75)),(5120,W,strong(65)),(6144,W,strong(55)),(7168,W,strong(45)),(H,W,strong(35))],
 'temporary':[(4096,W,strong(75)),(4608,W,strong(25)),(H,W,strong(75))],
 'weak_persistent':[(4096,W,strong(75)),(H,W,strong(55))],
 'rare_weak':[(4096,W,rare(90)),(H,W,rare(70))],
 'rare_loss_1pct':[(4096,W,rare(90)),(H,W,rare(50))],
 'rare_loss_5pct':[(4096,W5,rare(90)),(H,W5,rare(50))],
 'strong_reversal':[(4096,W,strong(75)),(H,W,strong(25))],
}
PLAN=dict(cases=CASES,seeds=list(SEEDS),offset_stride=1000000,methods=METHODS,unchanged_R103=True,synthetic_only=True,diagnostic='live eligible realized wins skipped and losses avoided; not ex ante opportunity value')
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def series(seed,case):
    xs=[];ys=[];start=0
    for i,(end,w,p) in enumerate(CASES[case]):
        x,y,_=inputs(seed+i*1000000,end-start,w,p);xs.append(x);ys.append(y);start=end
    return np.concatenate(xs),np.concatenate(ys)
def diagnostics(x,y,r):
    # Independent audit of realized live eligible outcomes. Monitor only uses prior observations.
    skipped_w=skipped_l=trades=gross=post_gross=eligible=0
    for e in r['epochs']:
        if e['pass_at'] is None:continue
        d=T[e['candidate'],x]; ix=np.flatnonzero(d[e['train_end']:e['live_end']])+e['train_end']; wins=d[ix]==y[ix]; hist=list(map(bool,wins[:e['audit_n']]))
        for i,win in zip(ix[e['audit_n']:],wins[e['audit_n']:]):
            eligible+=1
            if len(hist)>=4 and sum(hist[-4:])>=3:
                pnl=800 if win else -1200;gross+=pnl;trades+=1;post_gross+=pnl if i>=SHIFT else 0
            elif win:skipped_w+=1
            else:skipped_l+=1
            hist.append(bool(win))
    return dict(skipped_w=skipped_w,skipped_l=skipped_l,eligible=eligible,trades=trades,gross=gross,post_gross=post_gross)
def study(test):
    counts={};out={}
    def ck(k,a,b):
        if a!=b:raise AssertionError((k,a,b))
        counts[k]=counts.get(k,0)+1
    for case,phases in CASES.items():
        ck('schedule',phases[-1][0],H);ck('weights',all(sum(w)==100 and all(0<=q<=100 for q in p) for _,w,p in phases),True)
        rows={m:[] for m in METHODS}
        for seed in SEEDS:
            x,y=series(seed,case)
            ck('length',len(x)==len(y)==H,True)
            for m in METHODS:
                r=R['simulate'](x,y,m);d=diagnostics(x,y,r)
                ck('accounting',r['net'],r['gross']-r['fees']);ck('gross',d['gross'],r['gross']);ck('trades',d['trades'],r['trades']);ck('eligible',d['eligible'],d['trades']+d['skipped_w']+d['skipped_l']);ck('epoch_limit',len(r['epochs'])<=2,True)
                if test and seed<SEEDS.start+4:
                    ck('oracle',tuple(r[k] for k in ('net','gross','fees','trades','post_net','refresh'))+([e['pass_at'] for e in r['epochs'] if e['pass_at'] is not None],),R['oracle'](x,y,m))
                if test and r['refresh'] is not None:
                    cut=r['refresh'];q=R['simulate'](x[:cut],y[:cut],m);ck('prefix',q['epochs'][0]['live_end'],cut);ck('prefix_pass',q['epochs'][0]['pass_at'],r['epochs'][0]['pass_at'])
                rows[m].append((r,d))
            ck('matched_initial',len({rows[m][-1][0]['epochs'][0]['pass_at'] for m in METHODS}),1)
        out[case]={}
        for m,rs in rows.items():
            ref=[r['refresh'] for r,d in rs if r['refresh'] is not None];z=dict(initial_pass=sum(r['epochs'][0]['pass_at'] is not None for r,d in rs),refresh=len(ref),refresh_before_shift=sum(i<SHIFT for i in ref),refresh_during_temporary=sum(SHIFT<=i<4608 for i in ref) if case=='temporary' else None,second_pass=sum(len(r['epochs'])==2 and r['epochs'][1]['pass_at'] is not None for r,d in rs),mean_refresh_slot=sum(ref)/len(ref) if ref else None)
            z.update({'mean_'+k:sum(r[k] for r,d in rs)/len(rs) for k in ('net','gross','fees','post_net','trades')});z.update({'mean_'+k:sum(d[k] for r,d in rs)/len(rs) for k in ('eligible','skipped_w','skipped_l')});out[case][m]=z
    return dict(passed=sum(counts.values()),counts=counts,plan_sha=SHA) if test else dict(plan=PLAN,plan_sha=SHA,summary=out)
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(study(a.self_test),indent=2,sort_keys=True))
