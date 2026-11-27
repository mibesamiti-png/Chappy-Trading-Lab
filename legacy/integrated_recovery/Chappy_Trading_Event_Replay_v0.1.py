"""R60: synthetic event replay; not a broker or execution simulator. Python 3.10+."""
import argparse, copy, hashlib, importlib.util, json, sys
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).parent
P=ROOT/'Chappy_Trading_Integration_Study_v0.1.py'
PIN='b7065be266b27dfd7c923634325e23d1cd61e60b334b95293d06991ce0ceb144'
if hashlib.sha256(P.read_bytes()).hexdigest()!=PIN: raise RuntimeError('R59 mismatch')
spec=importlib.util.spec_from_file_location('r59',P);r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)
need=r.need; digest=r.j48.digest; Z='0'*64

def replay(events):
 g=r.recovery.Gate(); j=r.j48.Journal(); cash=r.CAP; held=dict.fromkeys(r.SYMBOLS,0); pending={}; terminal={}; plans={}; used_entries=set(); fills=[]; states=[]; last=-1; ids=set(); health=None
 for e in events:
  need(set(e)=={'id','at','kind','data'},'event shape'); i,t,k,d=(e[x] for x in ('id','at','kind','data'))
  need(type(i) is str and i and i not in ids,'duplicate event');need(type(t) is int and t>=last and t>=0,'event order');ids.add(i);last=t
  if k=='tick':
   need(set(d)=={'changes','external','approval','exit_requested'},'tick shape')
   local=r.recovery.snapshot(t,cash,copy.deepcopy(held),sorted(pending),copy.deepcopy(terminal));health=g.tick(t,r.recovery.dep.feed(d['changes'],t),local,d['external'],d['approval'],tuple(d['exit_requested']))
  elif k=='observe':
   need(set(d)=={'rows'},'observe shape');j.observations(t,d['rows'])
  elif k=='allocate':
   need(set(d)=={'scores','uncertainty','scenarios'},'allocate shape');need(health is not None and g.state=='NORMAL' and g.last==t and not pending and not plans,'allocation gate')
   p,h=r.allocate(j,g,health,t,cash,held,d['scores'],d['uncertainty'],d['scenarios']);plans[t]=(p,h)
  elif k=='intent':
   need(set(d)=={'order','symbol','side','qty','plan_sha'},'intent shape');o,s,side,q,h=(d[x] for x in ('order','symbol','side','qty','plan_sha'))
   need(type(o) is str and o and o not in pending and o not in terminal and s in held and type(q) is int and q>0 and q%100==0,'intent identity')
   need(health is not None and g.last==t,'intent tick');need(not any(v['symbol']==s for v in pending.values()),'symbol already pending')
   if side=='BUY':
    need(g.state=='NORMAL' and t in plans and h==plans[t][1],'entry plan');p=plans[t][0];need(j.head==p['journal_head'],'plan evidence changed');need(s in p['allocation']['held'] and held[s]==0,'not selected');quote=next(x for x in p['quotes'] if x['symbol']==s);need(q==quote['qty'],'quantity mismatch');limit=quote['price']
    reserve=sum(v['limit']*v['qty']*100+r.r51.fee(v['limit'],v['qty'],r.BPS) for v in pending.values() if v['side']=='BUY');need(reserve+limit*q*100+r.r51.fee(limit,q,r.BPS)<=cash,'cash reservation')
    need(s not in used_entries,'entry reused');used_entries.add(s)
   elif side=='SELL':
    need(h is None and q==held[s] and health['routing'][s]['exit']=='SIMULATED_EXIT_ELIGIBLE','exit gate');limit=None
   else:raise ValueError('side')
   pending[o]={'symbol':s,'side':side,'qty':q,'limit':limit,'at':t,'plan_sha':h}
  elif k=='fill':
   need(set(d)=={'order','evidence_id'},'fill shape');o=d['order'];need(o in pending,'unknown/terminal fill');v=pending[o];s,side,q=(v[x] for x in ('symbol','side','qty'))
   need(g.last==t and health is not None,'fill tick');need(t>=v['at'],'fill before intent')
   # A fill is only an artificial assumed resolution. No order is sent. Even a previously
   # pending entry may resolve after HALTED; blocking new intents must not erase it.
   _,rows=j._snapshot(s);field='ask' if side=='BUY' else 'bid';depth='ask_depth' if side=='BUY' else 'bid_depth'
   _,vals=r.r47.collect(rows,t,set(r.r47.FIELDS));need(r.r47.BOOK<=vals.keys() and vals['ask']>vals['bid'],'quote unavailable')
   snap=[x for x in rows if x.field==field and x.event==x.received==t and x.value==vals[field]]
   need(len(snap)==1 and any(x.field==depth and x.event==x.received==t and x.snapshot==snap[0].snapshot and x.source==snap[0].source and x.value==vals[depth] for x in rows),'quote not same tick')
   # Bind the active ID to the exact price observation, not a caller-defined label.
   active,_=j._snapshot(s);eid=d['evidence_id'];need(eid in active,'inactive evidence id')
   item=j._obs[eid];need(r.r47.Evidence(**item['evidence'])==snap[0],'wrong quote evidence')
   px=vals[field];need(type(px) is int and px>0 and vals[depth]>=q,'insufficient quote depth');fee=r.r51.fee(px,q,r.BPS);gross=px*q*100
   if side=='BUY':need(px<=v['limit'] and held[s]==0 and cash>=gross+fee,'entry fill constraints');cash-=gross+fee;held[s]+=q
   else:need(held[s]>=q,'oversell');cash+=gross-fee;held[s]-=q
   fills.append({'order':o,'symbol':s,'side':side,'qty':q,'price':px,'fee_cents':fee,'at':t,'evidence_id':d['evidence_id'],'plan_sha':v['plan_sha']});del pending[o];terminal[o]='FILLED'
  elif k=='cancel':
   need(set(d)=={'order'} and d['order'] in pending,'unknown cancel');del pending[d['order']];terminal[d['order']]='CANCELLED'
  else:raise ValueError('event kind')
  states.append({'id':i,'at':t,'cash':cash,'held':dict(held),'pending':sorted(pending),'terminal':dict(terminal),'gate':g.state,'journal_head':j.head})
 return {'states':states,'fills':fills,'cash_cents':cash,'held':held,'pending':sorted(pending),'terminal':terminal,'gate':g.state,'journal':j.export(),'journal_head':j.head,'plans':{str(t):h for t,(p,h) in plans.items()},'execution_proven':False,'live_adoption':False}

def seal(events):
 head=Z;records=[];state=replay(events)
 for e,s in zip(events,state['states']):
  body={'prev':head,'event':e,'state_sha':digest(s)};head=digest(body);records.append({**body,'hash':head})
 return {'head':head,'records':records,'result':state}
def restore(records,expected):
 events=[x['event'] for x in records];v=seal(events);need(v['records']==records and v['head']==expected,'chain or replay mismatch');return v

def fixture(cancel=False):
 ev=[]
 def add(t,k,**d):ev.append({'id':str(len(ev)+1),'at':t,'kind':k,'data':d})
 def tick(t,cash,held,terminal=None,pending=(),changes=None,approval=None,exit_requested=()):add(t,'tick',changes=changes,external=copy.deepcopy(r.recovery.snapshot(t,cash,held,pending,terminal)),approval=approval,exit_requested=list(exit_requested))
 empty=dict.fromkeys('ABC',0);full={'A':0,'B':100,'C':100};b={'A':0,'B':100,'C':0}
 for t in (100,105,110):tick(t,r.CAP,empty)
 token={'epoch':0,'ready_at':110,'account_sha':r.recovery.digest(r.recovery.account_payload(r.recovery.snapshot(110,r.CAP,empty)))}
 tick(115,r.CAP,empty,approval=token)
 for s in 'ABC':add(115,'observe',rows=r.obs(s,115))
 add(115,'allocate',scores={'A':1200,'B':1100,'C':900},uncertainty={'A':850,'B':100,'C':100},scenarios={'sector':{'A':900,'B':900,'C':990},'market':dict.fromkeys('ABC',950)})
 h=replay(ev)['plans']['115']
 for s in 'BC':add(115,'intent',order='E-'+s,symbol=s,side='BUY',qty=100,plan_sha=h)
 add(115,'fill',order='E-B',evidence_id='B-115-ask')
 if not cancel:add(115,'fill',order='E-C',evidence_id='C-115-ask')
 initial=89990000 if cancel else 79980000;positions=b if cancel else full;term={'E-B':'FILLED'} if cancel else {'E-B':'FILLED','E-C':'FILLED'}
 tick(120,initial,positions,term,['E-C'] if cancel else [],{'news':'FAILED'},exit_requested=['B'] if cancel else ['B','C'])
 if cancel:add(120,'cancel',order='E-C');term['E-C']='CANCELLED'
 for s,p in [('B',1021),('C',988)]:
  add(120,'observe',rows=r.obs(s,120,close=p+1,ask=p+1,bid=p))
  if s=='C' and cancel:continue
  add(120,'intent',order='X-'+s,symbol=s,side='SELL',qty=100,plan_sha=None);add(120,'fill',order='X-'+s,evidence_id=f'{s}-120-bid');term['X-'+s]='FILLED'
 final=100189790 if cancel else 100049910
 for t in (125,130,135):tick(t,final,empty,copy.deepcopy(term))
 token={'epoch':1,'ready_at':135,'account_sha':r.recovery.digest(r.recovery.account_payload(r.recovery.snapshot(135,final,empty,terminal=term)))}
 tick(140,final,empty,copy.deepcopy(term),approval=token)
 return ev

def self_test():
 tests=[]
 def ck(n,a,b=True):
  if a!=b:raise AssertionError((n,a,b))
  tests.append({'name':n,'pass':True})
 def reject(n,fn):
  try:fn()
  except (ValueError,KeyError,TypeError):ck(n,True)
  else:ck(n,False)
 for cancel in (False,True):
  ev=fixture(cancel);v=seal(ev);res=v['result'];label=str(cancel);ck(label+' replay',restore(v['records'],v['head']),v);ck(label+' pnl',res['cash_cents'],100189790 if cancel else 100049910);ck(label+' gate',res['gate'],'NORMAL');ck(label+' flat',res['held'],dict.fromkeys('ABC',0));ck(label+' pending',res['pending'],[])
  cash=Fraction(r.CAP,100)
  for f in res['fills']:
   gross=f['qty']*f['price'];fee=Fraction(gross*r.BPS,10000);cash+=(-gross if f['side']=='BUY' else gross)-fee
  ck(label+' independent cash',cash*100,res['cash_cents'])
  for i in range(1,len(ev)+1):ck(label+' prefix '+str(i),replay(ev[:i])['states'][-1],res['states'][i-1])
  reject(label+' truncation',lambda:restore(v['records'][:-1],v['head']))
  reject(label+' duplicate',lambda:replay(ev+[ev[-1]]))
  changed=copy.deepcopy(v['records']);changed[-1]['state_sha']='bad';reject(label+' state tamper',lambda:restore(changed,v['head']))
 ev=fixture();idx=next(i for i,e in enumerate(ev) if e['kind']=='fill'); bad=copy.deepcopy(ev);bad[idx]['data']['evidence_id']='A-115-ask';reject('wrong evidence',lambda:replay(bad));bad=copy.deepcopy(ev);bad[idx]['data']['order']='missing';reject('missing intent',lambda:replay(bad));bad=copy.deepcopy(ev);bad[idx]['at']=114;reject('time reversal',lambda:replay(bad));bad=copy.deepcopy(ev);bad.insert(idx+1,{**bad[idx],'id':'duplicate-fill'});reject('double fill',lambda:replay(bad));bad=copy.deepcopy(ev);bad[idx]['data']['evidence_id']='B-120-ask';reject('future quote',lambda:replay(bad));bad=copy.deepcopy(ev);bad[-1]['data']['external']['cash']+=1;ck('external mismatch stops',replay(bad)['gate'],'HALTED');ck('no execution',seal(ev)['result']['execution_proven'],False)
 # Reusing a canceled entry or silently replacing evidence after approval is prohibited.
 at=next(i for i,e in enumerate(ev) if e['kind']=='intent');prior=ev[:at];intent=copy.deepcopy(ev[at]);bad=prior+[intent,{'id':'cancel','at':115,'kind':'cancel','data':{'order':intent['data']['order']}},{**copy.deepcopy(intent),'id':'retry','data':{**intent['data'],'order':'retry'}}];reject('cancelled plan reused',lambda:replay(bad))
 extra=r.obs('A',115)[0];extra['id']='additional';bad=prior+[{'id':'extra','at':115,'kind':'observe','data':{'rows':[extra]}},intent];reject('plan evidence changed',lambda:replay(bad))
 bad=copy.deepcopy(ev);bad[idx]['data']['evidence_id']='B-115-bid';reject('wrong field id',lambda:replay(bad))
 bad=copy.deepcopy(ev);oi=next(i for i,e in enumerate(bad) if e['kind']=='observe' and e['at']==120);next(x for x in bad[oi]['data']['rows'] if x['evidence']['field']=='bid_depth')['evidence']['value']=0;reject('exit depth absent',lambda:replay(bad))
 return {'test_count':len(tests),'tests':tests}
if __name__=='__main__':
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=p.parse_args();print(json.dumps(self_test() if a.self_test else {'normal':seal(fixture()),'pending_cancel':seal(fixture(True))},sort_keys=True,indent=2))
