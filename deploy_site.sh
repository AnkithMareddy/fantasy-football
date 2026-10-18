#!/bin/bash
# Wraps site/index.html (an Artifact-style fragment) into a standalone HTML document and pushes
# it, with site/data.json, to the public GitHub Pages repo (AnkithMareddy/fantasy-football-hub).
# Run after build_site.py. Live at https://ankithmareddy.github.io/fantasy-football-hub/
set -euo pipefail
cd "$(dirname "$0")"

DEPLOY_DIR="$(mktemp -d)"
trap 'rm -rf "$DEPLOY_DIR"' EXIT

cd "$DEPLOY_DIR"
git init -q
git remote add origin https://github.com/AnkithMareddy/fantasy-football-hub.git
git fetch -q origin main
git checkout -q -b main origin/main
cd - > /dev/null

python3 - "$DEPLOY_DIR" <<'PYEOF'
import sys
deploy_dir = sys.argv[1]
content = open('site/index.html').read()
head_part = content.split('\n<style>', 1)[0]
style_part = content.split('<style>', 1)[1].split('</style>', 1)[0]
body_part = content.split('</style>', 1)[1]
wrapped = f"""<!DOCTYPE html>
<html lang="en">
<head>
{head_part}
<style>{style_part}</style>
</head>
<body>
{body_part}
</body>
</html>
"""
open(f'{deploy_dir}/index.html', 'w').write(wrapped)
PYEOF

cp site/data.json "$DEPLOY_DIR/data.json"

cd "$DEPLOY_DIR"
git add index.html data.json
if git diff --cached --quiet; then
  echo "deploy_site.sh: no changes to publish"
else
  git -c user.email="ankithmareddy@gmail.com" -c user.name="AnkithMareddy" commit -q -m "Refresh site data"
  git push -q origin main
  echo "deploy_site.sh: pushed update to https://github.com/AnkithMareddy/fantasy-football-hub"
fi
