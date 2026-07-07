"""Ambiente de treinamento por usuário (sandbox compartilhado, separado do teste global do admin)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ambiente_teste import garantir_banco_teste, iniciar_schema_banco_app, limpar_dados_app, resumo_banco_app

CHAVE_LIBERADO_TODOS = "sandbox_treinamento_liberado_todos"


def caminho_banco_sandbox_treinamento(app_dir: Path) -> Path:
    pasta = app_dir / "dados"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / "app_os_sandbox_treinamento.db"


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _init_app_os_config(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_os_config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
        """
    )


def init_sandbox_treinamento_tabelas(conn: sqlite3.Connection) -> None:
    """Tabelas de controle no banco principal."""
    _init_app_os_config(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sandbox_treinamento_sessao (
            usuario_id INTEGER PRIMARY KEY,
            ativo INTEGER NOT NULL DEFAULT 0,
            ativado_em TEXT,
            forcado_admin INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
        """
    )
    sess_cols = {r[1] for r in conn.execute("PRAGMA table_info(sandbox_treinamento_sessao)").fetchall()}
    if "forcado_admin" not in sess_cols:
        conn.execute(
            "ALTER TABLE sandbox_treinamento_sessao "
            "ADD COLUMN forcado_admin INTEGER NOT NULL DEFAULT 0"
        )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()}
    if "permissao_sandbox_treinamento" not in cols:
        conn.execute(
            "ALTER TABLE usuarios ADD COLUMN permissao_sandbox_treinamento INTEGER NOT NULL DEFAULT 0"
        )
    pres_cols = {r[1] for r in conn.execute("PRAGMA table_info(presenca_usuario)").fetchall()}
    if pres_cols and "sandbox_treinamento_ativo" not in pres_cols:
        conn.execute(
            "ALTER TABLE presenca_usuario ADD COLUMN sandbox_treinamento_ativo INTEGER NOT NULL DEFAULT 0"
        )


def _config_bool(valor: Any, *, padrao: bool = False) -> bool:
    if isinstance(valor, bool):
        return valor
    return str(valor or "").strip().lower() in ("1", "true", "sim", "yes", "on")


def ler_liberado_todos(conn: sqlite3.Connection) -> bool:
    init_sandbox_treinamento_tabelas(conn)
    row = conn.execute(
        "SELECT valor FROM app_os_config WHERE chave = ?",
        (CHAVE_LIBERADO_TODOS,),
    ).fetchone()
    if row is None:
        return False
    return _config_bool(row["valor"], padrao=False)


def salvar_liberado_todos(conn: sqlite3.Connection, ativo: bool) -> None:
    init_sandbox_treinamento_tabelas(conn)
    conn.execute(
        "INSERT OR REPLACE INTO app_os_config (chave, valor) VALUES (?, ?)",
        (CHAVE_LIBERADO_TODOS, "1" if ativo else "0"),
    )


def usuario_pode_usar_sandbox(
    usuario: dict[str, Any] | None,
    *,
    liberado_todos: bool,
) -> bool:
    if not usuario:
        return False
    perfil = str(usuario.get("perfil") or "").strip().lower()
    permitido = bool(usuario.get("permissao_sandbox_treinamento"))
    if perfil == "admin":
        return permitido
    if liberado_todos:
        return True
    return permitido


def registrar_sessao_ativa(
    conn: sqlite3.Connection,
    usuario_id: int,
    *,
    forcado_admin: bool = False,
) -> None:
    init_sandbox_treinamento_tabelas(conn)
    agora = _agora()
    conn.execute(
        """
        INSERT INTO sandbox_treinamento_sessao (usuario_id, ativo, ativado_em, forcado_admin)
        VALUES (?, 1, ?, ?)
        ON CONFLICT(usuario_id) DO UPDATE SET
            ativo = 1,
            ativado_em = excluded.ativado_em,
            forcado_admin = excluded.forcado_admin
        """,
        (int(usuario_id), agora, 1 if forcado_admin else 0),
    )


def registrar_sessao_inativa(conn: sqlite3.Connection, usuario_id: int) -> None:
    init_sandbox_treinamento_tabelas(conn)
    conn.execute(
        """
        INSERT INTO sandbox_treinamento_sessao (usuario_id, ativo, ativado_em, forcado_admin)
        VALUES (?, 0, NULL, 0)
        ON CONFLICT(usuario_id) DO UPDATE SET
            ativo = 0,
            ativado_em = NULL,
            forcado_admin = 0
        """,
        (int(usuario_id),),
    )


def sessao_sandbox_usuario(conn: sqlite3.Connection, usuario_id: int) -> dict[str, Any]:
    init_sandbox_treinamento_tabelas(conn)
    row = conn.execute(
        """
        SELECT ativo, forcado_admin, ativado_em
        FROM sandbox_treinamento_sessao
        WHERE usuario_id = ?
        """,
        (int(usuario_id),),
    ).fetchone()
    if row is None:
        return {"ativo": False, "forcado_admin": False, "ativado_em": ""}
    return {
        "ativo": _config_bool(row["ativo"]),
        "forcado_admin": _config_bool(row["forcado_admin"]),
        "ativado_em": row["ativado_em"] or "",
    }


def _ids_usuarios_ativos_nao_admin(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        """
        SELECT id FROM usuarios
        WHERE ativo = 1 AND perfil != 'admin'
        ORDER BY id
        """
    ).fetchall()
    return [int(r["id"]) for r in rows]


def ativar_sandbox_usuarios(
    conn: sqlite3.Connection,
    usuario_ids: list[int],
    *,
    forcado_admin: bool = True,
) -> int:
    total = 0
    for uid in usuario_ids:
        row = conn.execute(
            "SELECT id FROM usuarios WHERE id = ? AND ativo = 1",
            (int(uid),),
        ).fetchone()
        if row is None:
            continue
        registrar_sessao_ativa(conn, int(uid), forcado_admin=forcado_admin)
        total += 1
    return total


def desativar_sandbox_usuarios(conn: sqlite3.Connection, usuario_ids: list[int]) -> int:
    total = 0
    for uid in usuario_ids:
        row = conn.execute(
            "SELECT id FROM usuarios WHERE id = ?",
            (int(uid),),
        ).fetchone()
        if row is None:
            continue
        registrar_sessao_inativa(conn, int(uid))
        total += 1
    return total


def ativar_sandbox_todos(conn: sqlite3.Connection, *, forcado_admin: bool = True) -> int:
    return ativar_sandbox_usuarios(
        conn,
        _ids_usuarios_ativos_nao_admin(conn),
        forcado_admin=forcado_admin,
    )


def desativar_sandbox_todos(conn: sqlite3.Connection) -> int:
    return desativar_sandbox_usuarios(conn, _ids_usuarios_ativos_nao_admin(conn))


def listar_usuarios_sandbox_admin(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    init_sandbox_treinamento_tabelas(conn)
    rows = conn.execute(
        """
        SELECT u.id, u.usuario, u.nome_exibicao, u.perfil, u.ativo,
               u.permissao_sandbox_treinamento,
               s.ativo AS sandbox_ativo, s.ativado_em, s.forcado_admin AS sandbox_forcado_admin,
               p.atualizado_em AS presenca_em,
               p.modulo, p.aba, p.contexto
        FROM usuarios u
        LEFT JOIN sandbox_treinamento_sessao s ON s.usuario_id = u.id
        LEFT JOIN presenca_usuario p ON p.usuario_id = u.id
        WHERE u.ativo = 1
        ORDER BY u.nome_exibicao COLLATE NOCASE, u.usuario COLLATE NOCASE
        """
    ).fetchall()
    saida: list[dict[str, Any]] = []
    for row in rows:
        saida.append({
            "id": int(row["id"]),
            "usuario": row["usuario"] or "",
            "nome_exibicao": row["nome_exibicao"] or row["usuario"] or "",
            "perfil": row["perfil"] or "",
            "permissao_sandbox_treinamento": _config_bool(row["permissao_sandbox_treinamento"]),
            "sandbox_ativo": _config_bool(row["sandbox_ativo"]),
            "sandbox_forcado_admin": _config_bool(row["sandbox_forcado_admin"]),
            "sandbox_ativado_em": row["ativado_em"] or "",
            "presenca_em": row["presenca_em"] or "",
            "modulo": row["modulo"] or "",
            "aba": row["aba"] or "",
            "contexto": row["contexto"] or "",
        })
    return saida


def garantir_banco_sandbox(caminho: Path) -> None:
    garantir_banco_teste(caminho)


def limpar_banco_sandbox(caminho: Path) -> dict[str, int]:
    garantir_banco_sandbox(caminho)
    conn = sqlite3.connect(caminho, timeout=30)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        iniciar_schema_banco_app(conn)
        removidos = limpar_dados_app(conn)
        conn.commit()
        return removidos
    finally:
        conn.close()


def resumo_banco_sandbox(caminho: Path) -> dict[str, Any]:
    if not caminho.is_file():
        return {}
    conn = sqlite3.connect(caminho, timeout=30)
    try:
        conn.row_factory = sqlite3.Row
        iniciar_schema_banco_app(conn)
        return resumo_banco_app(conn)
    finally:
        conn.close()
