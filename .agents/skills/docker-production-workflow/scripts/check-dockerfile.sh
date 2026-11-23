#!/usr/bin/env bash
# Static, read-only Dockerfile audit; no build, no container changes.
set -euo pipefail

usage() { printf 'Cách dùng: %s [Dockerfile-path]\n' "$0"; }
if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
if (( $# > 1 )); then usage >&2; exit 2; fi
file=${1:-Dockerfile}
if [[ ! -f "$file" || ! -r "$file" ]]; then
  printf '[ERROR] Không đọc được Dockerfile: %s\n' "$file" >&2; exit 2
fi

errors=0
warnings=0
pass() { printf '[OK] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; warnings=$((warnings + 1)); }
fail() { printf '[FAIL] %s\n' "$*"; errors=$((errors + 1)); }

if grep -Eqi '^[[:space:]]*FROM[[:space:]]' "$file"; then
  pass 'Phát hiện FROM.'
else
  fail 'Thiếu chỉ thị FROM.'
fi

stages=$(awk 'toupper($1)=="FROM"{n++} END{print n+0}' "$file")
if (( stages >= 2 )); then
  pass "Multi-stage build: ${stages} stage(s)."
else
  warn 'Dockerfile chỉ có một FROM; cân nhắc multi-stage nếu cần tối ưu.'
fi

# Track user only in the last Dockerfile stage. USER inheritance from base is unknown.
last_user=$(awk '
  toupper($1)=="FROM" { user=""; in_stage=1; next }
  in_stage && toupper($1)=="USER" { user=$2 }
  END { print user }
' "$file")
if [[ -z "$last_user" ]]; then
  warn 'Không tìm thấy USER trong final stage (cần kiểm tra base image mặc định).'
elif [[ "$last_user" == root || "$last_user" == 0 || "$last_user" == 0:0 ]]; then
  fail "Final stage khai báo chạy root: ${last_user}."
else
  pass "Final stage khai báo non-root: ${last_user}."
fi

# ARG/ENV secrets are highly unsafe, even when value is interpolated at build-time.
if grep -Eqi '^[[:space:]]*(ARG|ENV)[[:space:]]+[^#]*(PASSWORD|TOKEN|SECRET|PRIVATE_KEY|API_KEY|ACCESS_KEY)' "$file"; then
  fail 'Phát hiện ARG/ENV có tên giống secret; dùng BuildKit secret/SSH mount.'
else
  pass 'Không thấy ARG/ENV tên nhạy cảm theo quy tắc tĩnh.'
fi

if grep -Eqi '^[[:space:]]*FROM[[:space:]]+([^[:space:]]+[[:space:]]+)?[^[:space:]]+:latest([[:space:]]|$)' "$file"; then
  fail 'Có base image dùng tag :latest.'
else
  pass 'Không phát hiện base image :latest theo quy tắc tĩnh.'
fi

if grep -Eq '^[[:space:]]*RUN[[:space:]]+.*(curl|wget).*[|][[:space:]]*(sh|bash)' "$file"; then
  warn 'Có curl/wget pipe shell; cần kiểm tra tính toàn vẹn và rủi ro supply chain.'
fi

if grep -Eqi '^[[:space:]]*RUN[[:space:]]+.*chmod[[:space:]]+(-R[[:space:]]+)?777' "$file"; then
  fail 'Dùng chmod 777 trong Dockerfile.'
fi

if grep -Eqi '^#[[:space:]]*syntax=docker/dockerfile:' "$file"; then
  pass 'Đã khai báo syntax directive cho Dockerfile.'
else
  warn 'Chưa có syntax directive rõ ràng (tùy yêu cầu BuildKit).'
fi

if grep -Eqi '^[[:space:]]*ENTRYPOINT[[:space:]]+\[' "$file"; then
  pass 'ENTRYPOINT exec form được phát hiện.'
else
  warn 'Không thấy ENTRYPOINT exec form; kiểm tra CMD/entrypoint và signal handling.'
fi

printf '\nTổng kết Dockerfile: %d lỗi, %d cảnh báo. Kiểm tra tĩnh, không chứng minh build/runtime pass.\n' "$errors" "$warnings"
if (( errors > 0 )); then exit 1; fi
exit 0
