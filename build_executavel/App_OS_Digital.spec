# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller para o inicializador do App O.S."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
spec_dir = Path(SPEC).resolve().parent
src = spec_dir.parent
icon_exe = spec_dir / "icone_os_digital.ico"

flask_datas, flask_bins, flask_hidden = collect_all("flask")
jinja_datas, jinja_bins, jinja_hidden = collect_all("jinja2")
werk_datas, werk_bins, werk_hidden = collect_all("werkzeug")

local_modules = [
    "app",
    "config_app_os",
    "seguranca_app_os",
    "banco_independente",
    "agendamentos",
    "pre_orcamentos",
    "catalogo_precos_kit",
    "pdf_pre_orcamento",
    "ambiente_teste",
    "atividade_log",
    "catalogo_pecas",
    "catalogo_servicos",
    "checklist_revisao",
    "estoque",
    "fluxo_requisicoes",
    "fotos_os_config",
    "nav_pos_acao_config",
    "notificacoes_aparelho_config",
    "os_fotos_mecanico",
    "os_lista_personalizacao",
    "pdf_checklist_revisao",
    "pdf_os",
    "pdf_os_fotos",
    "permissoes_arvore_os",
    "presenca_telespectador",
    "req_precondicoes_os",
    "sandbox_treinamento",
    "sync_oficina_servicos",
    "painel_suporte",
]

project_datas = [
    (str(src / "templates"), "templates"),
    (str(src / "static"), "static"),
    (str(src / "assets"), "assets"),
    (str(spec_dir / "icone_os_digital.ico"), "."),
    (str(spec_dir / "painel_suporte.py"), "."),
]

a = Analysis(
    [str(spec_dir / "launcher.py")],
    pathex=[str(src), str(spec_dir)],
    binaries=flask_bins + jinja_bins + werk_bins,
    datas=project_datas + flask_datas + jinja_datas + werk_datas,
    hiddenimports=local_modules + flask_hidden + jinja_hidden + werk_hidden + collect_submodules("PIL"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "matplotlib", "numpy", "pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="App_OS_Digital",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_exe) if icon_exe.is_file() else None,
)
