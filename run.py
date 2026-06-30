import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT    = Path(__file__).parent
VENV    = ROOT / "venv"
PYTHON  = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
LOG_DIR = ROOT / "logs"


class _Tee:
    """stdout/stderr를 터미널과 파일에 동시 출력"""
    def __init__(self, terminal, logfile):
        self._t = terminal
        self._f = logfile

    def write(self, data):
        self._t.write(data)
        self._t.flush()
        self._f.write(data)
        self._f.flush()

    def flush(self):
        self._t.flush()
        self._f.flush()

    def fileno(self):
        return self._t.fileno()


def _run(args, **kwargs) -> int:
    """서브프로세스 실행 — stdout/stderr를 현재 sys.stdout(Tee)으로 스트리밍"""
    with subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=kwargs.get("cwd", ROOT),
    ) as proc:
        for raw in proc.stdout:
            sys.stdout.write(raw.decode("utf-8", errors="replace"))
        proc.wait()
        return proc.returncode


def main():
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / "run.log"
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)

    # 세션 구분선
    log_file.write(f"\n{'='*60}\n  run.py 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*60}\n")
    log_file.flush()

    sys.stdout = _Tee(sys.__stdout__, log_file)
    sys.stderr = _Tee(sys.__stderr__, log_file)

    try:
        print("=" * 50)
        print("  Stock Harness 시작")
        print("=" * 50)

        if not (ROOT / "config.yaml").exists():
            print("\n❌ config.yaml 없음")
            sys.exit(1)
        print("\n✅ config.yaml 확인")

        if not PYTHON.exists():
            print("\n🔧 최초 실행 - 환경 세팅 중...\n")
            ret = _run([sys.executable, "setup/bootstrap.py"])
            if ret != 0:
                sys.exit(ret)

        print("\n🔨 프론트엔드 빌드 중...")
        if _run([str(PYTHON), "frontend/build.py"]) != 0:
            print("⚠️  프론트엔드 빌드 실패 (서버는 계속 시작합니다)\n")

        print("\n🚀 서버 시작...")
        print("   Dashboard:    http://localhost:8000/dashboard")
        print("   Dev Console:  http://localhost:8000/devconsole")
        print(f"   로그 파일:    logs/run.log  |  logs/harness.log")
        print("   종료: Ctrl+C\n")
        _run([str(PYTHON), "main.py"])

    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        log_file.close()


if __name__ == "__main__":
    main()