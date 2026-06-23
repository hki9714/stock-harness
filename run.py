import os
import subprocess
import sys
from pathlib import Path

ROOT   = Path(__file__).parent
VENV   = ROOT / "venv"
PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main():
    print("=" * 50)
    print("  Stock Harness 시작")
    print("=" * 50)

    if not (ROOT / "config.yaml").exists():
        print("\n❌ config.yaml 없음")
        sys.exit(1)
    print("\n✅ config.yaml 확인")

    if not PYTHON.exists():
        print("\n🔧 최초 실행 - 환경 세팅 중...\n")
        result = subprocess.run(
            [sys.executable, "setup/bootstrap.py"],
            cwd=ROOT
        )
        if result.returncode != 0:
            sys.exit(result.returncode)

    print("\n🚀 서버 시작...")
    print("   Dev Console: http://localhost:8000")
    print("   종료: Ctrl+C\n")
    subprocess.run(
        [str(PYTHON), "main.py"],
        cwd=ROOT
    )


if __name__ == "__main__":
    main()