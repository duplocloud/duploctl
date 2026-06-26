#!/usr/bin/env pyinstaller
# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import copy_metadata

# Add all the resources as hidden imports
directory = 'src/duplo_resource'
hi =[
  'duplocloud.formats',
  'duplocloud.client',
  'duplo_resource',
  'duplo_resource.argo_client',
]
for filename in os.listdir(directory):
  if filename != '__init__.py' and not os.path.isdir(f"{directory}/{filename}"):
    m = filename.split('.')[0]
    hi.append(f'duplo_resource.{m}')

# Bundle package metadata so importlib.metadata.entry_points() works
md = copy_metadata('duplocloud-client')

a = Analysis(
    ['../src/duplocloud/cli.py'],
    pathex=[],
    binaries=[],
    datas=md,
    hiddenimports=hi,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='duploctl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
