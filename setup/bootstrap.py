#!/usr/bin/env python3
"""
Stock Harness Bootstrap
========================
config.yaml 하나만 채우고 실행하면 환경에 맞게 자동 세팅됩니다.

  runtime: local   → venv 생성, 의존성 설치, .env 생성, 로컬 실행
  runtime: server  → 위 + Docker/Nginx 설정, EC2 배포, GitHub Actions 생성

Git 자동 커밋은 runtime 무관하게 항상 동작합니다.

사용법:
  python setup/bootstrap.py            # 환경 감지 후 자동 세팅
  python setup/bootstrap.py --check    # 설정 검증만
  python setup/bootstrap.py --run      # 세팅 + 즉시 실행
  python setup/bootstrap.py --deploy   # (server) EC2 배포까지
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "pyyaml", "-q"], check=True)
    import yaml

ROOT     = Path(__file__).parent.parent
CFG_PATH = ROOT / "config.yaml"
VENV_DIR = ROOT / "venv"


# ────────────────────────────────────────────────────────
# 설정 로드 / 검증
# ────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CFG_PATH.exists():
        print(f"❌ config.yaml 없음")
        print(f"   cp config.yaml.example config.yaml 후 값을 채워주세요")
        sys.exit(1)
    with open(CFG_PATH) as f:
        return yaml.safe_load(f)


def validate(cfg: dict) -> list:
    BAD = ("your_", "sk-ant-your", "https://github.com/username")
    warns = []
    required = [
        (cfg["telegram"]["bot_token"],     "telegram.bot_token"),
        (cfg["telegram"]["chat_id"],       "telegram.chat_id"),
        (cfg["ai"]["anthropic_api_key"],   "ai.anthropic_api_key"),
        (cfg["github"]["repo_url"],        "github.repo_url"),
    ]
    if cfg.get("runtime") == "server":
        required += [
            (cfg["aws"]["ec2_host"],       "aws.ec2_host"),
            (cfg["aws"]["ec2_pem_path"],   "aws.ec2_pem_path"),
        ]
    for val, key in required:
        if any(str(val).startswith(b) for b in BAD):
            warns.append(f"  ⚠️  {key} 가 아직 기본값입니다")
    return warns


# ────────────────────────────────────────────────────────
# 공통 파일 생성 (runtime 무관)
# ────────────────────────────────────────────────────────

def gen_env(cfg: dict):
    tg = cfg["telegram"]
    ai = cfg["ai"]
    st = cfg["stock"]
    gh = cfg["github"]
    content = f"""\
# 자동 생성 — bootstrap.py가 config.yaml에서 생성합니다
# 직접 수정하지 마세요

TELEGRAM_BOT_TOKEN={tg['bot_token']}
TELEGRAM_CHAT_ID={tg['chat_id']}

ANTHROPIC_API_KEY={ai['anthropic_api_key']}
DEFAULT_PROVIDER={ai.get('default_provider', 'claude')}
DEFAULT_MODEL={ai.get('default_model', 'claude-sonnet-4-6')}

WATCH_LIST={",".join(st['watch_list'])}
VOLUME_SURGE_RATIO={st['volume_surge_ratio']}
PRICE_SURGE_PCT={st['price_surge_pct']}
SENTIMENT_POSITIVE_THRESHOLD={st['sentiment_positive_threshold']}
SENTIMENT_SURGE_COUNT={st['sentiment_surge_count']}
CHECK_INTERVAL_MINUTES={st['check_interval_minutes']}

GIT_AUTO_COMMIT={'true' if gh['auto_commit'] else 'false'}
GIT_AUTO_COMMIT_DELAY={gh['auto_commit_delay_seconds']}

RUNTIME={cfg.get('runtime', 'local')}
"""
    write(ROOT / ".env", content)


def gen_gitignore():
    write(ROOT / ".gitignore", """\
# ⚠️ 민감 정보 — 절대 커밋 금지
.env
config.yaml

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/

# 로그
*.log
logs/

# IDE
.idea/
.vscode/
*.iml

# OS
.DS_Store
Thumbs.db

# 모델 캐시
.cache/
""")


# ────────────────────────────────────────────────────────
# 로컬 전용
# ────────────────────────────────────────────────────────

def setup_local(cfg: dict):
    print("\n[로컬 환경 세팅]")

    # 1. venv 생성
    if not VENV_DIR.exists():
        print("  🐍 가상환경 생성 중...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        print(f"  ✅ venv 생성: {VENV_DIR}")
    else:
        print(f"  ℹ️  venv 이미 존재: {VENV_DIR}")

    # 2. pip 설치
    pip = str(VENV_DIR / ("Scripts/pip" if os.name == "nt" else "bin/pip"))
    print("  📦 의존성 설치 중... (시간이 걸릴 수 있어요)")
    subprocess.run([pip, "install", "-r", str(ROOT / "requirements.txt"), "-q"], check=True)
    print("  ✅ 의존성 설치 완료")

    # 3. logs 디렉토리
    (ROOT / "logs").mkdir(exist_ok=True)

    print("\n  로컬 실행 준비 완료!")
    _print_local_guide()


def _print_local_guide():
    activate = "venv\\Scripts\\activate" if os.name == "nt" else "source venv/bin/activate"
    print(f"""
  ┌─ 실행 방법 ──────────────────────────────┐
  │  {activate}          │
  │  python main.py                           │
  │                                           │
  │  Dev Console:                             │
  │  브라우저에서 http://localhost:8000 열기  │
  └───────────────────────────────────────────┘
""")


def run_local():
    """venv Python으로 main.py 직접 실행"""
    python = str(VENV_DIR / ("Scripts/python" if os.name == "nt" else "bin/python"))
    if not Path(python).exists():
        print("❌ venv가 없습니다. 먼저 python setup/bootstrap.py 실행 필요")
        sys.exit(1)
    print("\n🚀 로컬 서버 시작...")
    print("   종료: Ctrl+C\n")
    os.chdir(ROOT)
    os.execv(python, [python, "main.py"])   # 현재 프로세스를 대체


# ────────────────────────────────────────────────────────
# 서버 전용
# ────────────────────────────────────────────────────────

def gen_docker_compose(cfg: dict):
    dk = cfg["docker"]
    write(ROOT / "docker-compose.yml", f"""\
# 자동 생성 — bootstrap.py가 config.yaml에서 생성합니다
version: "3.9"

services:
  app:
    build: .
    container_name: stock-harness-app
    restart: unless-stopped
    env_file: .env
    volumes:
      - {dk['log_path']}:/app/logs
      - ./.git:/app/.git
    expose:
      - "{dk['app_port']}"
    networks:
      - harness-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{dk['app_port']}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  nginx:
    image: nginx:alpine
    container_name: stock-harness-nginx
    restart: unless-stopped
    ports:
      - "{dk['nginx_port']}:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ui:/usr/share/nginx/html:ro
    depends_on:
      - app
    networks:
      - harness-net

networks:
  harness-net:
    driver: bridge
""")


def gen_nginx(cfg: dict):
    dk = cfg["docker"]
    (ROOT / "nginx").mkdir(exist_ok=True)
    write(ROOT / "nginx" / "nginx.conf", f"""\
# 자동 생성 — bootstrap.py가 config.yaml에서 생성합니다
events {{ worker_connections 1024; }}

http {{
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    client_max_body_size 10M;
    gzip on;
    gzip_types text/plain text/css application/javascript application/json;

    server {{
        listen 80;
        server_name _;

        location / {{
            root  /usr/share/nginx/html;
            index index.html;
            try_files $uri $uri/ /index.html;
        }}

        location /api/ {{
            proxy_pass       http://app:{dk['app_port']}/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            add_header Access-Control-Allow-Origin  "*" always;
            add_header Access-Control-Allow-Methods "GET,POST,DELETE,OPTIONS" always;
            add_header Access-Control-Allow-Headers "Content-Type,Authorization" always;
            if ($request_method = OPTIONS) {{ return 204; }}
        }}

        location /proxy/claude {{
            proxy_pass        https://api.anthropic.com/v1/messages;
            proxy_set_header  Host api.anthropic.com;
            proxy_set_header  Content-Type application/json;
            proxy_set_header  anthropic-version "2023-06-01";
            proxy_ssl_server_name on;
            add_header Access-Control-Allow-Origin  "*" always;
            add_header Access-Control-Allow-Methods "POST,OPTIONS" always;
            add_header Access-Control-Allow-Headers "Content-Type,x-api-key,anthropic-version" always;
            if ($request_method = OPTIONS) {{ return 204; }}
        }}

        location /health {{
            proxy_pass http://app:{dk['app_port']}/health;
        }}
    }}
}}
""")


def gen_github_actions(cfg: dict):
    gh = cfg["github"]
    (ROOT / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    write(ROOT / ".github" / "workflows" / "deploy.yml", f"""\
# 자동 생성 — bootstrap.py가 config.yaml에서 생성합니다
name: Deploy to EC2

on:
  push:
    branches: [ {gh['branch']} ]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: EC2 배포
        uses: appleboy/ssh-action@v1.0.3
        with:
          host:     ${{{{ secrets.EC2_HOST }}}}
          username: ${{{{ secrets.EC2_USER }}}}
          key:      ${{{{ secrets.EC2_SSH_KEY }}}}
          script: |
            set -e
            cd ~/stock-harness
            git pull origin {gh['branch']}
            docker compose down --remove-orphans
            docker compose build --no-cache
            docker compose up -d
            sleep 10
            curl -sf http://localhost/health && echo "✅ 배포 완료" || echo "❌ 헬스체크 실패"
            docker image prune -f
""")


def setup_server(cfg: dict):
    print("\n[서버 환경 세팅]")
    gen_docker_compose(cfg)
    gen_nginx(cfg)
    gen_github_actions(cfg)
    print("  ✅ docker-compose.yml 생성")
    print("  ✅ nginx/nginx.conf 생성")
    print("  ✅ .github/workflows/deploy.yml 생성")


def deploy_to_ec2(cfg: dict):
    aws = cfg["aws"]
    gh  = cfg["github"]
    host = aws["ec2_host"]
    user = aws["ec2_user"]
    pem  = Path(aws["ec2_pem_path"]).expanduser()

    if "your-ec2" in host:
        print("  ⚠️  aws.ec2_host 미설정 — EC2 배포 스킵")
        return

    print(f"\n  🔗 EC2 접속: {user}@{host}")
    remote = f"""
set -e
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker $USER
  sudo systemctl enable docker --now
fi
if [ ! -d ~/stock-harness ]; then
  git clone {gh['repo_url']} ~/stock-harness
fi
cd ~/stock-harness && git pull origin {gh['branch']}
echo "EC2 준비 완료"
"""
    r = subprocess.run(
        ["ssh", "-i", str(pem), "-o", "StrictHostKeyChecking=no", f"{user}@{host}", remote]
    )
    if r.returncode != 0:
        print("  ❌ EC2 접속 실패. DEPLOY.md의 수동 세팅을 참고하세요.")
        return

    subprocess.run(
        ["scp", "-i", str(pem), "-o", "StrictHostKeyChecking=no",
         str(ROOT / ".env"), f"{user}@{host}:~/stock-harness/.env"]
    )
    subprocess.run(
        ["ssh", "-i", str(pem), "-o", "StrictHostKeyChecking=no",
         f"{user}@{host}", "cd ~/stock-harness && docker compose up -d --build"]
    )
    print(f"\n  🎉 배포 완료!")
    print(f"  접속: http://{host}")
    print(f"  헬스: http://{host}/health")


def register_github_secrets(cfg: dict):
    if not shutil.which("gh"):
        print("  ℹ️  gh CLI 미설치 → DEPLOY.md 참고하여 수동 등록")
        _print_secrets_guide(cfg)
        return
    aws  = cfg["aws"]
    repo = cfg["github"]["repo_url"].replace("https://github.com/","").replace(".git","")
    pem  = Path(aws["ec2_pem_path"]).expanduser()
    secrets = {
        "EC2_HOST":    aws["ec2_host"],
        "EC2_USER":    aws["ec2_user"],
        "EC2_SSH_KEY": pem.read_text() if pem.exists() else "",
    }
    for name, val in secrets.items():
        if not val or "your-" in val:
            print(f"  ⚠️  {name} 미설정, 스킵")
            continue
        r = subprocess.run(
            ["gh", "secret", "set", name, "--repo", repo, "--body", val],
            capture_output=True, text=True
        )
        status = "✅" if r.returncode == 0 else "❌"
        print(f"  {status} GitHub Secret: {name}")


def _print_secrets_guide(cfg: dict):
    aws = cfg["aws"]
    print("\n  GitHub 저장소 → Settings → Secrets → Actions → New repository secret")
    print(f"    EC2_HOST    = {aws['ec2_host']}")
    print(f"    EC2_USER    = {aws['ec2_user']}")
    print(f"    EC2_SSH_KEY = (cat {aws['ec2_pem_path']})")


# ────────────────────────────────────────────────────────
# 유틸
# ────────────────────────────────────────────────────────

def write(path: Path, content: str):
    path.write_text(content, encoding="utf-8")
    print(f"  ✅ 생성: {path.relative_to(ROOT)}")


# ────────────────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stock Harness Bootstrap")
    parser.add_argument("--check",          action="store_true", help="설정 검증만")
    parser.add_argument("--run",            action="store_true", help="세팅 후 즉시 실행 (local)")
    parser.add_argument("--deploy",         action="store_true", help="EC2 배포 (server)")
    parser.add_argument("--github-secrets", action="store_true", help="GitHub Secrets 등록")
    args = parser.parse_args()

    print("=" * 52)
    print("  Stock Harness Bootstrap")
    print("=" * 52)

    cfg     = load_config()
    runtime = cfg.get("runtime", "local")
    print(f"\n  실행 환경: {'🖥  로컬' if runtime == 'local' else '☁️  서버 (EC2)'}")

    # 검증
    warns = validate(cfg)
    if warns:
        print("\n⚠️  미설정 항목:")
        for w in warns: print(w)
        if args.check: return
        print()

    if args.check:
        if not warns: print("✅ 모든 설정값 정상")
        return

    # 공통 파일 생성
    print("\n📄 공통 파일 생성...")
    gen_env(cfg)
    gen_gitignore()

    # AI 도구 가이드 파일 루트에 배포
    try:
        import sys
        sys.path.insert(0, str(ROOT / ".harness"))
        from harness import deploy, current_ai
        deploy(current_ai(cfg))
    except Exception as e:
        print(f"  ⚠️  AI 가이드 파일 배포 실패: {e}")

    # 환경별 분기
    if runtime == "local":
        setup_local(cfg)
        if args.run:
            run_local()   # 이 아래 코드는 실행 안 됨 (프로세스 대체)

    elif runtime == "server":
        setup_server(cfg)
        if args.github_secrets or args.deploy:
            print("\n🔑 GitHub Secrets 등록...")
            register_github_secrets(cfg)
        if args.deploy:
            deploy_to_ec2(cfg)
        else:
            print("\n다음 단계:")
            print("  python setup/bootstrap.py --github-secrets  # GitHub Secrets 등록")
            print("  python setup/bootstrap.py --deploy          # EC2 배포")

    print("\n✅ 완료!")


if __name__ == "__main__":
    main()
