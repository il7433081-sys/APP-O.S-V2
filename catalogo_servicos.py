"""Catálogo de serviços / M.O. da oficina (tabela catalogo no banco principal)."""

from __future__ import annotations

import sqlite3
from typing import Any

from catalogo_pecas import _formatar_moeda_br, _registrar_funcao_norm, normalizar_texto_busca


def _servico_para_dict(row: sqlite3.Row, *, incluir_preco: bool) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": int(row["id"]),
        "descricao": row["descricao"] or "",
        "codigo_exibicao": str(row["id"]),
        "gera_comissao": bool(int(row["gera_comissao"] or 0)),
    }
    if incluir_preco:
        vu = float(row["valor_unitario"] or 0)
        item["valor_unitario"] = vu
        item["valor_unitario_fmt"] = _formatar_moeda_br(vu)
    return item


def buscar_servicos_catalogo(
    conn: sqlite3.Connection,
    termo: str,
    *,
    limite: int = 12,
    incluir_preco: bool = False,
) -> list[dict[str, Any]]:
    termo = (termo or "").strip()
    if not termo:
        return []
    tn = f"%{normalizar_texto_busca(termo)}%"
    like = f"%{termo}%"
    limite = max(1, min(int(limite), 30))
    sql = """
        SELECT id, descricao, valor_unitario, COALESCE(gera_comissao, 1) AS gera_comissao
        FROM catalogo
        WHERE categoria = 'SERVIÇO'
          AND (
                NORM(descricao) LIKE ?
             OR descricao LIKE ?
             OR CAST(id AS TEXT) LIKE ?
          )
        ORDER BY
            CASE WHEN NORM(descricao) LIKE ? THEN 0 ELSE 1 END,
            descricao
        LIMIT ?
    """
    prefixo = f"{tn}"
    params = (tn, like, f"{termo}%", prefixo, limite)
    _registrar_funcao_norm(conn)
    rows = conn.execute(sql, params).fetchall()
    return [_servico_para_dict(r, incluir_preco=incluir_preco) for r in rows]


def obter_servico_catalogo(
    conn: sqlite3.Connection,
    catalogo_id: int,
    *,
    incluir_preco: bool = True,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, descricao, valor_unitario, COALESCE(gera_comissao, 1) AS gera_comissao
        FROM catalogo
        WHERE id = ? AND categoria = 'SERVIÇO'
        """,
        (int(catalogo_id),),
    ).fetchone()
    if row is None:
        return None
    return _servico_para_dict(row, incluir_preco=incluir_preco)


def inserir_servico_catalogo(
    conn: sqlite3.Connection,
    *,
    descricao: str,
    valor_unitario: float,
    gera_comissao: bool = True,
) -> int:
    desc = (descricao or "").strip()
    if not desc:
        raise ValueError("Informe a descrição do serviço.")
    vu = float(valor_unitario)
    if vu < 0:
        raise ValueError("Valor unitário não pode ser negativo.")
    gera = 1 if gera_comissao else 0
    cur = conn.execute(
        """
        INSERT INTO catalogo (
            categoria, tipo, codigo_barras, descricao, valor_unitario, gera_comissao
        )
        VALUES ('SERVIÇO', 'Serviço', NULL, ?, ?, ?)
        """,
        (desc, vu, gera),
    )
    return int(cur.lastrowid)


def atualizar_servico_catalogo(
    conn: sqlite3.Connection,
    catalogo_id: int,
    *,
    descricao: str,
    valor_unitario: float,
    gera_comissao: bool = True,
) -> None:
    desc = (descricao or "").strip()
    if not desc:
        raise ValueError("Informe a descrição do serviço.")
    vu = float(valor_unitario)
    if vu < 0:
        raise ValueError("Valor unitário não pode ser negativo.")
    gera = 1 if gera_comissao else 0
    cur = conn.execute(
        """
        UPDATE catalogo
        SET descricao = ?, valor_unitario = ?, gera_comissao = ?
        WHERE id = ? AND categoria = 'SERVIÇO'
        """,
        (desc, vu, gera, int(catalogo_id)),
    )
    if cur.rowcount == 0:
        raise ValueError("Serviço não encontrado no cadastro da oficina.")
