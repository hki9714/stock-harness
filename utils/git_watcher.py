"""
GitHub 자동 커밋 워처
- watchdog으로 프로젝트 파일 변경 감지
- 변경 후 10초 디바운스 → git add → commit → push
- .env에 GIT_AUTO_COMMIT=true 설정 시 활성화
"""
import os
import subprocess
import threading
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# 감시 제외 패턴
IGNORE_PATTERNS = {
    "__pycache__", ".git", ".env", "*.pyc",
    "*.log", "harness.log", ".DS_Store",
}

PROJECT_ROOT = Path(__file__).parent.parent


def _should_ignore(path: str) -> bool:
    p = Path(path)
    for part in p.parts:
        for pattern in IGNORE_PATTERNS:
            if pattern.startswith("*"):
                if part.endswith(pattern[1:]):
                    return True
            elif part == pattern:
                return True
    return False


def _git_run(args: list) -> tuple[int, str]:
    """git 명령어 실행, (returncode, output) 반환"""
    result = subprocess.run(
        ["git"] + args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip() or result.stderr.strip()


def git_status() -> list[str]:
    """변경된 파일 목록 반환"""
    _, output = _git_run(["status", "--porcelain"])
    changed = []
    for line in output.splitlines():
        if line.strip():
            changed.append(line[3:].strip())
    return changed


def git_commit_push(message: str = "") -> bool:
    """
    변경 파일 add → commit → push
    반환: 성공 여부
    """
    changed = git_status()
    if not changed:
        logger.info("[Git] 변경 없음, 스킵")
        return False

    if not message:
        files_summary = ", ".join(changed[:3])
        if len(changed) > 3:
            files_summary += f" 외 {len(changed)-3}개"
        message = f"auto: {files_summary} [{datetime.now().strftime('%H:%M')}]"

    # add
    code, out = _git_run(["add", "-A"])
    if code != 0:
        logger.error(f"[Git] add 실패: {out}")
        return False

    # commit
    code, out = _git_run(["commit", "-m", message])
    if code != 0:
        logger.error(f"[Git] commit 실패: {out}")
        return False
    logger.info(f"[Git] 커밋: {message}")

    # push
    code, out = _git_run(["push"])
    if code != 0:
        logger.error(f"[Git] push 실패: {out}")
        return False
    logger.info(f"[Git] Push 완료 → {out}")
    return True


class DebounceCommitter:
    """변경 감지 후 N초 디바운스, 연속 변경 시 타이머 리셋"""

    def __init__(self, delay: float = 10.0):
        self.delay = delay
        self._timer: threading.Timer | None = None
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def on_change(self, filepath: str):
        if _should_ignore(filepath):
            return
        with self._lock:
            self._pending.add(filepath)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.delay, self._flush)
            self._timer.daemon = True
            self._timer.start()
        logger.debug(f"[Git] 변경 감지: {filepath} (디바운스 {self.delay}s)")

    def _flush(self):
        with self._lock:
            files = list(self._pending)
            self._pending.clear()
        if files:
            git_commit_push()

    def force_commit(self, message: str = ""):
        """수동 즉시 커밋"""
        if self._timer:
            self._timer.cancel()
        git_commit_push(message)


def start_watcher(delay: float = 10.0) -> DebounceCommitter | None:
    """
    watchdog 파일 감시 시작
    GIT_AUTO_COMMIT=true 환경변수 필요
    반환: DebounceCommitter 인스턴스 (비활성 시 None)
    """
    if os.getenv("GIT_AUTO_COMMIT", "false").lower() != "true":
        logger.info("[Git] 자동 커밋 비활성 (GIT_AUTO_COMMIT=true 로 활성화)")
        return None

    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        committer = DebounceCommitter(delay=delay)

        class Handler(FileSystemEventHandler):
            def on_modified(self, event):
                if not event.is_directory:
                    committer.on_change(event.src_path)
            def on_created(self, event):
                if not event.is_directory:
                    committer.on_change(event.src_path)

        observer = Observer()
        observer.schedule(Handler(), str(PROJECT_ROOT), recursive=True)
        observer.daemon = True
        observer.start()
        logger.info(f"[Git] 파일 감시 시작 → {PROJECT_ROOT}")
        return committer

    except ImportError:
        logger.warning("[Git] watchdog 미설치. `pip install watchdog` 후 재시작")
        return None
