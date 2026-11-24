# -*- mode: python ; coding: utf-8 -*-

excludes = [
    'debugpy', 'IPython', 'ipykernel', 'jupyter_client', 'jupyter_core', 'nbformat',
    'numpy', 'matplotlib', 'PIL', 'PySide6', 'shiboken6', 'tkinter',
    'tornado', 'zmq', 'pygments', 'prompt_toolkit', 'jedi', 'parso', 'traitlets',
    'pyparsing', 'jinja2', 'contourpy', 'kiwisolver', 'cycler',
    'cryptography', 'bcrypt', 'chardet', 'charset_normalizer',
    'requests', 'urllib3', 'certifi', 'idna',
    'jsonschema', 'referencing', 'rpds', 'attrs', 'arrow', 'dateutil', 'isoduration',
    'jsonschema_specifications', 'mdurl', 'markdown_it', 'rich', 'lark',
    'fqdn', 'fastjsonschema', 'webcolors', 'rfc3987_syntax', 'uri_template',
    'simplejson', 'psutil', 'packaging',
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('static', 'static')],
    hiddenimports=['uvicorn.logging', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='获奖管理系统-单人版',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='获奖管理系统-单人版',
)