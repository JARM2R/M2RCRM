# -*- mode: python ; coding: utf-8 -*-
"""
M2R CRM — PyInstaller spec file
================================
Builds three executables into a single shared folder:
  - M2R CRM.exe          (main app, windowed)
  - CRM Contact Export.exe (export tool, windowed)
  - Analyze DB Schema.exe  (console utility)
"""

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Babel locale data is required by tkcalendar
babel_datas = collect_data_files('babel')

# ── Shared data / assets ────────────────────────────────────────────
added_files = [
    ('m2r_crm.ico',   '.'),
    ('M2RLogo.png',   '.'),
    ('m2r_crm.db',    '.'),
]

common_datas = added_files + babel_datas

hidden = [
    'babel.numbers',
    'babel.dates',
    'tkcalendar',
    'm2r_crm_invoice',
    'reportlab',
    'reportlab.pdfgen',
    'reportlab.pdfgen.canvas',
    'reportlab.lib.pagesizes',
    'reportlab.lib.units',
    'reportlab.lib.colors',
    'reportlab.lib.styles',
    'reportlab.platypus',
]

# ── Analysis for each entry point ───────────────────────────────────
a_main = Analysis(
    ['m2r_crm.py'],
    pathex=[],
    binaries=[],
    datas=common_datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

a_export = Analysis(
    ['crm_contact_export.py'],
    pathex=[],
    binaries=[],
    datas=common_datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

a_schema = Analysis(
    ['analyze_db_schema.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── Merge analyses so DLLs / packages are shared ───────────────────
MERGE(
    (a_main,   'M2R CRM',            'M2R CRM'),
    (a_export, 'CRM Contact Export',  'CRM Contact Export'),
    (a_schema, 'Analyze DB Schema',   'Analyze DB Schema'),
)

# ── PYZ archives ────────────────────────────────────────────────────
pyz_main   = PYZ(a_main.pure,   a_main.zipped_data,   cipher=block_cipher)
pyz_export = PYZ(a_export.pure, a_export.zipped_data, cipher=block_cipher)
pyz_schema = PYZ(a_schema.pure, a_schema.zipped_data, cipher=block_cipher)

# ── EXE definitions ────────────────────────────────────────────────
exe_main = EXE(
    pyz_main,
    a_main.scripts,
    [],
    exclude_binaries=True,
    name='M2R CRM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='m2r_crm.ico',
)

exe_export = EXE(
    pyz_export,
    a_export.scripts,
    [],
    exclude_binaries=True,
    name='CRM Contact Export',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='m2r_crm.ico',
)

exe_schema = EXE(
    pyz_schema,
    a_schema.scripts,
    [],
    exclude_binaries=True,
    name='Analyze DB Schema',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

# ── Collect everything into one folder ──────────────────────────────
coll = COLLECT(
    exe_main,   a_main.binaries,   a_main.zipfiles,   a_main.datas,
    exe_export, a_export.binaries, a_export.zipfiles, a_export.datas,
    exe_schema, a_schema.binaries, a_schema.zipfiles, a_schema.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='M2R CRM',
)
