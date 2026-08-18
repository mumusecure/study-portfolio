#!/usr/bin/env bash
# 옵시디언에 쓴 노트를 사이트에 반영한다.
#   ./publish.sh              → 커밋 메시지 자동
#   ./publish.sh "메시지"      → 메시지 지정
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "▸ 첫 실행: 빌드용 venv 생성"
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

echo "▸ 빌드"
.venv/bin/python scripts/build.py

if git diff --quiet && git diff --cached --quiet && [ -z "$(git status --porcelain)" ]; then
  echo "▸ 바뀐 게 없습니다."
  exit 0
fi

echo "▸ 올라갈 변경"
git status --short

msg="${1:-notes: $(date +%Y-%m-%d) 기록 업데이트}"
git add -A
git commit -q -m "$msg"
git push -q origin main
echo "▸ 완료 → https://mumusecure.github.io/study-portfolio/"
