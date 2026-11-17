#!/usr/bin/env bash
# Đo ma trận benchmark B / D / D' / E qua TLS (T13 đã đóng).
# C không đo: BitLocker Off, at-rest risk-accepted (docs/evidence/T13_2026-11-16.md).
# Chạy: bash bench/run_matrix.sh   (cần Docker + .env ở gốc repo)
set -euo pipefail
cd "$(dirname "$0")/.."
# Git Bash đổi "/work" thành đường dẫn Windows; tắt để docker nhận đúng mount.
export MSYS_NO_PATHCONV=1
W=$(cygpath -m "$PWD")
set -a; . ./.env; set +a
R=bench/results
mkdir -p "$R"
K6=(docker run --rm -v "$W:/work" -w /work grafana/k6:0.54.0)

measure() { # cfg vus run url
  local cfg=$1 vus=$2 run=$3 url=$4
  local base="$R/${cfg}_${vus}_run${run}"
  "${K6[@]}" run -e BASE_URL="$url" -e API_KEY="$API_KEY" -e VUS="$vus" -e DURATION=3m \
    --out csv="$base.csv" --summary-export "${base}_summary.json" bench/k6/mixed.js \
    > "$base.log" 2>&1
  gzip -f "$base.csv"
  echo "done $cfg vus=$vus run=$run"
}

warmup() { "${K6[@]}" run -e BASE_URL="$1" -e API_KEY="$API_KEY" -e VUS=10 -e DURATION=1m bench/k6/mixed.js >/dev/null 2>&1; }

wait_api() {
  for _ in $(seq 1 40); do
    [ "$(docker inspect detai20-api-1 --format '{{.State.Health.Status}}' 2>/dev/null)" = healthy ] && return 0
    sleep 3
  done
  echo "api not healthy" >&2; return 1
}

restart_api() { # dek_ttl
  DEK_CACHE_TTL_SECONDS="$1" USE_VAULT_DB_CREDS=true docker compose up -d --force-recreate api
  wait_api
}

start_baseline() {
  docker rm -f detai20-baseline >/dev/null 2>&1 || true
  docker run -d --name detai20-baseline --network detai20_default --network-alias baseline \
    -v "$W/bench/baseline:/baseline:ro" -w /baseline \
    -e BASELINE_DB_DSN="postgresql://postgres:${POSTGRES_PASSWORD:-local_demo_postgres_password}@postgres:5432/encryption_db" \
    -e API_KEY="$API_KEY" detai20-api:local uvicorn server:app --host 0.0.0.0 --port 8001
  sleep 8
}

rotate_once() { # tag
  curl -sk -X POST https://127.0.0.1:8443/admin/rotation/database \
    -H "X-Admin-Key: $ADMIN_API_KEY" > "$R/E_rotation_database_$1.json"
  docker compose run --rm --no-deps --entrypoint python vault-init \
    scripts/rotate_transit_key.py > "$R/E_rotation_transit_$1.log" 2>&1
}

TLS_API=https://host.docker.internal:8443
TLS_BASE=https://host.docker.internal:8444

echo "== B: TLS + plaintext baseline =="
start_baseline
warmup "$TLS_BASE"
for v in 10 50 100; do for r in 1 2 3 4 5; do measure B "$v" "$r" "$TLS_BASE"; done; done
docker rm -f detai20-baseline >/dev/null 2>&1 || true

echo "== D: TLS + envelope, cache 0 =="
restart_api 0
warmup "$TLS_API"
for v in 10 50 100; do for r in 1 2 3 4 5; do measure D "$v" "$r" "$TLS_API"; done; done

echo "== D': TLS + envelope, cache 120 =="
restart_api 120
warmup "$TLS_API"
for v in 10 50 100; do for r in 1 2 3 4 5; do measure Dprime "$v" "$r" "$TLS_API"; done; done
restart_api 0

echo "== E: D + rotation trong cửa sổ đo =="
warmup "$TLS_API"
for v in 10 50 100; do
  for r in 1 2 3 4 5; do
    base="$R/E_${v}_run${r}"
    "${K6[@]}" run -e BASE_URL="$TLS_API" -e API_KEY="$API_KEY" -e VUS="$v" -e DURATION=3m \
      --out csv="$base.csv" --summary-export "${base}_summary.json" bench/k6/mixed.js \
      > "$base.log" 2>&1 &
    k6pid=$!
    sleep 60
    rotate_once "${v}_run${r}"
    wait "$k6pid"
    gzip -f "$base.csv"
    echo "done E vus=$v run=$r"
  done
done

echo "MATRIX COMPLETE"