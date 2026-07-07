"""Banco separado para testes do app O.S. (O.S., requisições, checklist, assinaturas)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Callable

from checklist_revisao import init_checklist_tabelas
from fluxo_requisicoes import init_fluxo_tabelas
from os_fotos_mecanico import init_os_fotos_tabelas
from req_precondicoes_os import init_req_precondicoes_tabelas

TABELAS_DADOS_APP = (
    "os_fotos_item",
    "os_fotos_envio",
    "os_req_precondicoes",
    "requisicoes_material",
    "checklists_revisao",
    "assinaturas_remotas",
    "ordens_servico",
)


def caminho_banco_teste(app_dir: Path) -> Path:
    pasta = app_dir / "dados"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / "app_os_ambiente_teste.db"


def _ddl_ordens_servico() -> str:
    return """
    CREATE TABLE IF NOT EXISTS ordens_servico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_os INTEGER NOT NULL UNIQUE,
        data_entrada TEXT,
        nome_atendente TEXT,
        cliente_id INTEGER,
        cliente_nome TEXT,
        cliente_cpf_cnpj TEXT,
        status TEXT NOT NULL DEFAULT 'aberto',
        assinatura_tecnico TEXT,
        assinatura_cliente TEXT,
        mecanico_id INTEGER,
        mecanico_nome TEXT,
        dados_json TEXT NOT NULL,
        criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        atualizado_em TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_ordens_servico_numero ON ordens_servico(numero_os);
    CREATE INDEX IF NOT EXISTS idx_ordens_servico_cliente ON ordens_servico(cliente_id);
    """


def _ddl_assinaturas_remotas() -> str:
    return """
    CREATE TABLE IF NOT EXISTS assinaturas_remotas (
        token TEXT PRIMARY KEY,
        tipo TEXT NOT NULL,
        canvas_id TEXT,
        numero_os INTEGER,
        cliente_nome TEXT,
        titulo TEXT NOT NULL,
        imagem TEXT,
        status TEXT NOT NULL DEFAULT 'pendente',
        criado_em TEXT NOT NULL,
        expira_em TEXT NOT NULL,
        assinado_em TEXT,
        pin TEXT,
        assinante_nome TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_assin_remota_os ON assinaturas_remotas(numero_os);
    CREATE INDEX IF NOT EXISTS idx_assin_remota_status ON assinaturas_remotas(status);
    """


def _migrar_ordens_servico(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(ordens_servico)").fetchall()}
    if "assinatura_tecnico" not in cols:
        conn.execute("ALTER TABLE ordens_servico ADD COLUMN assinatura_tecnico TEXT")
    if "assinatura_cliente" not in cols:
        conn.execute("ALTER TABLE ordens_servico ADD COLUMN assinatura_cliente TEXT")
    if "mecanico_id" not in cols:
        conn.execute("ALTER TABLE ordens_servico ADD COLUMN mecanico_id INTEGER")
    if "mecanico_nome" not in cols:
        conn.execute("ALTER TABLE ordens_servico ADD COLUMN mecanico_nome TEXT")


def _migrar_assinaturas(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(assinaturas_remotas)")}
    if "pin" not in cols:
        conn.execute("ALTER TABLE assinaturas_remotas ADD COLUMN pin TEXT")
    if "assinante_nome" not in cols:
        conn.execute("ALTER TABLE assinaturas_remotas ADD COLUMN assinante_nome TEXT")


def iniciar_schema_banco_app(conn: sqlite3.Connection) -> None:
    """Cria tabelas de O.S. / fluxo no banco ativo (produção ou teste)."""
    conn.executescript(_ddl_ordens_servico())
    _migrar_ordens_servico(conn)
    init_fluxo_tabelas(conn)
    init_checklist_tabelas(conn)
    init_os_fotos_tabelas(conn)
    init_req_precondicoes_tabelas(conn)
    conn.executescript(_ddl_assinaturas_remotas())
    _migrar_assinaturas(conn)


def garantir_banco_teste(caminho: Path) -> None:
    if not caminho.parent.is_dir():
        caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(caminho, timeout=30)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        iniciar_schema_banco_app(conn)
        conn.commit()
    finally:
        conn.close()


def limpar_dados_app(conn: sqlite3.Connection) -> dict[str, int]:
    """Remove O.S., requisições, checklist e assinaturas do banco informado."""
    removidos: dict[str, int] = {}
    for tabela in TABELAS_DADOS_APP:
        try:
            antes = conn.execute(f"SELECT COUNT(*) AS n FROM {tabela}").fetchone()
            total = int(antes["n"]) if antes else 0
            if total:
                conn.execute(f"DELETE FROM {tabela}")
            removidos[tabela] = total
        except sqlite3.Error:
            removidos[tabela] = 0
    for tabela in TABELAS_DADOS_APP:
        try:
            conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (tabela,))
        except sqlite3.Error:
            pass
    return removidos


def resumo_banco_app(conn: sqlite3.Connection) -> dict[str, Any]:
    resumo: dict[str, int] = {}
    for tabela in TABELAS_DADOS_APP:
        try:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {tabela}").fetchone()
            resumo[tabela] = int(row["n"]) if row else 0
        except sqlite3.Error:
            resumo[tabela] = 0
    return resumo
