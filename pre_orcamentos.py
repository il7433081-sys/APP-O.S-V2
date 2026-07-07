"""Configurador de Pré-Orçamentos — banco dedicado (kits de motor + pré-orçamentos)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

STATUS_RASCUNHO = "rascunho"
STATUS_SALVO = "salvo"
STATUS_CONVERTIDO_OS = "convertido_os"

_ITEM_PADRAO = {
    "descricao": "",
    "quantidade": 1,
    "valor_unitario": 0.0,
    "tipo": "peca",
}


def caminho_banco_pre_orcamentos(app_dir: Path) -> Path:
    pasta = app_dir / "dados"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / "pre_orcamentos.db"


def init_pre_orcamentos_tabelas(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS kits_motor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modelo_motor TEXT NOT NULL,
            lista_pecas_json TEXT NOT NULL DEFAULT '[]',
            preco_base REAL NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            atualizado_em TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_kits_motor_modelo ON kits_motor(modelo_motor);

        CREATE TABLE IF NOT EXISTS pre_orcamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL UNIQUE,
            cliente_nome TEXT NOT NULL,
            cliente_id INTEGER,
            motor TEXT NOT NULL,
            motor_id INTEGER,
            data TEXT NOT NULL,
            itens TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'salvo',
            numero_os_gerado INTEGER,
            kit_motor_id INTEGER,
            preco_total REAL NOT NULL DEFAULT 0,
            observacoes TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            atualizado_em TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pre_orcamentos_status ON pre_orcamentos(status);
        CREATE INDEX IF NOT EXISTS idx_pre_orcamentos_data ON pre_orcamentos(data);
        CREATE INDEX IF NOT EXISTS idx_pre_orcamentos_numero ON pre_orcamentos(numero);
        """
    )


def garantir_banco_pre_orcamentos(caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(caminho, timeout=30)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        init_pre_orcamentos_tabelas(conn)
        conn.commit()
    finally:
        conn.close()


def _agora_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalizar_itens(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except json.JSONDecodeError:
            raw = []
    if not isinstance(raw, list):
        return []
    saida: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        desc = str(item.get("descricao") or "").strip()
        if not desc:
            continue
        try:
            qtd = float(item.get("quantidade") or 1)
        except (TypeError, ValueError):
            qtd = 1.0
        if qtd <= 0:
            qtd = 1.0
        try:
            valor = float(item.get("valor_unitario") or 0)
        except (TypeError, ValueError):
            valor = 0.0
        tipo = str(item.get("tipo") or "peca").strip().lower()
        if tipo not in ("peca", "servico"):
            tipo = "peca"
        registro: dict[str, Any] = {
            "descricao": desc,
            "quantidade": qtd,
            "valor_unitario": round(valor, 2),
            "tipo": tipo,
        }
        cat_id = item.get("catalogo_id")
        if cat_id not in (None, "", 0):
            try:
                registro["catalogo_id"] = int(cat_id)
            except (TypeError, ValueError):
                pass
        saida.append(registro)
    return saida


def _total_itens(itens: list[dict[str, Any]]) -> float:
    return round(
        sum(float(i.get("quantidade") or 0) * float(i.get("valor_unitario") or 0) for i in itens),
        2,
    )


def _kit_para_json(row: sqlite3.Row) -> dict[str, Any]:
    itens = _normalizar_itens(row["lista_pecas_json"])
    return {
        "id": int(row["id"]),
        "modelo_motor": str(row["modelo_motor"] or ""),
        "lista_pecas": itens,
        "lista_pecas_json": json.dumps(itens, ensure_ascii=False),
        "preco_base": float(row["preco_base"] or 0),
        "criado_em": str(row["criado_em"] or ""),
        "atualizado_em": str(row["atualizado_em"] or ""),
    }


def _pre_orcamento_para_json(row: sqlite3.Row) -> dict[str, Any]:
    itens = _normalizar_itens(row["itens"])
    return {
        "id": int(row["id"]),
        "numero": str(row["numero"] or ""),
        "cliente_nome": str(row["cliente_nome"] or ""),
        "cliente_id": int(row["cliente_id"]) if row["cliente_id"] else None,
        "motor": str(row["motor"] or ""),
        "motor_id": int(row["motor_id"]) if row["motor_id"] else None,
        "data": str(row["data"] or "")[:10],
        "itens": itens,
        "status": str(row["status"] or STATUS_SALVO),
        "numero_os_gerado": int(row["numero_os_gerado"]) if row["numero_os_gerado"] else None,
        "kit_motor_id": int(row["kit_motor_id"]) if row["kit_motor_id"] else None,
        "preco_total": float(row["preco_total"] or 0),
        "observacoes": str(row["observacoes"] or ""),
        "criado_em": str(row["criado_em"] or ""),
        "atualizado_em": str(row["atualizado_em"] or ""),
    }


def proximo_numero_pre_orcamento(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
        SELECT numero FROM pre_orcamentos
        WHERE numero GLOB 'PRE-[0-9]*'
        ORDER BY CAST(SUBSTR(numero, 5) AS INTEGER) DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return "PRE-001"
    texto = str(row["numero"] or "")
    try:
        seq = int(texto.split("-", 1)[1])
    except (IndexError, ValueError):
        seq = conn.execute("SELECT COUNT(*) AS n FROM pre_orcamentos").fetchone()["n"]
    return f"PRE-{seq + 1:03d}"


def _rank_kit_busca(modelo: str, termo: str) -> tuple[int, int, str]:
    """Menor tupla = melhor correspondência (exato, depois mais curto, depois A-Z)."""
    m = str(modelo or "").strip().casefold()
    t = str(termo or "").strip().casefold()
    if not t:
        return (0, len(m), m)
    if m == t:
        return (0, len(m), m)
    if m.startswith(t):
        return (1, len(m), m)
    if t in m:
        return (2, len(m), m)
    return (3, len(m), m)


def buscar_kits_motor(
    conn: sqlite3.Connection,
    *,
    termo: str = "",
    limite: int = 25,
    modo: str = "busca",
) -> list[dict[str, Any]]:
    termo_norm = str(termo or "").strip()
    limite = max(1, min(int(limite or 25), 100))
    modo_norm = str(modo or "busca").strip().lower()
    if not termo_norm:
        rows = conn.execute(
            """
            SELECT * FROM kits_motor
            ORDER BY modelo_motor ASC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()
        return [_kit_para_json(r) for r in rows]

    if modo_norm in ("sugestao", "sugestoes", "autocomplete"):
        padrao = f"{termo_norm}%"
        rows = conn.execute(
            """
            SELECT * FROM kits_motor
            WHERE modelo_motor LIKE ? COLLATE NOCASE
            ORDER BY
                CASE WHEN modelo_motor = ? COLLATE NOCASE THEN 0 ELSE 1 END,
                length(modelo_motor) ASC,
                modelo_motor ASC
            LIMIT ?
            """,
            (padrao, termo_norm, limite),
        ).fetchall()
        return [_kit_para_json(r) for r in rows]

    padrao_inicio = f"{termo_norm}%"
    padrao_contem = f"%{termo_norm}%"
    rows = conn.execute(
        """
        SELECT * FROM kits_motor
        WHERE modelo_motor LIKE ? COLLATE NOCASE
           OR modelo_motor LIKE ? COLLATE NOCASE
        """,
        (padrao_inicio, padrao_contem),
    ).fetchall()
    kits = [_kit_para_json(r) for r in rows]
    kits.sort(key=lambda k: _rank_kit_busca(k["modelo_motor"], termo_norm))
    return kits[:limite]


def buscar_kit_motor_exato(
    conn: sqlite3.Connection,
    modelo_motor: str,
) -> dict[str, Any] | None:
    modelo = str(modelo_motor or "").strip()
    if not modelo:
        return None
    row = conn.execute(
        "SELECT * FROM kits_motor WHERE modelo_motor = ? COLLATE NOCASE",
        (modelo,),
    ).fetchone()
    return _kit_para_json(row) if row else None


def obter_kit_motor(conn: sqlite3.Connection, kit_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM kits_motor WHERE id = ?", (int(kit_id),)).fetchone()
    if row is None:
        return None
    return _kit_para_json(row)


def salvar_kit_motor(
    conn: sqlite3.Connection,
    *,
    modelo_motor: str,
    lista_pecas: Any,
    preco_base: float | None = None,
    kit_id: int | None = None,
) -> dict[str, Any]:
    modelo = str(modelo_motor or "").strip()
    if not modelo:
        raise ValueError("Informe o modelo do motor.")
    itens = _normalizar_itens(lista_pecas)
    if not itens:
        raise ValueError("O kit precisa ter ao menos uma peça ou serviço.")
    total = _total_itens(itens)
    preco = round(float(preco_base), 2) if preco_base is not None else total
    agora = _agora_local()
    itens_json = json.dumps(itens, ensure_ascii=False)
    if kit_id:
        atual_row = conn.execute(
            "SELECT id, modelo_motor FROM kits_motor WHERE id = ?",
            (int(kit_id),),
        ).fetchone()
        if atual_row is None:
            raise ValueError("Kit não encontrado.")
        modelo_existente = str(atual_row["modelo_motor"] or "").strip()
        if modelo_existente.casefold() != modelo.casefold():
            kit_id = None
    if not kit_id:
        existente = conn.execute(
            "SELECT id FROM kits_motor WHERE modelo_motor = ? COLLATE NOCASE",
            (modelo,),
        ).fetchone()
        if existente is not None:
            kit_id = int(existente["id"])
    if kit_id:
        atual = conn.execute("SELECT id FROM kits_motor WHERE id = ?", (int(kit_id),)).fetchone()
        if atual is None:
            raise ValueError("Kit não encontrado.")
        conn.execute(
            """
            UPDATE kits_motor
            SET modelo_motor = ?, lista_pecas_json = ?, preco_base = ?, atualizado_em = ?
            WHERE id = ?
            """,
            (modelo, itens_json, preco, agora, int(kit_id)),
        )
        saida_id = int(kit_id)
    else:
        cur = conn.execute(
            """
            INSERT INTO kits_motor (modelo_motor, lista_pecas_json, preco_base, criado_em)
            VALUES (?, ?, ?, ?)
            """,
            (modelo, itens_json, preco, agora),
        )
        saida_id = int(cur.lastrowid)
    item = obter_kit_motor(conn, saida_id)
    if item is None:
        raise RuntimeError("Falha ao salvar kit.")
    return item


def excluir_kit_motor(conn: sqlite3.Connection, kit_id: int) -> None:
    atual = conn.execute("SELECT id FROM kits_motor WHERE id = ?", (int(kit_id),)).fetchone()
    if atual is None:
        raise ValueError("Kit não encontrado.")
    conn.execute("DELETE FROM kits_motor WHERE id = ?", (int(kit_id),))


def listar_todos_kits_motor(
    conn: sqlite3.Connection,
    *,
    limite: int = 500,
) -> list[dict[str, Any]]:
    return buscar_kits_motor(conn, termo="", limite=limite)


def importar_kits_motor_lote(
    conn: sqlite3.Connection,
    kits: list[dict[str, Any]],
) -> dict[str, Any]:
    criados = 0
    atualizados = 0
    erros: list[str] = []
    for idx, kit in enumerate(kits, start=1):
        try:
            modelo = str(kit.get("modelo_motor") or "").strip()
            if not modelo:
                raise ValueError("modelo_motor obrigatório")
            existente = conn.execute(
                "SELECT id FROM kits_motor WHERE modelo_motor = ? COLLATE NOCASE",
                (modelo,),
            ).fetchone()
            salvar_kit_motor(
                conn,
                modelo_motor=modelo,
                lista_pecas=kit.get("lista_pecas") or kit.get("lista_pecas_json") or [],
                preco_base=kit.get("preco_base"),
                kit_id=int(existente["id"]) if existente else None,
            )
            if existente:
                atualizados += 1
            else:
                criados += 1
        except (ValueError, sqlite3.Error) as exc:
            erros.append(f"Item {idx}: {exc}")
    return {"criados": criados, "atualizados": atualizados, "erros": erros}


def listar_pre_orcamentos(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    limite: int = 200,
) -> list[dict[str, Any]]:
    limite = max(1, min(int(limite or 200), 500))
    sql = "SELECT * FROM pre_orcamentos"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(str(status).strip())
    sql += """
        ORDER BY
            CASE status
                WHEN 'salvo' THEN 0
                WHEN 'rascunho' THEN 1
                WHEN 'convertido_os' THEN 2
                ELSE 3
            END,
            data DESC, id DESC
        LIMIT ?
    """
    params.append(limite)
    rows = conn.execute(sql, params).fetchall()
    return [_pre_orcamento_para_json(r) for r in rows]


def obter_pre_orcamento(conn: sqlite3.Connection, pre_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM pre_orcamentos WHERE id = ?", (int(pre_id),)).fetchone()
    if row is None:
        return None
    return _pre_orcamento_para_json(row)


def criar_pre_orcamento(
    conn: sqlite3.Connection,
    *,
    cliente_nome: str,
    motor: str,
    data: str | None = None,
    itens: Any = None,
    cliente_id: int | None = None,
    motor_id: int | None = None,
    kit_motor_id: int | None = None,
    observacoes: str = "",
    status: str = STATUS_SALVO,
) -> dict[str, Any]:
    nome = str(cliente_nome or "").strip()
    motor_txt = str(motor or "").strip()
    if not nome:
        raise ValueError("Informe o cliente.")
    if not motor_txt:
        raise ValueError("Informe o motor.")
    itens_norm = _normalizar_itens(itens)
    if not itens_norm:
        raise ValueError("Adicione ao menos um item ao pré-orçamento.")
    data_norm = str(data or date.today().isoformat())[:10]
    st = str(status or STATUS_SALVO).strip()
    if st not in (STATUS_RASCUNHO, STATUS_SALVO):
        st = STATUS_SALVO
    agora = _agora_local()
    numero = proximo_numero_pre_orcamento(conn)
    total = _total_itens(itens_norm)
    cur = conn.execute(
        """
        INSERT INTO pre_orcamentos (
            numero, cliente_nome, cliente_id, motor, motor_id, data, itens, status,
            kit_motor_id, preco_total, observacoes, criado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            numero,
            nome,
            int(cliente_id) if cliente_id else None,
            motor_txt,
            int(motor_id) if motor_id else None,
            data_norm,
            json.dumps(itens_norm, ensure_ascii=False),
            st,
            int(kit_motor_id) if kit_motor_id else None,
            total,
            str(observacoes or "").strip(),
            agora,
        ),
    )
    item = obter_pre_orcamento(conn, int(cur.lastrowid))
    if item is None:
        raise RuntimeError("Falha ao criar pré-orçamento.")
    return item


def atualizar_pre_orcamento(
    conn: sqlite3.Connection,
    pre_id: int,
    *,
    cliente_nome: str | None = None,
    motor: str | None = None,
    data: str | None = None,
    itens: Any = None,
    cliente_id: int | None = None,
    motor_id: int | None = None,
    observacoes: str | None = None,
) -> dict[str, Any]:
    atual = conn.execute("SELECT * FROM pre_orcamentos WHERE id = ?", (int(pre_id),)).fetchone()
    if atual is None:
        raise ValueError("Pré-orçamento não encontrado.")
    if str(atual["status"] or "") == STATUS_CONVERTIDO_OS:
        raise ValueError("Pré-orçamento já convertido em O.S. Não pode ser editado.")

    nome = str(cliente_nome).strip() if cliente_nome is not None else str(atual["cliente_nome"] or "")
    motor_txt = str(motor).strip() if motor is not None else str(atual["motor"] or "")
    if not nome:
        raise ValueError("Informe o cliente.")
    if not motor_txt:
        raise ValueError("Informe o motor.")

    itens_norm = _normalizar_itens(itens) if itens is not None else _normalizar_itens(atual["itens"])
    if not itens_norm:
        raise ValueError("Adicione ao menos um item.")
    data_norm = str(data or atual["data"] or "")[:10]
    cli_id = int(cliente_id) if cliente_id is not None else (int(atual["cliente_id"]) if atual["cliente_id"] else None)
    mot_id = int(motor_id) if motor_id is not None else (int(atual["motor_id"]) if atual["motor_id"] else None)
    obs = str(observacoes).strip() if observacoes is not None else str(atual["observacoes"] or "")
    total = _total_itens(itens_norm)

    conn.execute(
        """
        UPDATE pre_orcamentos
        SET cliente_nome = ?, cliente_id = ?, motor = ?, motor_id = ?, data = ?,
            itens = ?, preco_total = ?, observacoes = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (
            nome,
            cli_id,
            motor_txt,
            mot_id,
            data_norm,
            json.dumps(itens_norm, ensure_ascii=False),
            total,
            obs,
            _agora_local(),
            int(pre_id),
        ),
    )
    item = obter_pre_orcamento(conn, pre_id)
    if item is None:
        raise RuntimeError("Falha ao atualizar pré-orçamento.")
    return item


def excluir_pre_orcamento(conn: sqlite3.Connection, pre_id: int) -> None:
    atual = conn.execute("SELECT id FROM pre_orcamentos WHERE id = ?", (int(pre_id),)).fetchone()
    if atual is None:
        raise ValueError("Pré-orçamento não encontrado.")
    conn.execute("DELETE FROM pre_orcamentos WHERE id = ?", (int(pre_id),))


def marcar_pre_orcamento_convertido(
    conn: sqlite3.Connection,
    pre_id: int,
    *,
    numero_os: int,
) -> dict[str, Any]:
    atual = conn.execute("SELECT * FROM pre_orcamentos WHERE id = ?", (int(pre_id),)).fetchone()
    if atual is None:
        raise ValueError("Pré-orçamento não encontrado.")
    if str(atual["status"] or "") == STATUS_CONVERTIDO_OS:
        raise ValueError("Este pré-orçamento já foi convertido em O.S.")
    conn.execute(
        """
        UPDATE pre_orcamentos
        SET status = ?, numero_os_gerado = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (STATUS_CONVERTIDO_OS, int(numero_os), _agora_local(), int(pre_id)),
    )
    item = obter_pre_orcamento(conn, pre_id)
    if item is None:
        raise RuntimeError("Falha ao atualizar status.")
    return item


def _fmt_brl(valor: float) -> str:
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def itens_para_texto_os(itens: list[dict[str, Any]], observacoes: str = "") -> str:
    linhas: list[str] = []
    for item in itens:
        desc = str(item.get("descricao") or "").strip()
        qtd = item.get("quantidade") or 1
        valor = float(item.get("valor_unitario") or 0)
        tipo = "Serv." if str(item.get("tipo") or "") == "servico" else "Peça"
        linhas.append(f"- [{tipo}] {desc} — Qtd {qtd} × {_fmt_brl(valor)}")
    obs = str(observacoes or "").strip()
    if obs:
        linhas.append("")
        linhas.append(f"Obs.: {obs}")
    return "\n".join(linhas)


def _tipo_pessoa_de_cpf(cpf_cnpj: str) -> str:
    digitos = "".join(c for c in (cpf_cnpj or "") if c.isdigit())
    if len(digitos) > 11:
        return "pj"
    if digitos:
        return "pf"
    return ""


def itens_para_requisicao_os(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Converte itens do pré-orçamento para rascunho de requisição (peças + M.O.)."""
    saida: list[dict[str, Any]] = []
    for item in itens:
        desc = str(item.get("descricao") or "").strip()
        if not desc:
            continue
        qtd = item.get("quantidade") or 1
        valor = float(item.get("valor_unitario") or 0)
        tipo_raw = str(item.get("tipo") or "peca").strip().lower()
        tipo_item = "mo" if tipo_raw == "servico" else "peca"
        entrada: dict[str, Any] = {
            "descricao": desc,
            "quantidade": str(qtd),
            "tipo_item": tipo_item,
        }
        cat_id = item.get("catalogo_id")
        if cat_id not in (None, "", 0):
            try:
                entrada["catalogo_id"] = int(cat_id)
            except (TypeError, ValueError):
                pass
        if valor > 0:
            entrada["preco"] = _fmt_brl(valor)
        saida.append(entrada)
    return saida


def _cliente_payload_os(
    cliente_row: sqlite3.Row | dict[str, Any],
    *,
    nome_fallback: str = "",
    cliente_id_fallback: int | None = None,
) -> dict[str, Any]:
    keys = cliente_row.keys() if hasattr(cliente_row, "keys") else cliente_row

    def _get(k: str, default: str = "") -> str:
        if isinstance(cliente_row, dict):
            return str(cliente_row.get(k) or default)
        return str(cliente_row[k] if k in keys else default)

    cpf = _get("cpf_cnpj")
    cid = cliente_id_fallback
    if cid in (None, ""):
        try:
            cid = int(_get("id") or 0) or None
        except (TypeError, ValueError):
            cid = None
    return {
        "cliente_id": cid,
        "cliente_nome": _get("nome", nome_fallback),
        "cliente_cpf_cnpj": cpf,
        "cliente_rg": _get("rg"),
        "cliente_endereco": _get("endereco"),
        "cliente_numero": _get("numero"),
        "cliente_bairro": _get("bairro"),
        "cliente_cidade": _get("cidade"),
        "cliente_estado": _get("estado"),
        "cliente_cep": _get("cep"),
        "cliente_telefone": _get("telefone"),
        "cliente_celular": _get("celular"),
        "tipo_pessoa": _tipo_pessoa_de_cpf(cpf),
    }


def montar_payload_os_de_pre_orcamento(
    pre: dict[str, Any],
    *,
    cliente_row: sqlite3.Row | dict[str, Any] | None = None,
    motor_row: sqlite3.Row | dict[str, Any] | None = None,
    nome_atendente: str = "",
) -> dict[str, Any]:
    itens = pre.get("itens") or []
    itens_req = itens_para_requisicao_os(itens)
    payload: dict[str, Any] = {
        "data_entrada": pre.get("data") or date.today().isoformat(),
        "nome_atendente": nome_atendente,
        "cliente_id": pre.get("cliente_id"),
        "cliente_nome": pre.get("cliente_nome") or "",
        "alegacoes_cliente": f"Pré-orçamento {pre.get('numero') or ''} — revisão programada.",
        "requisicoes_pecas": itens_para_texto_os(itens, str(pre.get("observacoes") or "")),
        "pre_orcamento_id": pre.get("id"),
        "pre_orcamento_numero": pre.get("numero"),
        "orcamento_numero": pre.get("numero"),
        "pre_orcamento_itens_requisicao": itens_req,
        "os_tipo": ["orcamento"],
    }
    if cliente_row is not None:
        cid_fb: int | None = None
        try:
            cid_fb = int(pre.get("cliente_id") or 0) or None
        except (TypeError, ValueError):
            cid_fb = None
        payload.update(
            _cliente_payload_os(
                cliente_row,
                nome_fallback=str(pre.get("cliente_nome") or ""),
                cliente_id_fallback=cid_fb,
            )
        )
    if motor_row is not None:
        keys = motor_row.keys() if hasattr(motor_row, "keys") else motor_row

        def _mget(k: str, default: str = "") -> str:
            if isinstance(motor_row, dict):
                return str(motor_row.get(k) or default)
            return str(motor_row[k] if k in keys else default)

        payload.update(
            {
                "motor_id": pre.get("motor_id") or _mget("id"),
                "fabricante": _mget("fabricante"),
                "modelo": _mget("marca_modelo", pre.get("motor") or ""),
                "embarcacao_nome": _mget("embarcacao"),
                "num_chassi": _mget("chassi"),
                "horas_uso": _mget("horas"),
            }
        )
    else:
        payload["modelo"] = pre.get("motor") or ""
    return payload
