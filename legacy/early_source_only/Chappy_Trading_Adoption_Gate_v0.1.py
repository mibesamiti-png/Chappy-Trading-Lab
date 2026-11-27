"""R35: scope-local research adoption gate over R34 raw-inbox projection.
No live eligibility, facts, authentication or orders. All expected candidate coverage
is relative to the bounded verifier, not proof of complete document understanding.
"""
import csv, json, hashlib, tempfile, sys, base64
from pathlib import Path
from datetime import datetime, timezone, timedelta
import importlib.util
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('r35_integration',P/'Chappy_Trading_Document_Integration_v0.1.py'); m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
r=m.r;require=r.require;ident=r.ident;canon=r.canon

def gate(projected,rows):
    records,_,ledger,docs,_=projected; state=ledger[2]; groups={}; issues=[]
    require(len(records)==len(rows),'PREFIX_ROWS')
    for rec in records:
        if rec['status']=='QUARANTINED' and rows[rec['seq']-1]['format']=='DOCUMENT':issues.append(rec['seq'])
    for d in docs.values():
        key=d['doc'];require(key in state['documents'],'DOCUMENT_LINK')
        if state['documents'][key]['retired']:continue
        raw=rows[d['seq']-1]; require(raw['sha256']==d['sha256'],'RAW_LINK'); env=m.decode(base64.b64decode(raw['raw']))['envelope'];require(ident(env)==key,'ENV_LINK')
        scope=tuple(d['scope'][1:4]);require(scope==(env['symbol'],env['event'],env['period_end']),'SCOPE_LINK')
        g=groups.setdefault(scope,{'documents':[], 'candidates':{},'blockers':[]});g['documents'].append(key)
        result=r.r32.project(env)
        if result['status']!='CANDIDATE_ONLY' or not result['candidates']:
            g['blockers'].append(['UNPARSED_DOCUMENT',key]);continue
        for c in result['candidates']:
            p=ident([key,c,'SIMULATED_AI']);q=state['proposals'].get(p);status=q['effective'] if q else 'NOT_SUBMITTED'
            if q:require(q['doc']==key and canon(q['candidate'])==canon(c),'PROPOSAL_LINK')
            if status!='APPROVED_RESEARCH_ONLY':g['blockers'].append([status,p])
            g['candidates'].setdefault(r.candidate_key(c),[]).append((c,p,status))
    output=[]
    for scope,g in sorted(groups.items()):
        conflicts=[];eligible=[]
        for key,cs in sorted(g['candidates'].items()):
            if len({r.comparison(c) for c,_,_ in cs})>1:conflicts.append(list(key))
            elif all(status=='APPROVED_RESEARCH_ONLY' for _,_,status in cs):eligible.append({'key':list(key),'proposal_ids':sorted(p for _,p,_ in cs),'values':list(r.comparison(cs[0][0]))})
        status='HOLD_CONFLICT' if conflicts else 'HOLD_UNRESOLVED' if g['blockers'] else 'READY_RESEARCH_ONLY'
        output.append(dict(scope=list(scope),status=status,documents=sorted(g['documents']),blockers=sorted(g['blockers']),conflicts=conflicts,verified_candidates=sorted(p for cs in g['candidates'].values() for _,p,_ in cs),research_evidence=eligible if status=='READY_RESEARCH_ONLY' else []))
    return dict(scopes=output,quarantined_document_receipts=issues,coverage='BOUNDED_VERIFIER_ONLY',source_completeness='UNVERIFIED',live_eligible=0,execution='DISABLED')

def replay(box,path,limit=None,expected=None):
    rows,head=box.rows(expected);p=m.project(box,path,expected=(len(rows),head),limit=limit);return gate(p,rows[:limit])

def main(out):
    protected=[P/'Trading_Prospective_Plan_01.json',P/'Chappy_Trading_Document_Integration_v0.1.py',P/'Chappy_Trading_Review_Workflow_v0.1.py',P/'Chappy_Trading_Common_Document_Study_v0.1.py',P/'Chappy_Trading_Ingest_Study_v0.1.py',P/'Chappy_Trading_Lab_v1.1.0-rc1.py',P/'CTRL.zip'];before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected};require(before['Trading_Prospective_Plan_01.json']=='3311941f206b44220374d38e7cef86900cdb1bd480c111d0d2403ad73d1589cb','PLAN')
    out.mkdir(parents=True,exist_ok=False);tests=[];timeline=[]
    def ok(name,b):require(b,name);tests.append(dict(test=name,result='PASS'))
    old=P/'Trading_Round34_Integration_verified';cp=json.loads((old/'manifest.json').read_text())['checkpoint']
    import shutil
    with tempfile.TemporaryDirectory() as td:
        copy=Path(td)/'old.sqlite';shutil.copy2(old/'inbox.sqlite',copy)
        with m.Inbox(copy) as box:
            p=m.project(box,Path(td)/'review.sqlite',expected=cp);ok('R34_snapshot',canon(p[2][2])==(old/'snapshot.json').read_bytes());rows,_=box.rows(cp)
            for n in range(len(rows)+1):
                g=replay(box,Path(td)/'review.sqlite',n,cp);timeline.append(dict(case='R34',seq=n,gate=g));ok('R34_no_execution_'+str(n),g['live_eligible']==0 and g['execution']=='DISABLED')
            ok('R34_unparsed_revision_blocks',g['scopes'][0]['status']=='HOLD_UNRESOLVED' and any(x[0]=='UNPARSED_DOCUMENT' for x in g['scopes'][0]['blockers']))
    source=json.loads((P/'Trading_Round32_Common_Document/evidence.json').read_text());src='synthetic://issuerA';other='synthetic://issuerB';env=dict(source[1]['input'],origin='SYNTHETIC',source=src)
    # use a different valid corporate excerpt to test independent scope
    other_env=next(dict(row['input'],origin='SYNTHETIC',source=other) for row in source if row['input']['symbol']!=env['symbol'] and row['output']['status']=='CANDIDATE_ONLY')
    changed=dict(env,text=env['text'].replace('6,900（10.0%）','6,800（10.0%）').replace('▲407','▲507').replace('▲5.6%','▲6.9%').replace('▲300','▲400'));bad=dict(changed,text=changed['text'].replace('▲400','▲401'))
    require(r.r32.project(changed)['status']=='CANDIDATE_ONLY' and r.r32.project(bad)['status']!='CANDIDATE_ONLY','FIXTURE')
    at=datetime(2026,11,25,12,tzinfo=timezone.utc);n=0
    with m.Inbox(out/'inbox.sqlite',True) as box:
        def send(source,fmt,d):
            nonlocal n
            n+=1;box.append(source,fmt,canon(d),at+timedelta(seconds=n));g=replay(box,out/'review.sqlite');timeline.append(dict(case='new',seq=n,gate=g));return g
        def doc(e,v,old=None):return send(e['source'],'DOCUMENT',dict(version=v,replaces=old,envelope=e))
        def status(g,e):return next(x['status'] for x in g['scopes'] if x['scope'][0]==e['symbol'])
        def submit(e,c):
            key=ident(e);p=ident([key,c,'SIMULATED_AI']);g=send('synthetic://proposer','COMMAND',dict(kind='SUBMIT',doc=key,candidate=c));return p,g
        def review(p,decision='APPROVE'):return send('synthetic://reviewer','COMMAND',dict(kind='REVIEW',proposal=p,binding=p,decision=decision,reason='fixture'))
        def all_approve(e):
            for c in r.r32.project(e)['candidates']:
                p,g=submit(e,c);g=review(p)
            return g
        g=doc(env,'v1');ok('missing_submission_holds',status(g,env)=='HOLD_UNRESOLVED');cs=r.r32.project(env)['candidates'];p,g=submit(env,cs[0]);ok('pending_holds',status(g,env)=='HOLD_UNRESOLVED');g=review(p);ok('partial_approval_holds',status(g,env)=='HOLD_UNRESOLVED');p,g=submit(env,cs[1]);g=review(p);ok('complete_approval_ready',status(g,env)=='READY_RESEARCH_ONLY')
        g=doc(other_env,'x');g=all_approve(other_env);ok('other_company_ready',status(g,other_env)=='READY_RESEARCH_ONLY');e2=dict(changed,source=other);g=doc(e2,'alt');ok('conflict_before_submission',status(g,env)=='HOLD_CONFLICT' and status(g,other_env)=='READY_RESEARCH_ONLY');g=all_approve(e2);ok('approved_conflict',status(g,env)=='HOLD_CONFLICT');g=doc(bad,'v2','v1');ok('unparsed_revision_holds_other_approved',status(g,env)=='HOLD_UNRESOLVED' and status(g,other_env)=='READY_RESEARCH_ONLY');g=doc(changed,'v3','v2');ok('new_version_requires_review',status(g,env)=='HOLD_UNRESOLVED');g=all_approve(changed);ok('matching_full_approval_ready',status(g,env)=='READY_RESEARCH_ONLY');g=doc(env,'v4','v3');# identical original document prohibited; quarantine must not silently disappear
        ok('quarantine_visible',len(g['quarantined_document_receipts'])==1 and g['source_completeness']=='UNVERIFIED');ok('research_only',g['live_eligible']==0 and g['execution']=='DISABLED')
        rows,head=box.rows();expected=(len(rows),head)
        with tempfile.TemporaryDirectory() as td:
            with m.Inbox(Path(td)/'prefix.sqlite',True) as prefix:
                for j,e in enumerate(rows,1):
                    prefix.append(e['source'],e['format'],base64.b64decode(e['raw']),m.i.parse_time(e['received']),e['transport']);a=replay(prefix,Path(td)/'a.sqlite');b=replay(box,Path(td)/'b.sqlite',j,expected);require(a==b==next(x['gate'] for x in timeline if x['case']=='new' and x['seq']==j),'PREFIX')
            ok('independent_prefixes',True)
    with m.Inbox(out/'inbox.sqlite') as box:ok('reopen',replay(box,out/'rebuilt.sqlite',expected=expected)==g)
    ok('protected',before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected})
    with (out/'tests.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=['test','result']);w.writeheader();w.writerows(tests)
    (out/'timeline.json').write_bytes(canon(timeline));(out/'manifest.json').write_text(json.dumps(dict(tests=len(tests),old_states=len(cp) and cp[0]+1,new_receipts=len(rows),independent_prefixes=len(rows),protected=before,checkpoint=expected,limits='synthetic only; quarantined document receipts flagged, not automatically attributed to a scope; ready only means bounded candidate coverage; no live facts/orders'),indent=2));print((out/'manifest.json').read_text())
if __name__=='__main__':main(Path(sys.argv[1]))
