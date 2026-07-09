"""Sincroniza ações do app O.S. Digital com o Controle de O.S. (tabela servicos)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

_STATUS_PARA_SITUACAO: dict[str, str] = {
    "aberto": "Em andamento",
    "em_servico": "Em andamento",
    "aguardando_pecas": "Em andamento",
    "aguardando_garantia": "Em andamento",
    "aguardando_retifica": "Em andamento",
    "aprovado_orcamento": "Em andamento",
    "pronto_mecanico": "Pronto",
    "cliente_avisado": "Pronto",
    "entregue": "Entregue",
}

_RANK_SITUACAO: dict[str, int] = {
    "orçamento": 0,
    "aberto": 0,
    "em andamento": 0,
    "pronto": 1,
    "entregue": 2,
}


def _rank_situacao(situacao: str | None) -> int:
    chave = str(situacao or "Em andamento").strip().casefold()
    if chave in _RANK_SITUACAO:
        return _RANK_SITUACAO[chave]
    if chave == "orçamento":
        return 0
    return 0


def _primeiro_nome_cliente(nome: str | None) -> str:
    partes = str(nome or "").strip().split()
    return partes[0] if partes else "—"


def _resolver_usuario_mecanico_por_cadastro(
    conn: sqlite3.Connection,
    mecanico_cadastro_id: int,
) -> int | None:
    row = conn.execute(
        """
        SELECT id FROM usuarios
        WHERE mecanico_cadastro_id = ? AND perfil = 'mecanico' AND ativo = 1
        LIMIT 1
        """,
        (int(mecanico_cadastro_id),),
    ).fetchone()
    if row is not None:
        return int(row["id"])
    mec = conn.execute(
        "SELECT nome FROM mecanicos WHERE id = ?",
        (int(mecanico_cadastro_id),),
    ).fetchone()
    if mec is None:
        return None
    nome_mec = str(mec["nome"] or "").strip().upper()
    if not nome_mec:
        return None
    row = conn.execute(
        """
        SELECT id FROM usuarios
        WHERE perfil = 'mecanico' AND ativo = 1
          AND UPPER(TRIM(nome_exibicao)) = ?
        LIMIT 1
        """,
        (nome_mec,),
    ).fetchone()
    if row is not None:
        return int(row["id"])
    primeiro = nome_mec.split()[0] if nome_mec.split() else nome_mec
    row = conn.execute(
        """
        SELECT id FROM usuarios
        WHERE perfil = 'mecanico' AND ativo = 1
          AND (
            UPPER(TRIM(nome_exibicao)) = ?
            OR UPPER(TRIM(nome_exibicao)) LIKE ?
          )
        LIMIT 1
        """,
        (primeiro, f"{primeiro} %"),
    ).fetchone()
    return int(row["id"]) if row is not None else None


def _garantir_historico_controle_os(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mecanico_historico_controle_os (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servico_id INTEGER NOT NULL UNIQUE,
            mecanico_cadastro_id INTEGER,
            usuario_mecanico_id INTEGER,
            data_entrada TEXT,
            motor TEXT,
            cliente_primeiro_nome TEXT,
            responsavel TEXT,
            valor_servico REAL NOT NULL DEFAULT 0,
            finalizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
        """
    )


def _registrar_historico_servico(conn: sqlite3.Connection, servico_id: int) -> None:
    """Registra nota vinculada no histórico do mecânico (mesma tabela do Sistema Oficina)."""
    _garantir_historico_controle_os(conn)
    sid = int(servico_id)
    if conn.execute(
        "SELECT 1 FROM mecanico_historico_controle_os WHERE servico_id = ?",
        (sid,),
    ).fetchone():
        return
    row = conn.execute(
        """
        SELECT s.id, s.mecanico_id, s.entrada, s.responsavel, s.mo,
               s.valor_comissao_revisao, s.situacao, s.pago,
               COALESCE(s.tipo_documento, 'ORÇAMENTO') AS tipo_documento,
               m.marca_modelo, c.nome AS cliente_nome
        FROM servicos s
        JOIN motores m ON m.id = s.motor_id
        JOIN clientes c ON c.id = m.cliente_id
        WHERE s.id = ?
        """,
        (sid,),
    ).fetchone()
    if row is None:
        return
    if str(row["tipo_documento"] or "").upper() != "NOTA":
        return
    if row["mecanico_id"] is None:
        return
    sit = str(row["situacao"] or "").strip().casefold()
    if sit not in {"entregue", "pronto"} and not int(row["pago"] or 0):
        return
    mec_cadastro_id = int(row["mecanico_id"])
    usuario_id = _resolver_usuario_mecanico_por_cadastro(conn, mec_cadastro_id)
    valor = round(float(row["mo"] or 0), 2)
    if valor <= 0:
        valor = round(float(row["valor_comissao_revisao"] or 0), 2)
    conn.execute(
        """
        INSERT INTO mecanico_historico_controle_os (
            servico_id, mecanico_cadastro_id, usuario_mecanico_id,
            data_entrada, motor, cliente_primeiro_nome, responsavel, valor_servico
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sid,
            mec_cadastro_id,
            usuario_id,
            str(row["entrada"] or "").strip() or None,
            str(row["marca_modelo"] or "").strip() or "—",
            _primeiro_nome_cliente(row["cliente_nome"]),
            str(row["responsavel"] or "").strip() or "—",
            valor,
        ),
    )


def _parse_dados_json(dados_json: str | None) -> dict[str, Any]:
    try:
        dados = json.loads(dados_json or "{}")
    except json.JSONDecodeError:
        return {}
    return dados if isinstance(dados, dict) else {}


def _parse_horas_uso(valor: Any) -> float | None:
    if valor in (None, ""):
        return None
    texto = str(valor).strip().lower().replace("h", "").replace(" ", "")
    texto = texto.replace(",", ".")
    try:
        horas = float(texto)
    except ValueError:
        return None
    return max(0.0, horas)


def sincronizar_horas_app_para_oficina(
    conn_principal: sqlite3.Connection,
    numero_os: int,
    horas_uso: Any,
    *,
    motor_id: int | None = None,
    dados_json: str | None = None,
) -> None:
    """Propaga horas informadas no App O.S. para servicos.horas_servico e cadastro do motor."""
    horas = _parse_horas_uso(horas_uso)
    if horas is None and dados_json:
        dados = _parse_dados_json(dados_json)
        horas = _parse_horas_uso(dados.get("horas_uso"))
        if motor_id is None and dados.get("motor_id") not in (None, ""):
            try:
                motor_id = int(dados["motor_id"])
            except (TypeError, ValueError):
                motor_id = None
    if horas is None:
        return
    conn_principal.execute(
        """
        UPDATE servicos
        SET horas_servico = ?
        WHERE numero_os_digital = ?
          AND UPPER(COALESCE(tipo_documento, '')) = 'NOTA'
        """,
        (horas, int(numero_os)),
    )
    mid = motor_id
    if mid is None:
        return
    try:
        mid = int(mid)
    except (TypeError, ValueError):
        return
    if mid <= 0:
        return
    conn_principal.execute(
        "UPDATE motores SET horas = ? WHERE id = ?",
        (horas, mid),
    )


def _aplicar_status_servico(
    conn: sqlite3.Connection,
    servico_id: int,
    situacao_atual: str | None,
    nova_situacao: str,
    *,
    data_saida: str | None = None,
) -> bool:
    atual = str(situacao_atual or "Em andamento").strip() or "Em andamento"
    if _rank_situacao(nova_situacao) < _rank_situacao(atual):
        return False
    if nova_situacao == atual:
        return False
    params: list[Any] = [nova_situacao]
    sql = "UPDATE servicos SET situacao = ?"
    if data_saida and nova_situacao == "Entregue":
        sql += ", saida = COALESCE(NULLIF(TRIM(saida), ''), ?)"
        params.append(data_saida)
    sql += " WHERE id = ?"
    params.append(int(servico_id))
    conn.execute(sql, params)
    return True


def sincronizar_status_app_para_oficina(
    conn_principal: sqlite3.Connection,
    numero_os: int,
    status_web: str,
    *,
    dados_json: str | None = None,
) -> None:
    """Atualiza servicos.situacao vinculados à O.S. digital (somente avanço de status)."""
    st = str(status_web or "").strip()
    nova = _STATUS_PARA_SITUACAO.get(st)
    if not nova and st.startswith("aguardando_"):
        nova = "Em andamento"
    if not nova:
        return
    data_saida: str | None = None
    if nova == "Entregue" and dados_json:
        dados = _parse_dados_json(dados_json)
        data_saida = str(dados.get("entrega_data") or dados.get("saida") or "").strip() or None
        if data_saida and len(data_saida) >= 10:
            data_saida = data_saida[:10]
    rows = conn_principal.execute(
        """
        SELECT id, situacao
        FROM servicos
        WHERE numero_os_digital = ?
          AND UPPER(COALESCE(tipo_documento, '')) = 'NOTA'
        """,
        (int(numero_os),),
    ).fetchall()
    for row in rows:
        if _aplicar_status_servico(
            conn_principal,
            int(row["id"]),
            row["situacao"],
            nova,
            data_saida=data_saida,
        ):
            _registrar_historico_servico(conn_principal, int(row["id"]))
