"""Checklist de Revisão por O.S. (v2.9+)."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from typing import Any

_PREFIXO_DIAGNOSTICO = "Diagnóstico do Checklist"
_PREFIXO_SERVICOS = "Serviços realizados"

# Marcadores legados (removidos na exportação; ainda limpos em O.S. antigas)
_MARCADOR_ORC_INICIO = "--- Checklist Revisão — Orçamento ---"
_MARCADOR_ORC_FIM = "--- Fim Checklist Orçamento ---"
_MARCADOR_MONT_INICIO = "--- Checklist Revisão — Montagem ---"
_MARCADOR_MONT_FIM = "--- Fim Checklist Montagem ---"

ITENS_CHECKLIST_REVISAO: list[dict[str, Any]] = [
    {"id": "orc_1", "secao": "orcamento", "numero": 1, "texto": "Aparência geral", "sub_opcao": None},
    {"id": "orc_2", "secao": "orcamento", "numero": 2, "texto": "Retirar óleo da rabeta", "sub_opcao": None},
    {"id": "orc_3", "secao": "orcamento", "numero": 3, "texto": "Verificar rotor", "sub_opcao": None},
    {"id": "orc_4", "secao": "orcamento", "numero": 4, "texto": "Retirar anodo do cavalete", "sub_opcao": None},
    {"id": "orc_5", "secao": "orcamento", "numero": 5, "texto": "Retirar anodos do bloco", "sub_opcao": None},
    {"id": "orc_6", "secao": "orcamento", "numero": 6, "texto": "Retirar anodo da mufla", "sub_opcao": None},
    {"id": "orc_7", "secao": "orcamento", "numero": 7, "texto": "Retirar e verificar velas", "sub_opcao": None},
    {"id": "orc_8", "secao": "orcamento", "numero": 8, "texto": "Retirar", "sub_opcao": "vst_carburador"},
    {"id": "orc_9", "secao": "orcamento", "numero": 9, "texto": "Verificar agulha da", "sub_opcao": "vst_carburador"},
    {"id": "orc_10", "secao": "orcamento", "numero": 10, "texto": "Retirar filtros de combustível", "sub_opcao": None},
    {"id": "orc_11", "secao": "orcamento", "numero": 11, "texto": "Verificar qual filtro separador lata ou elemento", "sub_opcao": None},
    {"id": "orc_12", "secao": "orcamento", "numero": 12, "texto": "Retirar óleo do cárter", "sub_opcao": None},
    {"id": "orc_13", "secao": "orcamento", "numero": 13, "texto": "Verificar borne de bateria", "sub_opcao": None},
    {"id": "orc_14", "secao": "orcamento", "numero": 14, "texto": "Escovar anodos", "sub_opcao": None},
    {"id": "orc_15", "secao": "orcamento", "numero": 15, "texto": "Conferir alarme do comando", "sub_opcao": None},
    {"id": "mont_1", "secao": "montagem", "numero": 1, "texto": "Limpeza da", "sub_opcao": "vst_carburador"},
    {"id": "mont_2", "secao": "montagem", "numero": 2, "texto": "Montagem da", "sub_opcao": "vst_carburador"},
    {"id": "mont_3", "secao": "montagem", "numero": 3, "texto": "Troca dos filtros de combustível", "sub_opcao": None},
    {"id": "mont_4", "secao": "montagem", "numero": 4, "texto": "Aperto com torque de 25nm das velas", "sub_opcao": None},
    {"id": "mont_5", "secao": "montagem", "numero": 5, "texto": "Recolocar os anodos do bloco", "sub_opcao": None},
    {"id": "mont_6", "secao": "montagem", "numero": 6, "texto": "Recolocar anodo da mufla", "sub_opcao": None},
    {"id": "mont_7", "secao": "montagem", "numero": 7, "texto": "Troca do filtro de óleo", "sub_opcao": None},
    {"id": "mont_8", "secao": "montagem", "numero": 8, "texto": "Colocar óleo do cárter", "sub_opcao": None},
    {"id": "mont_9", "secao": "montagem", "numero": 9, "texto": "Colocar óleo da rabeta", "sub_opcao": None},
    {"id": "mont_10", "secao": "montagem", "numero": 10, "texto": "Montar rotor", "sub_opcao": None},
    {"id": "mont_11", "secao": "montagem", "numero": 11, "texto": "Recolocar anodo cavalete", "sub_opcao": None},
    {"id": "mont_12", "secao": "montagem", "numero": 12, "texto": "Recolocar anodo da rabeta", "sub_opcao": None},
    {"id": "mont_13", "secao": "montagem", "numero": 13, "texto": "Conferir bujão do óleo de rabeta", "sub_opcao": None},
    {"id": "mont_14", "secao": "montagem", "numero": 14, "texto": "Conferir nível de óleo do cárter", "sub_opcao": None},
    {"id": "mont_15", "secao": "montagem", "numero": 15, "texto": "Limpar borne de bateria", "sub_opcao": None},
    {"id": "mont_16", "secao": "montagem", "numero": 16, "texto": "Lavar motor", "sub_opcao": None},
    {"id": "mont_17", "secao": "montagem", "numero": 17, "texto": "Lubricar motor", "sub_opcao": None},
    {"id": "mont_18", "secao": "montagem", "numero": 18, "texto": "Engraxar as articulações", "sub_opcao": None},
    {"id": "mont_19", "secao": "montagem", "numero": 19, "texto": "Colocar adesivo de revisão", "sub_opcao": None},
]

_ITENS_POR_ID = {item["id"]: item for item in ITENS_CHECKLIST_REVISAO}


def init_checklist_tabelas(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS checklists_revisao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_os INTEGER NOT NULL UNIQUE,
            mecanico_id INTEGER NOT NULL,
            cabecalho_json TEXT NOT NULL DEFAULT '{}',
            itens_json TEXT NOT NULL DEFAULT '[]',
            atualizado_em TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_checklist_rev_os ON checklists_revisao(numero_os);
        """
    )


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_json(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw or "")
    except json.JSONDecodeError:
        return default


def itens_estado_vazio() -> list[dict[str, Any]]:
    return [{"id": item["id"], "marcado": False, "sub_opcao": None} for item in ITENS_CHECKLIST_REVISAO]


def normalizar_itens_salvos(raw: list[Any] | None) -> list[dict[str, Any]]:
    por_id: dict[str, dict[str, Any]] = {}
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            iid = str(entry.get("id") or "")
            if iid in _ITENS_POR_ID:
                sub = entry.get("sub_opcao")
                if sub not in (None, "vst", "carburador"):
                    sub = None
                por_id[iid] = {
                    "id": iid,
                    "marcado": bool(entry.get("marcado")),
                    "sub_opcao": sub,
                }
    return [por_id.get(item["id"], {"id": item["id"], "marcado": False, "sub_opcao": None})
            for item in ITENS_CHECKLIST_REVISAO]


def montar_cabecalho_de_os(
    dados_os: dict[str, Any],
    *,
    mecanico_nome: str = "",
) -> dict[str, str]:
    fabricante = str(dados_os.get("fabricante") or "").strip()
    modelo = str(dados_os.get("modelo") or "").strip()
    motor = f"{fabricante} {modelo}".strip()
    return {
        "data": str(dados_os.get("data_entrada") or "").strip(),
        "embarcacao": str(dados_os.get("embarcacao_nome") or "").strip(),
        "motor": motor,
        "horas": str(dados_os.get("horas_uso") or "").strip(),
        "mecanico": (mecanico_nome or str(dados_os.get("mecanico_nome") or "")).strip(),
        "cliente": str(dados_os.get("cliente_nome") or "").strip(),
        "alegacoes": str(dados_os.get("alegacoes_cliente") or "").strip(),
    }


def _texto_item_marcado(item_def: dict[str, Any], estado: dict[str, Any]) -> str:
    texto = item_def["texto"]
    if item_def.get("sub_opcao") == "vst_carburador":
        sub = estado.get("sub_opcao")
        if sub == "vst":
            texto = f"{texto} VST"
        elif sub == "carburador":
            texto = f"{texto} carburador"
        else:
            texto = f"{texto} (VST/carburador)"
    return texto


def texto_itens_marcados(itens: list[dict[str, Any]], secao: str) -> str:
    """Itens marcados em texto corrido, separados por vírgula (uma linha)."""
    partes: list[str] = []
    estados = {x["id"]: x for x in itens if isinstance(x, dict)}
    for item_def in ITENS_CHECKLIST_REVISAO:
        if item_def["secao"] != secao:
            continue
        estado = estados.get(item_def["id"])
        if not estado or not estado.get("marcado"):
            continue
        partes.append(_texto_item_marcado(item_def, estado))
    return ", ".join(partes)


def _remover_bloco_marcador(texto: str, inicio: str, fim: str) -> str:
    if not texto:
        return ""
    pattern = re.escape(inicio) + r"[\s\S]*?" + re.escape(fim)
    return re.sub(pattern, "", texto).strip()


def _remover_sufixo_checklist(texto: str, prefixo_rotulo: str) -> str:
    """Remove sufixo [Prefixo: ...] gerado pelo checklist."""
    if not texto:
        return ""
    pattern = r"\n?\[" + re.escape(prefixo_rotulo) + r":[^\]]*\]"
    return re.sub(pattern, "", texto).strip()


def _limpar_exportacao_checklist(texto: str, *, secao: str) -> str:
    """Remove exportações antigas (traços) e atuais (colchetes) do campo."""
    if secao == "orcamento":
        texto = _remover_bloco_marcador(texto, _MARCADOR_ORC_INICIO, _MARCADOR_ORC_FIM)
        return _remover_sufixo_checklist(texto, _PREFIXO_DIAGNOSTICO)
    if secao == "montagem":
        texto = _remover_bloco_marcador(texto, _MARCADOR_MONT_INICIO, _MARCADOR_MONT_FIM)
        return _remover_sufixo_checklist(texto, _PREFIXO_SERVICOS)
    return (texto or "").strip()


def _texto_corrido_unica_linha(texto: str) -> str:
    """Garante texto em uma única linha (vírgulas no lugar de quebras)."""
    if not texto:
        return ""
    limpo = re.sub(r"\s*\n+\s*", ", ", str(texto).strip())
    limpo = re.sub(r",\s*,", ", ", limpo)
    return limpo.strip(" ,")


def _extrair_itens_formato_legado(texto: str) -> list[str]:
    """Converte listas antigas (• / traços) em lista de rótulos para join."""
    if not texto:
        return []
    itens: list[str] = []
    vistos: set[str] = set()

    def _add(raw: str) -> None:
        item = raw.strip().lstrip("•").strip()
        if item and item not in vistos:
            vistos.add(item)
            itens.append(item)

    blocos = (
        (_MARCADOR_ORC_INICIO, _MARCADOR_ORC_FIM),
        (_MARCADOR_MONT_INICIO, _MARCADOR_MONT_FIM),
    )
    restante = texto
    for inicio, fim in blocos:
        while inicio in restante:
            antes, depois = restante.split(inicio, 1)
            if fim in depois:
                corpo, depois = depois.split(fim, 1)
            else:
                corpo, depois = depois, ""
            for linha in corpo.split("\n"):
                t = linha.strip()
                if not t or (t.startswith("---") and t.endswith("---")):
                    continue
                _add(t)
            restante = antes + depois

    for linha in texto.split("\n"):
        t = linha.strip()
        if t.startswith("•"):
            _add(t)

    for prefixo in (_PREFIXO_DIAGNOSTICO, _PREFIXO_SERVICOS):
        match = re.search(
            r"\[" + re.escape(prefixo) + r":\s*([^\]]*)\]",
            texto,
        )
        if match:
            for parte in match.group(1).split(","):
                _add(parte)

    return itens


def _extrair_texto_manual_puro(texto: str, *, secao: str) -> str:
    """Remove qualquer injeção de checklist e devolve só o que o mecânico escreveu."""
    base = _limpar_exportacao_checklist(texto, secao=secao)
    linhas_limpas: list[str] = []
    for linha in base.split("\n"):
        t = linha.strip()
        if not t:
            if linhas_limpas and linhas_limpas[-1].strip():
                linhas_limpas.append("")
            continue
        if t.startswith("---") and "---" in t[3:]:
            continue
        if t.startswith("•"):
            continue
        if t.startswith("[") and t.endswith("]"):
            continue
        linhas_limpas.append(linha.rstrip())
    while linhas_limpas and not linhas_limpas[-1].strip():
        linhas_limpas.pop()
    return "\n".join(linhas_limpas).strip()


def _itens_csv_do_checklist(
    itens: list[dict[str, Any]] | None,
    secao: str,
    texto_legado: str,
) -> str:
    if itens is not None:
        return _texto_corrido_unica_linha(texto_itens_marcados(itens, secao))
    legado = _extrair_itens_formato_legado(texto_legado)
    return ", ".join(legado)


def mesclar_campo_com_checklist(texto_mecanico: str, itens_csv: str, prefixo_rotulo: str) -> str:
    """
    Preserva o texto do mecânico e acrescenta itens do checklist em uma linha:
    [Prefixo: item A, item B]
    """
    base = (texto_mecanico or "").strip()
    itens = _texto_corrido_unica_linha(itens_csv)
    if not itens:
        return base
    sufixo = f"[{prefixo_rotulo}: {itens}]"
    return f"{base}\n{sufixo}" if base else sufixo


def preparar_campos_diagnostico_os_para_impressao(
    dados: dict[str, Any],
    *,
    itens: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Formata constatação e conclusão para impressão/PDF.
    Limpa formato legado (listas verticais, traços) e aplica texto corrido.
    """
    saida = dict(dados)
    raw_constatacao = str(dados.get("constatacao_diagnostico") or "")
    raw_analise = str(dados.get("analise_reparos") or "")

    manual_constatacao = _extrair_texto_manual_puro(raw_constatacao, secao="orcamento")
    manual_analise = _extrair_texto_manual_puro(raw_analise, secao="montagem")

    csv_orc = _itens_csv_do_checklist(itens, "orcamento", raw_constatacao)
    csv_mont = _itens_csv_do_checklist(itens, "montagem", raw_analise)

    saida["constatacao_diagnostico"] = mesclar_campo_com_checklist(
        manual_constatacao, csv_orc, _PREFIXO_DIAGNOSTICO,
    )
    saida["analise_reparos"] = mesclar_campo_com_checklist(
        manual_analise, csv_mont, _PREFIXO_SERVICOS,
    )
    return saida


def carregar_itens_checklist_os(conn: sqlite3.Connection, numero_os: int) -> list[dict[str, Any]] | None:
    """Retorna itens salvos do checklist ou None se não existir registro."""
    init_checklist_tabelas(conn)
    row = conn.execute(
        "SELECT itens_json FROM checklists_revisao WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()
    if row is None:
        return None
    return normalizar_itens_salvos(_parse_json(row["itens_json"], []))


def _carregar_dados_os(conn: sqlite3.Connection, numero_os: int) -> tuple[sqlite3.Row, dict[str, Any]]:
    row = conn.execute(
        """
        SELECT numero_os, mecanico_id, mecanico_nome, dados_json
        FROM ordens_servico WHERE numero_os = ?
        """,
        (int(numero_os),),
    ).fetchone()
    if row is None:
        raise ValueError(f"O.S. nº {numero_os} não encontrada.")
    dados = _parse_json(row["dados_json"], {})
    if not isinstance(dados, dict):
        dados = {}
    return row, dados


def checklist_para_json(row: sqlite3.Row | None, *, modelo_itens: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    modelo = modelo_itens or itens_estado_vazio()
    if row is None:
        return {
            "numero_os": None,
            "cabecalho": {},
            "itens": modelo,
            "itens_modelo": ITENS_CHECKLIST_REVISAO,
            "atualizado_em": "",
        }
    return {
        "id": row["id"],
        "numero_os": row["numero_os"],
        "mecanico_id": row["mecanico_id"],
        "cabecalho": _parse_json(row["cabecalho_json"], {}),
        "itens": normalizar_itens_salvos(_parse_json(row["itens_json"], [])),
        "itens_modelo": ITENS_CHECKLIST_REVISAO,
        "atualizado_em": row["atualizado_em"] or "",
    }


def obter_ou_rascunho_checklist(
    conn: sqlite3.Connection,
    numero_os: int,
    *,
    mecanico_id: int,
    mecanico_nome: str,
) -> dict[str, Any]:
    init_checklist_tabelas(conn)
    row_os, dados = _carregar_dados_os(conn, numero_os)
    if row_os["mecanico_id"] is None or int(row_os["mecanico_id"]) != int(mecanico_id):
        raise ValueError("Esta O.S. não está atribuída a este mecânico.")

    row = conn.execute(
        "SELECT * FROM checklists_revisao WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()

    cabecalho = montar_cabecalho_de_os(
        {**dados, "mecanico_nome": row_os["mecanico_nome"] or mecanico_nome},
        mecanico_nome=mecanico_nome or str(row_os["mecanico_nome"] or ""),
    )

    if row is None:
        return {
            "numero_os": numero_os,
            "cabecalho": cabecalho,
            "itens": itens_estado_vazio(),
            "itens_modelo": ITENS_CHECKLIST_REVISAO,
            "atualizado_em": "",
            "rascunho": True,
        }

    payload = checklist_para_json(row)
    payload["rascunho"] = False
    merged = dict(payload["cabecalho"])
    for chave, valor in cabecalho.items():
        if chave == "horas" and merged.get("horas"):
            continue
        if not merged.get(chave):
            merged[chave] = valor
    payload["cabecalho"] = merged
    return payload


def obter_checklist_leitura(
    conn: sqlite3.Connection,
    numero_os: int,
) -> dict[str, Any] | None:
    init_checklist_tabelas(conn)
    row = conn.execute(
        "SELECT * FROM checklists_revisao WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()
    if row is None:
        row_os, dados = _carregar_dados_os(conn, numero_os)
        cabecalho = montar_cabecalho_de_os(
            {**dados, "mecanico_nome": row_os["mecanico_nome"]},
            mecanico_nome=str(row_os["mecanico_nome"] or ""),
        )
        return {
            "numero_os": numero_os,
            "cabecalho": cabecalho,
            "itens": itens_estado_vazio(),
            "itens_modelo": ITENS_CHECKLIST_REVISAO,
            "atualizado_em": "",
            "rascunho": True,
        }
    payload = checklist_para_json(row)
    payload["rascunho"] = False
    return payload


def aplicar_append_os(
    conn: sqlite3.Connection,
    numero_os: int,
    *,
    cabecalho: dict[str, Any],
    itens: list[dict[str, Any]],
) -> None:
    row_os, dados = _carregar_dados_os(conn, numero_os)
    horas = str(cabecalho.get("horas") or "").strip()
    if horas:
        dados["horas_uso"] = horas

    formatado = preparar_campos_diagnostico_os_para_impressao(dados, itens=itens)
    dados["constatacao_diagnostico"] = formatado["constatacao_diagnostico"]
    dados["analise_reparos"] = formatado["analise_reparos"]

    agora = _agora()
    conn.execute(
        """
        UPDATE ordens_servico SET dados_json = ?, atualizado_em = ? WHERE numero_os = ?
        """,
        (json.dumps(dados, ensure_ascii=False), agora, int(numero_os)),
    )


def salvar_checklist(
    conn: sqlite3.Connection,
    numero_os: int,
    *,
    mecanico_id: int,
    cabecalho: dict[str, Any],
    itens: list[dict[str, Any]],
) -> dict[str, Any]:
    init_checklist_tabelas(conn)
    row_os, _ = _carregar_dados_os(conn, numero_os)
    if row_os["mecanico_id"] is None or int(row_os["mecanico_id"]) != int(mecanico_id):
        raise ValueError("Esta O.S. não está atribuída a este mecânico.")

    itens_norm = normalizar_itens_salvos(itens)
    cabecalho_json = json.dumps(cabecalho, ensure_ascii=False)
    itens_json = json.dumps(itens_norm, ensure_ascii=False)
    agora = _agora()

    existente = conn.execute(
        "SELECT id FROM checklists_revisao WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()

    if existente is None:
        conn.execute(
            """
            INSERT INTO checklists_revisao (
                numero_os, mecanico_id, cabecalho_json, itens_json, atualizado_em
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (int(numero_os), int(mecanico_id), cabecalho_json, itens_json, agora),
        )
    else:
        conn.execute(
            """
            UPDATE checklists_revisao SET
                cabecalho_json = ?, itens_json = ?, atualizado_em = ?
            WHERE numero_os = ?
            """,
            (cabecalho_json, itens_json, agora, int(numero_os)),
        )

    aplicar_append_os(conn, numero_os, cabecalho=cabecalho, itens=itens_norm)

    row = conn.execute(
        "SELECT * FROM checklists_revisao WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()
    payload = checklist_para_json(row)
    payload["rascunho"] = False
    return payload
