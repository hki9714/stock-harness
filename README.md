# 📈 Stock Harness

거래량 급등 + "이건 사야돼" 시그널을 텔레그램으로 알려주는 주식 분석 자동화 시스템

---

## 목차

1. [시스템 구조](#1-시스템-구조)
2. [사전 준비](#2-사전-준비)
3. [설정 파일 작성](#3-설정-파일-작성-configyaml)
4. [실행 환경 선택](#4-실행-환경-선택-runtime)
5. [자동 세팅 및 실행](#5-자동-세팅-및-실행)
6. [로컬 → 서버 전환](#6-로컬--서버-전환)
7. [설정값 상세 설명](#7-설정값-상세-설명)
8. [AWS EC2 배포](#8-aws-ec2-배포)
9. [GitHub Actions 자동 배포](#9-github-actions-자동-배포)
10. [운영 명령어](#10-운영-명령어)
11. [텔레그램 봇 명령어](#11-텔레그램-봇-명령어)
12. [주요 종목 코드](#12-주요-종목-코드)
13. [트러블슈팅](#13-트러블슈팅)

---

## 1. 시스템 구조

```
pykrx (주가/거래량)
    ↓
signal_engine.py  ←  naver_crawler.py (네이버 토론) → sentiment.py (KR-FinBert)
    ↓
scheduler/job.py  (30분 주기, 장중 09:00~15:30만 실행)
    ↓
bot/telegram_bot.py  →  텔레그램 알림
    ↑
main.py (FastAPI + APScheduler + Nginx 프록시)
    ↑
ui/dev_console.html  (Claude AI 연동 개발 콘솔)
```

### 매수 시그널 조건

**🔥 거래량 급등 알림** — 5일 평균 거래량 대비 3배 이상 시 즉시 알림

**🚨 "이건 사야돼!" 시그널** — 아래 3조건 AND 충족 시 알림
1. 거래량 급등 + 주가 상승 동반
2. 전일 대비 +5% 이상 급등
3. 네이버 토론 긍정 감성 65% 이상 급증

---

## 2. 사전 준비

### 필수 설치

| 항목 | 버전 | 확인 명령어 |
|------|------|-------------|
| Python | 3.11 이상 | `python --version` |
| Git | 최신 | `git --version` |

### 서버 배포 시 추가 필요

| 항목 | 버전 | 확인 명령어 |
|------|------|-------------|
| Docker | 최신 | `docker --version` |
| Docker Compose | v2 이상 | `docker compose version` |

### 텔레그램 봇 토큰 발급

```
1. 텔레그램 → @BotFather 검색
2. /newbot 입력 → 봇 이름 지정
3. 발급된 토큰 복사  (예: 123456789:ABCdef...)
4. @userinfobot 검색 → /start → chat_id 확인
```

### Anthropic API 키 발급

```
1. https://console.anthropic.com 접속
2. API Keys → Create Key
3. 키 복사  (예: sk-ant-api03-...)
```

---

## 3. 설정 파일 작성 (`config.yaml`)

> ⚠️ `config.yaml`은 `.gitignore`에 포함되어 Git에 커밋되지 않습니다. 절대 직접 커밋하지 마세요.

```bash
cp config.yaml.example config.yaml
```

아래 항목을 채워주세요. `runtime` 값에 따라 필요한 항목이 달라집니다.

```yaml
# ── 실행 환경 ──────────────────────────────────────────────────
#  local  : 로컬 PC에서 Python 직접 실행 (Docker 불필요)
#  server : AWS EC2 + Docker 배포
runtime: "local"

# ── 텔레그램 ───────────────────────────────────────────────────
telegram:
  bot_token: "123456789:ABCdef..."   # @BotFather에서 발급
  chat_id: "987654321"               # @userinfobot에서 확인

# ── AI API ─────────────────────────────────────────────────────
ai:
  anthropic_api_key: "sk-ant-api03-..."  # console.anthropic.com
  default_provider: "claude"             # claude / openai / gemini / ollama
  default_model: "claude-sonnet-4-6"     # 기본 모델

# ── GitHub (runtime 무관하게 항상 입력) ────────────────────────
github:
  repo_url: "https://github.com/본인계정/stock-harness.git"
  branch: "main"
  auto_commit: true                      # 코드 변경 시 자동 커밋
  auto_commit_delay_seconds: 10          # 변경 감지 후 커밋까지 대기(초)

# ── AWS EC2 (runtime: server 일 때만 사용) ─────────────────────
aws:
  ec2_host: "13.125.xxx.xxx"         # EC2 퍼블릭 IP
  ec2_user: "ec2-user"               # Amazon Linux: ec2-user / Ubuntu: ubuntu
  ec2_pem_path: "~/.ssh/my-key.pem"  # 로컬 .pem 파일 경로
  region: "ap-northeast-2"           # 서울 리전

# ── Docker (runtime: server 일 때만 사용) ──────────────────────
docker:
  app_port: 8000
  nginx_port: 80
  log_path: "./logs"

# ── 주식 감시 설정 ─────────────────────────────────────────────
stock:
  watch_list:
    - "005930"  # 삼성전자
    - "000660"  # SK하이닉스
    - "035420"  # NAVER
    - "005380"  # 현대차
  volume_surge_ratio: 3.0            # 거래량 급등 배수 (권장: 2.5~5.0)
  price_surge_pct: 5.0               # 주가 급등 기준 % (권장: 3.0~7.0)
  sentiment_positive_threshold: 0.65 # 토론 긍정 비율 (0.0~1.0)
  sentiment_surge_count: 20          # 최근 1시간 긍정 게시글 최소 건수
  check_interval_minutes: 30         # 시그널 체크 주기 (권장: 15~60)
```

---

## 4. 실행 환경 선택 (`runtime`)

`config.yaml`의 `runtime` 값 하나로 전체 동작 방식이 결정됩니다.

| 항목 | `local` | `server` |
|------|---------|----------|
| 실행 방식 | Python 직접 실행 | Docker Compose |
| 필요 설치 | Python만 | Python + Docker |
| Dev Console 접속 | `http://localhost:8000` | `http://EC2_IP` |
| Git 자동 커밋 | ✅ 동작 | ✅ 동작 |
| AWS 설정 필요 | ❌ | ✅ |
| 권장 용도 | 개발 / 검증 | 실운영 |

**권장 순서**: `local`로 동작 확인 → 검증 완료 후 `server`로 변경해 EC2 배포

---

## 5. 자동 세팅 및 실행

`bootstrap.py`가 `config.yaml`을 읽어 모든 설정 파일을 자동 생성합니다.

### 로컬 실행 (`runtime: "local"`)

```bash
# 설정 검증 (미입력 항목 확인)
python setup/bootstrap.py --check

# 세팅만 (venv 생성 + 의존성 설치 + .env 생성)
python setup/bootstrap.py

# 세팅 + 즉시 실행
python setup/bootstrap.py --run
```

`--run` 내부 동작 순서:

```
config.yaml 읽기
    ↓
.env 자동 생성
.gitignore 자동 생성
    ↓
venv/ 가상환경 생성 (최초 1회)
pip install -r requirements.txt
    ↓
python main.py 실행
```

실행 후 브라우저에서 `http://localhost:8000` 접속 → Dev Console

### 서버 배포 (`runtime: "server"`)

```bash
# 설정 검증
python setup/bootstrap.py --check

# 서버용 파일 자동 생성
#   → docker-compose.yml, nginx/nginx.conf, .github/workflows/deploy.yml
python setup/bootstrap.py

# GitHub Secrets 등록 + EC2 배포까지 한번에
python setup/bootstrap.py --deploy
```

### bootstrap.py 옵션 전체

| 옵션 | 동작 |
|------|------|
| (없음) | 설정 파일 생성만 (.env, .gitignore, 환경별 파일) |
| `--check` | 설정값 검증만 (파일 생성 안 함) |
| `--run` | 세팅 + `python main.py` 즉시 실행 (local 전용) |
| `--deploy` | 세팅 + GitHub Secrets 등록 + EC2 배포 (server 전용) |
| `--github-secrets` | GitHub Secrets만 등록 |

---

## 6. 로컬 → 서버 전환

로컬 검증 완료 후 서버 배포로 전환하는 방법입니다.

```yaml
# config.yaml 수정
runtime: "server"   # local → server

aws:
  ec2_host: "13.125.xxx.xxx"   # EC2 IP 입력
  ec2_user: "ec2-user"
  ec2_pem_path: "~/.ssh/my-key.pem"
```

```bash
python setup/bootstrap.py --deploy
```

전환 시 변경되는 것:

| 항목 | local | server |
|------|-------|--------|
| `.env` | 재생성 (내용 동일) | 재생성 (내용 동일) |
| `docker-compose.yml` | 생성 안 함 | 자동 생성 |
| `nginx/nginx.conf` | 생성 안 함 | 자동 생성 |
| `.github/workflows/deploy.yml` | 생성 안 함 | 자동 생성 |
| Git 자동 커밋 | 그대로 유지 | 그대로 유지 |

---

## 7. 설정값 상세 설명

### `runtime`
| 값 | 설명 |
|----|------|
| `local` | venv + Python 직접 실행. Docker 불필요. |
| `server` | Docker Compose + Nginx. EC2 배포용. |

### `telegram.bot_token` / `telegram.chat_id`
- `bot_token`: @BotFather에서 발급. `숫자:영문` 형식
- `chat_id`: @userinfobot에서 확인. 개인 채팅은 양수, 그룹은 음수

### `ai.default_provider` / `ai.default_model`
| provider | 사용 가능 모델 |
|----------|---------------|
| `claude` | `claude-sonnet-4-6` (기본), `claude-opus-4-6`, `claude-haiku-4-5-20251001` |
| `openai` | `gpt-4o`, `gpt-4o-mini`, `o1-preview` |
| `gemini` | `gemini-1.5-pro`, `gemini-1.5-flash` |
| `ollama` | `llama3:8b`, `mistral:7b` (로컬 설치 필요) |

Dev Console의 AI 설정 탭에서 런타임 중 변경 가능합니다.

### `github.auto_commit`
- `true`: Dev Console에서 코드 수정 → 자동으로 GitHub push
- `auto_commit_delay_seconds`: 마지막 변경 감지 후 N초 대기 후 커밋 (디바운스)
- `runtime`과 무관하게 항상 동작

### `stock.volume_surge_ratio`
- 최근 5일 평균 거래량 대비 배수
- `3.0` → 평균의 3배 이상이면 알림
- 낮출수록 알림 빈도 증가 / 권장: 2.5 ~ 5.0

### `stock.price_surge_pct`
- 전일 종가 대비 상승률 %
- `5.0` → 5% 이상 상승 시 조건 충족
- 권장: 3.0 ~ 7.0

### `stock.sentiment_positive_threshold`
- 네이버 토론 긍정 게시글 비율 (0.0 ~ 1.0)
- `0.65` → 65% 이상 긍정일 때 조건 충족

### `stock.sentiment_surge_count`
- 최근 1시간 수집된 긍정 게시글 최소 건수
- 너무 낮으면 소규모 종목에서 과잉 알림 발생

### `stock.check_interval_minutes`
- 장중(09:00~15:30 평일) 시그널 체크 간격(분)
- 권장: 15 ~ 60. 너무 낮으면 네이버 크롤링 차단 위험

---

## 8. AWS EC2 배포

### EC2 인스턴스 권장 사양

| 용도 | 타입 | 메모리 | 월 비용 |
|------|------|--------|---------|
| 프리티어 (1년 무료) | t2.micro | 1GB | 무료 |
| 기본 운영 | t3.small | 2GB | ~$17 |
| 감성 분석 모델 포함 | t3.medium | 4GB | ~$34 |

> KR-FinBert 감성 모델 사용 시 **t3.small 이상** 권장

### EC2 생성 시 설정값

```
AMI:              Amazon Linux 2023 또는 Ubuntu 22.04 LTS
인스턴스 타입:    t3.small
키 페어:          새로 생성 → .pem 파일 안전하게 보관
보안 그룹 인바운드:
  - 포트 22  (SSH)  → 내 IP
  - 포트 80  (HTTP) → 0.0.0.0/0
스토리지:         20GB gp3
```

### 자동 배포 (권장)

```bash
# config.yaml의 aws 항목 입력 후
python setup/bootstrap.py --deploy
```

내부 동작: EC2 SSH 접속 → Docker 설치 → 소스 클론 → .env 업로드 → `docker compose up -d`

### 수동 배포

```bash
# EC2 접속
ssh -i ~/.ssh/my-key.pem ec2-user@EC2_IP

# Docker 설치
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
sudo systemctl enable docker --now
newgrp docker

# 소스 클론 및 실행
git clone https://github.com/본인계정/stock-harness.git ~/stock-harness
cd ~/stock-harness
cp .env.example .env && nano .env   # 값 입력
docker compose up -d --build
```

---

## 9. GitHub Actions 자동 배포

`main` 브랜치에 push 시 EC2에 자동 배포됩니다.

### GitHub Secrets 등록

GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| Secret 이름 | 값 |
|-------------|-----|
| `EC2_HOST` | EC2 퍼블릭 IP |
| `EC2_USER` | `ec2-user` 또는 `ubuntu` |
| `EC2_SSH_KEY` | .pem 파일 전체 내용 (`cat ~/.ssh/my-key.pem`) |

### gh CLI로 자동 등록

```bash
gh auth login
python setup/bootstrap.py --github-secrets
```

### 자동 배포 흐름

```
main 브랜치 push
    ↓
GitHub Actions 트리거
    ↓
EC2 SSH 접속 → git pull → docker compose build → docker compose up -d
    ↓
헬스체크 확인 → 미사용 이미지 정리
```

---

## 10. 운영 명령어

### 로컬

```bash
# 실행
python setup/bootstrap.py --run

# 재실행
source venv/bin/activate   # Windows: venv\Scripts\activate
python main.py
```

### 서버 (EC2)

```bash
# 상태 확인
docker compose ps

# 로그 실시간 확인
docker compose logs -f app

# 재시작
docker compose restart

# 코드 수동 업데이트
git pull origin main && docker compose up -d --build

# 중지
docker compose down

# 디스크 정리
docker system prune -f
```

---

## 11. 텔레그램 봇 명령어

| 명령어 | 설명 |
|--------|------|
| `/watch 005930` | 종목 감시 추가 |
| `/unwatch 005930` | 종목 감시 제거 |
| `/status` | 현재 감시 종목 및 설정 확인 |
| `/help` | 명령어 목록 |

---

## 12. 주요 종목 코드

| 종목명 | 코드 | 종목명 | 코드 |
|--------|------|--------|------|
| 삼성전자 | 005930 | LG에너지솔루션 | 373220 |
| SK하이닉스 | 000660 | 삼성바이오로직스 | 207940 |
| NAVER | 035420 | 카카오 | 035720 |
| 현대차 | 005380 | 셀트리온 | 068270 |
| 기아 | 000270 | KB금융 | 105560 |
| POSCO홀딩스 | 005490 | 신한지주 | 055550 |

코드 검색: [네이버 증권](https://finance.naver.com) → 종목명 검색 → URL의 `code=` 값

---

## 13. 트러블슈팅

### 포트 80 접속 안 될 때
```
AWS 콘솔 → EC2 → 보안 그룹 → 인바운드 규칙
포트 80, 소스 0.0.0.0/0 추가
```

### Docker 권한 오류
```bash
sudo usermod -aG docker $USER && newgrp docker
```

### 텔레그램 봇 응답 없을 때
```bash
# .env 값 확인
docker compose exec app env | grep TELEGRAM
```

### 메모리 부족 (t2.micro)
```bash
sudo dd if=/dev/zero of=/swapfile bs=128M count=16
sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
```

### 컨테이너 재시작 반복
```bash
docker compose logs app   # 에러 메시지 확인
```

### 감성 분석 모델 로드 실패
- 메모리 부족이 원인인 경우가 많음 → t3.small 이상으로 업그레이드
- 또는 `analyzer/sentiment.py`에서 키워드 폴백 자동 적용됨 (정상 동작)

---

> ⚠️ 본 시스템은 참고용입니다. 투자 판단은 본인 책임입니다.
> 네이버 토론 크롤링 시 서비스 이용약관을 확인하세요.
