"""Pré-requisitos (fotos + checklist) antes da requisição no perfil do mecânico."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from checklist_revisao import (
    ITENS_CHECKLIST_REVISAO,
    init_checklist_tabelas,
    normalizar_itens_salvos,
)
from os_fotos_mecanico import init_os_fotos_tabelas


def init_req_precondicoes_tabelas(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS os_req_precondicoes (
            numero_os INTEGER PRIMARY KEY,
            mecanico_id INTEGER NOT NULL,
            pulou_fotos INTEGER NOT NULL DEFAULT 0,
            pulou_checklist INTEGER NOT NULL DEFAULT 0,
            confirmado_em TEXT NOT NULL
        )
        """
    )


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def os_tem_fotos_enviadas(conn: sqlite3.Connection, numero_os: int) -> bool:
    init_os_fotos_tabelas(conn)
    row = conn.execute(
        "SELECT 1 FROM os_fotos_envio WHERE numero_os = ? LIMIT 1",
        (int(numero_os),),
    ).fetchone()
    return row is not None


def _carregar_checklist_os(
    conn: sqlite3.Connection, numero_os: int
) -> tuple[list[Any], str]:
    init_checklist_tabelas(conn)
    row = conn.execute(
        "SELECT itens_json, atualizado_em FROM checklists_revisao WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()
    if row is None:
        return [], ""
    try:
        bruto = json.loads(row["itens_json"] or "[]")
    except json.JSONDecodeError:
        bruto = []
    itens = bruto if isinstance(bruto, list) else []
    return itens, str(row["atualizado_em"] or "").strip()


def checklist_orcamento_registrado(itens: list[Any] | None, *, salvo: bool) -> bool:
    """Basta salvar o que o mecânico realmente fez — não precisa marcar todos os itens."""
    if not salvo:
        return False
    estados = {x["id"]: x for x in normalizar_itens_salvos(itens)}
    for item_def in ITENS_CHECKLIST_REVISAO:
        if item_def["secao"] != "orcamento":
            continue
        estado = estados.get(item_def["id"])
        if not estado or not estado.get("marcado"):
            continue
        if item_def.get("sub_opcao") == "vst_carburador":
            if estado.get("sub_opcao") not in ("vst", "carburador"):
                continue
        return True
    return False


def _carregar_pulos(conn: sqlite3.Connection, numero_os: int) -> dict[str, bool]:
    init_req_precondicoes_tabelas(conn)
    row = conn.execute(
        """
        SELECT pulou_fotos, pulou_checklist
        FROM os_req_precondicoes
        WHERE numero_os = ?
        """,
        (int(numero_os),),
    ).fetchone()
    if row is None:
        return {"pulou_fotos": False, "pulou_checklist": False}
    return {
        "pulou_fotos": bool(row["pulou_fotos"]),
        "pulou_checklist": bool(row["pulou_checklist"]),
    }


def _carregar_itens_checklist(conn: sqlite3.Connection, numero_os: int) -> list[Any]:
    itens, _ = _carregar_checklist_os(conn, numero_os)
    return itens


def status_pre_requisicao(
    conn: sqlite3.Connection,
    numero_os: int,
    *,
    mecanico_id: int | None = None,
) -> dict[str, Any]:
    init_req_precondicoes_tabelas(conn)
    fotos_enviadas = os_tem_fotos_enviadas(conn, int(numero_os))
    itens_chk, atualizado_chk = _carregar_checklist_os(conn, int(numero_os))
    checklist_ok = checklist_orcamento_registrado(
        itens_chk, salvo=bool(atualizado_chk)
    )
    pulos = _carregar_pulos(conn, int(numero_os))
    fotos_ok = fotos_enviadas or pulos["pulou_fotos"]
    checklist_liberado = checklist_ok or pulos["pulou_checklist"]
    pendencias: list[str] = []
    if not fotos_ok:
        pendencias.append("fotos")
    if not checklist_liberado:
        pendencias.append("checklist")
    return {
        "numero_os": int(numero_os),
        "fotos_enviadas": fotos_enviadas,
        "checklist_orcamento_ok": checklist_ok,
        "checklist_registrado": checklist_ok,
        "pulou_fotos": pulos["pulou_fotos"],
        "pulou_checklist": pulos["pulou_checklist"],
        "fotos_ok": fotos_ok,
        "checklist_ok": checklist_liberado,
        "pode_abrir_requisicao": fotos_ok and checklist_liberado,
        "pendencias": pendencias,
    }


def registrar_pulo_pre_requisicao(
    conn: sqlite3.Connection,
    *,
    numero_os: int,
    mecanico_id: int,
    pulou_fotos: bool,
    pulou_checklist: bool,
) -> dict[str, Any]:
    if not pulou_fotos and not pulou_checklist:
        raise ValueError("Marque ao menos uma opção para prosseguir sem completar.")
    init_req_precondicoes_tabelas(conn)
    row_os = conn.execute(
        "SELECT mecanico_id FROM ordens_servico WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()
    if row_os is None:
        raise ValueError("O.S. não encontrada.")
    if int(row_os["mecanico_id"] or 0) != int(mecanico_id):
        raise ValueError("Esta O.S. não está atribuída a você.")

    atual = status_pre_requisicao(conn, int(numero_os), mecanico_id=int(mecanico_id))
    if pulou_fotos and atual["fotos_enviadas"]:
        raise ValueError("As fotos já foram enviadas.")
    if pulou_checklist and atual["checklist_registrado"]:
        raise ValueError("O checklist já foi registrado para esta O.S.")

    pulos_ant = _carregar_pulos(conn, int(numero_os))
    novo_fotos = pulos_ant["pulou_fotos"] or bool(pulou_fotos)
    novo_chk = pulos_ant["pulou_checklist"] or bool(pulou_checklist)
    agora = _agora()
    conn.execute(
        """
        INSERT INTO os_req_precondicoes (
            numero_os, mecanico_id, pulou_fotos, pulou_checklist, confirmado_em
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(numero_os) DO UPDATE SET
            mecanico_id = excluded.mecanico_id,
            pulou_fotos = MAX(os_req_precondicoes.pulou_fotos, excluded.pulou_fotos),
            pulou_checklist = MAX(os_req_precondicoes.pulou_checklist, excluded.pulou_checklist),
            confirmado_em = excluded.confirmado_em
        """,
        (int(numero_os), int(mecanico_id), int(novo_fotos), int(novo_chk), agora),
    )
    return status_pre_requisicao(conn, int(numero_os), mecanico_id=int(mecanico_id))


def exigir_pode_abrir_requisicao_mecanico(
    conn: sqlite3.Connection,
    numero_os: int,
    *,
    mecanico_id: int,
) -> None:
    """Impede acesso à requisição de O.S. antes de fotos/checklist ou confirmação de exceção."""
    if not numero_os:
        return
    st = status_pre_requisicao(conn, int(numero_os), mecanico_id=int(mecanico_id))
    if st.get("pode_abrir_requisicao"):
        return
    pendencias = st.get("pendencias") or []
    if "fotos" in pendencias and "checklist" in pendencias:
        raise ValueError(
            "Envie as fotos e registre o checklist de orçamento antes de acessar a requisição."
        )
    if "fotos" in pendencias:
        raise ValueError("Envie as fotos da O.S. antes de acessar a requisição.")
    if "checklist" in pendencias:
        raise ValueError(
            "Registre no checklist o que fez no motor antes de acessar a requisição."
        )
    raise ValueError(
        "Conclua fotos e checklist (ou confirme a exceção no perfil) antes da requisição."
    )
