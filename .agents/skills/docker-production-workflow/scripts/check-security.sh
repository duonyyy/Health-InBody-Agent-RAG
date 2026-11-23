#!/usr/bin/env bash
# Conservative static checks + optional Trivy scan; never prune/restart/deploy.
set -euo pipefail
usage() {
  cat <<'HELP'
Cách dùng: check-security.sh [Dockerfile-path] [compose.yaml-path] [--image IMAGE]
Nếu không truyền --image: chỉ kiểm tra tĩnh. --image yêu cầu Trivy và có thể tải CVE DB.
Mã thoát: 0=không phát hiện lỗi nặng, 1=lỗi, 2=không thể kiểm tra đủ/yêu cầu sai.
HELP
}
if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
args=()
image=""
while (( $# > 0 )); do
  case "$1" in
    --image)
      if (( $# < 2 )) || [[ -z "$2" ]]; then usage >&2; exit 2; fi
      image=$2; shift 2 ;;
    --image=*)
      image=${1#--image=}; if [[ -z "$image" ]]; then exit 2; fi; shift ;;
    -*)
      printf '[ERROR] Đối số không hợp lệ: %s\n' "$1" >&2; exit 2 ;;
    *) args+=("$1"); shift ;;
  esac
done
if (( ${#args[@]} > 2 )); then usage >&2; exit 2; fi
dockerfile=${args[0]:-Dockerfile}
compose=${args[1]:-compose.yaml}
if [[ ! -f "$dockerfile" ]]; then
  printf '[ERROR] Không tìm thấy Dockerfile: %s\n' "$dockerfile" >&2; exit 2
fi
errors=0; warnings=0
warn() { printf '[WARN] %s\n' "$*"; warnings=$((warnings + 1)); }
fail() { printf '[FAIL] %s\n' "$*"; errors=$((errors + 1)); }
pass() { printf '[OK] %s\n' "$*"; }

if grep -Eqi '^[[:space:]]*(ARG|ENV)[[:space:]]+[^#]*(PASSWORD|TOKEN|SECRET|PRIVATE_KEY|API_KEY|ACCESS_KEY)' "$dockerfile"; then
  fail 'Dockerfile chứa ARG/ENV tên nhạy cảm.'
else
  pass 'Không phát hiện ARG/ENV tên nhạy cảm.'
fi
if grep -Eqi '^[[:space:]]*RUN[[:space:]]+.*chmod[[:space:]]+(-R[[:space:]]+)?777' "$dockerfile"; then
  fail 'Dockerfile có chmod 777.'
fi
final_user=$(awk 'toupper($1)=="FROM"{u=""; started=1; next} started&&toupper($1)=="USER"{u=$2} END{print u}' "$dockerfile")
if [[ -z "$final_user" ]]; then
  warn 'Không có USER trong final stage; phải xác minh non-root của base image.'
elif [[ "$final_user" == root || "$final_user" == 0 || "$final_user" == 0:0 ]]; then
  fail "Final stage khai báo root: ${final_user}."
else
  pass "Final stage dùng USER: ${final_user}."
fi

if [[ -f "$compose" ]]; then
  if grep -Eqi '^[[:space:]]*privileged:[[:space:]]*true([[:space:]#]|$)' "$compose"; then
    fail 'Compose có privileged: true.'
  fi
  if grep -Eq '(/var/run/docker\.sock|/run/docker\.sock)' "$compose"; then
    fail 'Compose mount/nhắc tới Docker socket; phải xem quyền daemon.'
  fi
  if grep -Eqi '^[[:space:]]*network_mode:[[:space:]]*host([[:space:]#]|$)' "$compose"; then
    warn 'Compose dùng host networking; xem lại trust boundary.'
  fi
  if grep -Eq '("?0\.0\.0\.0:|\x27?0\.0\.0\.0:)' "$compose"; then
    warn 'Có published port 0.0.0.0; xác minh nhu cầu public.'
  fi
  if grep -Eqi '^[[:space:]]*cap_drop:' "$compose"; then
    pass 'Đã phát hiện cap_drop (cần kiểm tra cấu hình từng service).'
  else
    warn 'Chưa thấy cap_drop; cân nhắc least privilege khi tương thích.'
  fi
  if grep -Eqi '^[[:space:]]*read_only:[[:space:]]*true' "$compose"; then
    pass 'Có read_only cho ít nhất một service (không chứng minh tất cả).'
  else
    warn 'Không thấy read_only; đánh giá writable paths trước khi bật.'
  fi
else
  warn "Không tìm thấy Compose file (${compose}); bỏ qua kiểm tra Compose."
fi

if [[ -n "$image" ]]; then
  if ! command -v trivy >/dev/null 2>&1; then
    printf '[UNVERIFIED] Đã yêu cầu scan image nhưng không tìm thấy Trivy.\n' >&2
    exit 2
  fi
  printf '[INFO] Trivy scan image %s (có thể tải database).\n' "$image"
  if trivy image --scanners vuln --severity HIGH,CRITICAL --exit-code 1 "$image"; then
    pass 'Trivy không phát hiện HIGH/CRITICAL theo dữ liệu scan hiện tại.'
  else
    fail 'Trivy scan không đạt hoặc xảy ra lỗi. Kiểm tra log để phân loại.'
  fi
fi

printf '\nTổng kết security: %d lỗi, %d cảnh báo (static heuristics, không phải security audit toàn diện).\n' "$errors" "$warnings"
if (( errors > 0 )); then exit 1; fi
exit 0
