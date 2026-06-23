#!/bin/bash
# ─────────────────────────────────────────────
# EC2 Amazon Linux 2023 / Ubuntu 초기 세팅
# 실행: bash ec2_setup.sh
# ─────────────────────────────────────────────
set -e

echo "======================================"
echo "  Stock Harness EC2 초기 세팅"
echo "======================================"

# OS 감지
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS=$ID
else
  OS="unknown"
fi

# 패키지 업데이트
echo "📦 패키지 업데이트..."
if [ "$OS" = "amzn" ]; then
  sudo yum update -y
  sudo yum install -y git curl
else
  sudo apt-get update -y
  sudo apt-get install -y git curl
fi

# Docker 설치
echo "🐳 Docker 설치..."
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker $USER
  sudo systemctl enable docker
  sudo systemctl start docker
  echo "✅ Docker 설치 완료"
else
  echo "ℹ️  Docker 이미 설치됨"
fi

# Docker Compose v2 확인
if ! docker compose version &>/dev/null; then
  echo "Docker Compose 플러그인 설치..."
  sudo apt-get install -y docker-compose-plugin 2>/dev/null || \
  sudo yum install -y docker-compose-plugin 2>/dev/null || true
fi

# 프로젝트 클론
echo ""
read -p "GitHub 저장소 URL 입력: " REPO_URL

if [ -d ~/stock-harness ]; then
  echo "ℹ️  이미 존재, pull로 업데이트..."
  cd ~/stock-harness && git pull
else
  git clone "$REPO_URL" ~/stock-harness
  cd ~/stock-harness
fi

# .env 설정
echo ""
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️  .env 파일을 편집하세요:"
  echo "   nano ~/stock-harness/.env"
  echo ""
  echo "필수 입력값:"
  echo "  TELEGRAM_BOT_TOKEN=..."
  echo "  TELEGRAM_CHAT_ID=..."
  echo "  ANTHROPIC_API_KEY=..."
  echo "  WATCH_LIST=005930,000660,..."
  echo ""
  read -p "지금 바로 편집할까요? (y/n): " EDIT_NOW
  if [ "$EDIT_NOW" = "y" ]; then
    nano .env
  fi
fi

# 방화벽 - 80 포트 오픈 안내
echo ""
echo "⚠️  EC2 보안 그룹에서 아래 포트를 열어주세요:"
echo "   인바운드 규칙 추가:"
echo "   - 포트 80 (HTTP) → 소스: 0.0.0.0/0"
echo "   - 포트 22 (SSH)  → 소스: 내 IP"
echo ""

# Docker 실행
read -p "지금 바로 실행할까요? (y/n): " RUN_NOW
if [ "$RUN_NOW" = "y" ]; then
  docker compose up -d --build
  sleep 5
  echo ""
  echo "======================================"
  echo "  🎉 배포 완료!"
  MYIP=$(curl -s ifconfig.me)
  echo "  접속 주소: http://$MYIP"
  echo "  헬스체크: http://$MYIP/health"
  echo "  Dev Console: http://$MYIP/"
  echo "======================================"
fi

# GitHub Actions 시크릿 안내
echo ""
echo "────────────────────────────────────────"
echo "GitHub Actions 자동배포 설정 (선택사항)"
echo "────────────────────────────────────────"
echo "GitHub 저장소 → Settings → Secrets 에 추가:"
echo ""
echo "  EC2_HOST    = $(curl -s ifconfig.me)"
KEYNAME=$(ls ~/.ssh/*.pem 2>/dev/null | head -1)
echo "  EC2_USER    = $USER"
echo "  EC2_SSH_KEY = (EC2 .pem 키 파일 내용 전체)"
echo ""
echo "push 시 자동으로 EC2에 배포됩니다."
