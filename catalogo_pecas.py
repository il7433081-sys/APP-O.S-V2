"""Catálogo de peças da oficina (tabela catalogo no banco principal)."""

from __future__ import annotations

import sqlite3
import unicodedata
from typing import Any


def normalizar_texto_busca(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", texto or "")
    sem_acentos = "".join(ch for ch in sem_acentos if not unicodedata.combining(ch))
    return sem_acentos.casefold()


def _registrar_funcao_norm(conn: sqlite3.Connection) -> None:
    conn.create_function("NORM", 1, normalizar_texto_busca, deterministic=True)


def _formatar_moeda_br(valor: float) -> str:
    txt = f"{float(valor):,.2f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def parse_valor_moeda_br(texto: str) -> float:
    t = (texto or "").strip()
    if not t:
        return 0.0
    t = t.replace("R$", "").replace(" ", "").strip()
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    return float(t)


def _peca_para_dict(row: sqlite3.Row, *, incluir_preco: bool) -> dict[str, Any]:
    codigo = (row["codigo_barras"] or "").strip() or str(row["id"])
    item: dict[str, Any] = {
        "id": int(row["id"]),
        "descricao": row["descricao"] or "",
        "codigo_barras": (row["codigo_barras"] or "").strip(),
        "codigo_exibicao": codigo,
    }
    if incluir_preco:
        vu = float(row["valor_unitario"] or 0)
        item["valor_unitario"] = vu
        item["valor_unitario_fmt"] = _formatar_moeda_br(vu)
    return item


def buscar_pecas_catalogo(
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
        SELECT id, descricao, valor_unitario, COALESCE(codigo_barras, '') AS codigo_barras
        FROM catalogo
        WHERE categoria = 'PEÇA'
          AND (
                NORM(descricao) LIKE ?
             OR NORM(IFNULL(codigo_barras, '')) LIKE ?
             OR descricao LIKE ?
             OR CAST(id AS TEXT) LIKE ?
          )
        ORDER BY
            CASE
                WHEN NORM(descricao) LIKE ? THEN 0
                WHEN NORM(IFNULL(codigo_barras, '')) LIKE ? THEN 1
                ELSE 2
            END,
            descricao
        LIMIT ?
    """
    prefixo = f"{tn}"
    params = (tn, tn, like, f"{termo}%", prefixo, prefixo, limite)
    _registrar_funcao_norm(conn)
    rows = conn.execute(sql, params).fetchall()
    return [_peca_para_dict(r, incluir_preco=incluir_preco) for r in rows]


def obter_peca_catalogo(
    conn: sqlite3.Connection,
    catalogo_id: int,
    *,
    incluir_preco: bool = True,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, descricao, valor_unitario, COALESCE(codigo_barras, '') AS codigo_barras
        FROM catalogo
        WHERE id = ? AND categoria = 'PEÇA'
        """,
        (int(catalogo_id),),
    ).fetchone()
    if row is None:
        return None
    return _peca_para_dict(row, incluir_preco=incluir_preco)


def inserir_peca_catalogo(
    conn: sqlite3.Connection,
    *,
    descricao: str,
    valor_unitario: float,
    codigo_barras: str = "",
) -> int:
    desc = (descricao or "").strip()
    if not desc:
        raise ValueError("Informe a descrição da peça.")
    vu = float(valor_unitario)
    if vu < 0:
        raise ValueError("Valor unitário não pode ser negativo.")
    cod = (codigo_barras or "").strip() or None
    cur = conn.execute(
        """
        INSERT INTO catalogo (
            categoria, tipo, codigo_barras, descricao, valor_unitario, gera_comissao
        )
        VALUES ('PEÇA', 'Peça', ?, ?, ?, 0)
        """,
        (cod, desc, vu),
    )
    return int(cur.lastrowid)


def atualizar_peca_catalogo(
    conn: sqlite3.Connection,
    catalogo_id: int,
    *,
    descricao: str,
    valor_unitario: float,
    codigo_barras: str = "",
) -> None:
    desc = (descricao or "").strip()
    if not desc:
        raise ValueError("Informe a descrição da peça.")
    vu = float(valor_unitario)
    if vu < 0:
        raise ValueError("Valor unitário não pode ser negativo.")
    cod = (codigo_barras or "").strip() or None
    cur = conn.execute(
        """
        UPDATE catalogo
        SET descricao = ?, valor_unitario = ?, codigo_barras = ?
        WHERE id = ? AND categoria = 'PEÇA'
        """,
        (desc, vu, cod, int(catalogo_id)),
    )
    if cur.rowcount == 0:
        raise ValueError("Peça não encontrada no cadastro da oficina.")
