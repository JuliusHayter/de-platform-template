#!/usr/bin/env bash
# Enforce the image retention policy of docs/adr/0006-image-tags.md on Docker Hub.
#
#   scripts/prune_dockerhub.sh                       dry run: lists what would go
#   DOCKERHUB_TOKEN=... scripts/prune_dockerhub.sh --delete [repo:tag ...]
#
# Policy: per image, (1) keep the 3 newest tags; (2) delete any tag that does not
# match <date>-<7-hex-sha>; (3) delete every tag named on the command line, which
# is how a tag superseded because of a defect is retired.
# Listing needs no login (the repositories are public). Deleting needs a Docker Hub
# access token with Read, Write and Delete scope, read from the environment and never
# written to disk.
set -euo pipefail

USER_NAME=julius24h
REPOS=(albert-ingestion albert-dbt)
KEEP=3
DELETE=0
EXPLICIT=()
for arg in "$@"; do
  if [[ "$arg" == "--delete" ]]; then DELETE=1; else EXPLICIT+=("$arg"); fi
done

if (( DELETE )); then
  : "${DOCKERHUB_TOKEN:?set DOCKERHUB_TOKEN to delete}"
  JWT=$(curl -s -H "Content-Type: application/json" \
        -d "{\"username\":\"$USER_NAME\",\"password\":\"$DOCKERHUB_TOKEN\"}" \
        https://hub.docker.com/v2/users/login | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
fi

for repo in "${REPOS[@]}"; do
  echo "== $USER_NAME/$repo"
  tags_json=$(curl -s "https://hub.docker.com/v2/repositories/$USER_NAME/$repo/tags?page_size=100")
  # newest first
  tags=()
  while IFS= read -r line; do tags+=("$line"); done < <(python3 -c '
import json,sys
for t in sorted(json.loads(sys.argv[1]).get("results",[]), key=lambda t:t["last_updated"], reverse=True):
    print(t["name"])' "$tags_json")
  i=0
  for tag in "${tags[@]}"; do
    i=$((i+1)); reason=""
    if (( i > KEEP )); then reason="older than the $KEEP newest"; fi
    if [[ ! "$tag" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9a-f]{7}$ ]]; then reason="does not match <date>-<sha>"; fi
    for e in "${EXPLICIT[@]:-}"; do [[ "$e" == "$repo:$tag" ]] && reason="named on the command line (superseded)"; done
    if [[ -z "$reason" ]]; then
      echo "  keep    $tag"
    elif (( DELETE )); then
      code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE -H "Authorization: JWT $JWT" \
             "https://hub.docker.com/v2/repositories/$USER_NAME/$repo/tags/$tag/")
      echo "  DELETED $tag  ($reason)  http $code"
    else
      echo "  would delete $tag  ($reason)"
    fi
  done
done
