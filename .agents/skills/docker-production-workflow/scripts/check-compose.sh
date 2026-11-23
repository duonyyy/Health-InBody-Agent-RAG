#!/usr/bin/env bash
# Read-only Compose validation. Uses --quiet to avoid printing interpolated secrets.
set -euo pipefail
usage() { printf 'Cách dùng: %s [compose.yaml]\n' "$0"; }
if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
if (( $# > 1 )); then usage >&2; exit 2; fi
file=${1:-compose.yaml}
if [[ ! -f "$file" || ! -r "$file" ]]; then
  printf '[ERROR] Không tìm thấy Compose file: %s\n' "$file" >&2; exit 2
fi

# Only the path is output; never print the resolved Compose config.
printf '[INFO] Kiểm tra Compose dạng chỉ đọc: %s\n' "$file"
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  printf '[UNVERIFIED] Không có Docker Compose v2. Chưa thể xác nhận ngữ nghĩa Compose.\n' >&2
  exit 2
fi

# --quiet suppresses interpolated config, but Docker error/warning may reveal input.
# Caller should avoid sharing logs verbatim if env values are sensitive.
if docker compose -f "$file" config --quiet; then
  printf '[OK] docker compose config --quiet thành công.\n'
  printf '[NOTE] Chưa xác minh image build, health, startup, kết nối hoặc persistence.\n'
  exit 0
fi
printf '[FAIL] Compose không hợp lệ hoặc thiếu biến/config/secret; không dump cấu hình.\n' >&2
exit 1
