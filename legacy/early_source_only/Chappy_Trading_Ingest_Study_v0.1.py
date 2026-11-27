"""R29 raw inbox and deterministic projection. Research only, no orders.
Synthetic JSON is the ONLY format allowed to produce evidence facts.
RSS/Atom is indexed as unverified headlines, not parsed financial facts.
CLI: python this.py NEW_OUTPUT_DIR ; see capture_feed() for explicit HTTPS collection.
"""
import base64, csv, hashlib, importlib.util, json, os, sqlite3, sys, tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.request import build_opener, HTTPRedirectHandler, Request, ProxyHandler
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r29journal',P/'Chappy_Trading_Evidence_Journal_v0.1.py');j=importlib.util.module_from_spec(spec);sys.modules[spec.name]=j;spec.loader.exec_module(j)
g=j.g; MAX=1024*1024; ZERO=j.ZERO
SYNTH={'synthetic://A','synthetic://B'}

def unique(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('DUPLICATE_KEY')
        d[k]=v
    return d

def parse_time(s):
    if not isinstance(s,str):raise ValueError('CLOCK_REQUIRED')
    t=datetime.fromisoformat(s)
    if not g.aware(t):raise ValueError('CLOCK_REQUIRED')
    return t

def hashfile(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Inbox:
    def __init__(self,path,create=False):
        self.path=Path(path)
        if create and self.path.exists():raise FileExistsError(path)
        self.db=sqlite3.connect(path if create else self.path.resolve().as_uri()+'?mode=rw',uri=not create,isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL')
        if create:self.db.execute('CREATE TABLE inbox(seq INTEGER PRIMARY KEY,payload BLOB NOT NULL,chain TEXT NOT NULL)')
        self.rows()
    def __enter__(self):return self
    def __exit__(self,*a):self.db.close()
    def rows(self,expected=None):
        out=[];head=ZERO;last=None
        for n,p,h in self.db.execute('SELECT seq,payload,chain FROM inbox ORDER BY seq'):
            if n!=len(out)+1 or j.digest(bytes.fromhex(head)+n.to_bytes(8,'big')+p)!=h:raise ValueError('INBOX_CHAIN')
            e=json.loads(p);raw=base64.b64decode(e['raw'],validate=True);t=parse_time(e['received'])
            if j.canonical(e)!=p or j.digest(raw)!=e['sha256'] or len(raw)>MAX or (last and t<last):raise ValueError('INBOX_CONTENT')
            out.append(e);head=h;last=t
        if expected is not None and (len(out),head)!=tuple(expected):raise ValueError('INBOX_CHECKPOINT')
        return out,head
    def append(self,source,fmt,raw,received,transport='OK'):
        if not g.aware(received):raise ValueError('CLOCK_REQUIRED')
        if not isinstance(raw,bytes) or len(raw)>MAX:raise ValueError('RAW_LIMIT')
        if fmt=='SYNTH_JSON' and source not in SYNTH:raise ValueError('SOURCE_NOT_SYNTHETIC')
        if fmt not in ('SYNTH_JSON','UNVERIFIED_FEED'):raise ValueError('FORMAT')
        e=dict(source=source,format=fmt,received=received.isoformat(),transport=transport,raw=base64.b64encode(raw).decode(),sha256=j.digest(raw))
        self.db.execute('BEGIN IMMEDIATE')
        try:
            rows,head=self.rows()
            if rows and received<parse_time(rows[-1]['received']):raise ValueError('RECEIPT_BACKDATED')
            n=len(rows)+1;p=j.canonical(e);h=j.digest(bytes.fromhex(head)+n.to_bytes(8,'big')+p)
            self.db.execute('INSERT INTO inbox VALUES(?,?,?)',(n,p,h));self.db.execute('COMMIT')
            return n,h
        except BaseException:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise

def eid(source,ident):return j.digest(j.canonical([source,ident]))

def to_event(e,raw):
    d=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('NONFINITE')))
    keys={'id','action','target','symbol','event','kind','period','metric','unit','value','observed','published'}
    if not isinstance(d,dict) or set(d)!=keys:raise ValueError('JSON_SCHEMA')
    if any(not isinstance(d[k],str) or not d[k].strip() or len(d[k])>256 for k in keys-{'target'}):raise ValueError('FIELD_TYPE')
    if d['action'] not in ('ADD','CORRECT','WITHDRAW') or (d['action']=='ADD')!=(d['target'] is None):raise ValueError('ACTION_TARGET')
    if d['target'] is not None and (not isinstance(d['target'],str) or not d['target'].strip()):raise ValueError('TARGET_TYPE')
    f=g.Fact(d['symbol'],d['event'],d['kind'],d['period'],d['metric'],d['unit'],Decimal(d['value']),parse_time(d['observed']),parse_time(d['published']),parse_time(e['received']),e['source'],eid(e['source'],d['id']))
    return d['id'],j.event(f,d['action'],None if d['target'] is None else eid(e['source'],d['target']),raw)

def headlines(raw):
    # No XML declarations with DTD/entity expansion; bytes must be UTF-8.
    s=raw.decode('utf-8-sig')
    if '<!DOCTYPE' in s.upper() or '<!ENTITY' in s.upper():raise ValueError('XML_DTD')
    root=ET.fromstring(s)
    if root.tag=='rss':items=root.findall('./channel/item');title='title';dt='pubDate';ident='guid'
    elif root.tag=='{http://www.w3.org/2005/Atom}feed':
        ns='{http://www.w3.org/2005/Atom}';items=root.findall(ns+'entry');title=ns+'title';dt=ns+'published';ident=ns+'id'
    else:raise ValueError('FEED_ROOT')
    if len(items)>1000:raise ValueError('ITEM_LIMIT')
    out=[]
    for i in items:
        name=i.findtext(title) or ''
        if not name.strip():raise ValueError('TITLE_REQUIRED')
        out.append(dict(title=name,reported_publication=i.findtext(dt) or '',external_id=i.findtext(ident) or '',status='UNVERIFIED_HEADLINE_ONLY'))
    return out

def project(inbox,path,expected=None):
    """Build a fresh projection from the immutable input. Interrupted rebuild never replaces prior result."""
    rows,head=inbox.rows(expected);path=Path(path);audit=[];news=[];seen={};seen_raw=set()
    with tempfile.TemporaryDirectory(dir=path.parent) as temp:
        tmp=Path(temp)/'projection.sqlite'
        with j.Journal(tmp,True) as journal:
            for n,e in enumerate(rows,1):
                raw=base64.b64decode(e['raw']);key=(e['source'],e['format'],e['sha256']);status='';detail='';fact_id=''
                try:
                    if e['transport']!='OK':raise ValueError('TRANSPORT_'+e['transport'])
                    if key in seen_raw:status='DUPLICATE_BYTES'
                    elif e['format']=='UNVERIFIED_FEED':
                        items=headlines(raw);news.extend(dict(inbox_seq=n,source=e['source'],received=e['received'],**x) for x in items);status='HEADLINES_ONLY';detail=str(len(items));seen_raw.add(key)
                    else:
                        ident,event=to_event(e,raw);identity=(e['source'],ident)
                        if identity in seen:raise ValueError('MESSAGE_ID_CHANGED_BYTES')
                        journal.append(event);seen[identity]=e['sha256'];seen_raw.add(key);status='ACCEPTED_SYNTHETIC';fact_id=event['fact']['evidence_id']
                except (ValueError,TypeError,KeyError,UnicodeError,ArithmeticError,ET.ParseError) as ex:status='QUARANTINED';detail=str(ex)
                audit.append(dict(seq=n,source=e['source'],receipt=e['received'],sha256=e['sha256'],status=status,detail=detail,evidence_id=fact_id))
            s=journal.verify();checkpoint=(s['seq'],s['head'])
        os.replace(tmp,path)
    return audit,news,checkpoint,(len(rows),head)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None

def capture_feed(inbox,url,*,loopback_test=False):
    """Explicit public HTTPS URL only; no credentials/redirects/proxy. Local HTTP only for test server.
    Does not authenticate news or pass it into the decision gate. Never auto-polls.
    """
    u=urlsplit(url)
    if not u.hostname or u.username or u.password or u.fragment or (u.scheme!='https' and not(loopback_test and u.scheme=='http' and u.hostname=='127.0.0.1')):raise ValueError('URL_POLICY')
    if loopback_test and u.hostname!='127.0.0.1':raise ValueError('LOOPBACK_ONLY')
    raw=b'';status='OK'
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(Request(url,headers={'User-Agent':'ChappyTradingResearch/0.1','Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml'}),timeout=5) as r:
            raw=r.read(MAX+1)
            if len(raw)>MAX:raw=b'';status='OVERSIZE_DISCARDED'
    except HTTPError as e:status='HTTP_'+str(e.code)
    except (URLError,TimeoutError,OSError):status='NETWORK_ERROR'
    return inbox.append(url,'UNVERIFIED_FEED',raw,datetime.now(timezone.utc),status)

def encode(f,action='ADD',target=None,ident=None):
    d=j.fact_dict(f)
    for k in ('received','source','origin'):d.pop(k)
    d['id']=ident or d.pop('evidence_id');d.pop('evidence_id',None);d.update(action=action,target=target)
    return j.canonical(d)

def main(out):
    from dataclasses import replace
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from threading import Thread
    protected=['CTRL.zip','Trading_Prospective_Plan_01.json','Chappy_Trading_Lab_v1.1.0-rc1.py','Chappy_Trading_Research_Lab_v0.5.0.py','Chappy_Trading_Evidence_Gate_v0.1.py','Chappy_Trading_Evidence_Journal_v0.1.py','Trading_Round26_Consensus/consensus_events.csv']
    before={n:hashfile(P/n) for n in protected};assert before['Trading_Prospective_Plan_01.json']=='3311941f206b44220374d38e7cef86900cdb1bd480c111d0d2403ad73d1589cb'
    out.mkdir(parents=True,exist_ok=False);ctx,fs=j.fixture();t=ctx.release;actual=next(f for f in fs if f.kind=='H1_ACTUAL');tests=[]
    def ok(name,condition):
        assert condition,name;tests.append(dict(test=name,result='PASS'))
    def rejects(name,fn,reason):
        try:fn()
        except ValueError as e:ok(name,str(e)==reason)
        else:raise AssertionError(name)
    rss=b'<rss version="2.0"><channel><item><title>Test earnings headline</title><guid>one</guid><pubDate>Wed, 04 Nov 2026 05:00:00 GMT</pubDate></item><item><title>No time</title></item></channel></rss>'
    atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Test atom</title><id>two</id></entry></feed>'
    with Inbox(out/'raw_inbox.sqlite',True) as inbox:
        for f in fs:inbox.append(f.source,'SYNTH_JSON',encode(f),f.received)
        at=t+timedelta(minutes=6);raw=encode(actual);inbox.append(actual.source,'SYNTH_JSON',raw,at)
        bad=encode(replace(actual,value=Decimal(90)));inbox.append(actual.source,'SYNTH_JSON',bad,at)
        correction=j.changed(actual,at,'ACTUAL2',90);inbox.append(actual.source,'SYNTH_JSON',encode(correction,'CORRECT',actual.evidence_id),correction.received)
        now=correction.received+timedelta(seconds=1)
        bads=[b'{',b'{"id":"x","id":"y"}',j.canonical({**json.loads(encode(actual,ident='BAD')),'received':now.isoformat()}),encode(replace(actual,observed=t.replace(tzinfo=None)),ident='BAD2'),encode(replace(actual,value=Decimal('NaN')),ident='BAD3'),encode(correction,'CORRECT','missing',ident='BAD4'),encode(replace(actual,published=now+timedelta(seconds=10)),ident='BAD5')]
        for b in bads:inbox.append(actual.source,'SYNTH_JSON',b,now)
        inbox.append('synthetic://B','SYNTH_JSON',encode(correction,'CORRECT',actual.evidence_id,ident='CROSS'),now)
        inbox.append('fixture-rss','UNVERIFIED_FEED',rss,now);inbox.append('fixture-rss','UNVERIFIED_FEED',rss,now);inbox.append('fixture-atom','UNVERIFIED_FEED',atom,now)
        inbox.append('fixture-xml','UNVERIFIED_FEED',b'<!DOCTYPE a [<!ENTITY b "x">]><rss/>',now)
        inbox.append('fixture-xml','UNVERIFIED_FEED',b'<rss><channel><item/></channel></rss>',now)
        inbox.append('fixture-xml','UNVERIFIED_FEED',b'<broken>',now)
        rejects('source_spoof',lambda:inbox.append('fake','SYNTH_JSON',raw,now),'SOURCE_NOT_SYNTHETIC')
        rejects('backdated_receipt',lambda:inbox.append(actual.source,'SYNTH_JSON',raw,t),'RECEIPT_BACKDATED')
        rejects('oversize_raw',lambda:inbox.append(actual.source,'SYNTH_JSON',b'x'*(MAX+1),now),'RAW_LIMIT')
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_GET(self):
                if self.path=='/redirect':self.send_response(302);self.send_header('Location','/rss');self.end_headers();return
                if self.path=='/missing':self.send_error(404);return
                self.send_response(200);self.end_headers();self.wfile.write(rss if self.path=='/rss' else b'x'*(MAX+1))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            for endpoint in ('/rss','/redirect','/missing','/oversize'):capture_feed(inbox,url+endpoint,loopback_test=True)
        finally:server.shutdown();server.server_close();thread.join()
        audit,news,cp,icp=project(inbox,out/'evidence.sqlite')
        expected=['ACCEPTED_SYNTHETIC']*6+['DUPLICATE_BYTES','QUARANTINED','ACCEPTED_SYNTHETIC']+['QUARANTINED']*8+['HEADLINES_ONLY','DUPLICATE_BYTES','HEADLINES_ONLY']+['QUARANTINED']*3+['HEADLINES_ONLY']+['QUARANTINED']*3
        ok('all_receipt_statuses',[a['status'] for a in audit]==expected)
        for idx,reason in {7:'MESSAGE_ID_CHANGED_BYTES',10:'DUPLICATE_KEY',11:'JSON_SCHEMA',12:'CLOCK_REQUIRED',13:'FACT_INVALID',14:'TARGET_NOT_ACTIVE',15:'CLOCK_ORDER',16:'TARGET_NOT_ACTIVE',20:'XML_DTD',21:'TITLE_REQUIRED',24:'TRANSPORT_HTTP_302',25:'TRANSPORT_HTTP_404',26:'TRANSPORT_OVERSIZE_DISCARDED'}.items():ok('quarantine_'+reason+'_'+str(idx),audit[idx]['detail']==reason)
        ok('headline_count',len(news)==5 and all(x['status']=='UNVERIFIED_HEADLINE_ONLY' for x in news))
        ok('missing_publication_preserved',sum(not x['reported_publication'] for x in news)==3)
        ok('no_news_fact',cp[0]==7)
        with j.Journal(out/'evidence.sqlite') as journal:
            ok('before_correction',journal.snapshot(ctx,at)['decision']['state']=='ALIGNED_UP_RESEARCH')
            ok('same_receipt',journal.snapshot(ctx,correction.received)['decision']['state']=='ALIGNED_UP_RESEARCH')
            ok('after_correction',journal.snapshot(ctx,now)['decision']['state']=='MIXED_SIGNALS_REVIEW')
            ok('all_orders_disabled',journal.snapshot(ctx,now)['decision']['execution']=='DISABLED_RESEARCH_ONLY')
            ok('fact_raw_exact',all(j.digest(base64.b64decode(json.loads(p)['raw_b64']))==json.loads(p)['raw_sha256'] for p, in journal.db.execute('SELECT payload FROM journal')))
        a2,n2,c2,i2=project(inbox,out/'evidence_rebuild.sqlite',icp);ok('rebuild_deterministic',(audit,news,cp,icp)==(a2,n2,c2,i2))
        # Every prefix projection agrees with the corresponding journal snapshot before the next receipt.
        rows,_=inbox.rows();prefix=0
        with j.Journal(out/'evidence.sqlite') as full:
            for k in range(1,len(rows)+1):
                with tempfile.TemporaryDirectory() as temp:
                    with Inbox(Path(temp)/'prefix.sqlite',True) as part:
                        for e in rows[:k]:part.append(e['source'],e['format'],base64.b64decode(e['raw']),parse_time(e['received']),e['transport'])
                        _,_,_,_=project(part,Path(temp)/'derived.sqlite')
                    query=parse_time(rows[k-1]['received']) # strict <, including same-time batches
                    with j.Journal(Path(temp)/'derived.sqlite') as partial:assert partial.snapshot(ctx,query)==full.snapshot(ctx,query)
                    prefix+=1
        ok('prefix_snapshots',prefix==len(rows));ok('raw_receipts_preserved',len(rows)==len(audit))
        # Tail deletion is detected only against externally retained checkpoint.
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'tampered.sqlite';dest=sqlite3.connect(p);inbox.db.backup(dest);dest.execute('DELETE FROM inbox WHERE seq=(SELECT MAX(seq) FROM inbox)');dest.commit();dest.close()
            with Inbox(p) as tampered:rejects('tail_deletion_checkpoint',lambda:tampered.rows(icp),'INBOX_CHECKPOINT')
    ok('protected_files_unchanged',before=={n:hashfile(P/n) for n in protected})
    for name,data in [('tests.csv',tests),('receipts.csv',audit),('headlines.csv',news)]:g.write(out/name,data)
    manifest=dict(tests=len(tests),prefix_checks=prefix,raw_receipts=len(audit),accepted_facts=cp[0],headline_count=len(news),status_counts={s:sum(a['status']==s for a in audit) for s in sorted(set(expected))},inbox_checkpoint=icp,evidence_checkpoint=cp,protected=before,real_external_receipts=0,local_http_requests=4,execution='DISABLED_RESEARCH_ONLY',notes='Synthetic facts and loopback HTTP only. Public HTTPS capture function not tested remotely; headlines unverified, no fact conversion. Receipt clock not independently trusted. Oversize and failed transport bodies are not preserved. External checkpoint needed for tail deletion.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False));print(json.dumps(manifest,indent=2))
if __name__=='__main__':main(Path(sys.argv[1]))
