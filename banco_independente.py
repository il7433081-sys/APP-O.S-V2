"""Banco SQLite independente para o App O.S. (sem Sistema Oficina)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ambiente_teste import iniciar_schema_banco_app


def garantir_banco_independente(caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(caminho, timeout=30)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_DDL_BASE)
        iniciar_schema_banco_app(conn)
        _garantir_empresa_config(conn)
        _garantir_app_os_config(conn)
        conn.commit()
    finally:
        conn.close()


_DDL_BASE = """
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    telefone TEXT,
    celular TEXT,
    email TEXT,
    cpf_cnpj TEXT,
    rg TEXT,
    endereco TEXT,
    numero TEXT,
    bairro TEXT,
    cidade TEXT,
    estado TEXT,
    cep TEXT,
    observacoes TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS motores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    chassi TEXT,
    horas REAL NOT NULL DEFAULT 0,
    marca_modelo TEXT,
    embarcacao TEXT,
    observacoes TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mecanicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS servicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    motor_id INTEGER NOT NULL,
    mecanico_id INTEGER,
    entrada TEXT,
    saida TEXT,
    horas_servico REAL,
    responsavel TEXT,
    mo REAL,
    garantia TEXT,
    situacao TEXT NOT NULL DEFAULT 'aberto',
    is_pre_orcamento INTEGER NOT NULL DEFAULT 0,
    numero_pre_orcamento INTEGER NOT NULL DEFAULT 0,
    is_teste INTEGER NOT NULL DEFAULT 0,
    numero_teste INTEGER NOT NULL DEFAULT 0,
    pago INTEGER NOT NULL DEFAULT 0,
    status_pagamento_detalhado TEXT NOT NULL DEFAULT 'Nao',
    valor_pago_parcial REAL NOT NULL DEFAULT 0,
    digitalizado INTEGER NOT NULL DEFAULT 0,
    descricao TEXT,
    alegacao_cliente TEXT,
    relato_mecanico TEXT,
    laudo_tecnico TEXT,
    servico_efetuado TEXT,
    detalhamento_tecnico TEXT,
    nota_tecnica TEXT,
    embedding_json TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (motor_id) REFERENCES motores(id) ON DELETE CASCADE,
    FOREIGN KEY (mecanico_id) REFERENCES mecanicos(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS catalogo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT NOT NULL DEFAULT 'SERVICO',
    tipo TEXT NOT NULL,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL DEFAULT 0,
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


def _garantir_empresa_config(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS empresa_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nome TEXT,
            razao_social TEXT,
            nome_fantasia TEXT,
            cnpj TEXT,
            endereco TEXT,
            telefone TEXT,
            email TEXT,
            exigir_login INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    row = conn.execute("SELECT id FROM empresa_config WHERE id = 1").fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO empresa_config (
                id, nome, razao_social, nome_fantasia, endereco, telefone, email, exigir_login
            ) VALUES (1, 'Oficina Nautica', 'Oficina Nautica', 'Oficina Nautica', '', '', '', 1)
            """
        )


def _garantir_app_os_config(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_os_config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
        """
    )
