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
| `com.showmeyourtds.text` | Sun 08:00, Sun 22:30, Mon 22:30, **Thu 17:30** | `textreport.sh auto --send` |

`auto` picks preview vs recap by whether a kickoff is still ahead of you: Sunday before
noon (1 PM ET slate) and Thursday before 8 PM (8:15 PM ET TNF) are previews, everything
else is a recap. The Thursday slot was added 2026-10-28 — before that a Thursday-game week
got no pre-kickoff text at all.

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
