"""R171: offline collection foundation. Synthetic only; no provider/network access.
Prices are exact integer milliyen. Explicit expected sessions, not a calendar API.
"""
import argparse, hashlib, json, re, sqlite3, tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from decimal import Decimal
from fractions import Fraction

CUTOFF='2026-11-24'
SYMBOLS=('6501.T','6758.T','7203.T','7267.T','8058.T','8306.T')
SLOTS=tuple(f'{m//60:02}:{m%60:02}:00' for a,b in ((540,690),(750,930)) for m in range(a,b,5))
SCHEMA='collector.synthetic.v1'
def need(ok,msg):
    if not ok: raise ValueError(msg)
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(x): return hashlib.sha256(canonical(x)).hexdigest()
def day(s):
    need(type(s) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}',s),'date syntax')
    d=date.fromisoformat(s); need(s<=CUTOFF,'date outside development boundary'); return d
def plan(symbols,dates):
    need(type(symbols) in (tuple,list) and 1<=len(symbols)<=30,'symbol count')
    need(all(type(s) is str and re.fullmatch(r'[0-9]{4}\.T',s) for s in symbols),'symbol syntax')
    need(len(set(symbols))==len(symbols),'duplicate symbol')
    need(type(dates) in (tuple,list) and len(dates)>0,'empty calendar')
    for d in dates: need(day(d).weekday()<5,'weekend')
    need(len(set(dates))==len(dates),'duplicate day')
    return {'schema':SCHEMA,'symbols':sorted(symbols),'dates':sorted(dates),'slots':list(SLOTS),'interval':'5m','timezone':'Asia/Tokyo','cutoff_inclusive':CUTOFF,'source':'SYNTHETIC_ONLY'}
def validate_plan(p):
    need(p==plan(p['symbols'],p['dates']),'plan mismatch')
def request(p,symbol,start,end_exclusive):
    validate_plan(p); need(symbol in p['symbols'],'unapproved symbol'); a=day(start)
    need(type(end_exclusive) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}',end_exclusive),'end syntax')
    b=date.fromisoformat(end_exclusive); need(a<b<=date.fromisoformat(CUTOFF)+timedelta(days=1),'request outside development boundary')
    ds=[d for d in p['dates'] if start<=d<end_exclusive]; need(ds,'no planned days')
    return {'plan_sha256':sha(p),'symbol':symbol,'start':start,'end_exclusive':end_exclusive,'expected_days':ds,'interval':'5m','source':'SYNTHETIC_ONLY'}
def integer_price(x,scale):
    need(type(x) is str and re.fullmatch(r'[0-9]{1,12}(?:\.[0-9]{1,3})?',x),'decimal syntax')
    v=Fraction(Decimal(x))*scale; need(v.denominator==1,'precision'); return int(v)
def normalized(p,req,rows):
    need(req==request(p,req['symbol'],req['start'],req['end_exclusive']),'request mismatch')
    need(type(rows) is list and len(rows)<=len(req['expected_days'])*len(SLOTS),'row count')
    keys=set()
    # Check all temporal/symbol keys before numeric conversion. No inference of missing bars.
    for row in rows:
        need(type(row) is list and len(row)==6,'row shape'); t=row[0]
        need(type(t) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',t),'timestamp syntax')
        need(t[:10] in req['expected_days'] and t[11:] in SLOTS,'unexpected time'); need(t not in keys,'duplicate in batch'); keys.add(t)
    result=[]
    for t,o,h,l,c,v in rows:
        o,h,l,c=[integer_price(x,1000) for x in (o,h,l,c)]; v=integer_price(v,1)
        need(0<l<=min(o,c)<=max(o,c)<=h and v>=0,'invalid OHLCV')
        result.append((req['symbol'],t,o,h,l,c,v))
    return sorted(result)
def open_db(path,p):
    validate_plan(p); conn=sqlite3.connect(path)
    try:
        conn.execute('PRAGMA foreign_keys=ON'); conn.execute('PRAGMA busy_timeout=5000')
        with conn:
            conn.execute('CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK(id=1), plan TEXT NOT NULL)')
            prior=conn.execute('SELECT plan FROM metadata WHERE id=1').fetchone()
            if prior is None: conn.execute('INSERT INTO metadata VALUES(1,?)',(canonical(p).decode(),))
            else: need(prior[0]==canonical(p).decode(),'database plan mismatch')
            conn.execute('CREATE TABLE IF NOT EXISTS bars (symbol TEXT, t TEXT, o INTEGER, h INTEGER, l INTEGER, c INTEGER, v INTEGER, PRIMARY KEY(symbol,t))')
            conn.execute('CREATE TABLE IF NOT EXISTS batches (digest TEXT PRIMARY KEY, request TEXT NOT NULL, received TEXT NOT NULL, rows INTEGER NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS evidence (digest TEXT REFERENCES batches(digest), symbol TEXT, t TEXT, PRIMARY KEY(digest,symbol,t), FOREIGN KEY(symbol,t) REFERENCES bars(symbol,t))')
        return conn
    except Exception:
        conn.close(); raise
def ingest(conn,p,req,rows,received):
    validate_plan(p); need(conn.execute('SELECT plan FROM metadata WHERE id=1').fetchone()[0]==canonical(p).decode(),'database plan mismatch')
    need(type(received) is str,'receipt syntax'); dt=datetime.fromisoformat(received); need(dt.utcoffset()==timedelta(hours=9),'receipt offset')
    records=normalized(p,req,rows)
    for _,t,*_ in records: need(dt.replace(tzinfo=None)>=datetime.fromisoformat(t)+timedelta(minutes=5),'receipt before bar close')
    digest=sha({'request':req,'rows':rows,'received':received})
    try:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM batches WHERE digest=?',(digest,)).fetchone():
            conn.commit(); return {'batch_sha256':digest,'new':0,'identical':len(records),'replay':True}
        new=0; identical=0
        for s,t,*vals in records:
            prior=conn.execute('SELECT o,h,l,c,v FROM bars WHERE symbol=? AND t=?',(s,t)).fetchone()
            if prior is None: conn.execute('INSERT INTO bars VALUES(?,?,?,?,?,?,?)',(s,t,*vals)); new+=1
            else: need(prior==tuple(vals),'conflicting bar: entire batch rejected'); identical+=1
        conn.execute('INSERT INTO batches VALUES(?,?,?,?)',(digest,canonical(req).decode(),received,len(records)))
        conn.executemany('INSERT INTO evidence VALUES(?,?,?)',[(digest,s,t) for s,t,*_ in records]); conn.commit()
        return {'batch_sha256':digest,'new':new,'identical':identical,'replay':False}
    except Exception:
        conn.rollback(); raise
def inventory(conn,p):
    validate_plan(p); need(conn.execute('SELECT plan FROM metadata WHERE id=1').fetchone()[0]==canonical(p).decode(),'database plan mismatch')
    rows=list(conn.execute('SELECT * FROM bars ORDER BY symbol,t')); actual={(s,t) for s,t,*_ in rows}; expected={(s,d+'T'+t) for s in p['symbols'] for d in p['dates'] for t in SLOTS}; need(actual<=expected,'unexpected stored key')
    missing=sorted(expected-actual); batches=list(conn.execute('SELECT digest,request,received,rows FROM batches ORDER BY digest'))
    links=list(conn.execute('SELECT digest,symbol,t FROM evidence ORDER BY digest,symbol,t')); need({(s,t) for _,s,t in links}==actual,'missing provenance')
    return {'schema':SCHEMA,'plan_sha256':sha(p),'expected':len(expected),'stored':len(rows),'missing':len(missing),'missing_keys':missing,'complete':not missing,'zero_volume':sum(r[-1]==0 for r in rows),'batches':len(batches),'evidence_links':len(links),'data_sha256':sha(rows),'provenance_sha256':sha({'batches':batches,'links':links})}
def fixture(d):
    return [[d+'T'+t,'1000.125','1002.125','999.125','1001.125',str(100+i)] for i,t in enumerate(SLOTS)]
def self_test():
    from collections import Counter
    checks=Counter()
    def check(ok,n):
        if not ok: raise RuntimeError('failed: '+n)
        checks[n]+=1
    def reject(fn,n):
        try: fn()
        except (ValueError,TypeError,KeyError,sqlite3.IntegrityError): checks[n]+=1
        else: raise RuntimeError('accepted invalid: '+n)
    p=plan(SYMBOLS,['2026-11-20','2026-11-24']); receipt='2026-11-25T09:00:00+09:00'; snapshot=[]
    with tempfile.TemporaryDirectory() as tmp:
        db=Path(tmp)/'synthetic.sqlite'; c=open_db(db,p)
        for s in p['symbols']:
            req=request(p,s,'2026-11-20','2026-11-25'); rows=fixture('2026-11-20')+fixture('2026-11-24'); half=rows[:-1]
            r=ingest(c,p,req,half,receipt); check(r['new']==131 and r['identical']==0,'first_ingest')
            before=inventory(c,p); check(not before['complete'],'partial_inventory')
            check(ingest(c,p,req,half,receipt)['replay'],'exact_retry'); check(inventory(c,p)==before,'retry_unchanged')
            r=ingest(c,p,req,rows,receipt); check(r['new']==1 and r['identical']==131,'partial_retry')
            r=ingest(c,p,req,rows,'2026-11-25T09:01:00+09:00'); check(r['new']==0 and r['identical']==132,'new_receipt')
        full=inventory(c,p); check(full['complete'] and full['stored']==792,'full_coverage'); check(full['evidence_links']==6*(131+132+132),'evidence_count')
        for s,t,o,h,l,cl,v in c.execute('SELECT * FROM bars'):
            check((o,h,l,cl)==(1000125,1002125,999125,1001125),'exact_price'); check(v==100+SLOTS.index(t[11:]),'volume')
        req=request(p,SYMBOLS[0],'2026-11-20','2026-11-25')
        for start,end in [('2026-11-26','2026-11-27'),('2026-11-24','2026-11-26'),('2026-11-25','2026-11-26'),('2026-11-24','2026-11-24')]: reject(lambda:request(p,SYMBOLS[0],start,end),'date_reject')
        reject(lambda:request(p,'9999.T','2026-11-20','2026-11-25'),'symbol_reject')
        for bad in ['2026-11-26T09:00:00','2026-11-25T09:00:00','2026-11-24T11:30:00','2026-11-24T15:30:00','2026-11-23T09:00:00']:
            row=fixture('2026-11-24')[0]; row[0]=bad; reject(lambda:ingest(c,p,req,[row],receipt),'bar_time_reject')
        row=fixture('2026-11-24')[0]; reject(lambda:ingest(c,p,req,[row,row],receipt),'duplicate_reject')
        for idx,bad in [(1,'NaN'),(1,'1000.0001'),(2,'900'),(3,'0'),(5,'0.5'),(5,'-1')]:
            row=fixture('2026-11-24')[0]; row[idx]=bad; reject(lambda:ingest(c,p,req,[row],receipt),'number_reject')
        row=fixture('2026-11-24')[0]; row[4]='1000.500'; reject(lambda:ingest(c,p,req,[row],receipt),'conflict_reject')
        reject(lambda:ingest(c,p,req,fixture('2026-11-24'),'2026-11-24T09:00:00+09:00'),'early_receipt_reject')
        reject(lambda:ingest(c,p,req,fixture('2026-11-24'),'2026-11-25T09:00:00+00:00'),'offset_reject')
        check(inventory(c,p)==full,'all_rejections_unchanged'); c.close()
        c=open_db(db,p); check(inventory(c,p)==full,'restart_persistence'); c.close()
        reject(lambda:open_db(db,plan(SYMBOLS[:1],p['dates'])),'plan_mismatch_reject')
        # Atomic rollback after an earlier insert in the same batch.
        c=open_db(Path(tmp)/'atomic.sqlite',p); last=fixture('2026-11-24')[-1]; ingest(c,p,req,[last],receipt); before=inventory(c,p)
        rows=fixture('2026-11-24'); rows[-1][4]='1000.500'; reject(lambda:ingest(c,p,req,rows,receipt),'late_conflict_reject'); check(inventory(c,p)==before,'transaction_rollback'); c.close()
        snapshot=full
    return {'status':'SYNTHETIC_STORAGE_FOUNDATION_ONLY','checks':dict(checks),'passed':sum(checks.values()),'inventory':snapshot,'plan':p,'limits':['No network/provider access or actual market prices','Synthetic expected dates and 66-slot schedule, not verified exchange calendar','Conflicting values rejected, no automatic correction or merge','No raw provider response archive yet; digest covers submitted fixture rows and receipt','No live or protected-period collection; R170 not modified']}
if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--self-test',action='store_true',required=True); a.add_argument('--output',required=True); x=a.parse_args(); r=self_test()
    with open(x.output,'x',encoding='utf-8') as f: json.dump(r,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
    print(r['passed'],r['inventory']['stored'],r['inventory']['batches'])
