"""R49 retrospective decision diagnostics, synthetic only. Not a trading engine.
Counterfactual substitutes correction-chain final values into original observations;
not a claim that the corrected information was knowable or executable at the time.
"""
import argparse, copy, hashlib, importlib.util, json, sys
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from fractions import Fraction
BASE=Path(__file__).with_name('Chappy_Trading_Decision_Journal_v0.1.py')
BASE_SHA='738f38920519d81fbb7fe3df303bea41ab39bb7172aae8e55f93e4588cbe54a8'
if hashlib.sha256(BASE.read_bytes()).hexdigest()!=BASE_SHA: raise RuntimeError('R48 dependency changed')
spec=importlib.util.spec_from_file_location('r48_pinned',BASE); j48=importlib.util.module_from_spec(spec); sys.modules[spec.name]=j48; spec.loader.exec_module(j48)
r=j48.r47

def audit(records, head, cutoff):
    j48.require(isinstance(head,str) and len(head)==64,'trusted head required')
    j48.Journal.restore(records,head)
    j48.require(j48.nat(cutoff),'invalid audit cutoff')
    prefix=[x for x in records if x['clock']<=cutoff]
    original=j48.Journal.restore(prefix)
    # Match every original ID to its latest correction known at cutoff; retain original time/provenance.
    successor={}; items={}
    for rec in prefix:
        if rec['kind']=='OBS':
            for x in rec['body']['items']:
                items[x['id']]=x
                if x['supersedes'] is not None: successor[x['supersedes']]=x['id']
    def final_id(i):
        while i in successor: i=successor[i]
        return i
    alternative=j48.Journal(); out=[]
    for rec in prefix:
        b=rec['body']; t=rec['clock']
        if rec['kind']=='OBS':
            batch=[]
            for x in b['items']:
                if x['supersedes'] is not None: continue
                y=copy.deepcopy(x); y['evidence']['value']=items[final_id(x['id'])]['evidence']['value']; batch.append(y)
            if batch: alternative.observations(t,batch)
        elif rec['kind']=='DECISION':
            alt=alternative.decide(t,b['id'],b['symbol'],j48.parse_plan(b['plan']),b['supported'])
            row={'id':b['id'],'symbol':b['symbol'],'decision_hash':rec['hash'],'gate':b['gate']['gate'],'counterfactual_gate':alt['gate']['gate'],'blockers':b['gate']['blockers'],'errors':b['gate']['errors'],'corrected_at_decision_ids':sorted(i for i in b['evidence_ids'] if i in successor),'observed_outcome':None,'counterfactual_outcome':None,'counterfactual_if_gate_eligible':False}
            out.append(row)
    for row in out:
        i=row['id']
        if row['gate']=='RESEARCH_ELIGIBLE':
            rr=original._review_result(i,cutoff); row['observed_outcome']=rr['outcome']; row['decisive_evidence_corrected']=rr['decisive_evidence_corrected']
        if row['counterfactual_gate']=='RESEARCH_ELIGIBLE':
            row['counterfactual_outcome']=alternative._review_result(i,cutoff)['outcome']; row['counterfactual_if_gate_eligible']=True
        row['gate_changed']=row['gate']!=row['counterfactual_gate']
        row['outcome_changed']=None if row['observed_outcome'] is None or row['counterfactual_outcome'] is None else row['observed_outcome']!=row['counterfactual_outcome']
    gates=Counter(x['gate'] for x in out); outcomes=Counter(x['observed_outcome'] for x in out if x['observed_outcome'] is not None)
    eligible=gates['RESEARCH_ELIGIBLE']; c=outcomes['CONFIRMED_OBSERVED']; f=outcomes['REFUTED']; resolved=c+f
    def ratio(n,d): return str(Fraction(n,d)) if d else None
    return {'scope':'synthetic; as-if correction substitution, not historical knowledge or execution','cutoff':cutoff,'source_head':head,'prefix_head':original.head,'rows':out,'summary':{'decisions':len(out),'gates':dict(gates),'outcomes':dict(outcomes),'eligible':eligible,'resolved':resolved,'confirmed_over_resolved':ratio(c,resolved),'confirmed_over_eligible':ratio(c,eligible),'resolved_over_eligible':ratio(resolved,eligible),'gate_changes':sum(x['gate_changed'] for x in out),'comparable_outcomes':sum(x['outcome_changed'] is not None for x in out),'outcome_changes':sum(x['outcome_changed'] is True for x in out),'blocker_counts':dict(Counter(z for x in out for z in x['blockers'])),'execution_proven':False}}

def coverage(records,head,symbol,start,end,supported):
    """Duration of observed states over [start,end); synthetic integer-second time.
    Atomic batches; final same-second state only. No assumption of actual market uptime.
    """
    j48.Journal.restore(records,head)
    j48.require(j48.nat(start) and j48.nat(end) and start<end and end-start<=86400,'invalid coverage window')
    j48.require(j48.name(symbol) and set(supported)<=r.FIELDS.keys(),'invalid coverage scope')
    obs=[x for x in records if x['kind']=='OBS' and x['clock']<end]; active={}; idx=0; states={f:Counter() for f in r.FIELDS}
    for t in range(start,end):
        while idx<len(obs) and obs[idx]['clock']<=t:
            for x in obs[idx]['body']['items']:
                if x['symbol']!=symbol: continue
                active.pop(x['supersedes'],None); active[x['id']]=r.Evidence(**x['evidence'])
            idx+=1
        s,_=r.collect(list(active.values()),t,set(supported))
        for f,v in s.items(): states[f][v]+=1
    return {'symbol':symbol,'start':start,'end':end,'seconds':end-start,'states':{f:dict(v) for f,v in states.items()}}

def self_test():
    tests=[]
    def check(n,a,b):
        if a!=b: raise RuntimeError(f'{n}: {a!r} != {b!r}')
        tests.append({'test':n,'result':'PASS'})
    def reject(n,fn):
        try: fn()
        except (ValueError,TypeError,KeyError): tests.append({'test':n,'result':'PASS'}); return
        raise RuntimeError(n+' unexpectedly accepted')
    p=r.Plan(r.Predicate('close','>=',100),r.Predicate('close','<=',95),r.Predicate('close','>=',110),1100,100,100000,100000,100,10,1); s=set(r.FIELDS)
    def obs(i,f,v,e=995,t=997,symbol='A',old=None): return {'id':i,'symbol':symbol,'evidence':asdict(r.Evidence(f,v,e,t,'feed',str(e))),'supersedes':old}
    def fresh():
        j=j48.Journal(); j.observations(998,[obs(f,f,v) for f,v in {'close':100,'bid':99,'ask':100,'bid_depth':100,'ask_depth':100,'volume':0}.items()]); j.decide(1000,'D','A',p,s); return j
    def run(j,t=1100): return audit(j.export(),j.head,t)
    j=fresh(); a=run(j,1001); check('open',a['rows'][0]['observed_outcome'],'OPEN_UNRESOLVED');check('open not resolved',a['summary']['resolved'],0);check('undefined resolved ratio',a['summary']['confirmed_over_resolved'],None);check('eligible ratio zero',a['summary']['confirmed_over_eligible'],'0');check('no execution',a['summary']['execution_proven'],False)
    check('expiry',run(j)['rows'][0]['observed_outcome'],'EXPIRED_UNRESOLVED')
    j.observations(1010,[obs('hit','close',111,1009,1010)]);j.review(1010,'D');j.observations(1020,[obs('fix','close',94,1009,1020,old='hit')]); frozen=j.export(); a=run(j); row=a['rows'][0]
    check('observed confirm unchanged',row['observed_outcome'],'CONFIRMED_OBSERVED');check('corrected alternative refute',row['counterfactual_outcome'],'REFUTED');check('changed flag',row['outcome_changed'],True);check('decisive id',row['decisive_evidence_corrected'],['hit']);check('source immutable',j.export(),frozen);check('cutoff before correction',run(j,1015)['rows'][0]['counterfactual_outcome'],'CONFIRMED_OBSERVED')
    j.observations(1030,[obs('fix2','close',105,1009,1030,old='fix')]);check('chained correction',run(j)['rows'][0]['counterfactual_outcome'],'EXPIRED_UNRESOLVED')
    j.observations(1040,[obs('entryfix','close',94,995,1040,old='close')]);a=run(j);check('original eligible',a['rows'][0]['gate'],'RESEARCH_ELIGIBLE');check('alternative blocked',a['rows'][0]['counterfactual_gate'],'BLOCK');check('gate changed',a['summary']['gate_changes'],1);check('blocked outcome absent',a['rows'][0]['counterfactual_outcome'],None);check('not comparable',a['rows'][0]['outcome_changed'],None);check('entry correction id',a['rows'][0]['corrected_at_decision_ids'],['close'])
    k=fresh();k.observations(1010,[obs('a','close',94,1009,1010),obs('b','close',111,1009,1010)]);k.observations(1020,[obs('bc','close',94,1009,1020,old='b')]);check('conflict resolves original',run(k)['rows'][0]['observed_outcome'],'REFUTED');check('alternative resolves',run(k)['rows'][0]['counterfactual_outcome'],'REFUTED')
    cv=coverage(k.export(),k.head,'A',1000,1030,s);check('conflict duration',cv['states']['close']['CONFLICT'],10);check('close ok duration',cv['states']['close']['OK'],20);check('stale book duration',cv['states']['bid']['STALE'],24);check('book ok duration',cv['states']['bid']['OK'],6);check('partition',all(sum(v.values())==30 for v in cv['states'].values()),True)
    cv=coverage(k.export(),k.head,'B',1000,1030,{'close'});check('missing symbol',cv['states']['close'],{'UNKNOWN':30});check('unsupported duration',cv['states']['bid'],{'UNSUPPORTED':30})
    reject('invalid window',lambda:coverage(k.export(),k.head,'A',2,2,s));reject('oversize window',lambda:coverage(k.export(),k.head,'A',0,86401,s));reject('bad head',lambda:audit(k.export(),'0'*64,1100));reject('missing head',lambda:audit(k.export(),None,1100));reject('negative cutoff',lambda:run(k,-1));check('empty prefix',run(k,0)['summary']['decisions'],0);check('empty denominator',run(k,0)['summary']['confirmed_over_eligible'],None)
    m=fresh();m.decide(1001,'W','A',replace(p,action='WAIT'),s);m.decide(1002,'B','B',p,s);m.observations(1010,[obs('other','close',111,1009,1010,symbol='B')]); a=run(m);check('decision count',a['summary']['decisions'],3);check('wait counted',a['summary']['gates']['WAIT_UNVERIFIED'],1);check('block counted',a['summary']['gates']['BLOCK'],1);check('other symbol no outcome',a['rows'][0]['observed_outcome'],'EXPIRED_UNRESOLVED');check('wait outcome null',a['rows'][1]['observed_outcome'],None);check('block outcome null',a['rows'][2]['observed_outcome'],None);check('blocker counted',a['summary']['blocker_counts']['close:UNKNOWN'],1)
    # One confirmation and one unresolved, never omit unresolved from eligible denominator.
    n=fresh();n.decide(1001,'D2','A',replace(p,confirm=r.Predicate('close','>=',120)),s);n.observations(1010,[obs('rise','close',111,1009,1010)]);a=run(n);check('resolved ratio',a['summary']['confirmed_over_resolved'],'1');check('all eligible ratio',a['summary']['confirmed_over_eligible'],'1/2');check('coverage ratio',a['summary']['resolved_over_eligible'],'1/2');check('two outcomes comparable',a['summary']['comparable_outcomes'],2)
    # A future correction may alter as-if analysis after deadline but never original outcome.
    q=fresh();q.observations(1010,[obs('up','close',111,1009,1010)]);q.observations(1110,[obs('down','close',94,1009,1110,old='up')]);check('late correction absent at deadline',run(q,1100)['rows'][0]['counterfactual_outcome'],'CONFIRMED_OBSERVED');check('late correction as-if',run(q,1110)['rows'][0]['counterfactual_outcome'],'REFUTED');check('late correction not historical',run(q,1110)['rows'][0]['observed_outcome'],'CONFIRMED_OBSERVED')
    check('R48 regression',j48.self_test()[0]['test_count'],52)
    return {'test_count':len(tests),'tests':tests}, {'correction_example':run(j),'coverage_example':coverage(k.export(),k.head,'A',1000,1030,s),'denominator_example':run(n),'late_correction_example':run(q,1110)}

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--self-test',action='store_true');ap.add_argument('--example',action='store_true');a=ap.parse_args()
    if a.self_test==a.example: ap.error('choose exactly one mode')
    print(json.dumps(self_test()[0 if a.self_test else 1],ensure_ascii=False,sort_keys=True,indent=2))
