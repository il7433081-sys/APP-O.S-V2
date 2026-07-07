"""Histórico de serviços no perfil do mecânico (consulta por mês/cliente/O.S.)."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from fluxo_requisicoes import _itens_para_mecanico, _parse_itens

_HISTORICO_DIAS_VISIVEL = 365
_MESES_PT = (
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)
_OS_FINALIZADAS = frozenset({
    "pronto_mecanico",
    "cliente_avisado",
    "entregue",
    "concluido",
    "fechado",
})
_REQ_STATUS_HISTORICO = frozenset({
    "respondida",
    "alterada_responsavel",
    "aprovada",
    "finalizada",
})


def garantir_tabela_lembrete(conn_app: sqlite3.Connection) -> None:
    conn_app.execute(
        """
        CREATE TABLE IF NOT EXISTS mecanico_servico_lembrete (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_mecanico_id INTEGER NOT NULL,
            numero_os INTEGER NOT NULL,
            servico_id INTEGER,
            servico_realizado TEXT NOT NULL DEFAULT '',
            atualizado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            UNIQUE (usuario_mecanico_id, numero_os)
        )
        """
    )
    conn_app.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_msl_usuario_os
        ON mecanico_servico_lembrete (usuario_mecanico_id, numero_os)
        """
    )


def _ids_mecanico_cadastro_usuario(
    conn: sqlite3.Connection,
    usuario_mecanico_id: int,
) -> set[int]:
    urow = conn.execute(
        "SELECT id, nome_exibicao, mecanico_cadastro_id FROM usuarios WHERE id = ?",
        (int(usuario_mecanico_id),),
    ).fetchone()
    if urow is None:
        return set()
    ids: set[int] = set()
    if urow["mecanico_cadastro_id"] is not None:
        ids.add(int(urow["mecanico_cadastro_id"]))
    nome_u = str(urow["nome_exibicao"] or "").strip().upper()
    if not nome_u:
        return ids
    for row in conn.execute("SELECT id, nome FROM mecanicos").fetchall():
        nome_m = str(row["nome"] or "").strip().upper()
        if not nome_m:
            continue
        if (
            nome_m == nome_u
            or nome_m.startswith(nome_u + " ")
            or nome_u.startswith(nome_m.split()[0] + " ")
            or nome_m.split()[0] == nome_u
        ):
            ids.add(int(row["id"]))
    return ids


def _parse_data_referencia(txt: str | None) -> date | None:
    s = str(txt or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _servico_controle_finalizado(row: sqlite3.Row) -> bool:
    sit = str(row["situacao"] or "").strip().casefold()
    if sit in {"entregue", "pronto"}:
        return True
    try:
        return int(row["pago"] or 0) == 1
    except (TypeError, ValueError):
        return False


def _pecas_de_servico_itens_json(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    pecas: list[dict[str, Any]] = []
    vistos: set[str] = set()

    def _add(desc: str, qtd: Any) -> None:
        desc = str(desc or "").strip()
        if not desc:
            return
        chave = desc.casefold()
        if chave in vistos:
            return
        vistos.add(chave)
        try:
            quantidade = float(str(qtd or "1").replace(",", "."))
        except (TypeError, ValueError):
            quantidade = 1.0
        pecas.append({"descricao": desc, "quantidade": quantidade})

    if isinstance(data, dict):
        for p in data.get("pecas") or []:
            if isinstance(p, dict):
                _add(p.get("descricao"), p.get("quantidade"))
        for item in data.get("itens") or []:
            if isinstance(item, dict):
                cat = str(item.get("categoria") or item.get("tipo") or "").upper()
                if "SERV" in cat:
                    continue
                _add(item.get("descricao"), item.get("quantidade"))
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            if str(item.get("tipo_item") or "").lower() == "mo":
                continue
            cat = str(item.get("categoria") or "").upper()
            if cat == "SERVIÇO":
                continue
            _add(item.get("descricao"), item.get("quantidade"))
    return pecas


def _pecas_de_requisicao_itens(raw: str | None) -> list[dict[str, Any]]:
    itens = _itens_para_mecanico(_parse_itens(raw))
    pecas: list[dict[str, Any]] = []
    for item in itens:
        if str(item.get("tipo_item") or "").lower() == "mo":
            continue
        desc = str(item.get("descricao") or "").strip()
        if not desc:
            continue
        try:
            qtd = float(str(item.get("quantidade") or "1").replace(",", "."))
        except (TypeError, ValueError):
            qtd = 1.0
        pecas.append({"descricao": desc, "quantidade": qtd})
    return pecas


def _mesclar_pecas(*listas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for lista in listas:
        for p in lista:
            desc = str(p.get("descricao") or "").strip()
            if not desc:
                continue
            chave = desc.casefold()
            if chave in vistos:
                continue
            vistos.add(chave)
            out.append(p)
    return out


def _dados_os_dict(raw: str | None) -> dict[str, Any]:
    try:
        dados = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return dados if isinstance(dados, dict) else {}


def _motor_de_dados_os(dados: dict[str, Any]) -> str:
    fab = str(dados.get("fabricante") or "").strip()
    mod = str(dados.get("modelo") or "").strip()
    motor = f"{fab} {mod}".strip()
    return motor or "—"


def _texto_busca_normalizado(txt: str | None) -> str:
    return re.sub(r"\s+", " ", str(txt or "").strip().casefold())


def _filtro_ativo(
    *,
    ano: int | None,
    mes: int | None,
    cliente: str,
    servico: str,
    incluir_antigos: bool,
) -> bool:
    if incluir_antigos:
        return True
    if ano or mes or cliente.strip() or servico.strip():
        return True
    return False


def _carregar_lembretes(
    conn_app: sqlite3.Connection,
    usuario_mecanico_id: int,
) -> dict[int, dict[str, Any]]:
    garantir_tabela_lembrete(conn_app)
    rows = conn_app.execute(
        """
        SELECT numero_os, servico_id, servico_realizado, atualizado_em
        FROM mecanico_servico_lembrete
        WHERE usuario_mecanico_id = ?
        """,
        (int(usuario_mecanico_id),),
    ).fetchall()
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        out[int(row["numero_os"])] = {
            "servico_id": row["servico_id"],
            "servico_realizado": str(row["servico_realizado"] or "").strip(),
            "atualizado_em": str(row["atualizado_em"] or "").strip(),
        }
    return out


def listar_historico_servicos_mecanico(
    conn_app: sqlite3.Connection,
    conn_principal: sqlite3.Connection,
    usuario_mecanico_id: int,
    *,
    ano: int | None = None,
    mes: int | None = None,
    cliente: str = "",
    servico: str = "",
    incluir_antigos: bool = False,
) -> dict[str, Any]:
    uid = int(usuario_mecanico_id)
    hoje = date.today()
    limite = hoje - timedelta(days=_HISTORICO_DIAS_VISIVEL)
    filtro_explicito = _filtro_ativo(
        ano=ano,
        mes=mes,
        cliente=cliente,
        servico=servico,
        incluir_antigos=incluir_antigos,
    )
    cliente_filtro = _texto_busca_normalizado(cliente)
    servico_filtro = _texto_busca_normalizado(servico)

    cadastro_ids = _ids_mecanico_cadastro_usuario(conn_principal, uid)
    lembretes = _carregar_lembretes(conn_app, uid)

    os_rows: dict[int, sqlite3.Row] = {}
    if cadastro_ids:
        ph = ", ".join("?" * len(_OS_FINALIZADAS))
        rows = conn_app.execute(
            f"""
            SELECT numero_os, cliente_nome, status, data_entrada, atualizado_em, dados_json
            FROM ordens_servico
            WHERE mecanico_id = ?
              AND LOWER(COALESCE(status, 'aberto')) IN ({ph})
            ORDER BY numero_os DESC
            """,
            (uid, *tuple(sorted(_OS_FINALIZADAS))),
        ).fetchall()
        for row in rows:
            os_rows[int(row["numero_os"])] = row

    servicos_por_os: dict[int, sqlite3.Row] = {}
    if cadastro_ids:
        placeholders = ", ".join("?" * len(cadastro_ids))
        srows = conn_principal.execute(
            f"""
            SELECT s.id, s.entrada, s.saida, s.servico_efetuado, s.alegacao_cliente,
                   s.relato_mecanico, s.itens_json, s.situacao, s.pago,
                   s.numero_os_digital, m.marca_modelo, c.nome AS cliente_nome
            FROM servicos s
            JOIN motores m ON m.id = s.motor_id
            JOIN clientes c ON c.id = m.cliente_id
            WHERE s.mecanico_id IN ({placeholders})
              AND s.numero_os_digital IS NOT NULL
              AND UPPER(COALESCE(s.tipo_documento, '')) = 'NOTA'
            ORDER BY s.id DESC
            """,
            tuple(sorted(cadastro_ids)),
        ).fetchall()
        for row in srows:
            if not _servico_controle_finalizado(row):
                continue
            nos = int(row["numero_os_digital"])
            if nos not in servicos_por_os:
                servicos_por_os[nos] = row

    numeros_os = sorted(set(os_rows.keys()) | set(servicos_por_os.keys()), reverse=True)

    registros: list[dict[str, Any]] = []
    clientes_disp: set[str] = set()
    anos_disp: set[int] = set()
    total_ocultos = 0

    for numero_os in numeros_os:
        os_row = os_rows.get(numero_os)
        svc_row = servicos_por_os.get(numero_os)
        dados_os = _dados_os_dict(os_row["dados_json"] if os_row else None)

        if os_row:
            cliente_nome = str(os_row["cliente_nome"] or "").strip()
            data_ref_txt = (
                str(os_row["data_entrada"] or "").strip()
                or str(os_row["atualizado_em"] or "").strip()
            )
            motor = _motor_de_dados_os(dados_os)
        elif svc_row:
            cliente_nome = str(svc_row["cliente_nome"] or "").strip()
            data_ref_txt = str(svc_row["entrada"] or svc_row["saida"] or "").strip()
            motor = str(svc_row["marca_modelo"] or "").strip() or "—"
        else:
            continue

        data_ref = _parse_data_referencia(data_ref_txt)
        if data_ref is None and svc_row:
            data_ref = _parse_data_referencia(str(svc_row["saida"] or ""))
        if data_ref is None:
            data_ref = hoje

        antigo = data_ref < limite
        if antigo and not filtro_explicito:
            total_ocultos += 1
            continue

        cliente_norm = _texto_busca_normalizado(cliente_nome.split()[0] if cliente_nome else "")
        clientes_disp.add(cliente_nome.split()[0] if cliente_nome else "—")
        anos_disp.add(data_ref.year)

        if ano and data_ref.year != int(ano):
            continue
        if mes and data_ref.month != int(mes):
            continue
        if cliente_filtro and cliente_filtro not in _texto_busca_normalizado(cliente_nome):
            continue

        servico_id = int(svc_row["id"]) if svc_row else None
        lembrete = lembretes.get(numero_os, {})
        servico_realizado = str(lembrete.get("servico_realizado") or "").strip()
        if not servico_realizado and svc_row:
            servico_realizado = str(svc_row["servico_efetuado"] or "").strip()
        if not servico_realizado:
            servico_realizado = str(
                dados_os.get("analise_reparos")
                or dados_os.get("constatacao_diagnostico")
                or ""
            ).strip()

        if servico_filtro and servico_filtro not in _texto_busca_normalizado(servico_realizado):
            continue

        alegacao = ""
        if svc_row and svc_row["alegacao_cliente"]:
            alegacao = str(svc_row["alegacao_cliente"] or "").strip()
        if not alegacao:
            alegacao = str(dados_os.get("alegacoes_cliente") or "").strip()

        relato = ""
        if svc_row and svc_row["relato_mecanico"]:
            relato = str(svc_row["relato_mecanico"] or "").strip()
        if not relato:
            relato = str(
                dados_os.get("analise_reparos")
                or dados_os.get("constatacao_diagnostico")
                or ""
            ).strip()

        pecas_svc = _pecas_de_servico_itens_json(
            str(svc_row["itens_json"] or "") if svc_row else None
        )
        req_rows = conn_app.execute(
            """
            SELECT id, itens_json, status
            FROM requisicoes_material
            WHERE numero_os = ? AND mecanico_id = ?
              AND LOWER(COALESCE(status, '')) IN (
                  'respondida', 'alterada_responsavel', 'aprovada', 'finalizada'
              )
            ORDER BY id ASC
            """,
            (numero_os, uid),
        ).fetchall()
        pecas_req: list[dict[str, Any]] = []
        req_ids: list[int] = []
        for rr in req_rows:
            st = str(rr["status"] or "").lower()
            if st not in _REQ_STATUS_HISTORICO:
                continue
            req_ids.append(int(rr["id"]))
            pecas_req.extend(_pecas_de_requisicao_itens(str(rr["itens_json"] or "")))

        pecas = _mesclar_pecas(pecas_svc, pecas_req)

        chave_mes = f"{data_ref.year:04d}-{data_ref.month:02d}"
        mes_rotulo = f"{_MESES_PT[data_ref.month]}/{data_ref.year}"

        registros.append(
            {
                "numero_os": numero_os,
                "servico_id": servico_id,
                "requisicao_ids": req_ids,
                "data_referencia": data_ref.isoformat(),
                "data_exibicao": data_ref.strftime("%d/%m/%Y"),
                "chave_mes": chave_mes,
                "mes_rotulo": mes_rotulo,
                "cliente_nome": cliente_nome or "—",
                "cliente_primeiro_nome": cliente_nome.split()[0] if cliente_nome else "—",
                "motor": motor,
                "servico_realizado": servico_realizado,
                "alegacao_cliente": alegacao,
                "relato_mecanico": relato,
                "pecas": pecas,
                "antigo": antigo,
                "editavel": True,
            }
        )

    meses_map: dict[str, dict[str, Any]] = {}
    for reg in registros:
        chave = reg["chave_mes"]
        if chave not in meses_map:
            meses_map[chave] = {
                "chave": chave,
                "rotulo": reg["mes_rotulo"],
                "clientes": {},
            }
        cm = meses_map[chave]["clientes"]
        cn = reg["cliente_nome"]
        if cn not in cm:
            cm[cn] = {"nome": cn, "requisicoes": []}
        cm[cn]["requisicoes"].append(reg)

    meses_lista: list[dict[str, Any]] = []
    for chave in sorted(meses_map.keys(), reverse=True):
        bloco = meses_map[chave]
        clientes_lista = []
        for cn in sorted(bloco["clientes"].keys()):
            reqs = bloco["clientes"][cn]["requisicoes"]
            reqs.sort(key=lambda r: (r.get("data_referencia") or ""), reverse=True)
            clientes_lista.append({"nome": cn, "requisicoes": reqs})
        meses_lista.append(
            {
                "chave": bloco["chave"],
                "rotulo": bloco["rotulo"],
                "clientes": clientes_lista,
            }
        )

    return {
        "meses": meses_lista,
        "filtros": {
            "anos_disponiveis": sorted(anos_disp, reverse=True),
            "clientes_disponiveis": sorted(clientes_disp, key=lambda x: x.casefold()),
        },
        "limite_dias": _HISTORICO_DIAS_VISIVEL,
        "total_visiveis": len(registros),
        "total_ocultos": total_ocultos,
        "filtro_explicito": filtro_explicito,
    }


def atualizar_servico_realizado_mecanico(
    conn_app: sqlite3.Connection,
    conn_principal: sqlite3.Connection,
    usuario_mecanico_id: int,
    *,
    numero_os: int,
    servico_id: int | None,
    texto: str,
) -> dict[str, Any]:
    uid = int(usuario_mecanico_id)
    nos = int(numero_os)
    texto_limpo = str(texto or "").strip()
    garantir_tabela_lembrete(conn_app)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn_app.execute(
        """
        INSERT INTO mecanico_servico_lembrete (
            usuario_mecanico_id, numero_os, servico_id, servico_realizado, atualizado_em
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(usuario_mecanico_id, numero_os) DO UPDATE SET
            servico_id = excluded.servico_id,
            servico_realizado = excluded.servico_realizado,
            atualizado_em = excluded.atualizado_em
        """,
        (uid, nos, servico_id, texto_limpo, agora),
    )

    if servico_id:
        cadastro_ids = _ids_mecanico_cadastro_usuario(conn_principal, uid)
        if cadastro_ids:
            placeholders = ", ".join("?" * len(cadastro_ids))
            row = conn_principal.execute(
                f"""
                SELECT id FROM servicos
                WHERE id = ? AND mecanico_id IN ({placeholders})
                  AND numero_os_digital = ?
                """,
                (int(servico_id), *tuple(sorted(cadastro_ids)), nos),
            ).fetchone()
            if row:
                conn_principal.execute(
                    "UPDATE servicos SET servico_efetuado = ? WHERE id = ?",
                    (texto_limpo or None, int(servico_id)),
                )

    return {"servico_realizado": texto_limpo, "atualizado_em": agora}
