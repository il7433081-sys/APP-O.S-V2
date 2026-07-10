"""Detecta e resolve pendências entre App O.S. Digital e Controle de O.S. (Oficina)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from sync_oficina_servicos import (
    _ids_mecanico_cadastro_por_usuario,
    reconciliar_os_digital_com_oficina,
    tentar_vincular_servico_orfao_os,
)

_OS_STATUS_FINALIZADOS = frozenset({
    "pronto_mecanico", "cliente_avisado", "entregue", "fechado", "concluido",
})

_ROTULOS_TIPO: dict[str, str] = {
    "requisicao_aguardando": "Requisição aguardando resposta",
    "nota_sem_vinculo": "NOTA na Oficina sem vínculo com a O.S.",
    "status_desatualizado": "Status do Controle de O.S. desatualizado",
    "nota_com_requisicao_pendente": "NOTA lançada — requisição ainda pendente",
}


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _servico_finalizado(situacao: str | None, pago: Any) -> bool:
    sit = str(situacao or "").strip().casefold()
    if sit in {"entregue", "pronto"}:
        return True
    try:
        return int(pago or 0) == 1
    except (TypeError, ValueError):
        return False


def _buscar_nota_orfa_cliente(
    conn: sqlite3.Connection,
    *,
    cliente_id: int | None,
    mecanico_cadastro_ids: set[int],
    data_entrada: str | None,
    excluir_os: int | None = None,
) -> sqlite3.Row | None:
    if not mecanico_cadastro_ids or cliente_id in (None, "", 0):
        return None
    ph = ", ".join("?" * len(mecanico_cadastro_ids))
    params: list[Any] = list(sorted(mecanico_cadastro_ids))
    params.append(int(cliente_id))
    data_txt = str(data_entrada or "").strip()[:10]
    filtro_data = ""
    if data_txt:
        filtro_data = " AND COALESCE(s.entrada, '') LIKE ?"
        params.append(f"{data_txt}%")
    filtro_os = ""
    if excluir_os is not None:
        filtro_os = " AND (s.numero_os_digital IS NULL OR s.numero_os_digital = ?)"
        params.append(int(excluir_os))
    else:
        filtro_os = " AND s.numero_os_digital IS NULL"
    return conn.execute(
        f"""
        SELECT s.id, s.numero_os_digital, s.situacao, s.pago, s.entrada, s.mecanico_id,
               c.nome AS cliente_nome
        FROM servicos s
        JOIN motores m ON m.id = s.motor_id
        JOIN clientes c ON c.id = m.cliente_id
        WHERE UPPER(COALESCE(s.tipo_documento, '')) = 'NOTA'
          AND s.mecanico_id IN ({ph})
          AND m.cliente_id = ?
          {filtro_os}
          {filtro_data}
        ORDER BY s.id DESC
        LIMIT 1
        """,
        tuple(params),
    ).fetchone()


def listar_pendencias_integracao_os(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Pendências que exigem conferência do responsável."""
    saida: list[dict[str, Any]] = []
    chaves: set[str] = set()

    def _add(item: dict[str, Any]) -> None:
        chave = str(item.get("chave") or "").strip()
        if not chave or chave in chaves:
            return
        chaves.add(chave)
        saida.append(item)

    rows_req = conn.execute(
        """
        SELECT r.id AS requisicao_id, r.numero_os, r.mecanico_id, r.status AS req_status,
               r.enviada_em, r.atualizado_em,
               o.cliente_id, o.cliente_nome, o.status AS os_status, o.data_entrada,
               o.mecanico_nome
        FROM requisicoes_material r
        INNER JOIN ordens_servico o ON o.numero_os = r.numero_os
        WHERE COALESCE(r.tipo_requisicao, 'os') = 'os'
          AND r.status = 'aguardando_responsavel'
        ORDER BY r.atualizado_em DESC, r.id DESC
        """
    ).fetchall()

    for row in rows_req:
        num = int(row["numero_os"])
        cadastro_ids = _ids_mecanico_cadastro_por_usuario(conn, int(row["mecanico_id"] or 0))
        nota_vinc = conn.execute(
            """
            SELECT id, situacao, pago, entrada
            FROM servicos
            WHERE numero_os_digital = ?
              AND UPPER(COALESCE(tipo_documento, '')) = 'NOTA'
            ORDER BY id DESC LIMIT 1
            """,
            (num,),
        ).fetchone()
        nota_orfa = None
        if nota_vinc is None:
            nota_orfa = _buscar_nota_orfa_cliente(
                conn,
                cliente_id=row["cliente_id"],
                mecanico_cadastro_ids=cadastro_ids,
                data_entrada=row["data_entrada"],
            )

        if nota_orfa is not None:
            _add({
                "chave": f"nota_sem_vinculo:{num}:{int(nota_orfa['id'])}",
                "tipo": "nota_sem_vinculo",
                "rotulo_tipo": _ROTULOS_TIPO["nota_sem_vinculo"],
                "numero_os": num,
                "requisicao_id": int(row["requisicao_id"]),
                "servico_id": int(nota_orfa["id"]),
                "cliente_nome": row["cliente_nome"] or nota_orfa["cliente_nome"] or "",
                "mecanico_nome": row["mecanico_nome"] or "",
                "os_status": row["os_status"] or "",
                "req_status": row["req_status"] or "",
                "detalhe": (
                    f"Existe NOTA (serviço #{nota_orfa['id']}) para o cliente, "
                    f"mas não está vinculada à O.S. nº {num}."
                ),
                "acoes_sugeridas": {
                    "vincular_os": True,
                    "sincronizar_status": True,
                    "encerrar_requisicao": True,
                },
                "atualizado_em": row["atualizado_em"] or row["enviada_em"] or "",
            })
            continue

        if nota_vinc is not None:
            _add({
                "chave": f"nota_req_pendente:{num}:{int(row['requisicao_id'])}",
                "tipo": "nota_com_requisicao_pendente",
                "rotulo_tipo": _ROTULOS_TIPO["nota_com_requisicao_pendente"],
                "numero_os": num,
                "requisicao_id": int(row["requisicao_id"]),
                "servico_id": int(nota_vinc["id"]),
                "cliente_nome": row["cliente_nome"] or "",
                "mecanico_nome": row["mecanico_nome"] or "",
                "os_status": row["os_status"] or "",
                "req_status": row["req_status"] or "",
                "detalhe": (
                    "A NOTA já está vinculada à O.S., mas a requisição continua "
                    "«aguardando responsável» (etapa pulada na Oficina)."
                ),
                "acoes_sugeridas": {
                    "vincular_os": False,
                    "sincronizar_status": True,
                    "encerrar_requisicao": True,
                },
                "atualizado_em": row["atualizado_em"] or "",
            })
            if not _servico_finalizado(nota_vinc["situacao"], nota_vinc["pago"]):
                _add({
                    "chave": f"status_desatualizado:{num}:{int(nota_vinc['id'])}",
                    "tipo": "status_desatualizado",
                    "rotulo_tipo": _ROTULOS_TIPO["status_desatualizado"],
                    "numero_os": num,
                    "requisicao_id": int(row["requisicao_id"]),
                    "servico_id": int(nota_vinc["id"]),
                    "cliente_nome": row["cliente_nome"] or "",
                    "mecanico_nome": row["mecanico_nome"] or "",
                    "os_status": row["os_status"] or "",
                    "req_status": row["req_status"] or "",
                    "detalhe": (
                        f"O.S. com status «{row['os_status']}» no app, mas o Controle "
                        f"de O.S. ainda está «{nota_vinc['situacao'] or 'Em andamento'}»."
                    ),
                    "acoes_sugeridas": {
                        "vincular_os": False,
                        "sincronizar_status": True,
                        "encerrar_requisicao": False,
                    },
                    "atualizado_em": row["atualizado_em"] or "",
                })
            continue

        _add({
            "chave": f"requisicao_aguardando:{num}:{int(row['requisicao_id'])}",
            "tipo": "requisicao_aguardando",
            "rotulo_tipo": _ROTULOS_TIPO["requisicao_aguardando"],
            "numero_os": num,
            "requisicao_id": int(row["requisicao_id"]),
            "servico_id": None,
            "cliente_nome": row["cliente_nome"] or "",
            "mecanico_nome": row["mecanico_nome"] or "",
            "os_status": row["os_status"] or "",
            "req_status": row["req_status"] or "",
            "detalhe": "Mecânico enviou a requisição e aguarda preços/resposta do responsável.",
            "acoes_sugeridas": {
                "vincular_os": False,
                "sincronizar_status": False,
                "encerrar_requisicao": False,
            },
            "atualizado_em": row["atualizado_em"] or row["enviada_em"] or "",
        })

    rows_os = conn.execute(
        """
        SELECT o.numero_os, o.cliente_id, o.cliente_nome, o.status, o.data_entrada,
               o.mecanico_id, o.mecanico_nome, o.dados_json
        FROM ordens_servico o
        WHERE o.status IN ('pronto_mecanico', 'cliente_avisado', 'entregue', 'fechado', 'concluido')
        ORDER BY o.numero_os DESC
        """
    ).fetchall()
    for row in rows_os:
        num = int(row["numero_os"])
        if any(p["numero_os"] == num and p["tipo"] == "status_desatualizado" for p in saida):
            continue
        nota = conn.execute(
            """
            SELECT id, situacao, pago
            FROM servicos
            WHERE numero_os_digital = ?
              AND UPPER(COALESCE(tipo_documento, '')) = 'NOTA'
            ORDER BY id DESC LIMIT 1
            """,
            (num,),
        ).fetchone()
        if nota is None:
            continue
        if _servico_finalizado(nota["situacao"], nota["pago"]):
            continue
        _add({
            "chave": f"status_desatualizado:{num}:{int(nota['id'])}",
            "tipo": "status_desatualizado",
            "rotulo_tipo": _ROTULOS_TIPO["status_desatualizado"],
            "numero_os": num,
            "requisicao_id": None,
            "servico_id": int(nota["id"]),
            "cliente_nome": row["cliente_nome"] or "",
            "mecanico_nome": row["mecanico_nome"] or "",
            "os_status": row["status"] or "",
            "req_status": "",
            "detalhe": (
                f"O.S. «{row['status']}» no app; Controle de O.S. ainda "
                f"«{nota['situacao'] or 'Em andamento'}»."
            ),
            "acoes_sugeridas": {
                "vincular_os": False,
                "sincronizar_status": True,
                "encerrar_requisicao": False,
            },
            "atualizado_em": "",
        })

    saida.sort(key=lambda x: (x.get("tipo") or "", -(x.get("numero_os") or 0)))
    return saida


def marcar_requisicao_atendida_nota_oficina(
    conn: sqlite3.Connection,
    req_id: int,
    *,
    usuario_nome: str = "responsavel",
) -> None:
    """Encerra requisição quando a NOTA já foi lançada direto no Controle de O.S."""
    agora = _agora()
    row = conn.execute(
        "SELECT observacao FROM requisicoes_material WHERE id = ?",
        (int(req_id),),
    ).fetchone()
    obs_ant = str(row["observacao"] or "").strip() if row else ""
    marca = "[Atendida via NOTA na Oficina — conferido pelo responsável]"
    obs = f"{obs_ant}\n{marca}".strip() if obs_ant else marca
    conn.execute(
        """
        UPDATE requisicoes_material SET
            status = 'respondida',
            ultima_acao_por = 'responsavel',
            observacao = ?,
            respondida_em = COALESCE(respondida_em, ?),
            atualizado_em = ?
        WHERE id = ? AND status = 'aguardando_responsavel'
        """,
        (obs, agora, agora, int(req_id)),
    )


def resolver_pendencia_integracao(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    *,
    usuario_id: int | None = None,
    usuario_nome: str = "",
) -> dict[str, Any]:
    """Aplica as ações marcadas pelo responsável em uma pendência."""
    numero_os = int(item.get("numero_os") or 0)
    if numero_os <= 0:
        raise ValueError("O.S. inválida na pendência.")
    acoes = item.get("acoes") or {}
    servico_id = item.get("servico_id")
    requisicao_id = item.get("requisicao_id")
    mensagens: list[str] = []

    os_row = conn.execute(
        """
        SELECT status, dados_json, cliente_id, mecanico_id, data_entrada
        FROM ordens_servico WHERE numero_os = ?
        """,
        (numero_os,),
    ).fetchone()
    if os_row is None:
        raise ValueError(f"O.S. nº {numero_os} não encontrada.")

    if acoes.get("vincular_os"):
        cadastro_ids = _ids_mecanico_cadastro_por_usuario(
            conn, int(os_row["mecanico_id"] or 0)
        )
        sid = None
        if servico_id:
            row_svc = conn.execute(
                """
                SELECT id, numero_os_digital FROM servicos
                WHERE id = ? AND UPPER(COALESCE(tipo_documento, '')) = 'NOTA'
                """,
                (int(servico_id),),
            ).fetchone()
            if row_svc and row_svc["numero_os_digital"] in (None, "", 0):
                conn.execute(
                    "UPDATE servicos SET numero_os_digital = ? WHERE id = ?",
                    (numero_os, int(servico_id)),
                )
                sid = int(servico_id)
        if sid is None:
            sid = tentar_vincular_servico_orfao_os(
                conn,
                numero_os,
                cliente_id=os_row["cliente_id"],
                mecanico_cadastro_ids=cadastro_ids,
                data_entrada=os_row["data_entrada"],
            )
        if sid:
            mensagens.append(f"NOTA #{sid} vinculada à O.S. nº {numero_os}.")
        else:
            mensagens.append("Não foi possível vincular NOTA automaticamente.")

    if acoes.get("sincronizar_status"):
        reconciliar_os_digital_com_oficina(
            conn,
            numero_os,
            status_web=str(os_row["status"] or ""),
            dados_json=os_row["dados_json"],
            cliente_id=os_row["cliente_id"],
            mecanico_usuario_id=os_row["mecanico_id"],
            data_entrada=os_row["data_entrada"],
        )
        mensagens.append("Status sincronizado com o Controle de O.S.")

    if acoes.get("encerrar_requisicao") and requisicao_id:
        marcar_requisicao_atendida_nota_oficina(
            conn,
            int(requisicao_id),
            usuario_nome=usuario_nome or "responsavel",
        )
        mensagens.append(f"Requisição #{requisicao_id} marcada como atendida.")

    return {
        "chave": item.get("chave"),
        "numero_os": numero_os,
        "mensagens": mensagens,
        "sucesso": True,
    }
