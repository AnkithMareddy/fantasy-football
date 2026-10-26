#!/usr/bin/env python3
"""Build the report text from pipeline output alone — no model, no judgement, no prompts.

Why this exists: the texted report has only ever been produced by the scheduled Claude
routine, and that routine runs in a permission mode where its first Bash call waits for a
human to click Approve. Twice now (2026-10-18 and 2026-10-23) it froze on that click at
11 PM, sat for days, and because the scheduler will not start a run while one is in
flight it also swallowed every run behind it — including the Sunday morning start/sit,
which is the one text that has to arrive before kickoff.

So this is the floor, not the ceiling. It writes a factual report from files update.sh
already produced. It cannot research injuries, read the news, or write the paragraph that
explains what a result means — the Claude routine still does that better, and when it
runs it supersedes this. But this one cannot be blocked by a prompt, which means a text
always goes out.

Modes:
  preview  — pre-kickoff: the start/sit call, the lines that moved, who to watch
  recap    — post-slate: what the matchup did, where it leaves the standings

Usage:  python3 autoreport.py preview|recap  [> outfile]
"""
import json, os, sys, datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
ME = 'uaintgotjuicehoeido'


def load(p, default=None):
    try:
        return json.load(open(p))
    except Exception:
        return default


def read(p):
    try:
        return open(p).read()
    except Exception:
        return ''


def main(mode):
    week_state = load('state/week.json', {}) or {}
    standings = load('state/standings.json', {}) or {}
    cfg = load('state/league_config.json', {}) or {}
    wk = week_state.get('nfl_week')
    sched = (cfg.get('schedule') or {}).get(ME) or []
    opp = sched[wk - 1] if wk and len(sched) >= wk else None

    live = week_state.get('live') or {}
    cur = live.get(str(wk)) or live.get(wk) or {}
    mine, theirs = cur.get(ME), cur.get(opp)

    out = []
    stamp = datetime.datetime.now().strftime('%a %b %-d, %-I:%M %p')
    out.append(f"ShowMeYourTDs | Week {wk} | {'preview' if mode == 'preview' else 'recap'} | {stamp}")
    out.append("(Auto-report: built from the model's own output. No injury research in this one.)")
    out.append("")

    # ---- where the matchup stands -------------------------------------------------
    if opp and mine is not None and theirs is not None:
        detail = week_state.get('live_detail') or {}
        left_me = [r for r in detail.get(ME, []) if r.get('state') in ('todo', 'live')]
        left_opp = [r for r in detail.get(opp, []) if r.get('state') in ('todo', 'live')]
        out.append("MATCHUP")
        out.append(f"You {mine:.2f} - {theirs:.2f} {opp}")
        if left_me or left_opp:
            out.append(f"Still to play: you {len(left_me)}, them {len(left_opp)}.")
            for tag, rows in (("yours", left_me), ("theirs", left_opp)):
                for r in rows:
                    out.append(f"  {tag}: {r['name']} ({r['pos']}, {r['nfl']}) {r['pts']:.1f}")
            # a live win probability is the one genuinely useful number here
            try:
                import winprob as W
                import gamelog as GL   # noqa: F401  (kept for parity with the pipeline)
                PW = load('state/player_weeks.json', {}) or {}
                KO = load('state/kickoffs.json', {}) or {}
                P = load('sleeper/players.json', {}) or {}
                ppg = W.blended_ppg(W.ppg_index(), PW, KO, P)
                todo = lambda rows: [(ppg.get(str(r['pid']), (0.0, r['pos']))[0], r['pos']) for r in rows]
                wp = W.win_prob(mine, todo(left_me), theirs, todo(left_opp), n=20000)
                out.append(f"Win probability: {wp*100:.1f}%")
            except Exception as e:
                out.append(f"(win probability unavailable: {e})")
        else:
            verdict = "WON" if mine > theirs else ("LOST" if mine < theirs else "TIED")
            out.append(f"Final — you {verdict}.")
        out.append("")

    # ---- the start/sit call, verbatim from the model ------------------------------
    ss = read('state/latest_startsit.txt')
    if mode == 'preview' and ss.strip():
        out.append("START/SIT")
        for line in ss.splitlines():
            if line.strip():
                out.append(line.rstrip())
        out.append("")

    # ---- odds ----------------------------------------------------------------------
    odds = read('state/latest_odds.txt')
    if odds:
        rows = [l for l in odds.splitlines() if l.strip() and not l.startswith(('10,000', 'researched', 'TEAM', 'EXPECTED', '  '))]
        if rows:
            # Column order in latest_odds.txt is:
            #   TEAM  W-L  10-90%  PF  PLAYOFF  BYE  #1  FINAL  TITLE  SOS
            # so playoff is field 4 (carrying a +/- error term) and title is field 8.
            # Reading field 5 instead silently reported BYE odds as playoff odds.
            out.append("PLAYOFF / TITLE ODDS")
            for l in rows[:12]:
                parts = l.split()
                if len(parts) >= 9:
                    playoff = parts[4].split('±')[0]
                    mark = '  <- you' if parts[0] == ME else ''
                    out.append(f"  {parts[0]:<22} {playoff:>5}% playoff / {parts[8]:>5}% title{mark}")
            out.append("")

    # ---- standings -----------------------------------------------------------------
    if standings:
        out.append("STANDINGS")
        order = sorted(standings.items(), key=lambda kv: (-kv[1]['w'], -kv[1]['pf']))
        for i, (t, v) in enumerate(order, 1):
            mark = '  <- you' if t == ME else ''
            out.append(f"  {i:>2}. {t:<22} {v['w']}-{v['l']}  {v['pf']:.1f} PF{mark}")
        out.append("")

    # ---- waivers --------------------------------------------------------------------
    wv = read('state/latest_waivers.txt')
    if wv.strip():
        out.append("WAIVERS / FAAB")
        for line in wv.splitlines()[:18]:
            if line.strip():
                out.append(line.rstrip())
        out.append("")

    out.append("Site: https://ankithmareddy.github.io/fantasy-football-hub/")
    return "\n".join(out)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'recap'
    if mode not in ('preview', 'recap'):
        raise SystemExit("usage: autoreport.py preview|recap")
    print(main(mode))
