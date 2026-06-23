"""
Harness AI Router
=================
config.yaml의 harness.ai 값을 읽어
.harness/{ai}/ 폴더의 가이드 파일을 프로젝트 루트에 복사합니다.

  claude  → CLAUDE.md
  codex   → AGENTS.md
  gemini  → GEMINI.md

bootstrap.py에서 자동 호출됩니다.
직접 실행도 가능합니다:
  python .harness/harness.py
  python .harness/harness.py --ai claude
"""
import argparse
import shutil
from pathlib import Path

ROOT    = Path(__file__).parent.parent
HARNESS = Path(__file__).parent

# AI별 루트에 배포할 파일명
AI_GUIDE_FILES = {
    "claude": "CLAUDE.md",
    "codex":  "AGENTS.md",
    "gemini": "GEMINI.md",
}

# 모든 AI 가이드 파일 목록 (전환 시 이전 파일 제거용)
ALL_GUIDE_FILES = set(AI_GUIDE_FILES.values())


def deploy(ai: str):
    """선택된 AI의 가이드 파일을 루트에 복사, 나머지는 제거"""
    ai = ai.lower()

    if ai not in AI_GUIDE_FILES:
        print(f"❌ 지원하지 않는 AI: '{ai}'")
        print(f"   지원 목록: {', '.join(AI_GUIDE_FILES.keys())}")
        return False

    # 기존 가이드 파일 제거 (이전 AI 잔여물 정리)
    for filename in ALL_GUIDE_FILES:
        old = ROOT / filename
        if old.exists():
            old.unlink()

    # 선택된 AI 가이드 파일 복사
    src      = HARNESS / ai / AI_GUIDE_FILES[ai]
    dst      = ROOT / AI_GUIDE_FILES[ai]

    if not src.exists():
        print(f"❌ 가이드 파일 없음: {src}")
        return False

    shutil.copy2(src, dst)
    print(f"  ✅ AI 도구 설정: {ai}")
    print(f"     {src.relative_to(ROOT)} → {dst.name}")
    return True


def current_ai(cfg: dict) -> str:
    return cfg.get("harness", {}).get("ai", "claude")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harness AI Router")
    parser.add_argument("--ai", help="사용할 AI (claude/codex/gemini)")
    args = parser.parse_args()

    if args.ai:
        deploy(args.ai)
    else:
        # config.yaml에서 읽기
        try:
            import yaml
            cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
            deploy(current_ai(cfg))
        except FileNotFoundError:
            print("❌ config.yaml 없음. --ai 옵션으로 직접 지정하세요.")
            print("   예: python .harness/harness.py --ai claude")
