"""R173: authorized offline CSV import. No network, no synthetic/real database mixing."""
import argparse, csv, hashlib, io, json, sqlite3, tempfile, importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from collections import Counter
P=Path(__file__).with_name('Chappy_Market_Data_Collector_v0.1.py')
EXPECTED='184f3674d28f15cbc9c2c289bf844bc12907eefcafb37f0fb284ae110129a67f'
if hashlib.sha256(P.read_bytes()).hexdigest()!=EXPECTED: raise ValueError('R171 dependency changed')
spec=importlib.util.spec_from_file_location('r171_import',P); base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
need=base.need; JST=timezone(timedelta(hours=9)); MAX_BYTES=4_000_000
START='2026-10-01'; END='2026-11-25'; HOLIDAYS={'2026-10-12','2026-11-03','2026-11-23'}
DAYS=tuple(d.isoformat() for i in range((date.fromisoformat(END)-date.fromisoformat(START)).days) if (d:=date.fromisoformat(START)+timedelta(days=i)).weekday()<5 and d.isoformat() not in HOLIDAYS)
SCHEMA='collector.authorized.offline.v1'; COLS=('Datetime','Open','High','Low','Close','Volume')

def plan(source):
    need(type(source) is str and 0<len(source.strip())<=120,'source identifier required')
    return {'schema':SCHEMA,'source':source,'symbols':list(base.SYMBOLS),'days':list(DAYS),'slots':list(base.SLOTS),'interval':'5m','timezone':'Asia/Tokyo','start':START,'end_exclusive':END,'calendar':'JPX 2026 published holidays and weekday schedule','price_unit':'milliyen exact; no rounding','receipt':'declared import timestamp, not original market receipt'}

def parse(raw,symbol,received):
    need(symbol in base.SYMBOLS,'unapproved symbol'); need(type(raw) is bytes and len(raw)<=MAX_BYTES,'input size')
    receipt=datetime.fromisoformat(received); need(receipt.utcoffset() is not None,'receipt timezone required'); receipt=receipt.astimezone(JST)
    reader=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True); header=next(reader,[])
    need(len(header)==len(set(header)) and set(header) in (set(COLS),set(COLS)|{'Adj Close'}),'flat single-symbol OHLCV CSV required')
    ix=[header.index(k) for k in COLS]; seen=set(); staged=[]
    for row in reader:
        need(len(row)==len(header),'row width'); rawtime=row[ix[0]]
        t=datetime.fromisoformat(rawtime); need(t.utcoffset() is not None,'timestamp timezone required'); t=t.astimezone(JST)
        key=t.replace(tzinfo=None).isoformat(timespec='seconds')
        need(t.microsecond==0 and t.date().isoformat() in DAYS and key[11:] in base.SLOTS,'out-of-scope timestamp')
        need(key not in seen,'duplicate timestamp'); seen.add(key); need(receipt>=t+timedelta(minutes=5),'receipt before close')
        staged.append((key,row))
    # No numeric conversion until the entire timestamp scope is checked.
    result=[]
    for key,row in staged:
        o,h,l,c=[base.integer_price(row[i],1000) for i in ix[1:5]]; v=base.integer_price(row[ix[5]],1)
        need(0<l<=min(o,c)<=max(o,c)<=h and v>=0,'invalid OHLCV'); result.append((symbol,key,o,h,l,c,v))
    return sorted(result)

def open_db(path,source):
    p=plan(source); c=sqlite3.connect(path); c.execute('PRAGMA foreign_keys=ON')
    try:
        with c:
            c.execute('CREATE TABLE IF NOT EXISTS real_metadata(id INTEGER PRIMARY KEY CHECK(id=1),plan TEXT NOT NULL)')
            old=c.execute('SELECT plan FROM real_metadata WHERE id=1').fetchone()
            if old is None:
                need(not c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'").fetchone(),'synthetic database prohibited')
                c.execute('INSERT INTO real_metadata VALUES(1,?)',(base.canonical(p).decode(),))
            else: need(old==(base.canonical(p).decode(),),'plan/source mismatch')
            c.execute('CREATE TABLE IF NOT EXISTS real_bars(symbol TEXT,t TEXT,o INTEGER,h INTEGER,l INTEGER,c INTEGER,v INTEGER,PRIMARY KEY(symbol,t))')
            c.execute('CREATE TABLE IF NOT EXISTS real_imports(id TEXT PRIMARY KEY,symbol TEXT,received TEXT,raw_sha TEXT,raw BLOB,rows INTEGER)')
            c.execute('CREATE TABLE IF NOT EXISTS real_evidence(id TEXT REFERENCES real_imports(id),symbol TEXT,t TEXT,PRIMARY KEY(id,symbol,t),FOREIGN KEY(symbol,t) REFERENCES real_bars(symbol,t))')
        return c
    except Exception: c.close(); raise

def import_csv(c,source,symbol,raw,received):
    need(c.execute('SELECT plan FROM real_metadata WHERE id=1').fetchone()==(base.canonical(plan(source)).decode(),),'plan/source mismatch')
    records=parse(raw,symbol,received); digest=hashlib.sha256(raw).hexdigest(); ident=base.sha([source,symbol,received,digest]); new=0
    try:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM real_imports WHERE id=?',(ident,)).fetchone(): c.commit(); return 0
        for s,t,*v in records:
            old=c.execute('SELECT o,h,l,c,v FROM real_bars WHERE symbol=? AND t=?',(s,t)).fetchone()
            if old is None: c.execute('INSERT INTO real_bars VALUES(?,?,?,?,?,?,?)',(s,t,*v)); new+=1
            else: need(old==tuple(v),'conflicting bar; rollback')
        c.execute('INSERT INTO real_imports VALUES(?,?,?,?,?,?)',(ident,symbol,received,digest,raw,len(records)))
        c.executemany('INSERT INTO real_evidence VALUES(?,?,?)',[(ident,s,t) for s,t,*_ in records]); c.commit(); return new
    except Exception: c.rollback(); raise

def verify(c,source):
    need(c.execute('SELECT plan FROM real_metadata WHERE id=1').fetchone()==(base.canonical(plan(source)).decode(),),'plan/source mismatch')
    expected={}; links=set(); count=0
    for ident,symbol,received,digest,raw,n in c.execute('SELECT * FROM real_imports'):
        need(hashlib.sha256(raw).hexdigest()==digest and ident==base.sha([source,symbol,received,digest]),'raw/import hash mismatch'); records=parse(raw,symbol,received); need(len(records)==n,'row count mismatch'); count+=1
        for s,t,*v in records:
            need((s,t) not in expected or expected[(s,t)]==tuple(v),'archive conflict'); expected[s,t]=tuple(v); links.add((ident,s,t))
    actual={(s,t):tuple(v) for s,t,*v in c.execute('SELECT * FROM real_bars')}
    need(actual==expected,'bar replay mismatch'); need(set(c.execute('SELECT * FROM real_evidence'))==links,'evidence mismatch')
    total=len(DAYS)*len(base.SYMBOLS)*len(base.SLOTS)
    coverage={s:sum(k[0]==s for k in actual) for s in base.SYMBOLS}
    return {'schema':SCHEMA,'source':source,'plan_sha256':base.sha(plan(source)),'expected_slots':total,'stored':len(actual),'missing_slots':total-len(actual),'imports':count,'coverage':coverage,'data_sha256':base.sha(sorted((s,t,*v) for (s,t),v in actual.items()))}

def self_test():
    checks=Counter(); source='TEST_FIXTURE_ONLY'; receipt='2026-11-25T09:00:00+09:00'
    def check(ok,k): need(ok,'failed '+k); checks[k]+=1
    def reject(f,k):
        try: f()
        except (ValueError,TypeError,UnicodeError,csv.Error,sqlite3.IntegrityError): checks[k]+=1
        else: raise RuntimeError('accepted '+k)
    def raw(rows):
        b=io.StringIO(); w=csv.writer(b,lineterminator='\n'); w.writerow(COLS); w.writerows(rows); return b.getvalue().encode()
    rows=[[f'2026-11-24T{t}+09:00','1000.125','1002.125','999.125','1001.125',str(i)] for i,t in enumerate(base.SLOTS)]
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'test.sqlite'; c=open_db(path,source)
        for s in base.SYMBOLS:
            check(import_csv(c,source,s,raw(rows[:30]),receipt)==30,'partial'); check(import_csv(c,source,s,raw(rows),receipt)==36,'completion'); check(import_csv(c,source,s,raw(rows),receipt)==0,'duplicate')
        snapshot=verify(c,source); check(snapshot['stored']==396 and snapshot['imports']==12,'raw_replay')
        for s,t,o,h,l,cl,v in c.execute('SELECT * FROM real_bars'):
            check((o,h,l,cl,v)==(1000125,1002125,999125,1001125,base.SLOTS.index(t[11:])),'exact_bar')
        s=base.SYMBOLS[0]
        for t in ['2026-11-26T09:00:00+09:00','2026-11-25T09:00:00+09:00','2026-11-23T09:00:00+09:00','2026-11-24T11:30:00+09:00','2026-11-24T09:00:00','2026-11-24T09:00:00.001+09:00']:
            bad=rows[0].copy(); bad[0]=t; bad[1]='INVALID'; reject(lambda:import_csv(c,source,s,raw([bad]),receipt),'scope_reject')
        for i,val in [(1,'1000.0001'),(2,'800'),(3,'0'),(5,'0.5'),(5,'NaN')]:
            bad=rows[0].copy(); bad[i]=val; reject(lambda:import_csv(c,source,s,raw([bad]),receipt),'numeric_reject')
        reject(lambda:import_csv(c,source,s,raw([rows[0],rows[0]]),receipt),'duplicate_row'); reject(lambda:import_csv(c,source,'9999.T',raw(rows),receipt),'symbol'); reject(lambda:import_csv(c,source,s,raw(rows),'2026-11-24T09:00:00+09:00'),'early_receipt')
        utc=rows[0].copy(); utc[0]='2026-11-24T00:00:00+00:00'; check(parse(raw([utc]),s,receipt)==parse(raw(rows[:1]),s,receipt),'timezone_conversion')
        conflict=rows[-1].copy(); conflict[4]='1001.250'; earlier=rows[0].copy(); earlier[0]='2026-11-20T09:00:00+09:00'; reject(lambda:import_csv(c,source,s,raw([earlier,conflict]),receipt),'atomic_conflict'); check(verify(c,source)==snapshot,'rollback')
        c.close(); c=open_db(path,source); check(verify(c,source)==snapshot,'restart'); reject(lambda:open_db(path,'OTHER'),'source_isolation')
        c.execute("UPDATE real_imports SET raw=? WHERE id=(SELECT min(id) FROM real_imports)",(b'tampered',)); c.commit(); reject(lambda:verify(c,source),'tamper'); c.close()
        p=base.plan(base.SYMBOLS,['2026-11-24']); synthetic=Path(tmp)/'synthetic.db'; base.open_db(synthetic,p).close(); reject(lambda:open_db(synthetic,source),'synthetic_isolation')
    return {'status':'OFFLINE_IMPORT_FIXTURE_ONLY','checks':dict(checks),'passed':sum(checks.values()),'plan':plan(source),'fixture_inventory':snapshot,'limits':['No network or market price acquisition','Only flat single-symbol CSV; symbol and source declared by operator','No actual provider authentication or HTTP raw archive','Strict exact milliyen; floating artifacts rejected rather than rounded','Missing expected slots are diagnostics, not necessarily provider errors','No live automation; verify applicable data rights first']}

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__); a.add_argument('--self-test',action='store_true'); a.add_argument('--plan-only',action='store_true'); a.add_argument('--csv'); a.add_argument('--db'); a.add_argument('--symbol'); a.add_argument('--source'); a.add_argument('--received'); a.add_argument('--authorized',action='store_true',help='Confirm source permits local import/storage'); a.add_argument('--output',required=True); x=a.parse_args()
    need(sum([x.self_test,x.plan_only,bool(x.csv)])==1,'choose one mode'); need(not Path(x.output).exists(),'output exists')
    if x.self_test: r=self_test()
    elif x.plan_only: r=plan(x.source or 'AUTHORIZED_SOURCE_NOT_YET_SELECTED')
    else:
        need(x.authorized and all([x.db,x.symbol,x.source,x.received]),'permission and explicit metadata required'); need(Path(x.csv).stat().st_size<=MAX_BYTES,'input size'); raw=Path(x.csv).read_bytes(); parse(raw,x.symbol,x.received)
        c=open_db(x.db,x.source)
        try: verify(c,x.source); new=import_csv(c,x.source,x.symbol,raw,x.received); r=verify(c,x.source); r['new']=new
        finally: c.close()
    with open(x.output,'x',encoding='utf-8') as f: json.dump(r,f,sort_keys=True,indent=2); f.write('\n')
    print(r.get('passed',r.get('stored','PLAN_ONLY')))
