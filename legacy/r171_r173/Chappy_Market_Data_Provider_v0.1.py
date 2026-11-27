"""R172: synthetic provider contract; no network implementation.
Raw bytes are synthetic provider payloads, not Yahoo HTTP responses.
"""
import argparse, hashlib, importlib, json, sqlite3, tempfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import importlib.util
spec=importlib.util.spec_from_file_location('collector_r171',Path(__file__).with_name('Chappy_Market_Data_Collector_v0.1.py'))
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
need=base.need
MAX_BYTES=4_000_000
MAX_ATTEMPTS=3

def setup(c):
    with c:
        c.execute('CREATE TABLE IF NOT EXISTS provider_attempts(id INTEGER PRIMARY KEY, request TEXT NOT NULL, receipt TEXT, status TEXT NOT NULL, raw_sha TEXT, batch_sha TEXT, raw BLOB)')

def audit(c,req,status,receipt=None,raw=None):
    with c:
        cur=c.execute('INSERT INTO provider_attempts(request,receipt,status,raw_sha,raw) VALUES(?,?,?,?,?)',(base.canonical(req).decode(),receipt,status,hashlib.sha256(raw).hexdigest() if raw is not None else None,raw))
    return cur.lastrowid

def finish(c,i,status,batch=None):
    with c:
        c.execute('UPDATE provider_attempts SET status=?,batch_sha=? WHERE id=?',(status,batch,i))

def strict_object(pairs):
    d={}
    for k,v in pairs:
        need(k not in d,'duplicate JSON key'); d[k]=v
    return d

def decode(p,req,raw,receipt):
    need(type(raw) is bytes and len(raw)<=MAX_BYTES,'response size/type')
    obj=json.loads(raw,object_pairs_hook=strict_object)
    need(type(obj) is dict and set(obj)=={'symbol','interval','rows'},'response shape')
    need(obj['symbol']==req['symbol'] and obj['interval']==req['interval'],'response identity')
    # R171 checks all timestamps before converting prices.
    records=base.normalized(p,req,obj['rows'])
    dt=datetime.fromisoformat(receipt); need(dt.utcoffset()==timedelta(hours=9),'receipt offset')
    for _,t,*_ in records: need(dt.replace(tzinfo=None)>=datetime.fromisoformat(t)+timedelta(minutes=5),'early receipt')
    return obj['rows']

def collect(c,p,req,provider,receipt,max_attempts=MAX_ATTEMPTS):
    base.validate_plan(p); need(req==base.request(p,req['symbol'],req['start'],req['end_exclusive']),'request mismatch')
    need(c.execute('SELECT plan FROM metadata WHERE id=1').fetchone()[0]==base.canonical(p).decode(),'database plan mismatch')
    need(type(max_attempts) is int and 1<=max_attempts<=MAX_ATTEMPTS,'attempt limit')
    setup(c)
    need(not c.execute("SELECT 1 FROM provider_attempts WHERE status='PENDING'").fetchone(),'pending attempt; manual audit required')
    expected={(d+'T'+t) for d in req['expected_days'] for t in base.SLOTS}
    for n in range(max_attempts):
        try: raw=provider(dict(req))
        except (TimeoutError,ConnectionError):
            audit(c,req,'TRANSIENT_FAILURE'); continue
        try: rows=decode(p,req,raw,receipt)
        except (ValueError,TypeError,KeyError,UnicodeError,OverflowError):
            # Never retain invalid/out-of-scope response payloads.
            audit(c,req,'INVALID_RESPONSE'); return 'INVALID_RESPONSE'
        i=audit(c,req,'PENDING',receipt,raw)
        try: result=base.ingest(c,p,req,rows,receipt)
        except (ValueError,TypeError,KeyError,sqlite3.IntegrityError,OverflowError):
            finish(c,i,'REJECTED'); return 'REJECTED'
        actual={t for (t,) in c.execute('SELECT t FROM bars WHERE symbol=? AND t>=? AND t<?',(req['symbol'],req['start'],req['end_exclusive']))}
        complete=expected<=actual
        finish(c,i,'COMPLETE' if complete else 'PARTIAL' if rows else 'EMPTY',result['batch_sha256'])
        if complete: return 'COMPLETE'
    return 'EXHAUSTED'

def verify(c,p):
    setup(c); count=0
    for req,receipt,status,digest,batch,raw in c.execute('SELECT request,receipt,status,raw_sha,batch_sha,raw FROM provider_attempts ORDER BY id'):
        req=json.loads(req); need(req==base.request(p,req['symbol'],req['start'],req['end_exclusive']),'bad audit request')
        if raw is None:
            need(status in ('TRANSIENT_FAILURE','INVALID_RESPONSE') and digest is None and batch is None,'invalid audit state'); continue
        need(hashlib.sha256(raw).hexdigest()==digest,'raw changed'); rows=decode(p,req,raw,receipt); count+=1
        if status in ('COMPLETE','PARTIAL','EMPTY'):
            need(batch==base.sha({'request':req,'rows':rows,'received':receipt}),'batch mismatch')
            need(c.execute('SELECT rows FROM batches WHERE digest=?',(batch,)).fetchone()==(len(rows),),'batch missing')
            records=base.normalized(p,req,rows)
            for s,t,*vals in records:
                need(c.execute('SELECT o,h,l,c,v FROM bars WHERE symbol=? AND t=?',(s,t)).fetchone()==tuple(vals),'stored price changed')
                need(c.execute('SELECT 1 FROM evidence WHERE digest=? AND symbol=? AND t=?',(batch,s,t)).fetchone(),'missing evidence')
        else: need(status in ('PENDING','REJECTED') and batch is None,'bad status')
    return count

def self_test():
    checks=Counter()
    def check(ok,k): need(ok,'test '+k); checks[k]+=1
    def reject(fn,k):
        try: fn()
        except (ValueError,KeyError,TypeError): checks[k]+=1
        else: raise RuntimeError('accepted '+k)
    p=base.plan(base.SYMBOLS,['2026-11-24']); received='2026-11-25T09:00:00+09:00'; rows=base.fixture('2026-11-24')
    def payload(req,rs): return base.canonical({'symbol':req['symbol'],'interval':'5m','rows':rs})
    class Fake:
        def __init__(self,items): self.items=list(items); self.calls=[]
        def __call__(self,req):
            self.calls.append(req); x=self.items.pop(0)
            if isinstance(x,Exception): raise x
            return x
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'provider.db'; c=base.open_db(path,p)
        for s in p['symbols']:
            req=base.request(p,s,'2026-11-24','2026-11-25'); f=Fake([TimeoutError(),payload(req,rows[:30]),payload(req,rows[30:])])
            check(collect(c,p,req,f,received)=='COMPLETE','partial_recovery'); check(f.calls==[req]*3,'bounded_identical_requests')
            check(collect(c,p,req,Fake([payload(req,rows)]),received)=='COMPLETE','duplicate_retrieval')
        check(base.inventory(c,p)['stored']==396,'coverage'); check(verify(c,p)==18,'raw_replay')
        req=base.request(p,p['symbols'][0],'2026-11-24','2026-11-25'); before=base.inventory(c,p)
        for t in ('2026-11-25T09:00:00','2026-11-26T09:00:00','2026-11-24T11:30:00'):
            bad=[rows[0].copy()]; bad[0][0]=t; bad[0][1]='NOT_A_PRICE'; f=Fake([payload(req,bad)])
            check(collect(c,p,req,f,received)=='INVALID_RESPONSE' and len(f.calls)==1,'out_of_scope_response')
        for raw in (b'not json',b'{"symbol":1,"symbol":2}',base.canonical({'symbol':'9999.T','interval':'5m','rows':rows}),b'x'*(MAX_BYTES+1)):
            check(collect(c,p,req,Fake([raw]),received)=='INVALID_RESPONSE','malformed_response')
        f=Fake([]); bad=dict(req,end_exclusive='2026-11-26'); reject(lambda:collect(c,p,bad,f,received),'protected_request'); check(not f.calls,'no_provider_call')
        conflict=[rows[0].copy()]; conflict[0][4]='1000.500'
        check(collect(c,p,req,Fake([payload(req,conflict)]),received)=='REJECTED','conflict_terminal'); check(base.inventory(c,p)==before,'bars_unchanged')
        check(c.execute("SELECT count(*) FROM provider_attempts WHERE status='INVALID_RESPONSE' AND raw IS NOT NULL").fetchone()==(0,),'invalid_not_archived')
        c.close(); c=base.open_db(path,p); check(verify(c,p)==19,'restart_raw_replay'); check(base.inventory(c,p)==before,'restart_inventory')
        i=audit(c,req,'PENDING',received,payload(req,rows)); f=Fake([]); reject(lambda:collect(c,p,req,f,received),'pending_blocks'); check(not f.calls,'pending_no_call'); finish(c,i,'REJECTED')
        c.execute('UPDATE provider_attempts SET raw=? WHERE id=?',(b'changed',i)); c.commit(); reject(lambda:verify(c,p),'tamper_detected'); c.close()
        c=base.open_db(Path(tmp)/'empty.db',p); f=Fake([payload(req,[]),ConnectionError(),payload(req,[])])
        check(collect(c,p,req,f,received)=='EXHAUSTED','empty_exhaustion'); check(len(f.calls)==3,'retry_bound'); check(base.inventory(c,p)['stored']==0,'empty_not_complete'); check(verify(c,p)==2,'empty_raw_replay'); c.close()
    return {'status':'SYNTHETIC_PROVIDER_CONTRACT_ONLY','checks':dict(checks),'passed':sum(checks.values()),'stored':396,'limits':['No network or real prices','Raw bytes are synthetic response JSON, not HTTP wire data','No automatic pending recovery; two commit boundaries','No sleeping/backoff or live provider implementation','R171 synthetic calendar unchanged']}
if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--self-test',action='store_true',required=True); a.add_argument('--output',required=True); x=a.parse_args(); result=self_test()
    with open(x.output,'x',encoding='utf-8') as f: json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
    print(result['passed'])
