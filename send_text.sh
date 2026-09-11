#!/bin/bash
# usage: ./send_text.sh <message-file>   — texts the file to every number in recipients.txt
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${1:-}" ] || { echo "message file not found: ${1:-}"; exit 1; }
MSG="$(cat "$1")"
COUNT=0
while IFS= read -r line; do
  num="$(echo "$line" | sed 's/#.*//' | tr -d '[:space:]()-')"
  [ -z "$num" ] && continue
  res="$(osascript "$DIR/send_text.applescript" "$num" "$MSG" </dev/null 2>&1)"
  echo "...${num: -4} -> $res"
  COUNT=$((COUNT+1))
done < "$DIR/recipients.txt"
[ "$COUNT" -eq 0 ] && { echo "NO RECIPIENTS: add phone numbers to $DIR/recipients.txt"; exit 2; }
exit 0
