#!/usr/bin/env python3
"""Season simulator.
- Completed fantasy weeks use REAL scores (state/actuals.json)
- The in-progress week uses real points for starters who already played + simulation for the rest
- Remaining weeks are simulated with a deliberately harsh injury model
- Known injuries use researched return weeks (state/injury_overrides.json), else a generic rule
Writes season_out.json. SIMS env var sets the number of seasons (default 10000)."""
import json, os, random, re, math
from collections import defaultdict

os.chdir(os.path.dirname(os.path.abspath(__file__)))
N = int(os.environ.get('SIMS', '10000'))
D = json.load(open('season_input.json')); teams = D['teams']; SCHED = D['sched']
NAMES = list(SCHED.keys())

def norm(x):
    x = (x or '').lower().replace('.', '').replace("'", '').replace('-', ' ')
    x = re.sub(r'\b(jr|sr|ii|iii|iv)\b', '', x); return ' '.join(x.split())

ACT = {}
if os.path.exists('state/actuals.json'):
    ACT = {int(k): v for k, v in json.load(open('state/actuals.json')).items()}
SIM_WEEKS = [w for w in range(1, 15) if w not in ACT]
FIRST_SIM = SIM_WEEKS[0] if SIM_WEEKS else 15

LIVE = {}; PLAYED_TEAMS = set()
if os.path.exists('state/week.json'):
    wj = json.load(open('state/week.json'))
    if wj.get('live_detail') and int(wj.get('nfl_week', 0)) == FIRST_SIM:
        LIVE = wj['live_detail']; PLAYED_TEAMS = set(wj.get('played_teams', []))

OVR = {}
if os.path.exists('state/injury_overrides.json'):
    OVR = {norm(k): v for k, v in json.load(open('state/injury_overrides.json')).items() if not k.startswith('_')}

# realistic week-to-week variation (coefficient of variation) per position
CV = {'QB': 0.40, 'RB': 0.60, 'WR': 0.65, 'TE': 0.75, 'K': 0.50, 'DEF': 0.85}
SLOTS = [('QB', 1), ('RB', 2), ('WR', 2), ('TE', 1)]
PID = {t: {p.get('pid'): i for i, p in enumerate(teams[t]) if p.get('pid')} for t in NAMES}

# starting unavailability, in simulated weeks from FIRST_SIM
init_out = {t: {} for t in NAMES}; applied = []
for t in NAMES:
    for i, p in enumerate(teams[t]):
        o = OVR.get(norm(p['n']))
        if o and 'return_week' in o:
            wk = max(0, int(o['return_week']) - FIRST_SIM)
            if wk: init_out[t][i] = wk
            applied.append(f"{p['n']} ({t}) back wk{o['return_week']}")
            continue
        st = (p.get('inj') or '').upper()
        if p.get('ir') or st in ('IR', 'PUP', 'SUS', 'NA', 'COV'): init_out[t][i] = 4
        elif st in ('OUT', 'DOUBTFUL'): init_out[t][i] = 1

rnd = random.Random(20260907); gauss = rnd.gauss; rand = rnd.random

def dur():
    r = rand()
    if r < 0.42: return 1
    if r < 0.68: return 2
    if r < 0.82: return 3
    if r < 0.90: return 5
    if r < 0.96: return 8
    return 17

gamma = rnd.gammavariate

def draw(p):
    # gamma: never negative, mean preserved, right-skewed like real fantasy scoring (boom weeks)
    m = p['ppg']
    if m <= 0: return 0.0
    cv = CV.get(p['pos'], 0.65)
    return gamma(1.0 / (cv * cv), m * cv * cv)

def lineup(avail):
    # avail[pos] = [(projection, simulated points)]. Start by PROJECTION (decided before kickoff), score the draws.
    for k in avail: avail[k].sort(key=lambda x: -x[0])
    tot = 0.0; used = {}
    for pos, n in SLOTS:
        g = avail.get(pos, [])[:n]; tot += sum(v for _, v in g); used[pos] = len(g)
    flex = []
    for pos in ('RB', 'WR', 'TE'): flex += avail.get(pos, [])[used.get(pos, 0):]
    if flex: tot += max(flex, key=lambda x: x[0])[1]
    for pos in ('K', 'DEF'):
        if avail.get(pos): tot += avail[pos][0][1]
    return tot

SLOT_TYPES = ['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'K', 'DEF']

def fill(slots, avail):
    """Best lineup for the still-open slots from players whose games haven't started."""
    for k in avail: avail[k].sort(key=lambda x: -x[0])
    idx = defaultdict(int); tot = 0.0
    for s_ in slots:
        if s_ == 'FLEX': continue
        L = avail.get(s_, [])
        if idx[s_] < len(L): tot += L[idx[s_]][1]; idx[s_] += 1
    if 'FLEX' in slots:
        rest = []
        for pos in ('RB', 'WR', 'TE'): rest += avail.get(pos, [])[idx[pos]:]
        if rest: tot += max(rest, key=lambda x: x[0])[1]
    return tot

def playoff_score(t):
    avail = defaultdict(list)
    for p in teams[t]:
        if rand() > 0.93: continue
        avail[p['pos']].append((p['ppg'], draw(p)))
    return lineup(avail)

wk_sum = {t: [0.0] * 14 for t in NAMES}; wk_win = {t: [0] * 14 for t in NAMES}
W = {t: [] for t in NAMES}; PF = {t: 0.0 for t in NAMES}
po, bye, seed1, finals, title = (defaultdict(int) for _ in range(5))
missed_tot = defaultdict(float)

for s in range(N):
    out = {t: dict(init_out[t]) for t in NAMES}
    wins = {t: 0 for t in NAMES}; pf = {t: 0.0 for t in NAMES}
    wk = {t: [0.0] * 14 for t in NAMES}
    for w in range(1, 15):
        if w in ACT:
            for t in NAMES: wk[t][w - 1] = float(ACT[w].get(t, 0.0))
        else:
            for t in NAMES:
                R = teams[t]; o = out[t]; status = {}
                for i, p in enumerate(R):
                    if o.get(i, 0) > 0:
                        o[i] -= 1; missed_tot[(t, p['n'])] += 1; status[i] = 0
                    elif p['bye'] == w:
                        status[i] = 0
                    elif rand() < p['hz']:
                        o[i] = dur(); missed_tot[(t, p['n'])] += 1; status[i] = 0
                    else:
                        status[i] = 1
                if w == FIRST_SIM and t in LIVE:
                    # points already scored by starters are locked in
                    tot = 0.0; open_slots = list(SLOT_TYPES)
                    for stt in LIVE[t]:
                        if stt.get('played'):
                            tot += float(stt.get('pts') or 0)
                            sl = stt.get('slot')
                            if sl is not None and sl < len(SLOT_TYPES) and SLOT_TYPES[sl] in open_slots:
                                open_slots.remove(SLOT_TYPES[sl])
                    # managers fill the rest with their best healthy players who haven't played yet
                    avail = defaultdict(list)
                    for i, p in enumerate(R):
                        if status[i] and p.get('tm') not in PLAYED_TEAMS: avail[p['pos']].append((p['ppg'], draw(p)))
                    wk[t][w - 1] = tot + fill(open_slots, avail)
                else:
                    avail = defaultdict(list)
                    for i, p in enumerate(R):
                        if status[i]: avail[p['pos']].append((p['ppg'], draw(p)))
                    wk[t][w - 1] = lineup(avail)
        for t in NAMES:
            pf[t] += wk[t][w - 1]; wk_sum[t][w - 1] += wk[t][w - 1]
            if wk[t][w - 1] > wk[SCHED[t][w - 1]][w - 1]: wins[t] += 1; wk_win[t][w - 1] += 1
    for t in NAMES: W[t].append(wins[t]); PF[t] += pf[t]
    seeds = sorted(NAMES, key=lambda t: (-wins[t], -pf[t]))[:6]
    for t in seeds: po[t] += 1
    bye[seeds[0]] += 1; bye[seeds[1]] += 1; seed1[seeds[0]] += 1
    a = seeds[2] if playoff_score(seeds[2]) > playoff_score(seeds[5]) else seeds[5]
    b = seeds[3] if playoff_score(seeds[3]) > playoff_score(seeds[4]) else seeds[4]
    f1 = seeds[0] if playoff_score(seeds[0]) > playoff_score(b) else b
    f2 = seeds[1] if playoff_score(seeds[1]) > playoff_score(a) else a
    finals[f1] += 1; finals[f2] += 1
    title[f1 if playoff_score(f1) > playoff_score(f2) else f2] += 1

def q(p, L):
    L = sorted(L); return L[min(len(L) - 1, int(p * len(L)))]

season = {}
for t in NAMES:
    opp = [wk_sum[SCHED[t][w - 1]][w - 1] / N for w in SIM_WEEKS]
    p = po[t] / N
    season[t] = {'w': sum(W[t]) / N, 'w_p10': q(0.10, W[t]), 'w_p90': q(0.90, W[t]),
                 'pf': PF[t] / N, 'po': p, 'po_se': math.sqrt(p * (1 - p) / N),
                 'bye': bye[t] / N, 'seed1': seed1[t] / N, 'finals': finals[t] / N, 'title': title[t] / N,
                 'sos': (sum(opp) / len(opp)) if opp else None}
if SIM_WEEKS:
    avg = sum(v['sos'] for v in season.values()) / len(NAMES)
    for v in season.values(): v['sos_rel'] = v['sos'] - avg

json.dump({'meta': {'sims': N, 'actual_weeks': sorted(ACT), 'first_sim_week': FIRST_SIM,
                    'live_week_used': bool(LIVE), 'overrides_applied': applied},
           'weekly': {t: [{'mean': wk_sum[t][w] / N, 'winpct': wk_win[t][w] / N} for w in range(14)] for t in NAMES},
           'season': season,
           'games_missed': {f"{n} | {t}": g / N for (t, n), g in missed_tot.items() if g / N >= 1.0}},
          open('season_out.json', 'w'), indent=1)

print(f"{N:,} seasons | real scores locked: weeks {sorted(ACT) or 'none'} | "
      f"week {FIRST_SIM} {'uses live points already scored' if LIVE else 'fully simulated'}")
if applied: print("researched injury return weeks applied:", "; ".join(applied))
print(f"{'TEAM':<21}{'W-L':>9}{'10-90%':>8}{'PF':>6}{'PLAYOFF':>12}{'BYE':>5}{'#1':>5}{'FINAL':>6}{'TITLE':>6}{'SOS':>6}")
for t, v in sorted(season.items(), key=lambda kv: (-kv[1]['po'], -kv[1]['title'])):
    sos = f"{v.get('sos_rel', 0):+.1f}" if SIM_WEEKS else '-'
    print(f"{t:<21}{v['w']:>4.1f}-{14 - v['w']:<4.1f}{v['w_p10']:>4}-{v['w_p90']:<3}{v['pf']:>6.0f}"
          f"{v['po'] * 100:>6.1f}±{v['po_se'] * 100:.1f}{v['bye'] * 100:>5.0f}{v['seed1'] * 100:>5.0f}"
          f"{v['finals'] * 100:>6.0f}{v['title'] * 100:>6.1f}{sos:>6}")
print("\nEXPECTED GAMES MISSED (harsh model, >=2)")
gm = sorted(((g / N, n, t) for (t, n), g in missed_tot.items() if g / N >= 2), reverse=True)
for g, n, t in gm[:20]: print(f"  {n:<24}{t:<22}{g:.1f}")
