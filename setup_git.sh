#!/bin/bash
# ─────────────────────────────────────────────
# Stock Harness - GitHub 초기 연동 스크립트
# 실행: bash setup_git.sh
# ─────────────────────────────────────────────
set -e

echo "======================================"
echo "  Stock Harness GitHub 초기 설정"
echo "======================================"

# 1. git 초기화
if [ ! -d ".git" ]; then
  git init
  echo "✅ git 초기화 완료"
else
  echo "ℹ️  이미 git 저장소입니다"
fi

# 2. .gitignore 생성
cat > .gitignore << 'EOF'
# 환경변수 (절대 커밋 금지)
.env

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/

# 로그
*.log
harness.log

# IDE
.idea/
.vscode/
*.iml

# OS
.DS_Store
Thumbs.db

# 모델 캐시 (용량 큼)
~/.cache/huggingface/
EOF
echo "✅ .gitignore 생성 완료"

# 3. GitHub 원격 저장소 설정
echo ""
echo "GitHub 원격 저장소 URL을 입력하세요"
echo "예: https://github.com/username/stock-harness.git"
read -p "URL: " REMOTE_URL

if [ -n "$REMOTE_URL" ]; then
  git remote remove origin 2>/dev/null || true
  git remote add origin "$REMOTE_URL"
  echo "✅ 원격 저장소 연결: $REMOTE_URL"
fi

# 4. GitHub 사용자 정보 설정
echo ""
read -p "GitHub 이름 (git config user.name): " GIT_NAME
read -p "GitHub 이메일: " GIT_EMAIL
git config user.name "$GIT_NAME"
git config user.email "$GIT_EMAIL"

# 5. 자동 커밋 설정
echo ""
read -p "자동 커밋 활성화? (y/n): " AUTO_COMMIT
if [ "$AUTO_COMMIT" = "y" ]; then
  # .env에 추가
  if ! grep -q "GIT_AUTO_COMMIT" .env 2>/dev/null; then
    echo "GIT_AUTO_COMMIT=true" >> .env
    echo "✅ 자동 커밋 활성화 (.env에 추가됨)"
  fi
  pip install watchdog -q
  echo "✅ watchdog 설치 완료"
fi

# 6. 초기 커밋 + Push
echo ""
git add -A
git commit -m "init: Stock Harness 초기 커밋 🚀" 2>/dev/null || echo "ℹ️  커밋할 변경 없음"

if [ -n "$REMOTE_URL" ]; then
  git branch -M main
  git push -u origin main
  echo "✅ GitHub Push 완료!"
fi

echo ""
echo "======================================"
echo "  설정 완료! 이제 실행하세요:"
echo "  python main.py"
echo "  Dev Console: ui/dev_console.html"
echo "======================================"
