"""R34: synthetic document receipts -> bounded verifier -> replayable review.
No external document authenticity, actual AI, live facts, or orders.
The raw inbox is authoritative; derived review SQLite is replaceable.
"""
import base64,csv,hashlib,importlib.util,json,os,sqlite3,sys,tempfile,shutil
from datetime import datetime,timedelta,timezone
from pathlib import Path
P=Path(__file__).resolve().parent

def load(name,file):
    sp=importlib.util.spec_from_file_location(name,P/file);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
r=load('r34_review','Chappy_Trading_Review_Workflow_v0.1.py')
i=load('r34_ingest','Chappy_Trading_Ingest_Study_v0.1.py')
require=r.require; canon=r.canon; ident=r.ident
SOURCES={'synthetic://issuerA','synthetic://issuerB'}
ACTORS={'synthetic://proposer','synthetic://reviewer'}
class Inbox(i.Inbox):
    def append(self,source,fmt,raw,received,transport='OK'):
        require((fmt=='DOCUMENT' and source in SOURCES) or (fmt=='COMMAND' and source in ACTORS),'CHANNEL')
        require(i.g.aware(received),'CLOCK');require(isinstance(raw,bytes) and len(raw)<=i.MAX,'RAW_LIMIT')
        e=dict(source=source,format=fmt,received=received.isoformat(),transport=transport,raw=base64.b64encode(raw).decode(),sha256=r.digest(raw))
        self.db.execute('BEGIN IMMEDIATE')
        try:
            rows,head=self.rows();require(not rows or received>=i.parse_time(rows[-1]['received']),'BACKDATED')
            n=len(rows)+1;p=i.j.canonical(e);h=r.digest(bytes.fromhex(head)+n.to_bytes(8,'big')+p)
            self.db.execute('INSERT INTO inbox VALUES(?,?,?)',(n,p,h));self.db.execute('COMMIT');return n,h
        except BaseException:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise

def decode(raw):
    return json.loads(raw.decode('utf8'),object_pairs_hook=i.unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('NONFINITE')))

def project(inbox,path,expected=None,limit=None):
    rows,head=inbox.rows(expected);require(limit is None or 0<=limit<=len(rows),'PREFIX')
    path=Path(path);records=[];docs={};active={};seen=set();timeline=[]
    with tempfile.TemporaryDirectory(dir=path.parent) as td:
        tmp=Path(td)/'review.sqlite'
        with r.Ledger(tmp,'SYNTHETIC',True) as ledger:
            for n,e in enumerate(rows[:limit],1):
                raw=base64.b64decode(e['raw']);source=e['source'];fmt=e['format'];at=e['received'];key=(source,fmt,e['sha256']);status='';detail='';doc=''
                prior=ledger.read()
                try:
                    require(e['transport']=='OK','TRANSPORT');require((fmt=='DOCUMENT' and source in SOURCES) or (fmt=='COMMAND' and source in ACTORS),'CHANNEL')
                    if key in seen:status='DUPLICATE'
                    else:
                        d=decode(raw);require(isinstance(d,dict),'SCHEMA')
                        if fmt=='DOCUMENT':
                            require(set(d)=={'version','replaces','envelope'},'SCHEMA');v=d['version'];old=d['replaces'];env=d['envelope']
                            require(isinstance(v,str) and 0<len(v)<=128 and (old is None or isinstance(old,str)),'VERSION');require(isinstance(env,dict) and env.get('origin')=='SYNTHETIC' and env.get('source')==source,'ORIGIN_SOURCE')
                            require(set(env)=={'symbol','event','source','text','kind','origin','period_end'} and all(isinstance(x,str) for x in env.values()),'ENVELOPE')
                            identity=(source,v);scope=(source,env['symbol'],env['event'],env['period_end'],env['kind']);doc=r.ident(env)
                            require(identity not in docs,'VERSION_CHANGED');require(doc not in {x['doc'] for x in docs.values()},'SAME_DOCUMENT')
                            require(active.get(scope)==old,'REVISION_TARGET');require(old is None or (source,old) in docs,'REVISION_TARGET')
                            result=r.r32.project(env)
                            # A validly identified but unparseable revision still invalidates the old candidate.
                            # No exception after mutation is treated as a routine quarantine.
                            if old is not None:
                                ledger.append('RETIRE',at,{'doc':docs[(source,old)]['doc'],'reason':'synthetic replacement receipt '+str(n),'reviewer':'SIMULATED_REVIEWER'})
                            ledger.append('REGISTER',at,{'doc':doc,'envelope':env})
                            docs[identity]={'doc':doc,'scope':scope,'seq':n,'sha256':e['sha256'],'received':at};active[scope]=v
                            status='DOCUMENT_REGISTERED' if result['status']=='CANDIDATE_ONLY' else 'DOCUMENT_HOLD';detail=result.get('reason','')
                        else:
                            require(d.get('kind') in ('SUBMIT','REVIEW'),'COMMAND_KIND');state=ledger.read()[2]
                            if d['kind']=='SUBMIT':
                                require(source=='synthetic://proposer' and set(d)=={'kind','doc','candidate'},'ROLE_SCHEMA');doc=d['doc'];require(isinstance(doc,str) and isinstance(d['candidate'],dict),'SCHEMA');c=d['candidate'];p=ident([doc,c,'SIMULATED_AI']);ledger.append('SUBMIT',at,{'doc':doc,'candidate':c,'proposal':p,'proposer':'SIMULATED_AI'});status=ledger.read()[2]['proposals'][p]['status'];detail=p
                            else:
                                require(source=='synthetic://reviewer' and set(d)=={'kind','proposal','binding','decision','reason'},'ROLE_SCHEMA');p=d['proposal'];require(isinstance(p,str),'SCHEMA');ledger.append('REVIEW',at,{'proposal':p,'binding':d['binding'],'decision':d['decision'],'reason':d['reason'],'reviewer':'SIMULATED_REVIEWER'});status=ledger.read()[2]['proposals'][p]['status'];detail=p
                        seen.add(key)
                except (ValueError,TypeError,KeyError,UnicodeError,AttributeError) as ex:
                    # Any partially applied document event is an invariant failure, not a normal rejection.
                    if ledger.read()!=prior:raise RuntimeError('PARTIAL_RECEIPT') from ex
                    status='QUARANTINED';detail=str(ex)
                s=ledger.read()[2];records.append(dict(seq=n,source=source,received=at,raw_sha256=e['sha256'],status=status,detail=detail,document=doc));timeline.append(dict(seq=n,status=status,documents=len(s['documents']),pending=sum(p['effective']=='PENDING' for p in s['proposals'].values()),approved=sum(p['effective']=='APPROVED_RESEARCH_ONLY' for p in s['proposals'].values()),retired=sum(p['effective']=='RETIRED' for p in s['proposals'].values()),conflict=sum(p['effective']=='HOLD_CONFLICT' for p in s['proposals'].values()),state_sha256=ident(s),live_eligible=s['live_eligible']))
            final=ledger.read()
        os.replace(tmp,path)
    return records,timeline,final,docs,(len(rows),head)

def main(out):
    protected=['CTRL.zip','Trading_Prospective_Plan_01.json','Chappy_Trading_Lab_v1.1.0-rc1.py','Chappy_Trading_Research_Lab_v0.5.0.py','Chappy_Trading_Ingest_Study_v0.1.py','Chappy_Trading_Review_Workflow_v0.1.py','Chappy_Trading_Common_Document_Study_v0.1.py','Trading_Round32_Common_Document/evidence.json'];before={n:r.digest((P/n).read_bytes()) for n in protected};require(before['Trading_Prospective_Plan_01.json']=='3311941f206b44220374d38e7cef86900cdb1bd480c111d0d2403ad73d1589cb','PLAN')
    out.mkdir(parents=True,exist_ok=False);tests=[];at=datetime(2026,11,25,12,tzinfo=timezone.utc);src='synthetic://issuerA';other='synthetic://issuerB';prop='synthetic://proposer';rev='synthetic://reviewer';counter=0
    env=dict(json.loads((P/'Trading_Round32_Common_Document/evidence.json').read_text())[1]['input'],origin='SYNTHETIC',source=src)
    def ok(name,condition):require(condition,name);tests.append(dict(test=name,result='PASS'))
    with Inbox(out/'inbox.sqlite',True) as box:
        def send(source,fmt,d,status,name,transport='OK'):
            nonlocal counter
            counter+=1;raw=d if isinstance(d,bytes) else canon(d);box.append(source,fmt,raw,at+timedelta(seconds=counter),transport);p=project(box,out/'review.sqlite');ok(name,p[0][-1]['status']==status);return p
        def packet(v,e,old=None):return dict(version=v,replaces=old,envelope=e)
        def submit(e,c=None):return dict(kind='SUBMIT',doc=ident(e),candidate=c or r.r32.project(e)['candidates'][1])
        def pid(d):return ident([d['doc'],d['candidate'],'SIMULATED_AI'])
        def approve(p,**kw):return dict(kind='REVIEW',proposal=p,binding=p,decision='APPROVE',reason='synthetic approval',**kw)
        a=packet('v1',env);send(src,'DOCUMENT',a,'DOCUMENT_REGISTERED','register')
        send(src,'DOCUMENT',a,'DUPLICATE','resend')
        s=submit(env);p=pid(s);send(prop,'COMMAND',s,'PENDING','submit');send(rev,'COMMAND',approve(p),'APPROVED_RESEARCH_ONLY','approve')
        send(prop,'COMMAND',approve(p),'QUARANTINED','role_spoof')
        changed=dict(env,text=env['text'].replace('6,900（10.0%）','6,800（10.0%）').replace('▲407','▲507').replace('▲5.6%','▲6.9%').replace('▲300','▲400'))
        ok('changed_projection',r.r32.project(changed)['status']=='CANDIDATE_ONLY')
        send(src,'DOCUMENT',packet('v1',changed),'QUARANTINED','id_reused_changed_bytes')
        send(src,'DOCUMENT',packet('v2',changed,'missing'),'QUARANTINED','missing_parent')
        send(other,'DOCUMENT',packet('v2',changed,'v1'),'QUARANTINED','source_spoof')
        o=send(src,'DOCUMENT',packet('v2',changed,'v1'),'DOCUMENT_REGISTERED','correction');ok('old_approval_retired',o[2][2]['proposals'][p]['effective']=='RETIRED')
        send(rev,'COMMAND',dict(approve(p),reason='attempt old approval'),'QUARANTINED','old_approval')
        send(prop,'COMMAND',dict(s,candidate=dict(s['candidate'],value='1')),'QUARANTINED','old_submit')
        s2=submit(changed);p2=pid(s2);send(prop,'COMMAND',dict(s2,candidate=dict(s2['candidate'],value='1')),'REJECTED_BY_VERIFIER','numeric_tamper');send(prop,'COMMAND',s2,'PENDING','new_pending');send(rev,'COMMAND',dict(approve(p2),binding=p),'QUARANTINED','stale_binding');send(rev,'COMMAND',approve(p2),'APPROVED_RESEARCH_ONLY','new_approval')
        e2=dict(env,source=other);send(other,'DOCUMENT',packet('a',e2),'DOCUMENT_REGISTERED','other_source');s3=submit(e2);p3=pid(s3);send(prop,'COMMAND',s3,'PENDING','other_pending');o=send(rev,'COMMAND',approve(p3),'APPROVED_RESEARCH_ONLY','other_approval');ok('conflict',all(o[2][2]['proposals'][x]['effective']=='HOLD_CONFLICT' for x in (p2,p3)))
        bad=dict(changed,text=changed['text'].replace('▲400','▲401'));o=send(src,'DOCUMENT',packet('v3',bad,'v2'),'DOCUMENT_HOLD','unparseable_revision');ok('no_stale_approval',o[2][2]['proposals'][p2]['effective']=='RETIRED' and o[2][2]['proposals'][p3]['effective']=='APPROVED_RESEARCH_ONLY')
        send(src,'DOCUMENT',packet('v2',changed,'v1'),'DUPLICATE','late_resend');send(src,'DOCUMENT',b'{','QUARANTINED','bad_json');send(src,'DOCUMENT',b'{"version":"a","version":"b"}','QUARANTINED','duplicate_keys');send(src,'DOCUMENT',packet('v4',env,'v3'),'QUARANTINED','transport_failure','NETWORK_ERROR')
        full=project(box,out/'review.sqlite');rows,head=box.rows();ok('no_live',full[2][2]['live_eligible']==0 and full[2][2]['execution']=='DISABLED')
        # Inject a projection failure after an earlier retirement; prior output must survive.
        original_append=r.Ledger.append
        def fail_register(self,kind,stamp,data):
            if kind=='REGISTER' and data['doc']==ident(changed):raise ValueError('INJECT_REGISTER_FAILURE')
            return original_append(self,kind,stamp,data)
        saved=(out/'review.sqlite').read_bytes();r.Ledger.append=fail_register
        try:
            try:project(box,out/'review.sqlite')
            except RuntimeError as ex:ok('partial_projection_not_published',str(ex)=='PARTIAL_RECEIPT' and (out/'review.sqlite').read_bytes()==saved)
            else:raise RuntimeError('partial projection accepted')
        finally:r.Ledger.append=original_append
        with tempfile.TemporaryDirectory() as td:
            with Inbox(Path(td)/'prefix.sqlite',True) as pref:
                for n,e in enumerate(rows,1):
                    pref.append(e['source'],e['format'],base64.b64decode(e['raw']),i.parse_time(e['received']),e['transport']);a=project(pref,Path(td)/'prefix_review.sqlite');b=project(box,Path(td)/'full_prefix.sqlite',limit=n);require(a[:4]==b[:4] and a[1][-1]==full[1][n-1],'PREFIX_MISMATCH')
        ok('all_prefixes',True)
    with Inbox(out/'inbox.sqlite') as box:ok('reopen_rebuild',project(box,out/'rebuilt.sqlite',expected=(len(rows),head))==full)
    for name,sql in [('changed',"UPDATE inbox SET payload=x'7b7d' WHERE seq=2"),('middle','DELETE FROM inbox WHERE seq=2'),('tail','DELETE FROM inbox WHERE seq=(SELECT MAX(seq) FROM inbox)')]:
        with tempfile.TemporaryDirectory() as td:
            pth=Path(td)/'bad.sqlite';shutil.copy2(out/'inbox.sqlite',pth)
            with sqlite3.connect(pth) as db:db.execute(sql)
            try:
                with Inbox(pth) as box:box.rows((len(rows),head))
            except ValueError:ok('tamper_'+name,True)
            else:raise RuntimeError(name)
    ok('protected',before=={n:r.digest((P/n).read_bytes()) for n in protected})
    for name,data in [('tests.csv',tests),('receipts.csv',full[0]),('timeline.csv',full[1])]:
        with (out/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    (out/'snapshot.json').write_bytes(canon(full[2][2]));(out/'manifest.json').write_text(json.dumps(dict(tests=len(tests),receipts=len(rows),prefix_checks=len(rows),review_events=len(full[2][0]),protected=before,checkpoint=[len(rows),head],live_eligible=0,limits='synthetic JSON only; no authenticated identities, live data, actual AI or orders'),indent=2));print((out/'manifest.json').read_text())
if __name__=='__main__':main(Path(sys.argv[1]))
