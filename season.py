import os
import json, random, re, statistics
from collections import defaultdict

BYE = {"KC":5,"CAR":5,"MIA":6,"CIN":6,"DET":6,"MIN":6,"BUF":7,"LAC":7,"WAS":7,"JAX":7,
"NYG":8,"NO":8,"SF":8,"HOU":8,"TEN":9,"PIT":9,"DEN":10,"PHI":10,"CHI":10,"TB":10,
"NE":11,"CLE":11,"SEA":11,"GB":11,"ATL":11,"LAR":11,"IND":13,"NYJ":13,"LV":13,"BAL":13,
"DAL":14,"ARI":14}

def norm(x):
    x=x.lower().replace('.','').replace("'",'').replace('-',' ')
    x=re.sub(r'\b(jr|sr|ii|iii|iv)\b','',x); return ' '.join(x.split())

board={norm(p['name']):p for p in json.load(open('board.json'))}
ROLE={}
if os.path.exists('state/role_overrides.json'):
    ROLE={norm(k):(v['mult'] if isinstance(v,dict) else v)
          for k,v in json.load(open('state/role_overrides.json')).items() if not k.startswith('_')}
rost=json.load(open('sleeper/rosters.json'))
slot_name=json.load(open('sleeper/slot_name.json'))

# availability reads carried over from the draft model
AVAIL={"Christian McCaffrey":0.78,"Bijan Robinson":0.97,"Puka Nacua":0.80,"Ja'Marr Chase":0.91,
"Jonathan Taylor":0.90,"Derrick Henry":0.92,"De'Von Achane":0.85,"Breece Hall":0.88,
"Saquon Barkley":0.90,"Kyren Williams":0.92,"Rashee Rice":0.88,"Travis Kelce":0.90,
"Marvin Harrison Jr.":0.92,"Jahmyr Gibbs":0.93,"Ashton Jeanty":0.84,"Malik Nabers":0.76,
"MarShawn Lloyd":0.74,"George Kittle":0.74,"J.K. Dobbins":0.82,"Jonathon Brooks":0.80,
"Chuba Hubbard":0.82,"Cam Skattebo":0.85,"Josh Jacobs":0.38,"Zach Charbonnet":0.55,
"Sam LaPorta":0.87,"Jayden Reed":0.88,"DK Metcalf":0.88}
DEF_AVAIL={'QB':0.90,'RB':0.87,'WR':0.90,'TE':0.89,'K':0.98,'DEF':1.0}
BASE={'K':132.0,'DEF':112.0}
CV={'QB':0.28,'RB':0.42,'WR':0.40,'TE':0.40,'K':0.34,'DEF':0.55}   # WEEKLY variance
HARSH=1.65        # injury-hazard multiplier — "super harsh" setting

teams={}
for slot,plist in rost.items():
    nm=slot_name[slot]
    roster=[]
    for pl in plist:
        b=board.get(norm(pl['name']))
        pos=pl['pos']; tm=pl['team']
        if pos in ('K','DEF'):
            season=BASE[pos]
        elif b:
            season=b['proj']
        else:
            season={'QB':200,'RB':60,'WR':60,'TE':50}.get(pos,50)
        rm=ROLE.get(norm(pl['name']))
        if rm: season*=max(0.5,min(1.5,float(rm)))   # researched role change, clamped
        av=AVAIL.get(pl['name'], DEF_AVAIL.get(pos,0.9))
        # per-game injury hazard implied by availability, then made harsher
        miss=(1-av)*17
        hz=min(0.22, HARSH*miss/(3.2*17))
        roster.append({'n':pl['name'],'pos':pos,'tm':tm,'ppg':season/17.0,
                       'bye':BYE.get(tm,0),'hz':hz,
                       'ir':bool(pl.get('ir')),'inj':pl.get('inj'),'pid':pl.get('pid')})
    teams[nm]=roster

SCHED_RAW="""J2Money|joshsandorra,Ulyssesbo,zachschumann,raymondfeltons,uaintgotjuicehoeido,ryancrabbe,arabdhab,Gujju8,ak81,kisiluv,KamarasNuts,Ulyssesbo,zachschumann,joshsandorra
joshsandorra|J2Money,zachschumann,Ulyssesbo,Gujju8,ryancrabbe,raymondfeltons,ak81,uaintgotjuicehoeido,KamarasNuts,arabdhab,kisiluv,zachschumann,Ulyssesbo,J2Money
zachschumann|Ulyssesbo,joshsandorra,J2Money,KamarasNuts,kisiluv,arabdhab,ryancrabbe,ak81,Gujju8,raymondfeltons,uaintgotjuicehoeido,joshsandorra,J2Money,Ulyssesbo
Ulyssesbo|zachschumann,J2Money,joshsandorra,ryancrabbe,ak81,KamarasNuts,kisiluv,raymondfeltons,uaintgotjuicehoeido,Gujju8,arabdhab,J2Money,joshsandorra,zachschumann
ak81|raymondfeltons,kisiluv,KamarasNuts,arabdhab,Ulyssesbo,uaintgotjuicehoeido,joshsandorra,zachschumann,J2Money,ryancrabbe,Gujju8,kisiluv,KamarasNuts,raymondfeltons
raymondfeltons|ak81,KamarasNuts,kisiluv,J2Money,Gujju8,joshsandorra,uaintgotjuicehoeido,Ulyssesbo,arabdhab,zachschumann,ryancrabbe,KamarasNuts,kisiluv,ak81
kisiluv|KamarasNuts,ak81,raymondfeltons,uaintgotjuicehoeido,zachschumann,Gujju8,Ulyssesbo,arabdhab,ryancrabbe,J2Money,joshsandorra,ak81,raymondfeltons,KamarasNuts
KamarasNuts|kisiluv,raymondfeltons,ak81,zachschumann,arabdhab,Ulyssesbo,Gujju8,ryancrabbe,joshsandorra,uaintgotjuicehoeido,J2Money,raymondfeltons,ak81,kisiluv
arabdhab|Gujju8,ryancrabbe,uaintgotjuicehoeido,ak81,KamarasNuts,zachschumann,J2Money,kisiluv,raymondfeltons,joshsandorra,Ulyssesbo,uaintgotjuicehoeido,ryancrabbe,Gujju8
Gujju8|arabdhab,uaintgotjuicehoeido,ryancrabbe,joshsandorra,raymondfeltons,kisiluv,KamarasNuts,J2Money,zachschumann,Ulyssesbo,ak81,ryancrabbe,uaintgotjuicehoeido,arabdhab
uaintgotjuicehoeido|ryancrabbe,Gujju8,arabdhab,kisiluv,J2Money,ak81,raymondfeltons,joshsandorra,Ulyssesbo,KamarasNuts,zachschumann,arabdhab,Gujju8,ryancrabbe
ryancrabbe|uaintgotjuicehoeido,arabdhab,Gujju8,Ulyssesbo,joshsandorra,J2Money,zachschumann,KamarasNuts,kisiluv,ak81,raymondfeltons,Gujju8,arabdhab,uaintgotjuicehoeido"""
SCHED={}
for line in SCHED_RAW.strip().split('\n'):
    t,opps=line.split('|'); SCHED[t]=opps.split(',')
assert all(len(v)==14 for v in SCHED.values())
for t,opps in SCHED.items():
    for w,o in enumerate(opps):
        assert SCHED[o][w]==t, f"schedule mismatch wk{w+1} {t} vs {o}"
print("schedule verified symmetric: 12 teams x 14 weeks")
NAMES=list(SCHED.keys())
json.dump({'teams':{k:[{kk:vv for kk,vv in p.items()} for p in v] for k,v in teams.items()},
           'sched':SCHED}, open('season_input.json','w'))
print("teams built:", len(teams), "| players:", sum(len(v) for v in teams.values()))
for n in NAMES:
    tot=sum(p['ppg'] for p in teams[n])
    print(f"  {n:<22} roster ppg-sum {tot:6.1f}")
