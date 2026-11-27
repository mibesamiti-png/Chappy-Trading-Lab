"""R59: minimal synthetic integration; no market feeds or orders. Python 3.10+."""
import argparse, hashlib, importlib.util, json, sys, copy
from pathlib import Path
from dataclasses import asdict, replace
from fractions import Fraction
ROOT=Path(__file__).parent
PINS={
 'review':('Decision_Review','44e204330a9c363f8985e75e0036034a61312793f79b82e59e46cf9292463d88'),
 'stress':('Portfolio_Stress','29524882a9e0cd87fbf634b3b486ae5a27b80c5242b50738aa94ae6960333d2f'),
 'recovery':('Recovery_Study','17b61371aef926a5ddea0fd894059f90d6d2b3022c252a12057c5d3edd07d70b')}
def load(key):
 name,sha=PINS[key]; p=ROOT/f'Chappy_Trading_{name}_v0.1.py'
 if hashlib.sha256(p.read_bytes()).hexdigest()!=sha:raise RuntimeError('dependency hash mismatch '+key)
 spec=importlib.util.spec_from_file_location('r59_'+key,p);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
review,stress,recovery=(load(k) for k in PINS)
j48=review.j48; r47=j48.r47; r51=stress.r
CAP=100_000_000 # hundredths of yen; R47 uses yen
SYMBOLS='ABC'; BPS=10; BUDGET=500_000; STRESS_CAP=1_500_000

def need(x,msg):
 if not x:raise ValueError(msg)
def obs(symbol,t,close=1000,ask=1000,bid=999,depth=100):
 return [{'id':f'{symbol}-{t}-{f}','symbol':symbol,'evidence':asdict(r47.Evidence(f,v,t,t,'synthetic',f'{symbol}-{t}')),'supersedes':None} for f,v in {'close':close,'ask':ask,'bid':bid,'ask_depth':depth,'bid_depth':100,'volume':100}.items()]
def hypothesis(t,cash):
 return r47.Plan(r47.Predicate('close','>=',1000),r47.Predicate('close','<=',990),r47.Predicate('close','>=',1020),t+30,100,CAP//100,cash//100,50,BPS,1)
def account(t,cash,held,terminal=None):return recovery.snapshot(t,cash,dict(held),terminal=terminal)
def tick(g,t,cash,held,terminal=None,changes=None,approval=None,exit_requested=()):
 a=account(t,cash,held,terminal);return g.tick(t,recovery.dep.feed(changes,t),a,copy.deepcopy(a),approval,exit_requested)

def allocate(j,g,health,t,cash,held,score,uncertainty,scenarios):
 # No caller-supplied gate, price, stop or received time: derive from pinned decision evidence.
 need(g.last==t and health['at']==t and g.state==health['state'],'stale recovery state')
 need(g.account==recovery.digest(recovery.account_payload(account(t,cash,held,g.terminal))) or g.state!='NORMAL','account mismatch')
 need(set(held)==set(SYMBOLS) and all(v==0 for v in held.values()),'new allocation only')
 need(set(score)==set(uncertainty)==set(SYMBOLS),'score set')
 j48.Journal.restore(j.export(),j.head)
 quotes=[]; decisions={}; exclusions={}
 for s in SYMBOLS:
  p=hypothesis(t,cash); d=j.decide(t,f'D-{s}-{t}',s,p,set(r47.FIELDS));decisions[s]=d
  if health['routing'][s]['restart_gate']!='ELIGIBLE' or g.state!='NORMAL':exclusions[s]='RECOVERY_BLOCK';continue
  if d['gate']['gate']!='RESEARCH_ELIGIBLE':exclusions[s]='DECISION_BLOCK';continue
  _,rows=j._snapshot(s); _,v=r47.collect(rows,t,set(r47.FIELDS))
  # Additional adapter restriction: all required prices/depth must be observed in this tick.
  required=r47.BOOK|{'close'}
  if any(not any(e.field==f and e.event==e.received==t and e.value==v[f] for e in rows) for f in required):exclusions[s]='NOT_SAME_TICK';continue
  q=r51.Quote(s,v['ask'],p.refute.threshold-p.gap_yen,p.qty,score[s],t,available=v['ask_depth'],bid=v['bid'],bid_available=v['bid_depth'])
  need(r51.cost(q,BPS)==Fraction(d['gate']['risk']['cash_required'])*100,'cash unit mismatch')
  need(r51.risk(q,BPS,True)==Fraction(d['gate']['risk']['scenario_loss'])*100,'risk scenario mismatch')
  quotes.append(q)
 sy={q.symbol for q in quotes};need(bool(scenarios) and all(set(v)==set(SYMBOLS) for v in scenarios.values()),'scenario universe')
 result=stress.plan(quotes,t,cash,BUDGET,{k:{s:v[s] for s in sy} for k,v in scenarios.items()},{s:uncertainty[s] for s in sy},STRESS_CAP,BPS,robust=True)
 plan={'at':t,'journal_head':j.head,'recovery':copy.deepcopy(health),'decisions':{s:d['gate']['gate'] for s,d in decisions.items()},'exclusions':exclusions,'quotes':[asdict(q) for q in quotes],'score':dict(score),'uncertainty':dict(uncertainty),'scenarios':copy.deepcopy(scenarios),'allocation':result['chosen'],'execution_proven':False}
 return plan,j48.digest(plan)

def fixture(fault=None,depth=100,stale=False):
 g=recovery.Gate();j=j48.Journal();held=dict.fromkeys(SYMBOLS,0);cash=CAP; timeline=[]
 for t in (100,105,110):timeline.append(tick(g,t,cash,held))
 timeline.append(tick(g,115,cash,held,approval=timeline[-1]['ready_token'],changes={fault:'FAILED'} if fault else None))
 for s in SYMBOLS:j.observations(115,obs(s,114 if stale else 115,depth=depth if s=='A' else 100))
 scores={'A':1200,'B':1100,'C':900};u={'A':850,'B':100,'C':100};sc={'sector':{'A':900,'B':900,'C':990},'market':dict.fromkeys(SYMBOLS,950)}
 plan,sha=allocate(j,g,timeline[-1],115,cash,held,scores,u,sc)
 return g,j,plan,sha,timeline

def example():
 g,j,p,sha,tl=fixture();need(j48.digest(p)==sha,'plan digest')
 held={s:100 if s in p['allocation']['held'] else 0 for s in SYMBOLS};cash=p['allocation']['cash']
 fills=[{'symbol':q['symbol'],'qty':q['qty'],'price':q['price'],'at':115,'type':'synthetic_entry_assumption'} for q in p['quotes'] if q['symbol'] in p['allocation']['held']]
 tl.append(tick(g,120,cash,held,changes={'news':'FAILED'},exit_requested=tuple(s for s in SYMBOLS if held[s])))
 for s,px in [('A',1021),('B',1022),('C',989)]:j.observations(120,[obs(s,120,close=px)[0]])
 # Outcomes independent of allocation. Exit only when R58's route allows it, using separate artificial bids.
 exit_prices={'A':1020,'B':1021,'C':988}; terminals={}
 for s in SYMBOLS:
  if not held[s]:continue
  need(tl[-1]['routing'][s]['exit']=='SIMULATED_EXIT_ELIGIBLE','exit unavailable')
  px=exit_prices[s];q=held[s];cash+=px*q*100-r51.fee(px,q,BPS);fills.append({'symbol':s,'qty':q,'price':px,'at':120,'type':'synthetic_exit_assumption'});held[s]=0;terminals['X-'+s]='FILLED'
 for t in (125,130,135):tl.append(tick(g,t,cash,held,terminals))
 tl.append(tick(g,140,cash,held,terminals,approval=tl[-1]['ready_token']))
 audit=review.audit(j.export(),j.head,145)
 return {'scope':'synthetic only, assumed fills, A/B/C strategy-symbol mapping','plan':p,'plan_sha':sha,'journal':j.export(),'journal_head':j.head,'audit':audit,'timeline':tl,'assumed_fills':fills,'terminal_cash_cents':cash,'pnl_cents':cash-CAP,'execution_proven':False,'live_adoption':False}

def self_test():
 tests=[]
 def ck(n,a,b=True):
  if a!=b:raise AssertionError((n,a,b))
  tests.append({'name':n,'pass':True})
 e=example();p=e['plan'];ck('selected B C',p['allocation']['held'],['B','C']);ck('nominal eligible all',p['decisions'],dict.fromkeys(SYMBOLS,'RESEARCH_ELIGIBLE'));ck('plan hash',j48.digest(p),e['plan_sha']);ck('journal semantic replay',j48.Journal.restore(e['journal'],e['journal_head']).head,e['journal_head']);ck('timeline',[x['state'] for x in e['timeline']],['RECONCILED','SHADOW','READY','NORMAL','HALTED','RECONCILED','SHADOW','READY','NORMAL']);ck('all blocked at fault',all(x['restart_gate']=='BLOCKED' for x in e['timeline'][4]['routing'].values()));ck('exit during fault',[x['symbol'] for x in e['assumed_fills'] if 'exit' in x['type']],['B','C']);ck('selected cash',p['allocation']['cash'],79_980_000);ck('scenario risk',p['allocation']['stop_risk'],259_780);ck('stress cap',p['allocation']['worst_loss']<=STRESS_CAP);ck('pnl',e['pnl_cents'],49_910);ck('three hypotheses incl unselected',e['audit']['summary']['eligible'],3);ck('unselected hypothesis confirmed',e['audit']['rows'][0]['observed_outcome'],'CONFIRMED_OBSERVED');ck('no A assumed fill',all(x['symbol']!='A' for x in e['assumed_fills']));ck('no execution proven',e['execution_proven'],False);ck('no adoption',e['live_adoption'],False)
 for root in recovery.dep.ROOTS:
  _,_,plan,_,_=fixture(fault=root);ck('fault blocks '+root,plan['allocation']['held'],[])
 _,_,plan,_,_=fixture(depth=0);ck('depth gate rejects A',plan['exclusions']['A'],'DECISION_BLOCK');ck('depth excluded quote',all(x['symbol']!='A' for x in plan['quotes']));_,_,plan,_,_=fixture(stale=True);ck('prior tick evidence rejected',plan['allocation']['held'],[]);ck('prior tick cause',set(plan['exclusions'].values()),{'NOT_SAME_TICK'})
 changed=copy.deepcopy(p);changed['allocation']['held']=['A'];ck('tamper detectable',j48.digest(changed)!=e['plan_sha']);
 # Independent arithmetic, yen fractions, converted once.
 exact=Fraction(CAP,100)
 for f in e['assumed_fills']:
  gross=f['price']*f['qty'];fee=Fraction(gross*BPS,10000);exact+=(-gross-fee if 'entry' in f['type'] else gross-fee)
 ck('independent ledger',exact*100,e['terminal_cash_cents'])
 return {'test_count':len(tests),'tests':tests}
if __name__=='__main__':
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--self-test',action='store_true');g.add_argument('--example',action='store_true');a=ap.parse_args();print(json.dumps(self_test() if a.self_test else example(),sort_keys=True,indent=2))
