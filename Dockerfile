FROM python:3.11-slim

# 시스템 패키지 + Node.js (Claude Code CLI 설치용)
RUN apt-get update && apt-get install -y \
    gcc g++ git curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI 설치
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

# 의존성 먼저 설치 (레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .

# 로그 디렉토리
RUN mkdir -p /app/logs

# Claude Code 인증 토큰 마운트 위치 (docker-compose에서 볼륨으로 주입)
VOLUME ["/root/.claude"]

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
