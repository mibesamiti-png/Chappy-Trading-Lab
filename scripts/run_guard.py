"""Fail-closed, persistent single-writer guard. No network or market-data access."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import pathlib
import sqlite3
from contextlib import contextmanager

class Busy(RuntimeError): pass
class LostLease(RuntimeError): pass

def utcnow(): return dt.datetime.now(dt.timezone.utc)

class RunGuard:
    def __init__(self, path):
        self.path=pathlib.Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS guard (id INTEGER PRIMARY KEY CHECK(id=1),owner TEXT,status TEXT,deadline TEXT,checkpoint TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS completed (task TEXT,revision TEXT,owner TEXT,finished TEXT,PRIMARY KEY(task,revision))')
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        try: yield c
        finally: c.close()
    def acquire(self,owner,budget_minutes=40):
        if not owner or not 0<budget_minutes<=240: raise ValueError('invalid owner/budget')
        deadline=(utcnow()+dt.timedelta(minutes=budget_minutes)).isoformat()
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            current=c.execute('SELECT owner,status FROM guard WHERE id=1').fetchone()
            if current and current[1]=='active':
                c.rollback();raise Busy('active or abandoned run requires explicit stopped-writer reconciliation')
            c.execute("INSERT INTO guard VALUES(1,?,'active',?,?) ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,status=excluded.status,deadline=excluded.deadline,checkpoint=excluded.checkpoint",(owner,deadline,json.dumps({'stage':'acquired'})))
            c.commit()
        return deadline
    def live(self,owner):
        with self.connect() as c: row=c.execute('SELECT owner,status,deadline FROM guard WHERE id=1').fetchone()
        if not row or row[:2]!=(owner,'active') or dt.datetime.fromisoformat(row[2])<=utcnow():raise LostLease('writer mismatch, released run or exhausted budget')
        return True
    def checkpoint(self,owner,value):
        encoded=json.dumps(value,ensure_ascii=False)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT owner,status,deadline FROM guard WHERE id=1').fetchone()
            if not row or row[:2]!=(owner,'active') or dt.datetime.fromisoformat(row[2])<=utcnow():c.rollback();raise LostLease('checkpoint rejected')
            c.execute('UPDATE guard SET checkpoint=? WHERE id=1',(encoded,));c.commit()
    def release(self,owner):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT owner,status FROM guard WHERE id=1').fetchone()
            if not row or row!=(owner,'active'):c.rollback();raise LostLease('release rejected')
            c.execute("UPDATE guard SET status='released' WHERE id=1");c.commit()
    def inspect(self):
        with self.connect() as c:row=c.execute('SELECT owner,status,deadline,checkpoint FROM guard WHERE id=1').fetchone()
        if row is None:return None
        return dict(owner=row[0],status=row[1],deadline=row[2],checkpoint=json.loads(row[3]))
    def completed(self,task,revision):
        with self.connect() as c:return c.execute('SELECT 1 FROM completed WHERE task=? AND revision=?',(task,revision)).fetchone() is not None
    def finish_task(self,owner,task,revision):
        if not task or not revision:raise ValueError('task and revision required')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT owner,status,deadline FROM guard WHERE id=1').fetchone()
            if not row or row[:2]!=(owner,'active') or dt.datetime.fromisoformat(row[2])<=utcnow():c.rollback();raise LostLease('task checkpoint rejected')
            cursor=c.execute('INSERT OR IGNORE INTO completed VALUES(?,?,?,?)',(task,revision,owner,utcnow().isoformat()));created=cursor.rowcount==1;c.commit();return created

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['acquire','live','release','inspect']);p.add_argument('--db',required=True);p.add_argument('--owner');p.add_argument('--budget-minutes',type=float,default=40);a=p.parse_args();g=RunGuard(a.db)
    try:
        if a.action=='acquire':g.acquire(a.owner,a.budget_minutes)
        elif a.action=='live':g.live(a.owner)
        elif a.action=='release':g.release(a.owner)
        print(json.dumps({'status':'ok','guard':g.inspect()}))
    except (Busy,LostLease,ValueError):
        print(json.dumps({'status':'blocked'}));raise SystemExit(3)
if __name__=='__main__':main()
