"""
React 대시보드 빌드 스크립트
==============================
Node.js가 설치되어 있으면 npm build 실행
없으면 안내 메시지 출력

사용법:
  python frontend/build.py
"""
import subprocess
import sys
import shutil
from pathlib import Path

ROOT     = Path(__file__).parent.parent
FRONTEND = Path(__file__).parent
DIST     = ROOT / "static" / "dashboard"
CONSOLE  = ROOT / "static" / "console"


def check_node():
    return shutil.which("node") is not None and shutil.which("npm") is not None


def build():
    print("🔨 React 빌드 중...")

    if not check_node():
        print("\n❌ Node.js / npm이 설치되어 있지 않아요.")
        print("\n설치 방법:")
        print("  https://nodejs.org 에서 LTS 버전 다운로드 후 설치")
        print("\n설치 후 다시 실행:")
        print("  python frontend/build.py")
        sys.exit(1)

    # npm install
    print("📦 npm install 중...")
    r = subprocess.run(["npm", "install"], cwd=FRONTEND, shell=True)
    if r.returncode != 0:
        print("❌ npm install 실패")
        sys.exit(1)

    # 대시보드 빌드
    print("🏗  대시보드 빌드 중...")
    r = subprocess.run(["npm", "run", "build"], cwd=FRONTEND, shell=True)
    if r.returncode != 0:
        print("❌ 대시보드 빌드 실패")
        sys.exit(1)

    # Dev Console 빌드
    print("🏗  Dev Console 빌드 중...")
    r = subprocess.run(
        ["npm", "run", "build:console"],
        cwd=FRONTEND, shell=True,
    )
    if r.returncode != 0:
        print("❌ Dev Console 빌드 실패")
        sys.exit(1)

    # Vite는 입력 파일명 그대로 출력하므로 FastAPI StaticFiles가 찾는 index.html로 변경
    console_html = CONSOLE / "console.html"
    if console_html.exists():
        console_html.rename(CONSOLE / "index.html")

    print(f"\n✅ 빌드 완료")
    print(f"   대시보드  → http://localhost:8000/dashboard")
    print(f"   Dev Console → http://localhost:8000/devconsole")


if __name__ == "__main__":
    build()
