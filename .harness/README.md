# .harness

AI CLI 도구별 프로젝트 가이드 파일을 관리하는 폴더입니다.

## 구조

```
.harness/
├── harness.py          # AI 선택 라우터 (bootstrap.py에서 자동 호출)
├── claude/
│   └── CLAUDE.md       # Claude Code 가이드
├── codex/
│   └── AGENTS.md       # OpenAI Codex 가이드
└── gemini/
    └── GEMINI.md       # Google Gemini CLI 가이드
```

## 동작 방식

`config.yaml`의 `harness.ai` 값에 따라 bootstrap.py 실행 시
해당 AI의 가이드 파일을 프로젝트 루트에 자동 복사합니다.

```yaml
# config.yaml
harness:
  ai: "claude"    # → 루트에 CLAUDE.md 복사
```

## AI 전환 방법

```bash
# config.yaml 수정 후
python setup/bootstrap.py

# 또는 직접 전환
python .harness/harness.py --ai codex
```

## 지원 AI

| ai 값 | 가이드 파일 | CLI 도구 |
|-------|------------|---------|
| `claude` | `CLAUDE.md` | `claude` (Claude Code) |
| `codex`  | `AGENTS.md` | `codex` (OpenAI Codex) |
| `gemini` | `GEMINI.md` | `gemini` (Google Gemini CLI) |
