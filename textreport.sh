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

# `auto` lets a single scheduled job pick the right report for the moment it fires. The
# test is not the day of the week as such, it is whether there is still a kickoff ahead of
# you that you can act on:
#   Sunday morning  — the main slate starts at 1 PM ET, so anything before noon is a preview
#   Thursday        — TNF kicks at 8:15 PM ET, so anything before 8 PM is a preview
# Any other time, the games it would talk about have already been played: that's a recap.
# Thursday was missing until 2026-10-28, which meant a Thursday job would have texted a
# "recap" of a game that had not kicked off yet.
if [ "$MODE" = "auto" ]; then
    DOW="$(date +%u)"           # 1 = Monday ... 7 = Sunday
    HOUR="$(date +%H)"          # zero-padded, so strip the pad before comparing
    HOUR="${HOUR#0}"; HOUR="${HOUR:-0}"
    if { [ "$DOW" = "7" ] && [ "$HOUR" -lt 12 ]; } || \
       { [ "$DOW" = "4" ] && [ "$HOUR" -lt 20 ]; }; then
        MODE="preview"
    else
        MODE="recap"
    fi
fi
case "$MODE" in preview|recap) ;; *) echo "usage: $0 preview|recap|auto [--send]" >&2; exit 2 ;; esac

LOG=state/textreport.log
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
