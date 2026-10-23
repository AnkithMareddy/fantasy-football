#!/usr/bin/env python3
"""Evidence for a lineup call, and option ordering that doesn't give the answer away.

Both arcade games had the same flaw: they printed each option's season average next to
it and listed the options already sorted best-first, so the winning strategy was "click
the top button" or "click the biggest number". Measured on the shipped data, the
highest-projection option was the single best call in 72 of 72 drills.

That isn't fixable by reframing the question. Under the gamma draw model in winprob.py a
player's score distribution is set by (mean, position CV), so for a fixed opponent and a
fixed rest-of-lineup, win probability rises monotonically with the mean. A scan of 1,849
live known-deficit spots found 0 where a lower-projection player was the better call. The
"you need 24 points, take the boom/bust guy" intuition does not survive contact with this
model: tail weight is mean x CV^2, so a 14-point RB (5.04) and a 9-point TE (5.06) have
almost identical tails, and the CV spread inside FLEX (0.60-0.75) is far too narrow for
variance to ever overcome a mean gap at a probability anyone would play for.

So the fix is informational. Give the player what the manager actually had - recent form,
the matchup - and make them judge it, instead of handing over a number that ranks the
options for them. The projection is still shown, but only in the reveal.

Used by drill.py and comeback.py.
"""
import random


def game_log(pid, week, PW, KO, P, n=3):
    """A player's most recent n scores BEFORE `week`, newest first.

    Strictly earlier weeks only - including the drill's own week would hand over the
    outcome. Weeks where the player's NFL team had no game are skipped rather than
    recorded as zero, since a bye tells you nothing about form.
    """
    pid, week = str(pid), int(week)
    nfl = (P.get(pid) or {}).get('t')
    out = []
    for w in sorted((int(k) for k in PW if int(k) < week), reverse=True):
        if nfl not in (KO.get(str(w)) or {}):
            continue
        for row in PW[str(w)].values():
            if pid in row['all_pts']:
                out.append({'w': w, 'pts': round(row['all_pts'][pid], 1)})
                break
        if len(out) >= n:
            break
    return out


def form_line(log):
    """The log as a short string, e.g. "wk6 18.2 / wk5 4.1 / wk4 11.6"."""
    return ' / '.join(f"wk{e['w']} {e['pts']:.1f}" for e in log) if log else 'no prior games'


def deterministic_shuffle(items, *seed_parts):
    """Shuffle so presentation order carries no information, but stays reproducible.

    Reproducibility matters: everyone who opens the site should see the same spot laid out
    the same way, and two runs of the generator should not differ (see the 2026-10-18
    changelog entry on set-iteration non-determinism). Seeding from the spot's own
    identity gives a fixed order per spot without a stored shuffle.
    """
    out = list(items)
    random.Random('|'.join(str(p) for p in seed_parts)).shuffle(out)
    return out


def ppg_through(week, PW, KO, P, min_games=2):
    """pid -> (mean points per game BEFORE `week`, position).

    Why this exists: drill.py used to grade historical lineup calls with the season-long
    ppg from season_input.json, which is built from today's rosters and averages the
    WHOLE season. Grading a week-4 decision with a number that contains weeks 5-7 is
    hindsight, and the drill's own docstring claimed it had none.

    It also made role changes invisible. In the week-6 drill for Gujju8's RB slot the
    graded "best call" was Travis Etienne (season ppg 10.35, but he had missed weeks 4
    and 5 injured) over Emanuel Wilson (season ppg 3.53, because his early weeks as a
    backup are averaged in — he had just gone 25.5 and 12.2 as the starter). Any manager
    watching that week would have started Wilson, and the drill called that a mistake.

    Using only completed prior weeks fixes both. Players with fewer than `min_games`
    prior appearances are left out: one noisy game is not a basis for a graded call.
    """
    week = int(week)
    tot, cnt = {}, {}
    for w in (int(k) for k in PW if int(k) < week):
        games = KO.get(str(w)) or {}
        for row in PW[str(w)].values():
            for pid, pts in row['all_pts'].items():
                if (P.get(str(pid)) or {}).get('t') not in games:
                    continue        # bye or no game: not an appearance, not a zero
                tot[str(pid)] = tot.get(str(pid), 0.0) + pts
                cnt[str(pid)] = cnt.get(str(pid), 0) + 1
    return {pid: (tot[pid] / c, (P.get(pid) or {}).get('p'))
            for pid, c in cnt.items() if c >= min_games}
