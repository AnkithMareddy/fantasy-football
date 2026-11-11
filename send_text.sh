#!/bin/bash
# usage: ./send_text.sh <message-file>   — texts the file to every number in recipients.txt
#
# Exits non-zero if ANY recipient failed, so textreport.sh can log the truth. It used to
# capture osascript's output and then `exit 0` unconditionally, which meant a send could
# fail for every recipient and the log would still say "texted". That is exactly what
# happened on 2026-11-09: both sends were refused with "Not authorized to send Apple
# events to Messages" and the run was recorded as a success. A missing text you know
# about is recoverable; one you believe went out is not.
#
# Every recipient is still attempted even after one fails — one bad number should not
# stop the other person's copy.
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${1:-}" ] || { echo "message file not found: ${1:-}"; exit 1; }
MSG="$(cat "$1")"
COUNT=0
FAILED=0
NEEDS_AUTOMATION_PERMISSION=0

while IFS= read -r line; do
  num="$(echo "$line" | sed 's/#.*//' | tr -d '[:space:]()-')"
  [ -z "$num" ] && continue
  COUNT=$((COUNT+1))
  # Keep the status; osascript exits non-zero when Messages refuses or errors.
  if res="$(osascript "$DIR/send_text.applescript" "$num" "$MSG" </dev/null 2>&1)"; then
    echo "...${num: -4} -> sent via iMessage"
  else
    FAILED=$((FAILED+1))
    echo "...${num: -4} -> FAILED: $res"
    case "$res" in
      *"Not authorized to send Apple events"*|*"not allowed assistive access"*|*"-1743"*)
        NEEDS_AUTOMATION_PERMISSION=1 ;;
    esac
  fi
done < "$DIR/recipients.txt"

[ "$COUNT" -eq 0 ] && { echo "NO RECIPIENTS: add phone numbers to $DIR/recipients.txt"; exit 2; }

if [ "$NEEDS_AUTOMATION_PERMISSION" = "1" ]; then
  # This one is not a bug and cannot be fixed from a script — macOS has revoked the
  # Automation grant, which only the person at the keyboard can restore.
  echo "macOS is blocking Messages automation. Grant it in:"
  echo "  System Settings > Privacy & Security > Automation > (the app running this) > Messages"
  echo "This resets after some macOS updates, so it can come back."
fi

if [ "$FAILED" -gt 0 ]; then
  echo "$FAILED of $COUNT recipient(s) failed"
  exit 1
fi

# One ledger for every successful send, whatever started it. Both the launchd job and the
# Claude routine text through this script, and until now neither knew what the other had
# done: on 2026-11-01 and 11-02 both sent a report for the same slate, so two texts
# arrived for one set of games. textreport.sh reads this to stay quiet when the researched
# report already went out.
printf '%s\t%s\t%s\n' "$(date +%s)" "$(date '+%F %T')" "$1" >> "$DIR/state/sent_log.tsv"
exit 0
