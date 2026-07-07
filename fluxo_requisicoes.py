"""Requisições de material e indicadores do fluxo O.S. (v2.8+)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Any, Callable

_STATUS_REQUISICAO = frozenset({
    "rascunho",
    "aguardando_responsavel",
    "alterada_mecanico",
    "respondida",
    "alterada_responsavel",
    "aprovada",
    "finalizada",
})

_STATUS_OS_SERVICO_ENTREGUE = frozenset({"entregue", "fechado", "concluido"})


def _os_servico_entregue(os_status: str | None) -> bool:
    return str(os_status or "").strip().lower() in _STATUS_OS_SERVICO_ENTREGUE


def _mapa_status_os(conn: sqlite3.Connection, numeros_os: set[int]) -> dict[int, str]:
    if not numeros_os:
        return {}
    placeholders = ",".join("?" * len(numeros_os))
    rows = conn.execute(
        f"SELECT numero_os, status FROM ordens_servico WHERE numero_os IN ({placeholders})",
        tuple(sorted(numeros_os)),
    ).fetchall()
    return {int(r["numero_os"]): str(r["status"] or "") for r in rows}

_STATUS_OS_FLUXO = frozenset({
    "aberto",
    "em_servico",
    "aguardando_pecas",
    "aguardando_garantia",
    "aguardando_retifica",
    "pronto_mecanico",
    "cliente_avisado",
    "entregue",
    "aprovado_orcamento",
    "fechado",
    "cancelado",
    "concluido",
})

from os_lista_personalizacao import (
    carregar_pausas_tipos,
    meta_pausa_por_status,
    os_status_em_pausa_config,
    slug_de_status_pausa,
    status_pausa_de_slug,
    _normalizar_slug,
)


def init_fluxo_tabelas(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS requisicoes_material (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_os INTEGER NOT NULL DEFAULT 0,
            mecanico_id INTEGER NOT NULL,
            mecanico_nome TEXT,
            itens_json TEXT NOT NULL DEFAULT '[]',
            observacao TEXT,
            status TEXT NOT NULL DEFAULT 'rascunho',
            ultima_acao_por TEXT NOT NULL DEFAULT 'mecanico',
            visto_responsavel INTEGER NOT NULL DEFAULT 0,
            visto_mecanico INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            atualizado_em TEXT,
            enviada_em TEXT,
            respondida_em TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_req_mat_os ON requisicoes_material(numero_os);
        CREATE INDEX IF NOT EXISTS idx_req_mat_mec ON requisicoes_material(mecanico_id);
        CREATE INDEX IF NOT EXISTS idx_req_mat_status ON requisicoes_material(status);
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(requisicoes_material)").fetchall()}
    if "salvo_rascunho_em" not in cols:
        conn.execute("ALTER TABLE requisicoes_material ADD COLUMN salvo_rascunho_em TEXT")
    if "itens_rascunho_json" not in cols:
        conn.execute("ALTER TABLE requisicoes_material ADD COLUMN itens_rascunho_json TEXT")
    if "observacao_rascunho" not in cols:
        conn.execute("ALTER TABLE requisicoes_material ADD COLUMN observacao_rascunho TEXT")
    if "tipo_requisicao" not in cols:
        conn.execute(
            "ALTER TABLE requisicoes_material ADD COLUMN tipo_requisicao TEXT NOT NULL DEFAULT 'os'"
        )
    if "visto_mecanico_liberacao" not in cols:
        conn.execute(
            "ALTER TABLE requisicoes_material ADD COLUMN visto_mecanico_liberacao INTEGER NOT NULL DEFAULT 1"
        )
    if "liberacao_em" not in cols:
        conn.execute("ALTER TABLE requisicoes_material ADD COLUMN liberacao_em TEXT")
    if "alteracoes_mecanico_json" not in cols:
        conn.execute("ALTER TABLE requisicoes_material ADD COLUMN alteracoes_mecanico_json TEXT")
    if "titulo" not in cols:
        conn.execute("ALTER TABLE requisicoes_material ADD COLUMN titulo TEXT")
    if "publicada_oficina" not in cols:
        conn.execute(
            "ALTER TABLE requisicoes_material ADD COLUMN publicada_oficina INTEGER NOT NULL DEFAULT 0"
        )


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_STATUS_ITEM = frozenset({"ativo", "novo", "excluir_pendente", "excluido"})


def _chave_conteudo_item(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("descricao") or "").strip().lower(),
        str(item.get("quantidade") or "").strip().lower(),
    )


def _tipo_item_valido(tipo: str | None) -> str:
    chave = str(tipo or "peca").strip().lower()
    return chave if chave in ("peca", "mo") else "peca"


def _id_item_estavel(item: dict[str, Any]) -> str:
    """ID determinístico para itens legados sem id gravado no banco."""
    desc, qtd = _chave_conteudo_item(item)
    tipo = _tipo_item_valido(item.get("tipo_item"))
    base = f"{tipo}|{desc}|{qtd}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]


def _parse_itens(raw: str | None) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [_normalizar_item(i) for i in data if isinstance(i, dict)]


def _catalogo_id_item(item: dict[str, Any]) -> int | None:
    raw = item.get("catalogo_id")
    if raw in (None, "", 0, "0"):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _copiar_campos_estoque(destino: dict[str, Any], origem: dict[str, Any]) -> None:
    lib = origem.get("estoque_liberado_qtd")
    if lib not in (None, "", 0, "0", 0.0):
        try:
            destino["estoque_liberado_qtd"] = float(lib)
        except (TypeError, ValueError):
            pass
    if origem.get("estoque_liberado_em"):
        destino["estoque_liberado_em"] = str(origem["estoque_liberado_em"])


def _normalizar_item(item: dict[str, Any], *, gerar_id: bool = True) -> dict[str, Any]:
    iid = str(item.get("id") or "").strip()
    if not iid and gerar_id:
        iid = _id_item_estavel(item)
    status_item = str(item.get("status_item") or "").strip()
    if status_item not in _STATUS_ITEM:
        preco = str(item.get("preco") or "").strip()
        status_item = "ativo" if preco else "novo"
    out: dict[str, Any] = {
        "id": iid,
        "descricao": str(item.get("descricao") or "").strip(),
        "quantidade": str(item.get("quantidade") or "").strip(),
        "preco": str(item.get("preco") or "").strip(),
        "status_item": status_item,
        "tipo_item": _tipo_item_valido(item.get("tipo_item")),
        "catalogo_id": _catalogo_id_item(item),
        "codigo_barras": str(item.get("codigo_barras") or "").strip(),
    }
    _copiar_campos_estoque(out, item)
    return out


def _item_vazio(item: dict[str, Any]) -> bool:
    return not item.get("descricao") and not item.get("quantidade")


def _itens_para_mecanico(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mecânico vê descrição/qtd dos itens ativos; nunca recebe preços."""
    saida: list[dict[str, Any]] = []
    for item in itens:
        st = item.get("status_item", "ativo")
        if st in ("excluido", "excluir_pendente"):
            continue
        out: dict[str, Any] = {
            "id": item["id"],
            "descricao": item["descricao"],
            "quantidade": item["quantidade"],
            "status_item": st,
            "tipo_item": _tipo_item_valido(item.get("tipo_item")),
        }
        if item.get("catalogo_id"):
            out["catalogo_id"] = item["catalogo_id"]
        if item.get("codigo_barras"):
            out["codigo_barras"] = item["codigo_barras"]
        if item.get("estoque_liberado_qtd"):
            out["estoque_liberado_qtd"] = item["estoque_liberado_qtd"]
        if item.get("estoque_liberado_em"):
            out["estoque_liberado_em"] = item["estoque_liberado_em"]
        saida.append(out)
    return saida


def itens_requisicao_sem_precos(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove preços e referências de catálogo dos itens (visão restrita do mecânico)."""
    return _itens_para_mecanico(itens)


def _itens_para_responsavel(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Responsável vê todos os itens ativos/pendentes, inclusive exclusão pendente."""
    saida: list[dict[str, Any]] = []
    for item in itens:
        if item.get("status_item") == "excluido":
            continue
        saida.append(dict(item))
    return saida


def _mapas_itens(itens_db: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    mapa_id: dict[str, dict[str, Any]] = {}
    mapa_chave: dict[tuple[str, str], dict[str, Any]] = {}
    for item in itens_db:
        iid = item.get("id")
        if not iid:
            continue
        mapa_id[iid] = item
        chave = _chave_conteudo_item(item)
        if chave != ("", ""):
            mapa_chave[chave] = item
    return mapa_id, mapa_chave


def _resolver_item_existente(
    bruto: dict[str, Any],
    mapa_id: dict[str, dict[str, Any]],
    mapa_chave: dict[tuple[str, str], dict[str, Any]],
) -> tuple[str | None, dict[str, Any] | None]:
    iid = str(bruto.get("id") or "").strip()
    if iid and iid in mapa_id:
        return iid, mapa_id[iid]
    chave = _chave_conteudo_item(bruto)
    if chave != ("", "") and chave in mapa_chave:
        existente = mapa_chave[chave]
        return existente["id"], existente
    return None, None


def _mesclar_itens_mecanico(
    itens_db: list[dict[str, Any]],
    itens_payload: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Alterações do mecânico preservam preços e marcam exclusões pendentes."""
    mapa_id, mapa_chave = _mapas_itens(itens_db)
    resultado: list[dict[str, Any]] = []
    ids_payload: set[str] = set()

    for bruto in itens_payload:
        if not isinstance(bruto, dict):
            continue
        desc = str(bruto.get("descricao") or "").strip()
        qtd = str(bruto.get("quantidade") or "").strip()
        if not desc and not qtd:
            continue
        iid, existente = _resolver_item_existente(bruto, mapa_id, mapa_chave)
        if existente is not None and iid:
            st = existente.get("status_item", "ativo")
            if st == "excluido":
                novo = _normalizar_item({
                    "descricao": desc,
                    "quantidade": qtd,
                    "preco": "",
                    "catalogo_id": bruto.get("catalogo_id"),
                    "codigo_barras": bruto.get("codigo_barras"),
                })
                novo["status_item"] = "novo"
                resultado.append(novo)
            elif st == "excluir_pendente":
                restaurado = dict(existente)
                restaurado["descricao"] = desc
                restaurado["quantidade"] = qtd
                restaurado["status_item"] = "ativo" if existente.get("preco") else "novo"
                resultado.append(restaurado)
                ids_payload.add(iid)
            else:
                atualizado = dict(existente)
                atualizado["descricao"] = desc
                atualizado["quantidade"] = qtd
                _copiar_campos_estoque(atualizado, existente)
                resultado.append(atualizado)
                ids_payload.add(iid)
        else:
            novo = _normalizar_item({
                "descricao": desc,
                "quantidade": qtd,
                "preco": str(bruto.get("preco") or "").strip(),
                "tipo_item": bruto.get("tipo_item"),
                "catalogo_id": bruto.get("catalogo_id"),
                "codigo_barras": bruto.get("codigo_barras"),
            })
            if not novo.get("preco"):
                novo["status_item"] = "novo"
            resultado.append(novo)

    for iid, existente in mapa_id.items():
        if iid in ids_payload:
            continue
        if _tipo_item_valido(existente.get("tipo_item")) == "mo":
            resultado.append(dict(existente))
            continue
        st = existente.get("status_item", "ativo")
        if st == "excluido":
            continue
        if st == "excluir_pendente":
            resultado.append(dict(existente))
        else:
            marcado = dict(existente)
            marcado["status_item"] = "excluir_pendente"
            resultado.append(marcado)

    return resultado


def _rotulo_item_requisicao(item: dict[str, Any]) -> str:
    desc = str(item.get("descricao") or "Item").strip()
    cod = str(item.get("codigo_exibicao") or item.get("codigo_barras") or "").strip()
    qtd = str(item.get("quantidade") or "").strip()
    base = f"{cod} {desc}".strip() if cod else desc
    return f"{base} ({qtd})" if qtd else base


def calcular_alteracoes_mecanico(
    itens_antes: list[dict[str, Any]],
    itens_depois: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resume o que o mecânico removeu, adicionou ou alterou na quantidade."""
    mapa_antes = {str(i.get("id")): i for i in itens_antes if i.get("id")}
    removidos: list[str] = []
    adicionados: list[str] = []
    quantidades: list[dict[str, str]] = []

    for item in itens_depois:
        iid = str(item.get("id") or "")
        st = str(item.get("status_item") or "ativo")
        if st == "excluir_pendente" and iid in mapa_antes:
            if mapa_antes[iid].get("status_item") != "excluir_pendente":
                removidos.append(_rotulo_item_requisicao(mapa_antes[iid]))
            continue
        if st == "novo" and (not iid or iid not in mapa_antes):
            adicionados.append(_rotulo_item_requisicao(item))
            continue
        if iid in mapa_antes and st not in ("excluido", "excluir_pendente"):
            ant = mapa_antes[iid]
            if ant.get("status_item") == "excluir_pendente":
                continue
            q_ant = str(ant.get("quantidade") or "").strip()
            q_nov = str(item.get("quantidade") or "").strip()
            if q_ant != q_nov:
                rotulo = _rotulo_item_requisicao(item)
                desc_curta = rotulo.rsplit(" (", 1)[0] if " (" in rotulo else rotulo
                quantidades.append({
                    "descricao": desc_curta,
                    "de": q_ant or "0",
                    "para": q_nov or "0",
                })

    partes: list[str] = []
    for r in removidos[:6]:
        partes.append(f"Removido: {r}")
    for a in adicionados[:6]:
        partes.append(f"Adicionado: {a}")
    for q in quantidades[:4]:
        partes.append(f"Qtd. {q['descricao']}: {q['de']} → {q['para']}")

    return {
        "removidos": removidos,
        "adicionados": adicionados,
        "quantidades": quantidades,
        "resumo": " · ".join(partes) if partes else "",
        "atualizado_em": _agora(),
    }


def _parse_alteracoes_mecanico(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _mesclar_itens_responsavel(
    itens_db: list[dict[str, Any]],
    itens_payload: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Responsável cota preços e confirma exclusões removendo linhas cinzas ao salvar."""
    mapa = {i["id"]: i for i in itens_db if i.get("id")}
    resultado: list[dict[str, Any]] = []
    ids_payload: set[str] = set()

    for bruto in itens_payload:
        if not isinstance(bruto, dict):
            continue
        iid = str(bruto.get("id") or "").strip()
        tipo = _tipo_item_valido(bruto.get("tipo_item"))
        if not iid:
            novo = _normalizar_item(bruto)
            novo["tipo_item"] = tipo
            preco = str(bruto.get("preco") or "").strip()
            novo["preco"] = preco
            novo["status_item"] = "ativo" if preco else "novo"
            if _item_vazio(novo) and not preco:
                continue
            resultado.append(novo)
            continue
        ids_payload.add(iid)
        db_item = mapa.get(iid)
        if db_item is None:
            continue
        preco = str(bruto.get("preco") or "").strip()
        st = db_item.get("status_item", "ativo")
        if st == "excluir_pendente":
            resultado.append(dict(db_item))
            continue
        desc = str(bruto.get("descricao") or db_item.get("descricao") or "").strip()
        qtd = str(bruto.get("quantidade") or db_item.get("quantidade") or "").strip()
        if st == "novo":
            novo_st = "ativo" if preco else "novo"
        else:
            novo_st = "ativo"
        resultado.append({
            "id": iid,
            "descricao": desc,
            "quantidade": qtd,
            "preco": preco or db_item.get("preco", ""),
            "status_item": novo_st,
            "tipo_item": _tipo_item_valido(db_item.get("tipo_item")),
            "catalogo_id": db_item.get("catalogo_id"),
            "codigo_barras": str(bruto.get("codigo_barras") or db_item.get("codigo_barras") or "").strip(),
        })
        _copiar_campos_estoque(resultado[-1], db_item)

    return resultado


def _normalizar_itens_novos(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    saida: list[dict[str, Any]] = []
    for bruto in itens:
        if not isinstance(bruto, dict):
            continue
        item = _normalizar_item(bruto)
        if _item_vazio(item):
            continue
        if not item.get("preco"):
            item["status_item"] = "novo"
        saida.append(item)
    return saida


def _quantidade_item_requisicao(item: dict[str, Any]) -> float:
    try:
        return max(0.0, float(str(item.get("quantidade") or "0").replace(",", ".")))
    except (TypeError, ValueError):
        return 0.0


def _quantidade_liberada_item(item: dict[str, Any]) -> float:
    try:
        return max(0.0, float(str(item.get("estoque_liberado_qtd") or "0").replace(",", ".")))
    except (TypeError, ValueError):
        return 0.0


def resumo_liberacao_requisicao(itens: list[dict[str, Any]]) -> dict[str, Any]:
    """Contagem de peças liberadas (total, completas e parciais) para exibição na lista."""
    total_pecas = 0
    liberadas = 0
    parciais = 0
    for item in itens:
        if str(item.get("tipo_item") or "peca").lower() == "mo":
            continue
        if item.get("status_item") in ("excluido", "excluir_pendente"):
            continue
        total_pecas += 1
        pedida = _quantidade_item_requisicao(item)
        lib = _quantidade_liberada_item(item)
        if lib <= 0:
            continue
        if pedida <= 0 or lib >= pedida:
            liberadas += 1
        else:
            parciais += 1
    alguma = (liberadas + parciais) > 0
    todas = total_pecas > 0 and liberadas == total_pecas and parciais == 0
    return {
        "total_pecas": total_pecas,
        "liberadas": liberadas,
        "parciais": parciais,
        "alguma_liberada": alguma,
        "todas_liberadas": todas,
        "label_lista": f"{liberadas + parciais} lib." if alguma else "",
    }


def _interna_pecas_catalogo_liberadas(itens: list[dict[str, Any]]) -> bool:
    """True quando todas as peças com catálogo estão totalmente liberadas."""
    com_catalogo = 0
    ok = 0
    for item in itens:
        if str(item.get("tipo_item") or "peca").lower() == "mo":
            continue
        if item.get("status_item") in ("excluido", "excluir_pendente"):
            continue
        if not item.get("catalogo_id"):
            continue
        com_catalogo += 1
        pedida = _quantidade_item_requisicao(item)
        lib = _quantidade_liberada_item(item)
        if pedida <= 0 or lib >= pedida:
            ok += 1
    return com_catalogo > 0 and ok == com_catalogo


def finalizar_interna_apos_liberacao(conn: sqlite3.Connection, req_id: int) -> bool:
    """Marca requisição interna como finalizada quando as peças foram liberadas."""
    row = conn.execute(
        "SELECT * FROM requisicoes_material WHERE id = ?",
        (int(req_id),),
    ).fetchone()
    if row is None:
        return False
    tipo_req = str(row["tipo_requisicao"] if "tipo_requisicao" in row.keys() else "os") or "os"
    if tipo_req != "interna":
        return False
    st = str(row["status"] or "").strip().lower()
    if st in ("finalizada", "respondida"):
        return False
    itens = _parse_itens(row["itens_json"])
    if not _interna_pecas_catalogo_liberadas(itens):
        return False
    _publicar_itens_responsavel(
        conn, row, int(req_id), status_final="finalizada", publicada_oficina=False
    )
    return True


def _cor_para_perfil(status: str, *, visao: str) -> str:
    """verde | vermelho | laranja | cinza"""
    if visao == "mecanico":
        if status in ("aguardando_responsavel", "respondida", "aprovada", "finalizada"):
            return "verde"
        if status == "alterada_responsavel":
            return "vermelho"
        if status == "alterada_mecanico":
            return "laranja"
        return "cinza"
    # responsavel / admin
    if status == "aguardando_responsavel":
        return "laranja"
    if status == "alterada_mecanico":
        return "vermelho"
    if status in ("respondida", "aprovada", "finalizada"):
        return "verde"
    if status == "alterada_responsavel":
        return "vermelho"
    return "cinza"


def _rascunho_pendente(row: sqlite3.Row) -> bool:
    raw = ""
    if "itens_rascunho_json" in row.keys():
        raw = str(row["itens_rascunho_json"] or "").strip()
    return bool(raw and raw != "[]")


def _itens_observacao_para_visao(row: sqlite3.Row, *, visao: str) -> tuple[list[dict[str, Any]], str, bool]:
    """Retorna itens, observação e flag de rascunho pendente conforme o perfil."""
    tem_rascunho = _rascunho_pendente(row)
    status = str(row["status"] or "rascunho")
    if visao == "responsavel" and status == "alterada_mecanico":
        return _parse_itens(row["itens_json"]), str(row["observacao"] or "").strip(), tem_rascunho
    if visao == "responsavel" and tem_rascunho:
        itens_raw = _parse_itens(row["itens_rascunho_json"])
        obs = ""
        if "observacao_rascunho" in row.keys():
            obs = str(row["observacao_rascunho"] or "").strip()
        if not obs:
            obs = str(row["observacao"] or "").strip()
        return itens_raw, obs, True
    return _parse_itens(row["itens_json"]), str(row["observacao"] or "").strip(), tem_rascunho


def requisicao_para_json(
    row: sqlite3.Row,
    *,
    visao: str,
    os_status: str | None = None,
) -> dict[str, Any]:
    status = str(row["status"] or "rascunho")
    itens_raw, observacao, tem_rascunho = _itens_observacao_para_visao(row, visao=visao)
    if visao == "mecanico":
        itens_out = _itens_para_mecanico(itens_raw)
    else:
        itens_out = _itens_para_responsavel(itens_raw)
    payload: dict[str, Any] = {
        "id": row["id"],
        "numero_os": row["numero_os"],
        "mecanico_id": row["mecanico_id"],
        "mecanico_nome": row["mecanico_nome"] or "",
        "tipo_requisicao": (
            str(row["tipo_requisicao"]) if "tipo_requisicao" in row.keys() else "os"
        ) or "os",
        "titulo": (
            str(row["titulo"] or "").strip()
            if "titulo" in row.keys()
            else ""
        ),
        "publicada_oficina": bool(
            int(row["publicada_oficina"] or 0)
            if "publicada_oficina" in row.keys()
            else 0
        ),
        "itens": itens_out,
        "observacao": observacao,
        "status": status,
        "ultima_acao_por": row["ultima_acao_por"] or "",
        "cor_indicador": _cor_para_perfil(status, visao=visao),
        "criado_em": row["criado_em"] or "",
        "atualizado_em": row["atualizado_em"] or "",
        "salvo_rascunho_em": (row["salvo_rascunho_em"] if "salvo_rascunho_em" in row.keys() else "") or "",
        "tem_rascunho_pendente": tem_rascunho if visao == "responsavel" else False,
        "enviada_em": row["enviada_em"] or "",
        "respondida_em": row["respondida_em"] or "",
    }
    payload["liberacao"] = resumo_liberacao_requisicao(itens_raw)
    numero_os_req = int(row["numero_os"] or 0)
    if os_status is not None:
        payload["os_status"] = os_status
    elif numero_os_req > 0:
        payload["os_status"] = ""
    if visao == "responsavel" and status == "alterada_mecanico":
        alt_raw = row["alteracoes_mecanico_json"] if "alteracoes_mecanico_json" in row.keys() else None
        alteracoes = _parse_alteracoes_mecanico(alt_raw)
        if alteracoes and alteracoes.get("resumo"):
            payload["alteracoes_mecanico"] = alteracoes
    if visao == "mecanico":
        payload["orcamento_respondido"] = status in ("respondida", "aprovada", "finalizada")
        if status == "aprovada":
            payload["mensagem_mecanico"] = "Orçamento aprovado pelo cliente."
        elif status == "respondida":
            payload["mensagem_mecanico"] = "Orçamento respondido pelo responsável."
        elif status == "finalizada":
            payload["mensagem_mecanico"] = "Requisição interna finalizada pelo responsável."
    return payload


def sincronizar_aprovacoes_pendentes(conn: sqlite3.Connection) -> None:
    """Corrige requisições respondida→aprovada quando a O.S. já tem assinatura de aprovação."""
    rows = conn.execute(
        "SELECT numero_os, dados_json FROM ordens_servico"
    ).fetchall()
    for row in rows:
        dados = _parse_dados_os_json(row["dados_json"])
        marcar_requisicao_aprovada_se_assinada(conn, int(row["numero_os"]), dados)


def _requisicao_na_aba(
    aba: str,
    tipo_req: str,
    status: str,
    *,
    os_status: str | None = None,
) -> bool:
    tipo = str(tipo_req or "os").strip().lower()
    aba_norm = str(aba or "ativas").strip().lower()
    if aba_norm == "internas":
        return tipo == "interna"
    if tipo == "interna":
        return False
    if str(os_status or "").strip().lower() == "cancelado":
        return False
    entregue = _os_servico_entregue(os_status)
    if aba_norm == "finalizadas":
        return entregue
    return not entregue


def listar_requisicoes(
    conn: sqlite3.Connection,
    *,
    visao: str,
    numero_os: int | None = None,
    mecanico_id: int | None = None,
    tipo_requisicao: str | None = None,
    aba: str | None = None,
) -> list[dict[str, Any]]:
    sincronizar_aprovacoes_pendentes(conn)
    sql = "SELECT * FROM requisicoes_material WHERE 1=1"
    params: list[Any] = []
    if numero_os is not None:
        sql += " AND numero_os = ?"
        params.append(numero_os)
    if mecanico_id is not None:
        sql += " AND mecanico_id = ?"
        params.append(mecanico_id)
    if tipo_requisicao is not None:
        sql += " AND COALESCE(tipo_requisicao, 'os') = ?"
        params.append(tipo_requisicao)
    sql += " ORDER BY id DESC"
    rows = conn.execute(sql, params).fetchall()
    numeros_os = {
        int(r["numero_os"])
        for r in rows
        if int(r["numero_os"] or 0) > 0
        and str(r["tipo_requisicao"] if "tipo_requisicao" in r.keys() else "os").strip().lower() != "interna"
    }
    os_status_map = _mapa_status_os(conn, numeros_os)
    if aba:
        rows = [
            r for r in rows
            if _requisicao_na_aba(
                aba,
                str(r["tipo_requisicao"] if "tipo_requisicao" in r.keys() else "os"),
                str(r["status"] or ""),
                os_status=os_status_map.get(int(r["numero_os"] or 0)),
            )
        ]
    return [
        requisicao_para_json(
            r,
            visao=visao,
            os_status=os_status_map.get(int(r["numero_os"] or 0)),
        )
        for r in rows
    ]


def obter_requisicao(conn: sqlite3.Connection, req_id: int, *, visao: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM requisicoes_material WHERE id = ?",
        (int(req_id),),
    ).fetchone()
    if row is None:
        return None
    os_status: str | None = None
    numero_os = int(row["numero_os"] or 0)
    tipo = str(row["tipo_requisicao"] if "tipo_requisicao" in row.keys() else "os").strip().lower()
    if numero_os > 0 and tipo != "interna":
        os_row = conn.execute(
            "SELECT status FROM ordens_servico WHERE numero_os = ?",
            (numero_os,),
        ).fetchone()
        if os_row is not None:
            os_status = str(os_row["status"] or "")
    return requisicao_para_json(row, visao=visao, os_status=os_status)


def _resolver_mecanico_requisicao(
    conn: sqlite3.Connection,
    *,
    numero_os: int,
    mecanico_id: int,
    mecanico_nome: str,
    tipo_requisicao: str,
) -> tuple[int, str]:
    """Garante mecânico válido (payload ou O.S.) para recriar requisição excluída na oficina."""
    if mecanico_id:
        return int(mecanico_id), str(mecanico_nome or "").strip()
    if tipo_requisicao == "os" and numero_os:
        row = conn.execute(
            """
            SELECT mecanico_id, mecanico_nome
            FROM ordens_servico WHERE numero_os = ?
            """,
            (int(numero_os),),
        ).fetchone()
        if row is not None and row["mecanico_id"]:
            return int(row["mecanico_id"]), str(row["mecanico_nome"] or mecanico_nome or "").strip()
    raise ValueError(
        "Não foi possível recriar a requisição: informe o mecânico ou abra novamente pela O.S."
    )


def _recriar_requisicao_responsavel(
    conn: sqlite3.Connection,
    *,
    numero_os: int,
    mecanico_id: int,
    mecanico_nome: str,
    itens: list[dict[str, Any]],
    observacao: str,
    tipo_requisicao: str,
    agora: str,
) -> dict[str, Any]:
    """Recria requisição removida no Sistema Oficina (rascunho do responsável)."""
    mec_id, mec_nome = _resolver_mecanico_requisicao(
        conn,
        numero_os=numero_os,
        mecanico_id=mecanico_id,
        mecanico_nome=mecanico_nome,
        tipo_requisicao=tipo_requisicao,
    )
    itens_finais = _mesclar_itens_responsavel([], itens)
    rascunho_json = json.dumps(itens_finais, ensure_ascii=False)
    cur = conn.execute(
        """
        INSERT INTO requisicoes_material (
            numero_os, mecanico_id, mecanico_nome, itens_json, observacao,
            status, ultima_acao_por, tipo_requisicao,
            itens_rascunho_json, observacao_rascunho, salvo_rascunho_em,
            criado_em, atualizado_em
        ) VALUES (?, ?, ?, '[]', '', 'alterada_responsavel', 'responsavel', ?, ?, ?, ?, ?, ?)
        """,
        (
            int(numero_os),
            mec_id,
            mec_nome,
            tipo_requisicao,
            rascunho_json,
            observacao,
            agora,
            agora,
            agora,
        ),
    )
    novo_id = int(cur.lastrowid)
    return obter_requisicao(conn, novo_id, visao="responsavel") or {}


def _garantir_os_atribuida(
    conn: sqlite3.Connection,
    numero_os: int,
    mecanico_id: int,
) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT numero_os, mecanico_id, mecanico_nome, status
        FROM ordens_servico WHERE numero_os = ?
        """,
        (numero_os,),
    ).fetchone()
    if row is None:
        raise ValueError(f"O.S. nº {numero_os} não encontrada.")
    if row["mecanico_id"] is None or int(row["mecanico_id"]) != int(mecanico_id):
        raise ValueError("Esta O.S. não está atribuída a este mecânico.")
    return row


def salvar_requisicao(
    conn: sqlite3.Connection,
    *,
    numero_os: int,
    mecanico_id: int,
    mecanico_nome: str,
    itens: list[dict[str, Any]],
    observacao: str,
    req_id: int | None,
    como_responsavel: bool,
    tipo_requisicao: str = "os",
    titulo: str = "",
) -> dict[str, Any]:
    init_fluxo_tabelas(conn)
    agora = _agora()
    tipo_req = str(tipo_requisicao or "os").strip().lower()
    if tipo_req not in ("os", "interna"):
        tipo_req = "os"
    titulo_limpo = str(titulo or "").strip()

    if como_responsavel:
        row = None
        if req_id is not None:
            row = conn.execute(
                "SELECT * FROM requisicoes_material WHERE id = ?",
                (int(req_id),),
            ).fetchone()
        if row is None:
            return _recriar_requisicao_responsavel(
                conn,
                numero_os=numero_os,
                mecanico_id=mecanico_id,
                mecanico_nome=mecanico_nome,
                itens=itens,
                observacao=observacao,
                tipo_requisicao=tipo_req,
                agora=agora,
            )
        base_raw = row["itens_rascunho_json"] if _rascunho_pendente(row) else row["itens_json"]
        itens_existentes = _parse_itens(base_raw)
        itens_finais = _mesclar_itens_responsavel(itens_existentes, itens)
        from estoque import sincronizar_estoque_apos_alteracao_itens

        sincronizar_estoque_apos_alteracao_itens(
            conn,
            itens_antigos=itens_existentes,
            itens_novos=itens_finais,
                req_id=int(req_id),
                tipo_requisicao=str(row["tipo_requisicao"] if "tipo_requisicao" in row.keys() else "os"),
                usuario_id=None,
                usuario_nome="responsavel",
        )
        rascunho_json = json.dumps(itens_finais, ensure_ascii=False)
        conn.execute(
            """
            UPDATE requisicoes_material SET
                itens_rascunho_json = ?, observacao_rascunho = ?, salvo_rascunho_em = ?
            WHERE id = ?
            """,
            (rascunho_json, observacao, agora, int(req_id)),
        )
        return obter_requisicao(conn, int(req_id), visao="responsavel") or {}

    if tipo_req == "os":
        _garantir_os_atribuida(conn, numero_os, mecanico_id)
    elif numero_os:
        raise ValueError("Requisição interna não deve ter número de O.S.")
    if req_id is not None:
        existe = conn.execute(
            "SELECT id FROM requisicoes_material WHERE id = ? AND mecanico_id = ?",
            (int(req_id), int(mecanico_id)),
        ).fetchone()
        if existe is None:
            req_id = None
    if req_id is None and tipo_req == "os":
        row_exist = conn.execute(
            """
            SELECT id FROM requisicoes_material
            WHERE mecanico_id = ? AND COALESCE(tipo_requisicao, 'os') = ?
              AND numero_os = ?
            ORDER BY id DESC LIMIT 1
            """,
            (mecanico_id, tipo_req, numero_os),
        ).fetchone()
        if row_exist is not None:
            req_id = int(row_exist["id"])
    if req_id is None:
        if tipo_req == "os" and numero_os:
            _garantir_os_editavel_mecanico(conn, numero_os)
        itens_finais = _normalizar_itens_novos(itens)
        itens_json = json.dumps(itens_finais, ensure_ascii=False)
        cur = conn.execute(
            """
            INSERT INTO requisicoes_material (
                numero_os, mecanico_id, mecanico_nome, itens_json, observacao,
                status, ultima_acao_por, tipo_requisicao, titulo,
                criado_em, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, 'rascunho', 'mecanico', ?, ?, ?, ?)
            """,
            (
                numero_os, mecanico_id, mecanico_nome, itens_json, observacao,
                tipo_req, titulo_limpo or None, agora, agora,
            ),
        )
        rid = int(cur.lastrowid)
        if tipo_req == "os":
            _atualizar_status_os_fluxo_requisicao(conn, numero_os, "em_servico", agora)
        return obter_requisicao(conn, rid, visao="mecanico") or {}

    row = conn.execute(
        "SELECT * FROM requisicoes_material WHERE id = ? AND mecanico_id = ?",
        (int(req_id), int(mecanico_id)),
    ).fetchone()
    if row is None:
        raise ValueError("Requisição não encontrada ou não pertence a este mecânico.")
    tipo_atual = str(row["tipo_requisicao"] if "tipo_requisicao" in row.keys() else "os") or "os"
    if tipo_atual == "os" and int(row["numero_os"] or 0):
        _garantir_os_editavel_mecanico(conn, int(row["numero_os"]))
    itens_existentes = _parse_itens(row["itens_json"])
    itens_finais = _mesclar_itens_mecanico(itens_existentes, itens)
    from estoque import sincronizar_estoque_apos_alteracao_itens

    sincronizar_estoque_apos_alteracao_itens(
        conn,
        itens_antigos=itens_existentes,
        itens_novos=itens_finais,
        req_id=int(req_id),
        tipo_requisicao=tipo_atual,
        usuario_id=mecanico_id,
        usuario_nome=mecanico_nome,
    )
    itens_json = json.dumps(itens_finais, ensure_ascii=False)
    status_atual = str(row["status"])
    if status_atual == "rascunho":
        novo_status = "rascunho"
    elif status_atual in ("aguardando_responsavel", "respondida", "alterada_responsavel", "aprovada"):
        novo_status = "alterada_mecanico"
    else:
        novo_status = "alterada_mecanico"
    alteracoes_json: str | None = None
    if novo_status == "alterada_mecanico":
        alteracoes = calcular_alteracoes_mecanico(itens_existentes, itens_finais)
        if alteracoes.get("resumo"):
            alteracoes_json = json.dumps(alteracoes, ensure_ascii=False)
    cols_req = {r[1] for r in conn.execute("PRAGMA table_info(requisicoes_material)").fetchall()}
    titulo_sql = ", titulo = ?" if "titulo" in cols_req else ""
    titulo_params: tuple[Any, ...] = (titulo_limpo or None,) if "titulo" in cols_req else ()
    if novo_status == "alterada_mecanico" and "itens_rascunho_json" in cols_req:
        conn.execute(
            f"""
            UPDATE requisicoes_material SET
                itens_json = ?, observacao = ?, status = ?,
                ultima_acao_por = 'mecanico', visto_responsavel = 0,
                itens_rascunho_json = NULL, observacao_rascunho = NULL, salvo_rascunho_em = NULL,
                alteracoes_mecanico_json = ?, atualizado_em = ?{titulo_sql}
            WHERE id = ?
            """,
            (itens_json, observacao, novo_status, alteracoes_json, agora, *titulo_params, int(req_id)),
        )
    else:
        conn.execute(
            f"""
            UPDATE requisicoes_material SET
                itens_json = ?, observacao = ?, status = ?,
                ultima_acao_por = 'mecanico', visto_responsavel = 0,
                alteracoes_mecanico_json = ?, atualizado_em = ?{titulo_sql}
            WHERE id = ?
            """,
            (itens_json, observacao, novo_status, alteracoes_json, agora, *titulo_params, int(req_id)),
        )
    return obter_requisicao(conn, int(req_id), visao="mecanico") or {}


def enviar_requisicao_mecanico(conn: sqlite3.Connection, req_id: int, mecanico_id: int) -> dict[str, Any]:
    agora = _agora()
    row = conn.execute(
        "SELECT * FROM requisicoes_material WHERE id = ? AND mecanico_id = ?",
        (int(req_id), int(mecanico_id)),
    ).fetchone()
    if row is None:
        raise ValueError("Requisição não encontrada.")
    tipo_req = str(row["tipo_requisicao"] if "tipo_requisicao" in row.keys() else "os") or "os"
    if tipo_req == "os" and int(row["numero_os"] or 0):
        _garantir_os_editavel_mecanico(conn, int(row["numero_os"]))
    conn.execute(
        """
        UPDATE requisicoes_material SET
            status = 'aguardando_responsavel', ultima_acao_por = 'mecanico',
            visto_responsavel = 0, enviada_em = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (agora, agora, int(req_id)),
    )
    return obter_requisicao(conn, int(req_id), visao="mecanico") or {}


def enviar_resposta_responsavel(conn: sqlite3.Connection, req_id: int) -> dict[str, Any]:
    agora = _agora()
    row = conn.execute("SELECT * FROM requisicoes_material WHERE id = ?", (int(req_id),)).fetchone()
    if row is None:
        raise ValueError("Requisição não encontrada.")
    tipo_req = str(row["tipo_requisicao"] if "tipo_requisicao" in row.keys() else "os") or "os"
    if tipo_req == "interna":
        raise ValueError(
            "Requisições de uso interno devem ser finalizadas pelo botão «Finalizar». "
            "Para enviar à oficina, use a opção de administrador nas configurações."
        )
    itens_antigos = _parse_itens(row["itens_json"])
    if _rascunho_pendente(row):
        itens_publicar = row["itens_rascunho_json"]
        itens_novos = _parse_itens(itens_publicar)
        obs_publicar = ""
        if "observacao_rascunho" in row.keys():
            obs_publicar = str(row["observacao_rascunho"] or "").strip()
        if not obs_publicar:
            obs_publicar = str(row["observacao"] or "").strip()
    else:
        itens_publicar = row["itens_json"]
        itens_novos = _parse_itens(itens_publicar)
        obs_publicar = str(row["observacao"] or "").strip()
    from estoque import sincronizar_estoque_apos_alteracao_itens

    sincronizar_estoque_apos_alteracao_itens(
        conn,
        itens_antigos=itens_antigos,
        itens_novos=itens_novos,
        req_id=int(req_id),
        tipo_requisicao=tipo_req,
        usuario_id=None,
        usuario_nome="responsavel",
    )
    itens_publicar = json.dumps(itens_novos, ensure_ascii=False)
    conn.execute(
        """
        UPDATE requisicoes_material SET
            itens_json = ?, observacao = ?,
            itens_rascunho_json = NULL, observacao_rascunho = NULL, salvo_rascunho_em = NULL,
            alteracoes_mecanico_json = NULL,
            status = 'respondida', ultima_acao_por = 'responsavel',
            visto_mecanico = 0, respondida_em = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (itens_publicar, obs_publicar, agora, agora, int(req_id)),
    )
    return obter_requisicao(conn, int(req_id), visao="responsavel") or {}


def _publicar_itens_responsavel(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    req_id: int,
    *,
    status_final: str,
    publicada_oficina: bool,
) -> None:
    """Mescla rascunho/preços e grava status final (interna ou oficina)."""
    agora = _agora()
    itens_antigos = _parse_itens(row["itens_json"])
    if _rascunho_pendente(row):
        itens_novos = _parse_itens(row["itens_rascunho_json"])
        obs_publicar = ""
        if "observacao_rascunho" in row.keys():
            obs_publicar = str(row["observacao_rascunho"] or "").strip()
        if not obs_publicar:
            obs_publicar = str(row["observacao"] or "").strip()
    else:
        itens_novos = _parse_itens(row["itens_json"])
        obs_publicar = str(row["observacao"] or "").strip()
    from estoque import sincronizar_estoque_apos_alteracao_itens

    tipo_req = str(row["tipo_requisicao"] if "tipo_requisicao" in row.keys() else "os") or "os"
    sincronizar_estoque_apos_alteracao_itens(
        conn,
        itens_antigos=itens_antigos,
        itens_novos=itens_novos,
        req_id=int(req_id),
        tipo_requisicao=tipo_req,
        usuario_id=None,
        usuario_nome="responsavel",
    )
    itens_publicar = json.dumps(itens_novos, ensure_ascii=False)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(requisicoes_material)").fetchall()}
    pub_sql = ", publicada_oficina = ?" if "publicada_oficina" in cols else ""
    pub_val: tuple[Any, ...] = (1 if publicada_oficina else 0,) if "publicada_oficina" in cols else ()
    conn.execute(
        f"""
        UPDATE requisicoes_material SET
            itens_json = ?, observacao = ?,
            itens_rascunho_json = NULL, observacao_rascunho = NULL, salvo_rascunho_em = NULL,
            alteracoes_mecanico_json = NULL,
            status = ?, ultima_acao_por = 'responsavel',
            visto_mecanico = 0, respondida_em = ?, atualizado_em = ?{pub_sql}
        WHERE id = ?
        """,
        (itens_publicar, obs_publicar, status_final, agora, agora, *pub_val, int(req_id)),
    )


def finalizar_requisicao_interna(conn: sqlite3.Connection, req_id: int) -> dict[str, Any]:
    """Finaliza requisição de uso interno (não publica no Sistema Oficina)."""
    row = conn.execute("SELECT * FROM requisicoes_material WHERE id = ?", (int(req_id),)).fetchone()
    if row is None:
        raise ValueError("Requisição não encontrada.")
    tipo_req = str(row["tipo_requisicao"] if "tipo_requisicao" in row.keys() else "os") or "os"
    if tipo_req != "interna":
        raise ValueError("Esta ação é apenas para requisições de uso interno.")
    _publicar_itens_responsavel(
        conn, row, int(req_id), status_final="finalizada", publicada_oficina=False
    )
    return obter_requisicao(conn, int(req_id), visao="responsavel") or {}


def publicar_requisicao_interna_oficina(conn: sqlite3.Connection, req_id: int) -> dict[str, Any]:
    """Publica requisição interna no Sistema Oficina (admin + config)."""
    row = conn.execute("SELECT * FROM requisicoes_material WHERE id = ?", (int(req_id),)).fetchone()
    if row is None:
        raise ValueError("Requisição não encontrada.")
    tipo_req = str(row["tipo_requisicao"] if "tipo_requisicao" in row.keys() else "os") or "os"
    if tipo_req != "interna":
        raise ValueError("Somente requisições de uso interno podem usar este envio.")
    _publicar_itens_responsavel(
        conn, row, int(req_id), status_final="respondida", publicada_oficina=True
    )
    return obter_requisicao(conn, int(req_id), visao="responsavel") or {}


def marcar_requisicao_vista(
    conn: sqlite3.Connection,
    req_id: int,
    *,
    como_responsavel: bool,
) -> None:
    if como_responsavel:
        conn.execute(
            "UPDATE requisicoes_material SET visto_responsavel = 1 WHERE id = ?",
            (int(req_id),),
        )
    else:
        conn.execute(
            """
            UPDATE requisicoes_material SET
                visto_mecanico = 1,
                visto_mecanico_liberacao = 1
            WHERE id = ?
            """,
            (int(req_id),),
        )


def listar_notificacoes(
    conn: sqlite3.Connection,
    *,
    visao: str,
    usuario_id: int | None,
) -> list[dict[str, Any]]:
    init_fluxo_tabelas(conn)
    sincronizar_aprovacoes_pendentes(conn)
    itens: list[dict[str, Any]] = []
    if visao == "mecanico" and usuario_id:
        rows = conn.execute(
            """
            SELECT r.*, o.cliente_nome
            FROM requisicoes_material r
            JOIN ordens_servico o ON o.numero_os = r.numero_os
            WHERE r.mecanico_id = ? AND r.visto_mecanico = 0
              AND r.status IN ('respondida', 'aprovada')
            ORDER BY r.atualizado_em DESC
            """,
            (int(usuario_id),),
        ).fetchall()
        for row in rows:
            st = str(row["status"] or "")
            if st == "aprovada":
                msg = f"Cliente aprovou o orçamento (O.S. {row['numero_os']})"
                evento = "cliente_aprovou"
            else:
                msg = f"Orçamento respondido (O.S. {row['numero_os']})"
                evento = "orcamento_respondido"
            itens.append({
                "id": f"req-{row['id']}",
                "tipo": "requisicao",
                "evento": evento,
                "requisicao_id": row["id"],
                "numero_os": row["numero_os"],
                "mecanico_id": row["mecanico_id"],
                "mecanico_nome": row["mecanico_nome"] or "",
                "cliente_nome": row["cliente_nome"] or "",
                "mensagem": msg,
                "cor": _cor_para_perfil(st, visao="mecanico"),
            })
        rows_int = conn.execute(
            """
            SELECT r.*
            FROM requisicoes_material r
            WHERE r.mecanico_id = ? AND COALESCE(r.tipo_requisicao, 'os') = 'interna'
              AND r.visto_mecanico = 0 AND r.status = 'finalizada'
            ORDER BY r.atualizado_em DESC
            """,
            (int(usuario_id),),
        ).fetchall()
        for row in rows_int:
            tit = str(row["titulo"] or "").strip() if "titulo" in row.keys() else ""
            rotulo = tit or "Uso interno"
            itens.append({
                "id": f"req-int-{row['id']}",
                "tipo": "requisicao",
                "requisicao_id": row["id"],
                "numero_os": 0,
                "mecanico_id": row["mecanico_id"],
                "mecanico_nome": row["mecanico_nome"] or "",
                "cliente_nome": "",
                "mensagem": f"Requisição interna finalizada: {rotulo}",
                "cor": "verde",
            })
        rows_lib = conn.execute(
            """
            SELECT r.*, o.cliente_nome
            FROM requisicoes_material r
            JOIN ordens_servico o ON o.numero_os = r.numero_os
            WHERE r.mecanico_id = ? AND r.visto_mecanico_liberacao = 0
              AND COALESCE(r.liberacao_em, '') != ''
              AND r.status IN ('respondida', 'aprovada')
            ORDER BY r.liberacao_em DESC
            """,
            (int(usuario_id),),
        ).fetchall()
        for row in rows_lib:
            itens.append({
                "id": f"lib-{row['id']}",
                "tipo": "liberacao_estoque",
                "evento": "pecas_separadas",
                "requisicao_id": row["id"],
                "numero_os": row["numero_os"],
                "mecanico_id": row["mecanico_id"],
                "mecanico_nome": row["mecanico_nome"] or "",
                "cliente_nome": row["cliente_nome"] or "",
                "mensagem": f"Peças liberadas do estoque (O.S. {row['numero_os']})",
                "cor": "verde",
            })
    elif visao == "responsavel":
        rows = conn.execute(
            """
            SELECT r.*, o.cliente_nome
            FROM requisicoes_material r
            JOIN ordens_servico o ON o.numero_os = r.numero_os
            WHERE r.visto_responsavel = 0
              AND r.status IN ('aguardando_responsavel', 'alterada_mecanico', 'aprovada')
            ORDER BY r.atualizado_em DESC
            """
        ).fetchall()
        for row in rows:
            st = str(row["status"] or "")
            if st == "aprovada":
                msg = f"Cliente aprovou o orçamento — O.S. {row['numero_os']}"
                evento = "cliente_aprovou"
            elif st == "alterada_mecanico":
                evento = "requisicao_nova"
                alt = _parse_alteracoes_mecanico(
                    row["alteracoes_mecanico_json"]
                    if "alteracoes_mecanico_json" in row.keys()
                    else None
                )
                if alt and alt.get("resumo"):
                    msg = (
                        f"{row['mecanico_nome'] or 'Mecânico'} alterou itens — "
                        + str(alt["resumo"])
                    )
                else:
                    msg = (
                        f"{row['mecanico_nome'] or 'Mecânico'} alterou itens — "
                        "cotar novos / confirmar exclusões"
                    )
            else:
                msg = f"{row['mecanico_nome'] or 'Mecânico'} enviou requisição"
                evento = "requisicao_nova"
            itens.append({
                "id": f"req-{row['id']}",
                "tipo": "requisicao",
                "evento": evento,
                "requisicao_id": row["id"],
                "numero_os": row["numero_os"],
                "mecanico_id": row["mecanico_id"],
                "mecanico_nome": row["mecanico_nome"] or "",
                "cliente_nome": row["cliente_nome"] or "",
                "mensagem": msg,
                "cor": _cor_para_perfil(st, visao="responsavel"),
            })
        rows_int = conn.execute(
            """
            SELECT r.*
            FROM requisicoes_material r
            WHERE COALESCE(r.tipo_requisicao, 'os') = 'interna'
              AND r.visto_responsavel = 0
              AND r.status IN ('aguardando_responsavel', 'alterada_mecanico')
            ORDER BY r.atualizado_em DESC
            """
        ).fetchall()
        for row in rows_int:
            st = str(row["status"] or "")
            tit = str(row["titulo"] or "").strip() if "titulo" in row.keys() else ""
            rotulo = tit or "Uso interno"
            if st == "alterada_mecanico":
                msg = f"{row['mecanico_nome'] or 'Mecânico'} alterou requisição interna — {rotulo}"
            else:
                msg = f"{row['mecanico_nome'] or 'Mecânico'} enviou requisição interna — {rotulo}"
            itens.append({
                "id": f"req-int-{row['id']}",
                "tipo": "requisicao",
                "requisicao_id": row["id"],
                "numero_os": 0,
                "mecanico_id": row["mecanico_id"],
                "mecanico_nome": row["mecanico_nome"] or "",
                "cliente_nome": "",
                "mensagem": msg,
                "cor": _cor_para_perfil(st, visao="responsavel"),
            })
    return itens


def indicador_sidebar_mecanico(conn: sqlite3.Connection, mecanico_id: int) -> str | None:
    """Ponto no avatar do mecânico (visão responsável): vermelho > laranja > None."""
    rows = conn.execute(
        """
        SELECT status FROM requisicoes_material
        WHERE mecanico_id = ? AND visto_responsavel = 0
          AND status IN ('aguardando_responsavel', 'alterada_mecanico')
        """,
        (int(mecanico_id),),
    ).fetchall()
    if not rows:
        return None
    statuses = {str(r["status"]) for r in rows}
    if "alterada_mecanico" in statuses:
        return "vermelho"
    return "laranja"


def resumo_requisicoes_por_os(
    conn: sqlite3.Connection,
    numero_os: int,
    *,
    visao: str,
) -> dict[str, Any] | None:
    rows = conn.execute(
        "SELECT * FROM requisicoes_material WHERE numero_os = ? ORDER BY id DESC LIMIT 1",
        (numero_os,),
    ).fetchall()
    if not rows:
        return None
    row = rows[0]
    itens_raw = _parse_itens(row["itens_json"])
    lib = resumo_liberacao_requisicao(itens_raw)
    return {
        "requisicao_id": row["id"],
        "label": "Requisição de material",
        "cor": _cor_para_perfil(str(row["status"]), visao=visao),
        "status": row["status"],
        "liberacao": lib,
    }


def finalizar_servico_mecanico(
    conn: sqlite3.Connection,
    numero_os: int,
    mecanico_id: int,
) -> None:
    """Marca O.S. como pronto_mecanico (senha já validada na API)."""
    _garantir_os_atribuida(conn, numero_os, mecanico_id)
    agora = _agora()
    conn.execute(
        """
        UPDATE ordens_servico SET status = 'pronto_mecanico', atualizado_em = ?
        WHERE numero_os = ? AND mecanico_id = ?
        """,
        (agora, numero_os, mecanico_id),
    )


def _parse_dados_os_json(dados_json: str | None) -> dict[str, Any]:
    try:
        dados = json.loads(dados_json or "{}")
    except json.JSONDecodeError:
        return {}
    return dados if isinstance(dados, dict) else {}


def tem_assinatura_entrega_os(dados: dict[str, Any]) -> bool:
    val = dados.get("assinatura_cliente_entrega") or ""
    return isinstance(val, str) and val.strip().startswith("data:image")


def tem_assinatura_aprovacao_os(dados: dict[str, Any]) -> bool:
    val = dados.get("assinatura_cliente_aprovacao") or ""
    return isinstance(val, str) and val.strip().startswith("data:image")


def marcar_requisicao_aprovada_se_assinada(
    conn: sqlite3.Connection,
    numero_os: int,
    dados: dict[str, Any],
) -> bool:
    """Cliente assinou aprovação do orçamento → requisição respondida vira aprovada."""
    if not tem_assinatura_aprovacao_os(dados):
        return False
    init_fluxo_tabelas(conn)
    row = conn.execute(
        """
        SELECT id, status FROM requisicoes_material
        WHERE numero_os = ? AND status IN ('respondida', 'aprovada')
        ORDER BY id DESC LIMIT 1
        """,
        (int(numero_os),),
    ).fetchone()
    if row is None or str(row["status"]) == "aprovada":
        return False
    agora = _agora()
    conn.execute(
        """
        UPDATE requisicoes_material SET
            status = 'aprovada',
            visto_mecanico = 0,
            visto_responsavel = 0,
            ultima_acao_por = 'cliente',
            atualizado_em = ?
        WHERE id = ?
        """,
        (agora, int(row["id"])),
    )
    os_row = conn.execute(
        "SELECT status FROM ordens_servico WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()
    if os_row is not None:
        st_os = str(os_row["status"] or "").strip()
        if st_os not in ("entregue", "pronto_mecanico", "cliente_avisado"):
            conn.execute(
                """
                UPDATE ordens_servico SET status = 'aprovado_orcamento', atualizado_em = ?
                WHERE numero_os = ?
                """,
                (agora, int(numero_os)),
            )
    return True


_STATUS_BLOQUEIA_TROCA_MECANICO = frozenset({
    "pronto_mecanico",
    "cliente_avisado",
    "entregue",
})

_OS_STATUS_NAO_REGREDIR = _STATUS_BLOQUEIA_TROCA_MECANICO | frozenset({
    "fechado",
    "cancelado",
    "concluido",
})


def _atualizar_status_os_fluxo_requisicao(
    conn: sqlite3.Connection,
    numero_os: int,
    novo_status: str,
    agora: str,
) -> None:
    """Atualiza status da O.S. pelo fluxo de requisição, sem reabrir serviço já finalizado."""
    if not numero_os:
        return
    row = conn.execute(
        "SELECT status FROM ordens_servico WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()
    if row is None:
        return
    atual = str(row["status"] or "aberto").strip()
    if atual in _OS_STATUS_NAO_REGREDIR:
        return
    conn.execute(
        "UPDATE ordens_servico SET status = ?, atualizado_em = ? WHERE numero_os = ?",
        (novo_status, agora, int(numero_os)),
    )


def _garantir_os_editavel_mecanico(conn: sqlite3.Connection, numero_os: int) -> None:
    """Impede alteração de requisição quando a O.S. já foi finalizada pelo mecânico."""
    if not numero_os:
        return
    row = conn.execute(
        "SELECT status FROM ordens_servico WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()
    if row is None:
        return
    atual = str(row["status"] or "aberto").strip()
    if os_status_em_pausa(atual, conn=conn):
        raise ValueError(
            "Esta O.S. está em pausa (garantia, retífica ou peças). "
            "Aguarde o responsável retomar o serviço."
        )
    if atual in _OS_STATUS_NAO_REGREDIR:
        raise ValueError(
            "Esta O.S. já foi finalizada. Peça ao responsável para usar "
            "«Devolver ao mecânico» na lista de O.S. antes de alterar a requisição."
        )


def devolver_os_ao_mecanico(conn: sqlite3.Connection, numero_os: int) -> dict[str, Any]:
    """Reabre O.S. finalizada para o mesmo mecânico continuar o serviço."""
    row = conn.execute(
        """
        SELECT status, mecanico_id, mecanico_nome
        FROM ordens_servico WHERE numero_os = ?
        """,
        (int(numero_os),),
    ).fetchone()
    if row is None:
        raise ValueError("O.S. não encontrada.")
    status = str(row["status"] or "aberto").strip()
    mecanico_id = row["mecanico_id"]
    if not mecanico_id:
        raise ValueError("Esta O.S. não tem mecânico atribuído para devolver.")
    if status not in ("pronto_mecanico", "cliente_avisado"):
        raise ValueError(
            "Só é possível devolver ao mecânico quando a O.S. está finalizada ou com cliente avisado."
        )
    agora = _agora()
    conn.execute(
        """
        UPDATE ordens_servico SET status = 'em_servico', atualizado_em = ?
        WHERE numero_os = ?
        """,
        (agora, int(numero_os)),
    )
    return {
        "status": "em_servico",
        "mecanico_id": mecanico_id,
        "mecanico_nome": row["mecanico_nome"] or "",
    }


def os_status_em_pausa(
    status: str | None,
    *,
    conn: sqlite3.Connection | None = None,
    pausas: list[dict[str, Any]] | None = None,
) -> bool:
    if pausas is not None:
        return os_status_em_pausa_config(status, pausas)
    if conn is not None:
        return os_status_em_pausa_config(status, carregar_pausas_tipos(conn))
    return slug_de_status_pausa(status) is not None


def definir_pausa_os(
    conn: sqlite3.Connection,
    numero_os: int,
    tipo_pausa: str,
) -> dict[str, Any]:
    pausas = carregar_pausas_tipos(conn)
    slugs = {str(p["slug"]): p for p in pausas if p.get("slug")}
    bruto = str(tipo_pausa or "").strip().lower()
    slug = slug_de_status_pausa(bruto) or _normalizar_slug(bruto)
    if slug not in slugs:
        raise ValueError("Tipo de pausa inválido ou não configurado.")
    tipo = status_pausa_de_slug(slug)
    row = conn.execute(
        """
        SELECT status, mecanico_id, mecanico_nome
        FROM ordens_servico WHERE numero_os = ?
        """,
        (int(numero_os),),
    ).fetchone()
    if row is None:
        raise ValueError("O.S. não encontrada.")
    status = str(row["status"] or "aberto").strip()
    if status in _STATUS_BLOQUEIA_TROCA_MECANICO:
        raise ValueError("Não é possível pausar uma O.S. já finalizada ou entregue.")
    if not row["mecanico_id"]:
        raise ValueError("Atribua um mecânico antes de marcar a pausa.")
    agora = _agora()
    conn.execute(
        """
        UPDATE ordens_servico SET status = ?, atualizado_em = ?
        WHERE numero_os = ?
        """,
        (tipo, agora, int(numero_os)),
    )
    meta_item = slugs.get(slug) or {}
    return {
        "status": tipo,
        "mecanico_id": row["mecanico_id"],
        "mecanico_nome": row["mecanico_nome"] or "",
        "pausa_rotulo": meta_item.get("rotulo") or slug,
    }


def retomar_os_de_pausa(conn: sqlite3.Connection, numero_os: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT status, mecanico_id, mecanico_nome
        FROM ordens_servico WHERE numero_os = ?
        """,
        (int(numero_os),),
    ).fetchone()
    if row is None:
        raise ValueError("O.S. não encontrada.")
    status = str(row["status"] or "aberto").strip()
    if not os_status_em_pausa(status, conn=conn):
        raise ValueError("Esta O.S. não está em pausa.")
    if not row["mecanico_id"]:
        raise ValueError("O.S. sem mecânico vinculado.")
    agora = _agora()
    conn.execute(
        """
        UPDATE ordens_servico SET status = 'em_servico', atualizado_em = ?
        WHERE numero_os = ?
        """,
        (agora, int(numero_os)),
    )
    return {
        "status": "em_servico",
        "mecanico_id": row["mecanico_id"],
        "mecanico_nome": row["mecanico_nome"] or "",
    }


def marcar_cliente_avisado_os(conn: sqlite3.Connection, numero_os: int) -> None:
    row = conn.execute(
        "SELECT status FROM ordens_servico WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()
    if row is None:
        raise ValueError("O.S. não encontrada.")
    status = str(row["status"] or "aberto").strip()
    if status != "pronto_mecanico":
        raise ValueError("Só é possível avisar o cliente quando a O.S. está finalizada pelo mecânico.")
    agora = _agora()
    conn.execute(
        """
        UPDATE ordens_servico SET status = 'cliente_avisado', atualizado_em = ?
        WHERE numero_os = ?
        """,
        (agora, int(numero_os)),
    )


def marcar_os_entregue_se_assinada(
    conn: sqlite3.Connection,
    numero_os: int,
    dados: dict[str, Any],
) -> None:
    if not tem_assinatura_entrega_os(dados):
        return
    agora = _agora()
    conn.execute(
        """
        UPDATE ordens_servico SET status = 'entregue', atualizado_em = ?
        WHERE numero_os = ?
        """,
        (agora, int(numero_os)),
    )


def _ultima_requisicao_os(conn: sqlite3.Connection, numero_os: int) -> str | None:
    init_fluxo_tabelas(conn)
    row = conn.execute(
        """
        SELECT status FROM requisicoes_material
        WHERE numero_os = ?
        ORDER BY id DESC LIMIT 1
        """,
        (int(numero_os),),
    ).fetchone()
    return str(row["status"]) if row else None


def resolver_status_exibicao_lista_os(
    conn: sqlite3.Connection,
    *,
    numero_os: int,
    status_os: str | None,
    mecanico_id: int | None,
    dados_json: str | None,
) -> dict[str, Any]:
    """Rótulo e cor do status para a lista de O.S."""
    status = (status_os or "aberto").strip()
    dados = _parse_dados_os_json(dados_json)

    if status == "cancelado":
        return {
            "codigo": "cancelado",
            "rotulo": "Cancelada",
            "cor": "cancelada",
            "clicavel": False,
            "acao": None,
            "dica": "O.S. cancelada — cliente desistiu do serviço.",
        }

    if status == "entregue" or tem_assinatura_entrega_os(dados):
        return {
            "codigo": "entregue",
            "rotulo": "Entregue",
            "cor": "entregue",
            "clicavel": False,
            "acao": None,
            "dica": "Embarcação/motor entregue — assinatura de saída registrada.",
        }

    if status == "cliente_avisado":
        return {
            "codigo": "cliente_avisado",
            "rotulo": "Cliente avisado",
            "cor": "avisado",
            "clicavel": False,
            "acao": None,
            "dica": "Cliente já foi comunicado sobre a conclusão do serviço.",
        }

    if status == "pronto_mecanico":
        return {
            "codigo": "pronto_mecanico",
            "rotulo": "Finalizada",
            "cor": "finalizada",
            "clicavel": True,
            "acao": "marcar_cliente_avisado",
            "dica": "Clique para marcar visualmente que o cliente já foi avisado (não envia mensagem).",
        }

    pausas_cfg = carregar_pausas_tipos(conn)
    meta_pausa = meta_pausa_por_status(status, pausas_cfg)
    if meta_pausa:
        return meta_pausa

    req_status = _ultima_requisicao_os(conn, numero_os)
    if req_status == "aguardando_responsavel":
        return {
            "codigo": "req_aguardando",
            "rotulo": "Req. aguardando",
            "cor": "req-aguardando",
            "clicavel": False,
            "acao": None,
            "dica": "Requisição enviada — aguardando resposta do responsável.",
        }
    if req_status == "alterada_mecanico":
        return {
            "codigo": "req_alterada",
            "rotulo": "Req. alterada",
            "cor": "req-alterada",
            "clicavel": False,
            "acao": None,
            "dica": "Mecânico alterou a requisição após resposta.",
        }
    if req_status == "aprovada":
        return {
            "codigo": "req_aprovada",
            "rotulo": "Req. aprovada",
            "cor": "req-aprovada",
            "clicavel": False,
            "acao": None,
            "dica": "Cliente aprovou o orçamento.",
        }
    if req_status == "respondida":
        return {
            "codigo": "req_respondida",
            "rotulo": "Req. respondida",
            "cor": "req-respondida",
            "clicavel": False,
            "acao": None,
            "dica": "Orçamento/requisição respondido pelo responsável.",
        }

    if mecanico_id and status in ("em_servico", "aprovado_orcamento", "aberto"):
        return {
            "codigo": "em_andamento",
            "rotulo": "Em andamento",
            "cor": "andamento",
            "clicavel": False,
            "acao": None,
            "dica": "Mecânico atribuído — serviço em andamento.",
        }

    if mecanico_id:
        return {
            "codigo": "em_andamento",
            "rotulo": "Em andamento",
            "cor": "andamento",
            "clicavel": False,
            "acao": None,
            "dica": "Mecânico atribuído.",
        }

    return {
        "codigo": "aguardando",
        "rotulo": "Aguardando",
        "cor": "aguardando",
        "clicavel": False,
        "acao": None,
        "dica": "Aguardando atribuição de mecânico.",
    }
