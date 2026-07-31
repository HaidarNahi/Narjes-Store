#!/bin/bash
# Deploy narjes_custom (code + built assets) to the frappe_docker production
# stack on the Hostinger VPS, without rebuilding the container image.
#
# Why not rebuild the image? The VPS is 1 vCPU / 4 GB. A --no-cache image
# build pins the load average above 50 and takes the live site down. Syncing
# the app into the running containers achieves the same result in seconds.
# (An image rebuild is still required when Python DEPENDENCIES change — this
# script only ships app code, assets, and the assets.json bundle map.)
#
# Usage:  bash scripts/deploy_prod.sh
# Requires: SSH key access as root (no password), local `bench build` already run.

set -euo pipefail

VPS="${NARJES_VPS:-root@72.61.87.227}"
KEY="${NARJES_SSH_KEY:-$HOME/.ssh/narjes_deploy_ed25519}"
SITE="${NARJES_SITE:-narjes.store}"
BENCH_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
APP_DIR="$BENCH_DIR/apps/narjes_custom"
CONTAINERS="narjes-backend-1 narjes-frontend-1 narjes-scheduler-1 narjes-queue-long-1 narjes-queue-short-1 narjes-websocket-1"
REMOTE_APP="/home/frappe/frappe-bench/apps/narjes_custom"
SSH="ssh -i $KEY -o BatchMode=yes"
TARBALL="$(mktemp -t narjes_deploy).tar.gz"

echo "==> 1/6 packing app"
# COPYFILE_DISABLE stops macOS writing AppleDouble ._* files into the tar —
# frappe's migrate reads every .json under the app and chokes on their
# non-UTF8 header ("'utf-8' codec can't decode byte 0xa3").
cd "$APP_DIR"
COPYFILE_DISABLE=1 tar czf "$TARBALL" \
	--exclude .git --exclude .pytest_cache --exclude __pycache__ \
	--exclude node_modules --exclude '._*' --exclude .DS_Store .
echo "    $(du -h "$TARBALL" | cut -f1)"

echo "==> 2/6 backing up production site"
$SSH "$VPS" "docker exec -u frappe narjes-backend-1 bench --site $SITE backup" 2>&1 | grep -E "Backup|Database" || true

echo "==> 3/6 syncing into containers"
for c in $CONTAINERS; do
	cat "$TARBALL" | $SSH "$VPS" "docker exec -i -u frappe $c tar xzf - -C $REMOTE_APP" 2>/dev/null
	$SSH "$VPS" "docker exec -u frappe $c bash -c 'find $REMOTE_APP \( -name \"._*\" -o -name .DS_Store \) -delete'"
	echo "    $c ok"
done

echo "==> 4/6 patching assets.json bundle map"
# Bundle filenames are content-hashed and change every build, so take the
# mapping straight from the local build rather than hardcoding hashes.
python3 - "$BENCH_DIR" <<'PY' > /tmp/narjes_bundle_map.json
import json, sys
a = json.load(open(sys.argv[1] + "/sites/assets/assets.json"))
# every bundle this app owns — "storefront.*" does not start with
# "narjes", and filtering on that prefix silently shipped the
# storefront CSS/JS without its assets.json entry
own = ("narjes", "storefront")
json.dump({k: v for k, v in a.items() if k.startswith(own)}, sys.stdout)
PY
cat /tmp/narjes_bundle_map.json | $SSH "$VPS" "cat > /tmp/narjes_bundle_map.json && docker cp /tmp/narjes_bundle_map.json narjes-backend-1:/tmp/ >/dev/null && docker exec -u frappe narjes-backend-1 python3 -c '
import json
p = \"/home/frappe/frappe-bench/sites/assets/assets.json\"
a = json.load(open(p))
a.update(json.load(open(\"/tmp/narjes_bundle_map.json\")))
json.dump(a, open(p, \"w\"), indent=1)
print(\"    bundle map:\", \" \".join(sorted(k for k in a if k.startswith((\"narjes\", \"storefront\")))))
'"

echo "==> 5/6 migrate + clear cache"
$SSH "$VPS" "docker exec -u frappe narjes-backend-1 bench --site $SITE migrate" 2>&1 | tail -3
$SSH "$VPS" "docker exec -u frappe narjes-backend-1 bench --site $SITE clear-cache" >/dev/null

echo "==> 6/6 restarting app containers"
$SSH "$VPS" "for c in narjes-backend-1 narjes-scheduler-1 narjes-queue-long-1 narjes-queue-short-1; do docker restart \$c >/dev/null; done"

rm -f "$TARBALL"
echo "==> done. verifying:"
sleep 6
curl -sk -o /dev/null -w "    ping: %{http_code} in %{time_total}s\n" --max-time 30 "https://admin.narjes.store/api/method/ping"
