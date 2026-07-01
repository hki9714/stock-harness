# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hidden_imports = [
    # uvicorn 내부 (동적 import 사용)
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.loops.asyncio", "uvicorn.protocols", "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan", "uvicorn.lifespan.on", "uvicorn.lifespan.off",
    "uvicorn.config", "uvicorn.main",
    # fastapi / starlette
    "fastapi", "fastapi.middleware.cors", "fastapi.staticfiles",
    "starlette", "starlette.routing", "starlette.staticfiles",
    "starlette.responses", "starlette.middleware", "starlette.middleware.cors",
    "anyio", "anyio._backends._asyncio", "anyio._backends._trio",
    "sniffio",
    # pykrx
    "pykrx", "pykrx.stock", "pykrx.website", "pykrx.website.krx",
    "pykrx.website.naver",
    # apscheduler
    "apscheduler", "apscheduler.schedulers", "apscheduler.schedulers.asyncio",
    "apscheduler.triggers", "apscheduler.triggers.interval",
    "apscheduler.triggers.cron", "apscheduler.triggers.date",
    # telegram
    "telegram", "telegram.ext", "telegram.ext._application",
    "telegram.ext._updater", "telegram.ext._jobqueue",
    "httpx", "httpcore",
    # data / parsing
    "bs4", "bs4.builder", "bs4.builder._lxml", "bs4.builder._html5lib",
    "bs4.builder._htmlparser",
    "lxml", "lxml.etree",
    "pandas", "pandas_ta",
    "aiofiles",
    # config
    "yaml", "dotenv", "pydantic", "pydantic_settings",
    # watchdog (git watcher)
    "watchdog", "watchdog.observers", "watchdog.observers.polling",
    "watchdog.events",
    # finance data reader
    "FinanceDataReader",
    # matplotlib (pykrx 내부 의존성)
    "matplotlib", "matplotlib.pyplot", "matplotlib.backends",
    "matplotlib.backends.backend_agg",
    # 기타
    "multiprocessing", "multiprocessing.pool",
    "email.mime.text", "email.mime.multipart",
]

datas = [
    ("static",              "static"),
    ("config.yaml.example", "."),
]
datas += collect_data_files("pykrx")
datas += collect_data_files("certifi")

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch", "transformers", "tensorflow", "keras",
        "sklearn", "cv2",
        "tkinter", "PyQt5", "wx",
        "jupyter", "IPython", "notebook",
        "test", "tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StockHarness",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # 로그 확인용 콘솔 유지
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="StockHarness",
)
