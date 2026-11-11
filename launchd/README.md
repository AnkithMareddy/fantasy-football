# Unattended schedule (launchd)

These two LaunchAgents are what keep the site and the texts alive. They matter because
the scheduled Claude routine has frozen on its first permission prompt three times
(2026-10-18, 2026-10-23, 2026-10-26), and a frozen run blocks every run queued behind it.
Nothing in this directory can be asked a question, so nothing here can stall.

The live copies are in `~/Library/LaunchAgents/`. These are the reference copies — the
schedule used to exist only on one machine, with no record of it anywhere.

| agent | runs | does |
|---|---|---|
| `com.showmeyourtds.refresh` | daily 05:00, 14:00 | `autorefresh.sh` — `update.sh` then `deploy_site.sh`. No text. |
| `com.showmeyourtds.text` | Thu 18:30, Fri 09:30, Sun 09:30, Mon 09:30, Mon 18:30, Tue 09:30 | `textreport.sh auto --send` |

## Why these six times

The season has three slates a week, and a report is wanted on both sides of each:

| Slate | Kicks | Before | After |
|---|---|---|---|
| Thursday night | Thu 20:15 ET | Thu 18:30 | Fri 09:30 |
| Sunday | Sun 13:00, through SNF ~23:30 | Sun 09:30 | Mon 09:30 |
| Monday night | Mon 20:15 ET | Mon 18:30 | Tue 09:30 |

The post-slate reports are the **morning after** on purpose. The old schedule recapped
Sunday at 22:30 and Monday at 22:30, both of which land in the middle of a game that
kicked at 20:15 — so the Sunday slate never got a text that covered SNF, and MNF was
recapped while it was still being played.

`auto` picks preview vs recap from the day and hour; Monday is both, so it is a table
rather than a condition (see textreport.sh). Thursday was missing until 2026-10-28 and
Monday afternoon until 2026-11-10.

## How this relates to the Claude routine

The Claude scheduled task runs at **08:30 and 17:30 daily** — one hour ahead of each slot
above. It is the one that can actually research: read the news, weigh whether a
designation means anything for Sunday, and explain what a result means. `newsscan.py` only
diffs Sleeper's own fields.

So the routine is the ceiling and these agents are the floor, and the floor stays quiet
when the ceiling did its job: `send_text.sh` records every successful send to
`state/sent_log.tsv`, and `textreport.sh` skips sending if anything went out in the last
6 hours (`SUPPRESS_HOURS`, override with `FORCE_SEND=1`). Without that, both paths texted
the same slate — which is what happened on 2026-11-01 and 11-02.

`Weekday` is 0 for Sunday, 1 for Monday, 4 for Thursday. `date +%u` in `textreport.sh`
uses the OTHER convention (7 = Sunday), so don't copy a number from one into the other.

## Installing or changing them

    cp launchd/com.showmeyourtds.*.plist ~/Library/LaunchAgents/
    launchctl unload ~/Library/LaunchAgents/com.showmeyourtds.text.plist
    launchctl load   ~/Library/LaunchAgents/com.showmeyourtds.text.plist

Then confirm launchd actually took the calendar entries, rather than trusting the file:

    launchctl print "gui/$(id -u)/com.showmeyourtds.text" | sed -n '/calendarinterval/,/^	}/p'

## Known limits

- Neither agent runs while the Mac is off or asleep. launchd does not catch up a missed
  calendar run on wake, so a machine that is off at 05:00 simply has no 05:00 refresh.
- `textreport.sh` refuses to send if `update.sh` fails or the report comes out under 200
  bytes — a missing text is recoverable, stale numbers presented as current are not.
