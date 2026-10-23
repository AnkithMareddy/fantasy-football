#!/bin/bash
# Unattended daily refresh: run the model, publish the site. No Claude session involved.
#
# Why this exists: the site refresh and the model run are deterministic scripts, so they
# should never have depended on an interactive agent that can stop and wait for a
# permission prompt. On 2026-10-18 the scheduled Claude routine did exactly that — it
# froze on its first Bash call with nobody there to approve it, and because the scheduler
# won't start a run while one is in flight, the next seven runs never fired and the site
# sat four days stale. This path cannot fail that way: launchd runs it, it needs no
# approval, and a hung run releases its own lock on exit.
#
# What this deliberately does NOT do: injury research, writing the report, or texting.
# Those need judgment (and, for texting, the user's consent), so they stay with the
# Claude routine. If this script is all that ever runs, the numbers stay current and
# nobody gets a text.
set -uo pipefail
cd "$(dirname "$0")"

# launchd starts with a near-empty PATH; python3 is Homebrew's, git is Apple's.
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

LOG=state/autorefresh.log
LOCK=state/autorefresh.lock

# Don't stack runs. flock isn't on macOS, so use mkdir, which is atomic.
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date '+%F %T') SKIP: a refresh is already running ($LOCK exists)" >> "$LOG"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

{
  echo "=============================================================="
  echo "$(date '+%F %T') starting unattended refresh"
} >> "$LOG"

if ./update.sh >> "$LOG" 2>&1; then
  echo "$(date '+%F %T') update.sh OK" >> "$LOG"
  if ./deploy_site.sh >> "$LOG" 2>&1; then
    echo "$(date '+%F %T') deploy OK" >> "$LOG"
  else
    echo "$(date '+%F %T') DEPLOY FAILED (model data is current; site was not published)" >> "$LOG"
    exit 1
  fi
else
  echo "$(date '+%F %T') UPDATE FAILED — site left as it was, nothing published" >> "$LOG"
  exit 1
fi

# Keep the log from growing without bound.
if [ "$(wc -l < "$LOG" | tr -d ' ')" -gt 4000 ]; then
  tail -2000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
