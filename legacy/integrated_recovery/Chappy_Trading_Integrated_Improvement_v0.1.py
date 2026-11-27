"""R63: paired artificial policy review, not a market study or executable strategy."""
import argparse, copy, hashlib, importlib.util, json, sys
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).parent

def load(name,file,pin):
    p=ROOT/file
    if hashlib.sha256(p.read_bytes()).hexdigest()!=pin:raise RuntimeError(name+' hash mismatch')
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
old=load('r50','Chappy_Trading_Improvement_Study_v0.1.py','f93e62fa2dcbd88fed46e8c80e833b3d91dd5539332b70213ecb032e52e11512')
a=load('r62','Chappy_Trading_Integrated_Review_v0.1.py','da340996b7f7144fad54462dd0f245ef19b71933f97efa1d1bb22434d64479d5')
e=a.e;r=a.r;need=r.need;digest=old.digest
PLAN={'id':'R63-ARTIFICIAL-01','rules':{p:old.PLAN['policies'][p] for p in ('BASE','STRICT')},'splits':{'discovery':['D01','D02'],'evaluation':['E01','E02','E03']},'cutoffs':{'D01':145,'D02':145,'E01':145,'E02':145,'E03':115},'threshold_score':1000,'criterion':'all pairs complete and positive summed cents delta on both splits; no live adoption','scope':'fixed engineered cases, not statistical holdout; one artificial order resolution choice'}
PLAN_SHA='a338a6d20bc9629597c99aec2235713ac1f9ed6652a0db9f20049bd260547164'

def prefix():
    ev=e.fixture();i=next(i for i,x in enumerate(ev) if x['kind']=='fill' and x['data']['order']=='E-C');return ev[:i]

def freeze(plan,split,ids):
    need(digest(plan)==PLAN_SHA,'plan hash');need(split in plan['splits'] and ids==plan['splits'][split],'split identity')
    pre=prefix();v=e.seal(pre);scores=next(x['data']['scores'] for x in pre if x['kind']=='allocate');review=a.review(v['records'],v['head'],115)
    by={x['symbol']:x for x in review['rows']};need(by['C']['status']=='PENDING' and by['C']['selected'],'pending allocation')
    x=old.row('C',2 if scores['C']>=plan['threshold_score'] else 1,True);x['decision_tick']=115;x['received_tick']=115
    need(by['C']['gate']=='RESEARCH_ELIGIBLE','gate')
    return {'split':split,'ids':list(ids),'plan_sha':PLAN_SHA,'prefix_head':v['head'],'input':x,'decisions':{p:old.decide(rule,x) for p,rule in plan['rules'].items()}}

# Future prices are passed only after the decision snapshot has been constructed.
OUTCOMES={'D01':988,'D02':980,'E01':1021,'E02':1030,'E03':1025}

def branch(action,c_bid):
    need(action in ('SELECT','WAIT_SIGNAL'),'action');need(type(c_bid) is int and 1<=c_bid<=10000,'price')
    cancel=action=='WAIT_SIGNAL';ev=copy.deepcopy(e.fixture(cancel));
    if cancel:
        ix=next(i for i,x in enumerate(ev) if x['kind']=='cancel');x=ev.pop(ix);x['at']=115;idx=next(i for i,x in enumerate(ev) if x['at']==120);ev.insert(idx,x)
        tick=next(x for x in ev if x['kind']=='tick' and x['at']==120);tick['data']['external']['pending']=[];tick['data']['external']['terminal']['E-C']='CANCELLED'
    for x in ev:
        if x['kind']=='observe' and x['at']==120 and x['data']['rows'][0]['symbol']=='C':x['data']['rows']=r.obs('C',120,close=c_bid+1,ask=c_bid+1,bid=c_bid)
    # independent expected cash in cents (integer yen, 100 shares, 10 bps)
    final=100189790+(0 if cancel else (c_bid-1000)*10000-10000-c_bid*10)
    for x in ev:
        if x['kind']=='tick' and x['at']>=125:
            snap=x['data']['external'];snap['cash']=final
            if x['at']==140:x['data']['approval']['account_sha']=r.recovery.digest(r.recovery.account_payload(snap))
    # Renumber after shifting cancellation, preserving identical prefix IDs.
    for i,x in enumerate(ev,1):x['id']=str(i)
    return ev

def evaluate(plan,frozen,outcomes):
    need(frozen==freeze(plan,frozen['split'],frozen['ids']),'frozen mismatch');need(set(outcomes)==set(frozen['ids']),'case coverage')
    cases=[]
    for ident in frozen['ids']:
        result={};cutoff=plan['cutoffs'][ident]
        for p,action in frozen['decisions'].items():
            ev=branch(action,outcomes[ident]);need(e.seal(ev[:len(prefix())])['head']==frozen['prefix_head'],'common prefix');v=e.seal(ev);aud=a.review(v['records'],v['head'],cutoff);s=aud['execution_summary'];complete=not any(s['held'].values()) and not s['pending_orders'] and cutoff>=120
            result[p]={'action':action,'head':v['head'],'audit':aud,'complete':complete,'pnl_cents':s['realized_pnl_cents'] if complete else None}
        b,c=result['BASE'],result['STRICT'];need(b['audit']['hypothesis_summary']==c['audit']['hypothesis_summary'],'unequal observation outcome');need(b['audit']['plan_sha']==c['audit']['plan_sha'],'unequal allocation');
        cases.append({'id':ident,'cutoff':cutoff,'policies':result,'delta_cents':c['pnl_cents']-b['pnl_cents'] if b['complete'] and c['complete'] else None})
    known=[x['delta_cents'] for x in cases if x['delta_cents'] is not None];return {'cases':cases,'total_pairs':len(cases),'complete_pairs':len(known),'unknown_pairs':len(cases)-len(known),'complete_subset_delta_cents':sum(known) if known else None,'all_pairs_delta_cents':sum(known) if len(known)==len(cases) else None,'pass':len(known)==len(cases) and sum(known)>0}

def study():
    f={s:freeze(PLAN,s,ids) for s,ids in PLAN['splits'].items()};v={s:evaluate(PLAN,x,{i:OUTCOMES[i] for i in x['ids']}) for s,x in f.items()};return {'plan':PLAN,'plan_sha':PLAN_SHA,'frozen':f,'results':v,'candidate':'SYNTHETIC_PASS_ONLY' if all(x['pass'] for x in v.values()) else 'REJECT_OR_UNPROVEN','live_adoption':False}

def self_test():
    tests=[]
    def ck(n,x,y=True):
        if x!=y:raise AssertionError((n,x,y))
        tests.append({'name':n,'pass':True})
    def reject(n,fn):
        try:fn()
        except (ValueError,KeyError,TypeError):ck(n,True)
        else:ck(n,False)
    s=study();ck('plan sha',digest(PLAN),PLAN_SHA);ck('disjoint',not set(PLAN['splits']['discovery'])&set(PLAN['splits']['evaluation']));ck('frozen base',s['frozen']['discovery']['decisions']['BASE'],'SELECT');ck('frozen strict',s['frozen']['discovery']['decisions']['STRICT'],'WAIT_SIGNAL');ck('discovery pass',s['results']['discovery']['pass']);ck('evaluation fail',s['results']['evaluation']['pass'],False);ck('candidate rejected',s['candidate'],'REJECT_OR_UNPROVEN');ck('no adoption',s['live_adoption'],False)
    for split,z in s['results'].items():
        ck(split+' coverage',z['total_pairs'],len(PLAN['splits'][split]));ck(split+' unknown',z['unknown_pairs'],int(split=='evaluation'))
        for case in z['cases']:
            ident=case['id'];px=OUTCOMES[ident];b,c=(case['policies'][p] for p in ('BASE','STRICT'));complete=ident!='E03';expected=Fraction((px-1000)*100)-Fraction((px+1000)*100,1000)
            ck(ident+' complete base',b['complete'],complete);ck(ident+' complete strict',c['complete'],complete);ck(ident+' exact delta',case['delta_cents'],-expected*100 if complete else None);ck(ident+' same hypotheses',b['audit']['hypothesis_summary'],c['audit']['hypothesis_summary']);ck(ident+' three hypotheses',b['audit']['hypothesis_summary']['decisions'],3);ck(ident+' base C status',b['audit']['rows'][2]['status'],'CLOSED' if complete else 'OPEN_POSITION');ck(ident+' strict C status',c['audit']['rows'][2]['status'],'CANCELLED');ck(ident+' strict C no pnl',c['audit']['rows'][2]['realized_pnl_cents'],None);ck(ident+' same prefix',e.seal(branch('SELECT',px)[:len(prefix())])['head'],e.seal(branch('WAIT_SIGNAL',px)[:len(prefix())])['head']);ck(ident+' different branch heads',b['head']!=c['head']);ck(ident+' strict closed count',c['audit']['execution_summary']['closed_count'],1 if complete else 0);ck(ident+' base closed count',b['audit']['execution_summary']['closed_count'],2 if complete else 0)
    ck('evaluation all unknown',s['results']['evaluation']['all_pairs_delta_cents'],None);ck('evaluation complete subset adverse',s['results']['evaluation']['complete_subset_delta_cents']<0)
    f=s['frozen']['evaluation'];o={i:OUTCOMES[i] for i in f['ids']};bad=copy.deepcopy(f);bad['decisions']['STRICT']='SELECT';reject('changed decision',lambda:evaluate(PLAN,bad,o));bad=copy.deepcopy(PLAN);bad['threshold_score']=0;reject('changed plan',lambda:freeze(bad,'evaluation',f['ids']));reject('cross split',lambda:freeze(PLAN,'evaluation',PLAN['splits']['discovery']));reject('missing case',lambda:evaluate(PLAN,f,{k:v for k,v in o.items() if k!='E03'}));reject('extra case',lambda:evaluate(PLAN,f,{**o,'D01':988}));reject('invalid outcome',lambda:branch('SELECT',True));reject('invalid action',lambda:branch('BLOCK_UNKNOWN',988));ck('future changes do not change frozen decisions',freeze(PLAN,'evaluation',f['ids']),f)
    return {'test_count':len(tests),'tests':tests}
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');x=p.parse_args();print(json.dumps(self_test() if x.self_test else study(),sort_keys=True,indent=2))
