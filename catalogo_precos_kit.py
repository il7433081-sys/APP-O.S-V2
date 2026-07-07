"""Resolve preços de itens de kit no catálogo principal (peças e serviços)."""

from __future__ import annotations

import sqlite3
from typing import Any

from catalogo_pecas import (
    buscar_pecas_catalogo,
    normalizar_texto_busca,
    obter_peca_catalogo,
)
from catalogo_servicos import buscar_servicos_catalogo, obter_servico_catalogo


def _melhor_por_descricao(
    conn: sqlite3.Connection,
    descricao: str,
    *,
    tipo: str,
) -> dict[str, Any] | None:
    desc = (descricao or "").strip()
    if not desc:
        return None
    norm_alvo = normalizar_texto_busca(desc)
    if tipo == "servico":
        candidatos = buscar_servicos_catalogo(conn, desc, limite=8, incluir_preco=True)
    else:
        candidatos = buscar_pecas_catalogo(conn, desc, limite=8, incluir_preco=True)
    if not candidatos:
        return None
    for cand in candidatos:
        if normalizar_texto_busca(cand.get("descricao") or "") == norm_alvo:
            return cand
    for cand in candidatos:
        cand_norm = normalizar_texto_busca(cand.get("descricao") or "")
        if cand_norm.startswith(norm_alvo) or norm_alvo.startswith(cand_norm):
            return cand
    return candidatos[0]


def resolver_preco_item_catalogo(
    conn: sqlite3.Connection,
    item: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Retorna cópia do item com preço do catálogo e flag se encontrou."""
    tipo = str(item.get("tipo") or "peca").strip().lower()
    if tipo not in ("peca", "servico"):
        tipo = "peca"
    saida = dict(item)
    cat_id = item.get("catalogo_id")
    encontrado: dict[str, Any] | None = None
    if cat_id not in (None, "", 0):
        try:
            cid = int(cat_id)
        except (TypeError, ValueError):
            cid = 0
        if cid:
            if tipo == "servico":
                encontrado = obter_servico_catalogo(conn, cid, incluir_preco=True)
            else:
                encontrado = obter_peca_catalogo(conn, cid, incluir_preco=True)
    if encontrado is None:
        encontrado = _melhor_por_descricao(conn, str(item.get("descricao") or ""), tipo=tipo)
    if encontrado is None:
        return saida, False
    saida["catalogo_id"] = int(encontrado["id"])
    saida["descricao"] = str(encontrado.get("descricao") or saida.get("descricao") or "")
    saida["valor_unitario"] = round(float(encontrado.get("valor_unitario") or 0), 2)
    saida["tipo"] = tipo
    return saida, True


def atualizar_precos_itens_do_catalogo(
    conn: sqlite3.Connection,
    itens: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    saida: list[dict[str, Any]] = []
    atualizados = 0
    nao_encontrados: list[str] = []
    for bruto in itens or []:
        if not isinstance(bruto, dict):
            continue
        item, ok = resolver_preco_item_catalogo(conn, bruto)
        saida.append(item)
        if ok:
            atualizados += 1
        else:
            desc = str(item.get("descricao") or "").strip()
            if desc:
                nao_encontrados.append(desc)
    return saida, {
        "atualizados": atualizados,
        "total": len(saida),
        "nao_encontrados": nao_encontrados,
    }
