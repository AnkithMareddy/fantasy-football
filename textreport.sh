#!/bin/bash
# Refresh the model, build a report, and (optionally) text it — with no Claude session
# anywhere in the path, so nothing here can stop and wait for a permission prompt.
#
# Background: the texted report has only ever come from the scheduled Claude routine, and
# that routine froze on its first Bash call on 2026-10-18 and again on 2026-10-23, each
# time sitting for days and blocking every run queued behind it — including the Sunday
# morning start/sit, the one text that has to beat kickoff. Two misses in six days from
# the same cause is enough: the baseline text should not depend on anything that can be
# asked a question.
#
# This is the floor. The Claude routine still writes the better report when it runs —
# it researches injuries and explains what a result means, which autoreport.py cannot.
#
# Usage:
#   ./textreport.sh preview          build only, print the path   (safe, sends nothing)
#   ./textreport.sh recap  --send    build and text every number in recipients.txt
#   SKIP_UPDATE=1 ./textreport.sh …  use the data already on disk instead of re-running
set -uo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

MODE="${1:-recap}"
SEND=0
[ "${2:-}" = "--send" ] && SEND=1

# `auto` lets one scheduled job pick the right report for the moment it fires. The test is
# whether there is still a kickoff ahead of you that you can act on, versus a finished
# slate worth reporting. Monday is the only day that is both, which is why this is a table
# and not a one-line condition:
#
#   Sun  before 12:00   preview   the main slate kicks at 1 PM ET
#   Sun  12:00 onward   recap     under way or done
#   Thu  before 20:00   preview   TNF kicks at 8:15 PM ET
#   Thu  20:00 onward   recap
#   Mon  before 12:00   recap     Sunday's slate is finished - this is the real week recap
#   Mon  12:00-20:00    preview   MNF is still ahead and those players are startable
#   Mon  20:00 onward   recap
#   any other day       recap
#
# Thursday was missing until 2026-10-28 and Monday afternoon until 2026-11-10; before that
# a Monday evening job would have texted a "recap" of a game that had not kicked off.
if [ "$MODE" = "auto" ]; then
    DOW="$(date +%u)"           # 1 = Monday ... 7 = Sunday
    HOUR="$(date +%H)"          # zero-padded, so strip the pad before comparing
    HOUR="${HOUR#0}"; HOUR="${HOUR:-0}"
    MODE="recap"
    if [ "$DOW" = "7" ] && [ "$HOUR" -lt 12 ]; then
        MODE="preview"
    elif [ "$DOW" = "4" ] && [ "$HOUR" -lt 20 ]; then
        MODE="preview"
    elif [ "$DOW" = "1" ] && [ "$HOUR" -ge 12 ] && [ "$HOUR" -lt 20 ]; then
        MODE="preview"
    fi
fi
case "$MODE" in preview|recap) ;; *) echo "usage: $0 preview|recap|auto [--send]" >&2; exit 2 ;; esac

LOG=state/textreport.log

# Stay quiet if a report already went out recently. This job is the floor: it guarantees a
# text when the Claude routine cannot run. When that routine DID run, its report is the
# better one and this would be a second text about the same games — which is what happened
# on 2026-11-01 and 11-02. Both paths send through send_text.sh, so its ledger is the one
# place that knows. Checked before the lock and before update.sh so a suppressed run costs
# nothing. FORCE_SEND=1 overrides it.
SUPPRESS_HOURS="${SUPPRESS_HOURS:-6}"
if [ "$SEND" = "1" ] && [ -z "${FORCE_SEND:-}" ] && [ -s state/sent_log.tsv ]; then
    LAST_SENT="$(tail -1 state/sent_log.tsv | cut -f1)"
    NOW="$(date +%s)"
    case "$LAST_SENT" in
        ''|*[!0-9]*) LAST_SENT=0 ;;          # a malformed line must not suppress anything
    esac
    if [ "$LAST_SENT" -gt 0 ] && [ "$((NOW - LAST_SENT))" -lt "$((SUPPRESS_HOURS * 3600))" ]; then
        echo "$(date '+%F %T') a report was texted $(( (NOW - LAST_SENT) / 60 ))m ago - not sending another (SUPPRESS_HOURS=$SUPPRESS_HOURS)" >> "$LOG"
        exit 0
    fi
fi

. ./lock.sh
trap 'release_pipeline_lock' EXIT
acquire_pipeline_lock || { echo "$(date '+%F %T') could not get the pipeline lock" >> "$LOG"; exit 1; }

if [ -z "${SKIP_UPDATE:-}" ]; then
    if ! ./update.sh >> "$LOG" 2>&1; then
        # Stop rather than text stale numbers presented as current.
        echo "$(date '+%F %T') update.sh FAILED — no report sent" >> "$LOG"
        exit 1
    fi
fi

OUT="reports/$(date +%F)-week-$MODE-auto.txt"
mkdir -p reports
if ! python3 autoreport.py "$MODE" > "$OUT" 2>>"$LOG"; then
    echo "$(date '+%F %T') autoreport.py FAILED — no report sent" >> "$LOG"
    rm -f "$OUT"
    exit 1
fi
# A report that somehow came out empty or stub-length is a failure, not something to send.
if [ "$(wc -c < "$OUT" | tr -d ' ')" -lt 200 ]; then
    echo "$(date '+%F %T') report suspiciously short — not sending" >> "$LOG"
    exit 1
fi

echo "$(date '+%F %T') built $OUT ($MODE)" >> "$LOG"
echo "$OUT"

if [ "$SEND" = "1" ]; then
    ./send_text.sh "$OUT" >> "$LOG" 2>&1 && \
        echo "$(date '+%F %T') texted $OUT" >> "$LOG" || \
        echo "$(date '+%F %T') send_text.sh FAILED" >> "$LOG"
fi
