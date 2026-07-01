"""
Stock Harness launcher (PyInstaller exe entry point)
"""
import os
import sys
import shutil
import traceback
import webbrowser
import threading
import time

# Windows console UTF-8 (prevent UnicodeEncodeError crash)
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── path setup ───────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR   = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
    os.chdir(BASE_DIR)
    # _internal/ 안의 번들 모듈을 import할 수 있도록 경로 추가
    sys.path.insert(0, BUNDLE_DIR)
    sys.path.insert(0, BASE_DIR)
else:
    BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

CONFIG_PATH  = os.path.join(BASE_DIR,   "config.yaml")
EXAMPLE_PATH = os.path.join(BUNDLE_DIR, "config.yaml.example")
LOG_DIR      = os.path.join(BASE_DIR,   "logs")
ERROR_LOG    = os.path.join(BASE_DIR,   "error.log")

BANNER = """
==================================================
  Stock Harness v1.0
  Korean Stock Monitor + Telegram Alert
==================================================
"""


def load_config_to_env() -> bool:
    """config.yaml을 읽어 환경변수로 주입 (bootstrap.py 없이 pydantic-settings가 읽도록)"""
    try:
        import yaml
    except ImportError:
        print("  [ERROR] yaml module not found.")
        return False

    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"  [ERROR] Failed to read config.yaml: {e}")
        return False

    tg = cfg.get("telegram", {})
    os.environ["TELEGRAM_BOT_TOKEN"] = str(tg.get("bot_token", ""))
    os.environ["TELEGRAM_CHAT_ID"]   = str(tg.get("chat_id", ""))

    stock = cfg.get("stock", {})
    watch = stock.get("watch_list", ["005930", "000660"])
    os.environ["WATCH_LIST"]                    = ",".join(str(c) for c in watch)
    os.environ["VOLUME_SURGE_RATIO"]            = str(stock.get("volume_surge_ratio", 3.0))
    os.environ["PRICE_SURGE_PCT"]               = str(stock.get("price_surge_pct", 5.0))
    os.environ["PRICE_DROP_PCT"]                = str(stock.get("price_drop_pct", 5.0))
    os.environ["CHECK_INTERVAL_MINUTES"]        = str(stock.get("check_interval_minutes", 30))
    os.environ["SENTIMENT_POSITIVE_THRESHOLD"]  = str(stock.get("sentiment_positive_threshold", 0.65))
    os.environ["SENTIMENT_SURGE_COUNT"]         = str(stock.get("sentiment_surge_count", 20))

    ai = cfg.get("ai", {})
    os.environ["ANTHROPIC_API_KEY"] = str(ai.get("anthropic_api_key", ""))
    os.environ["DEFAULT_PROVIDER"]  = str(ai.get("default_provider", "claude"))
    os.environ["DEFAULT_MODEL"]     = str(ai.get("default_model", "claude-sonnet-4-6"))

    os.environ["RUNTIME"]          = str(cfg.get("runtime", "local"))
    os.environ["GIT_AUTO_COMMIT"]  = "false"  # exe 환경에서는 항상 비활성

    return True


def check_config() -> bool:
    if os.path.exists(CONFIG_PATH):
        return True

    if os.path.exists(EXAMPLE_PATH):
        shutil.copy(EXAMPLE_PATH, CONFIG_PATH)
    else:
        print("  [ERROR] config.yaml.example not found.")
        input("  Press Enter to exit.")
        return False

    print("  [First Run] Setup required.")
    print()
    print("  config.yaml will open in Notepad.")
    print("  Fill in your Telegram bot_token and chat_id,")
    print("  then Save and close Notepad.")
    print()
    input("  Press Enter to open config.yaml ... ")
    os.startfile(CONFIG_PATH)
    print()
    input("  After saving, press Enter to start the server ... ")
    print()
    return True


def open_browser(delay: float = 4.0):
    time.sleep(delay)
    webbrowser.open("http://localhost:8000")


def main():
    print(BANNER)

    if not check_config():
        sys.exit(1)

    os.makedirs(LOG_DIR, exist_ok=True)

    if not load_config_to_env():
        input("  Press Enter to exit.")
        sys.exit(1)

    # 플레이스홀더 값 그대로면 시작 전에 경고
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token or token == "your_bot_token_here":
        print()
        print("  [WARNING] Telegram bot_token is not set in config.yaml.")
        print(f"  Please edit: {CONFIG_PATH}")
        print()
        os.startfile(CONFIG_PATH)
        input("  After filling in the token, press Enter to retry ... ")
        if not load_config_to_env():
            sys.exit(1)

    print("  Starting server...")
    print("  URL   : http://localhost:8000")
    print("  Stop  : Close this window or Ctrl+C")
    print()

    threading.Thread(target=open_browser, daemon=True).start()

    # 문자열 방식("main:app")은 frozen exe에서 모듈을 못 찾을 수 있어
    # 직접 import 후 app 객체를 전달
    from main import app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        err = traceback.format_exc()
        print("\n[ERROR]", e)
        print(err)
        # 에러 내용을 파일로도 저장
        try:
            with open(ERROR_LOG, "w", encoding="utf-8") as f:
                f.write(err)
            print(f"\nError details saved to: {ERROR_LOG}")
        except Exception:
            pass
        input("\nPress Enter to exit.")
