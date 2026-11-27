"""Synthetic research: multi-leg feed gate + durable deterministic replay.
No brokerage/network. Requires FeedSafety and its existing dependencies alongside.
Run: python Chappy_Trading_Integrated_Replay_v0.1.py OUTPUT_DIR
"""
import csv, hashlib, importlib.util, json, math, sqlite3, sys, tempfile
from dataclasses import asdict
from pathlib import Path
p=Path(__file__).with_name('Chappy_Trading_FeedSafety_Study_v0.1.py')
spec=importlib.util.spec_from_file_location('integrated_feed',p); f=importlib.util.module_from_spec(spec);sys.modules[spec.name]=f;spec.loader.exec_module(f)
ls=f.ls
WINDOWS=((0,7200),(10800,18000)); EXIT_LEAD=60; HOLD=3600; ZERO='0'*64

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
class Gate:
    def __init__(self):
        self.symbols=('A','B','C');self.book=ls.Book();self.clock=-1;self.session=None;self.last={};self.history={};self.next=None;self.sync=None;self.pending=None;self.exit=None;self.expiry=None;self.fault=None;self.quotes={};self.events=[];self.decisions=0
    def log(self,kind,**kw):self.events.append(dict(now=self.clock,kind=kind,**kw))
    def cancel(self,reason):
        if self.pending is not None:self.pending=None;self.log('CANCEL',reason=reason)
    def exit_all(self,reason):
        self.cancel(reason)
        if self.book.legs and self.exit is None:self.exit=(self.clock,reason);self.log('EXIT_REQUEST',reason=reason)
    def halt(self,reason):
        if self.fault is None:self.fault=reason;self.log('HALT',reason=reason)
        self.exit_all(reason)
    def advance(self,now):
        if type(now)!=int or now<self.clock:raise ValueError('nonmonotonic clock')
        old=self.session;self.clock=now
        self.session=next((w for w in WINDOWS if w[0]<=now<w[1]),None)
        if old!=self.session:
            self.cancel('SESSION_CHANGE');self.sync=None;self.last={};self.next=self.session[0]+f.STEP if self.session else None
            if self.book.legs:self.halt('CARRY_EXPOSURE')
        if self.session and now>=self.session[1]-EXIT_LEAD:self.exit_all('SESSION_CUTOFF')
        if self.session and not self.fault and now<self.session[1]-EXIT_LEAD and now>self.next+f.LAG+f.GRACE:self.halt('SYNC_TIMEOUT')
        if self.pending and now-self.pending['created']>f.STEP:self.cancel('ORDER_EXPIRED')
        if self.book.legs:
            if self.expiry is not None and now>=self.expiry:self.exit_all('HOLD_EXPIRED')
            if any(now-self.quotes.get(k,(-10**9,0))[0]>f.QUOTE_SILENCE for k,s in self.book.legs):self.halt('QUOTE_TIMEOUT')
    def bar(self,k,end,price,volume):
        if k not in self.symbols or type(end)!=int or end>self.clock or end%f.STEP or not math.isfinite(price) or price<=0 or volume<=0:self.halt('INVALID_BAR');return
        key=(k,end);value=(price,volume)
        if key in self.history:
            if self.history[key]!=value:self.halt('CONFIRMED_CORRECTION')
            else:self.log('DUPLICATE_BAR',symbol=k,stamp=end)
            return
        if not self.session or not self.session[0]<end<=self.session[1]:self.log('OUTSIDE_SESSION_BAR',symbol=k,stamp=end);return
        if end!=self.last.get(k,self.session[0])+f.STEP:self.halt('GAP');return
        self.history[key]=value;self.last[k]=end
        if self.fault:return
        if len(self.last)!=len(self.symbols) or len(set(self.last.values()))!=1:self.cancel('UNSYNC');return
        if end!=self.next or self.clock-end>f.LAG+f.GRACE:self.halt('MISSED_SYNC');return
        self.sync=end;self.next=end+f.STEP;self.decisions+=1;self.log('SYNC',stamp=end)
    def eligible(self):
        return bool(self.session and self.clock<self.session[1]-EXIT_LEAD and not self.fault and self.sync is not None and len(self.last)==len(self.symbols) and set(self.last.values())=={self.sync} and self.clock-self.sync<=f.LAG+f.GRACE)
    def request(self,orders):
        if not orders or any(k not in self.symbols or s not in (-1,1) or type(q)!=int or q<=0 or q%ls.LOT for k,s,q in orders) or len({(k,s) for k,s,q in orders})!=len(orders):raise ValueError('invalid order')
        if not self.eligible() or self.pending or self.book.legs:self.log('REJECT_INTENT');return
        self.pending=dict(orders=orders,created=self.clock,sync=self.sync);self.log('INTENT',orders=orders)
    def quote(self,k,price,stamp):
        if k not in self.symbols or type(stamp)!=int or not math.isfinite(price) or price<=0 or stamp>self.clock or self.clock-stamp>f.QUOTE_MAX or stamp<=self.quotes.get(k,(-1,0))[0]:self.log('REJECT_QUOTE',symbol=k,stamp=stamp);return
        self.quotes[k]=(stamp,price)
        if not self.session or stamp<self.session[0]:self.log('NONTRADABLE_QUOTE',symbol=k);return
        if self.exit and stamp>self.exit[0]:
            for key,leg in list(self.book.legs.items()):
                if leg.symbol==k:self.book.close(key,leg.qty,{k:price},str(self.clock),self.exit[1]);self.log('EXIT_FILL',symbol=k,side=key[1])
            if not self.book.legs:self.exit=None;self.expiry=None
        if self.book.legs:
            syms={k for k,s in self.book.legs}
            if all(self.clock-self.quotes.get(k,(-10**9,0))[0]<=f.QUOTE_MAX for k in syms):
                px={k:self.quotes[k][1] for k in syms};self.book.mark(px)
                if self.book.margin_breach(px) and self.exit is None:self.book.margin_calls+=1;self.halt('MARGIN')
        if self.pending:
            if not self.eligible() or self.pending['sync']!=self.sync:self.cancel('UNSYNC_AT_FILL');return
            orders=self.pending['orders'];syms={k for k,s,q in orders};created=self.pending['created']
            if all(self.quotes.get(k,(-10**9,0))[0]>created and self.clock-self.quotes[k][0]<=f.QUOTE_MAX for k in syms):
                self.pending=None;px={k:self.quotes[k][1] for k in syms}
                if self.book.enter(orders,px,str(self.clock),'BATCH_ENTRY'):
                    self.expiry=self.clock+HOLD;self.book.mark(px);self.log('BATCH_FILL',legs=len(orders))
                else:self.log('REJECT_BOOK')
    def apply(self,e):
        self.advance(e['now']);kind=e['kind']
        if kind=='bar':self.bar(e['symbol'],e['end'],e['price'],e.get('volume',100))
        elif kind=='quote':self.quote(e['symbol'],e['price'],e['stamp'])
        elif kind=='request':self.request(e['orders'])
        elif kind=='recover':
            self.halt('RESTART_REVIEW')
            if self.book.legs:self.exit=(self.clock,'RESTART_REVIEW')
        elif kind=='tick':pass
        else:raise ValueError('unknown event')
    def state(self):
        return dict(clock=self.clock,session=self.session,last=self.last,history=sorted((k,t,*v) for (k,t),v in self.history.items()),next=self.next,sync=self.sync,pending=self.pending,exit=self.exit,expiry=self.expiry,fault=self.fault,quotes=self.quotes,decisions=self.decisions,book={k:v for k,v in vars(self.book).items() if k!='legs'},legs=[asdict(v) for k,v in sorted(self.book.legs.items())],events=self.events)
class Journal:
    def __init__(self,path):
        self.db=sqlite3.connect(path);self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA synchronous=FULL');self.db.execute('CREATE TABLE IF NOT EXISTS journal(seq INTEGER PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL, chain TEXT NOT NULL)');self.db.commit();self.reload();self.requires_recovery=self.seq>0
    def reload(self):
        self.g=Gate();self.seq=0;self.head=ZERO
        for seq,payload,state,chain in self.db.execute('SELECT seq,payload,state,chain FROM journal ORDER BY seq'):
            e=json.loads(payload);self.g.apply(e)
            if seq!=self.seq+1 or state!=digest(self.g.state()) or chain!=digest([self.head,seq,e,state]):raise ValueError('journal verification failed')
            self.seq=seq;self.head=chain
    def send(self,kind,now,**kw):
        if self.requires_recovery and kind!='recover':raise ValueError('restart requires recovery event')
        e=json.loads(canonical(dict(kind=kind,now=now,**kw)));self.db.execute('BEGIN IMMEDIATE')
        try:
            last=self.db.execute('SELECT seq,chain FROM journal ORDER BY seq DESC LIMIT 1').fetchone() or (0,ZERO)
            if last!=(self.seq,self.head):raise ValueError('stale writer')
            self.g.apply(e);state=digest(self.g.state());seq=self.seq+1;chain=digest([self.head,seq,e,state]);self.db.execute('INSERT INTO journal VALUES(?,?,?,?)',(seq,canonical(e),state,chain));self.db.commit();self.seq=seq;self.head=chain
            if kind=='recover':self.requires_recovery=False
        except BaseException:
            self.db.rollback();self.reload();self.requires_recovery=True;raise
    @classmethod
    def recover(cls,path,now):
        j=cls(path)
        try:j.send('recover',now)
        except BaseException:j.close();raise
        return j
    def close(self):self.db.close()

def test(out):
    rows=[]; events=[]
    with tempfile.TemporaryDirectory() as tmp:
        def sync(j,t=1200,end=300):
            for i,k in enumerate(j.g.symbols):j.send('bar',t+i,symbol=k,end=end,price=1000,volume=100)
        def enter(j,orders=None):
            sync(j);j.send('request',1202,orders=orders or [('A',1,300),('B',-1,300)]);j.send('quote',1203,symbol='A',price=1000,stamp=1203);j.send('quote',1204,symbol='B',price=1000,stamp=1204)
        def quote(j,k,t,price=1000,stamp=None):j.send('quote',t,symbol=k,price=price,stamp=t if stamp is None else stamp)
        def reopen(j,path):
            state=digest(j.g.state());j.close();n=Journal(path);assert digest(n.g.state())==state;return n
        def run(name,fn):
            path=Path(tmp)/(name+'.db');j=Journal(path);j=fn(j,path) or j
            n=reopen(j,path);g=n.g
            if not g.book.legs:ls.audit(g.book)
            rows.append(dict(case=name,result='PASS',journal_rows=n.seq,open_legs=len(g.book.legs),fills=len(g.book.fills),fault=g.fault or '',cash=g.book.cash,exit_pending=bool(g.exit)))
            events.extend(dict(case=name,**e) for e in g.events);n.close()
        def batch(j,p):
            sync(j);j.send('request',1202,orders=[('A',1,300),('B',-1,300)]);quote(j,'A',1203);assert not j.g.book.legs;quote(j,'B',1204);assert len(j.g.book.legs)==2
            j.send('recover',1205);quote(j,'A',1206,1100);assert len(j.g.book.legs)==1 and j.g.exit;quote(j,'B',1207,900);assert not j.g.book.legs and j.g.book.cash>ls.CAP
        def stale_batch(j,p):
            sync(j);j.send('request',1202,orders=[('A',1,300),('B',-1,300)]);quote(j,'A',1203);quote(j,'B',1210);assert not j.g.book.legs;quote(j,'A',1211);assert len(j.g.book.legs)==2
        def restart_pending(j,p):
            sync(j);j.send('request',1202,orders=[('A',1,300)]);j.close();j=Journal.recover(p,1203);quote(j,'A',1204);assert not j.g.book.legs and j.g.pending is None;return j
        def restart_partial(j,p):
            enter(j);j.send('recover',1205);quote(j,'A',1206);j.close();j=Journal.recover(p,1207);quote(j,'A',1208);quote(j,'B',1208,stamp=1206);assert len(j.g.book.fills)==3 and len(j.g.book.legs)==1;quote(j,'B',1209);assert len(j.g.book.fills)==4 and not j.g.book.legs;return j
        def skew(j,p):
            sync(j);j.send('request',1202,orders=[('A',1,300),('B',-1,300)]);quote(j,'A',1203);j.send('bar',1500,symbol='A',end=600,price=1000);quote(j,'B',1501);assert not j.g.book.legs and j.g.pending is None
        def gross(j,p):
            enter(j,[('A',1,600),('B',-1,600)]);assert not j.g.book.legs and j.g.book.rejections==1
        def margin(j,p):
            enter(j,[('A',-1,400),('B',1,400)]);quote(j,'A',1205,5000);assert j.g.fault=='MARGIN';quote(j,'B',1206);quote(j,'A',1207,5000);assert not j.g.book.legs and j.g.book.cash<0
        def cutoff(j,p):
            enter(j);j.send('tick',7140);quote(j,'A',7141);assert j.g.exit and len(j.g.book.legs)==1;quote(j,'B',7201);assert j.g.book.legs;quote(j,'B',10801);assert not j.g.book.legs and j.g.fault
        def afternoon(j,p):
            sync(j);j.send('tick',7140);j.send('tick',7200);sync(j,12000,11100);assert j.g.decisions==2 and not j.g.fault;j.send('request',12002,orders=[('A',1,300)]);quote(j,'A',12003);assert j.g.book.legs
        def stale_exit(j,p):
            enter(j);j.send('recover',1205);quote(j,'A',1206,1000,1205);assert len(j.g.book.legs)==2;quote(j,'A',1207);quote(j,'A',1208);assert len(j.g.book.fills)==3
        def correction(j,p):
            enter(j);j.send('bar',1205,symbol='A',end=300,price=999);assert j.g.fault=='CONFIRMED_CORRECTION' and j.g.exit
        def holding_deadline(j,p):
            enter(j)
            # Maintain confirmed bars and fresh quotes through the holding deadline.
            for t in range(1210,4804):
                if t%300==0:sync(j,t,t-900)
                elif t%150 in (10,11):quote(j,'A' if t%150==10 else 'B',t)
            assert not j.g.fault and len(j.g.book.legs)==2
            j.send('tick',4804);assert j.g.exit and j.g.exit[1]=='HOLD_EXPIRED';quote(j,'A',4805);quote(j,'B',4806);assert not j.g.book.legs
        def clean_cutoff(j,p):
            enter(j)
            for t in range(1210,7140):
                if t%300==0:sync(j,t,t-900)
                elif t%150 in (10,11):quote(j,'A' if t%150==10 else 'B',t)
            # HOLD_EXPIRED has already flattened at the first subsequent quotes.
            assert not j.g.book.legs and not j.g.fault
            j.send('tick',7140);j.send('tick',7200);sync(j,12000,11100);assert not j.g.fault
        def restart_guard(j,p):
            enter(j);n=reopen(j,p)
            try:quote(n,'A',1205)
            except ValueError:pass
            else:raise AssertionError('restart without review accepted')
            n.send('recover',1205);quote(n,'A',1206);quote(n,'B',1207);assert not n.g.book.legs;return n
        def stale_writer(j,p):
            n=Journal(p);j.send('tick',10)
            try:n.send('tick',11)
            except ValueError:pass
            else:raise AssertionError('stale writer accepted')
            assert n.seq==1;n.close()
        def rollback(j,p):
            sync(j);before=digest(j.g.state());seq=j.seq
            try:j.send('request',1203,orders=[('X',1,300)])
            except ValueError:pass
            else:raise AssertionError('invalid event committed')
            assert j.seq==seq and digest(j.g.state())==before
        def corrupt(j,p):
            sync(j);n=sqlite3.connect(p);n.execute("UPDATE journal SET state='bad' WHERE seq=1");n.commit();n.close()
            try:Journal(p)
            except ValueError:pass
            else:raise AssertionError('corruption accepted')
            # restore test copy only, allowing normal final replay audit
            j.db.execute('UPDATE journal SET state=? WHERE seq=1',(digest(single_bar_state()),));j.db.commit()
        def single_bar_state():
            g=Gate();g.apply(dict(kind='bar',now=1200,symbol='A',end=300,price=1000,volume=100));return g.state()
        for name,fn in [('atomic_batch_and_individual_exit',batch),('stale_batch_quote',stale_batch),('restart_pending',restart_pending),('restart_partial_exit',restart_partial),('sync_cancels_batch',skew),('gross_limit',gross),('margin_debt',margin),('break_no_fill',cutoff),('afternoon_reset',afternoon),('stale_and_duplicate_exit',stale_exit),('confirmed_correction',correction),('holding_deadline',holding_deadline),('clean_session_transition',clean_cutoff),('restart_guard',restart_guard),('stale_writer',stale_writer),('transaction_rollback',rollback),('corruption_detected',corrupt)]:run(name,fn)
    return rows,events

def main():
    out=Path(sys.argv[1]);old,_=f.selftest();rows,events=test(out);out.mkdir(exist_ok=False)
    for name,data in [('scenarios.csv',rows),('events.csv',events)]:
        with (out/name).open('x',encoding='utf-8-sig',newline='') as h:
            w=csv.DictWriter(h,fieldnames=list(dict.fromkeys(k for r in data for k in r)));w.writeheader();w.writerows(data)
    print(json.dumps(dict(scenarios=len(rows),prior_tests=len(old),events=len(events),journal_rows=sum(x['journal_rows'] for x in rows),unresolved=sum(x['open_legs']>0 for x in rows)),indent=2))
if __name__=='__main__':main()
