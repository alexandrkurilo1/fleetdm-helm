#!/usr/bin/env bash
# Verifies that Fleet, MySQL and Redis are up and wired together.
set -euo pipefail

CTX=${KUBE_CONTEXT:-kind-fleet}
NS=${NAMESPACE:-fleet}
REL=${RELEASE:-fleet}
FLEET_URL=${FLEET_URL:-https://localhost:8443}
k() { kubectl --context "$CTX" -n "$NS" "$@"; }

pass() { printf '  \033[32m✔\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✘\033[0m %s\n' "$1"; exit 1; }

echo "Pods:"
k get pods -l app.kubernetes.io/instance="$REL" -o wide

echo "Checks:"
k rollout status statefulset/"$REL"-mysql --timeout=180s >/dev/null && pass "MySQL StatefulSet ready" || fail "MySQL not ready"
k rollout status statefulset/"$REL"-redis --timeout=120s >/dev/null && pass "Redis StatefulSet ready" || fail "Redis not ready"
k rollout status deployment/"$REL" --timeout=300s >/dev/null && pass "Fleet Deployment ready" || fail "Fleet not ready"

job=$(k get jobs -l app.kubernetes.io/component=migration --sort-by=.metadata.creationTimestamp -o name | tail -n1)
if [[ -n "$job" ]]; then
  [[ "$(k get "$job" -o jsonpath='{.status.succeeded}')" == "1" ]] && pass "Migration $job succeeded" || fail "Migration $job not complete"
else
  pass "Migration job already cleaned up by TTL"
fi

tables=$(k exec statefulset/"$REL"-mysql -- sh -c \
  'mysql -N -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()" 2>/dev/null')
[[ "$tables" -gt 50 ]] && pass "MySQL: Fleet schema present ($tables tables)" || fail "MySQL: schema missing ($tables tables)"

[[ "$(k exec statefulset/"$REL"-redis -- redis-cli ping)" == "PONG" ]] && pass "Redis: PING -> PONG" || fail "Redis not responding"

# /healthz returns 200 only if Fleet can reach both MySQL and Redis.
ca=$(mktemp); trap 'rm -f "$ca"' EXIT
k get secret "$REL"-tls -o jsonpath='{.data.ca\.crt}' | base64 -d > "$ca"
code=$(curl -s -o /dev/null -w '%{http_code}' --cacert "$ca" "$FLEET_URL/healthz" || true)
[[ "$code" == "200" ]] && pass "Fleet /healthz via $FLEET_URL -> 200 (TLS verified)" || fail "Fleet /healthz via $FLEET_URL -> $code"

code=$(curl -s -o /dev/null -w '%{http_code}' --cacert "$ca" "$FLEET_URL/api/v1/osquery/enroll" -X POST -d '{}' || true)
[[ "$code" =~ ^4[0-9][0-9]$ ]] && pass "Agent enroll endpoint reachable (HTTP $code without enroll secret, as expected)" || fail "Agent enroll endpoint -> $code"

echo "All checks passed."
