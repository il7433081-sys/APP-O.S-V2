"""Controle de estoque de peças (catálogo + movimentações auditáveis)."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from catalogo_pecas import normalizar_texto_busca
from config_app_os import diretorio_instalacao, resolver_caminho_banco

DATABASE_PRINCIPAL_PATH = resolver_caminho_banco(diretorio_instalacao())


@contextmanager
def _conn_catalogo(conn_app: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    """Usa o mesmo SQLite do app em produção; em teste, abre o banco principal."""
    row = conn_app.execute("PRAGMA database_list").fetchone()
    caminho_app = Path(str(row[2] or "")).resolve() if row else None
    if caminho_app and caminho_app == DATABASE_PRINCIPAL_PATH.resolve():
        yield conn_app
        return
    conn_cat = sqlite3.connect(DATABASE_PRINCIPAL_PATH, timeout=30)
    conn_cat.row_factory = sqlite3.Row
    try:
        yield conn_cat
        conn_cat.commit()
    except Exception:
        conn_cat.rollback()
        raise
    finally:
        conn_cat.close()


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_quantidade(texto: str | float | int | None) -> float:
    if texto is None:
        return 0.0
    if isinstance(texto, (int, float)):
        return max(0.0, float(texto))
    t = str(texto).strip().replace(",", ".")
    if not t:
        return 0.0
    try:
        return max(0.0, float(t))
    except ValueError:
        return 0.0


def init_estoque_schema(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(catalogo)").fetchall()}
    if "estoque_atual" not in cols:
        conn.execute(
            "ALTER TABLE catalogo ADD COLUMN estoque_atual REAL NOT NULL DEFAULT 0"
        )
    if "estoque_minimo" not in cols:
        conn.execute(
            "ALTER TABLE catalogo ADD COLUMN estoque_minimo REAL NOT NULL DEFAULT 0"
        )
    if "fornecedor" not in cols:
        conn.execute("ALTER TABLE catalogo ADD COLUMN fornecedor TEXT")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS estoque_movimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            catalogo_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            quantidade REAL NOT NULL,
            saldo_apos REAL NOT NULL,
            requisicao_id INTEGER,
            requisicao_item_id TEXT,
            observacao TEXT,
            usuario_id INTEGER,
            usuario_nome TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_est_mov_cat ON estoque_movimentos(catalogo_id);
        CREATE INDEX IF NOT EXISTS idx_est_mov_req ON estoque_movimentos(requisicao_id);

        CREATE TABLE IF NOT EXISTS estoque_ordens_marcadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            fornecedor_ref TEXT,
            cor_orelha TEXT NOT NULL DEFAULT '#64748b',
            ordem INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_est_ord_marc_ordem ON estoque_ordens_marcadores(ordem);

        CREATE TABLE IF NOT EXISTS estoque_ordens_pedido_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            marcador_id INTEGER NOT NULL,
            catalogo_id INTEGER NOT NULL,
            quantidade REAL NOT NULL DEFAULT 1,
            origem TEXT NOT NULL DEFAULT 'loja',
            observacao TEXT,
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            UNIQUE (marcador_id, catalogo_id, origem)
        );
        CREATE INDEX IF NOT EXISTS idx_est_ord_item_marc ON estoque_ordens_pedido_itens(marcador_id);

        CREATE TABLE IF NOT EXISTS estoque_atualizar_pendente (
            catalogo_id INTEGER PRIMARY KEY,
            descricao TEXT NOT NULL DEFAULT '',
            codigo_exibicao TEXT NOT NULL DEFAULT '',
            saldo_registrado REAL NOT NULL DEFAULT 0,
            ultima_req_id INTEGER,
            ultima_os INTEGER,
            observacao TEXT,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        );
        """
    )


def _filtro_pecas_catalogo_sql(alias: str = "") -> str:
    p = f"{alias}." if alias else ""
    return f"({p}categoria = 'PEÇA' OR {p}tipo = 'Peça')"


def integrar_catalogo_ao_estoque(conn: sqlite3.Connection) -> dict[str, int]:
    """Garante schema de estoque e inclui todas as peças do cadastro da oficina."""
    init_estoque_schema(conn)
    conn.execute(
        """
        UPDATE catalogo SET categoria = 'PEÇA'
        WHERE tipo = 'Peça' AND COALESCE(categoria, '') != 'PEÇA'
        """
    )
    conn.execute(
        f"""
        UPDATE catalogo SET estoque_atual = COALESCE(estoque_atual, 0),
                            estoque_minimo = COALESCE(estoque_minimo, 0)
        WHERE {_filtro_pecas_catalogo_sql()}
        """
    )
    total = int(
        conn.execute(
            f"SELECT COUNT(*) FROM catalogo WHERE {_filtro_pecas_catalogo_sql()}"
        ).fetchone()[0]
    )
    com_saldo = int(
        conn.execute(
            f"""
            SELECT COUNT(*) FROM catalogo
            WHERE {_filtro_pecas_catalogo_sql()} AND estoque_atual > 0
            """
        ).fetchone()[0]
    )
    return {
        "total_pecas": total,
        "com_saldo_positivo": com_saldo,
        "saldo_zero": total - com_saldo,
    }


def _formatar_qtd(valor: float) -> str:
    if abs(valor - round(valor)) < 0.0001:
        return str(int(round(valor)))
    return f"{valor:.2f}".rstrip("0").rstrip(".")


def obter_saldo_peca(conn: sqlite3.Connection, catalogo_id: int) -> float:
    init_estoque_schema(conn)
    row = conn.execute(
        """
        SELECT estoque_atual FROM catalogo
        WHERE id = ? AND categoria = 'PEÇA'
        """,
        (int(catalogo_id),),
    ).fetchone()
    if row is None:
        raise ValueError("Peça não encontrada no catálogo.")
    return float(row["estoque_atual"] or 0)


def _registrar_movimento(
    conn: sqlite3.Connection,
    *,
    catalogo_id: int,
    tipo: str,
    quantidade: float,
    saldo_apos: float,
    requisicao_id: int | None = None,
    requisicao_item_id: str | None = None,
    observacao: str = "",
    usuario_id: int | None = None,
    usuario_nome: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO estoque_movimentos (
            catalogo_id, tipo, quantidade, saldo_apos,
            requisicao_id, requisicao_item_id, observacao,
            usuario_id, usuario_nome, criado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(catalogo_id),
            tipo,
            float(quantidade),
            float(saldo_apos),
            requisicao_id,
            requisicao_item_id,
            observacao,
            usuario_id,
            usuario_nome,
            _agora(),
        ),
    )


def movimentar_estoque(
    conn: sqlite3.Connection,
    *,
    catalogo_id: int,
    tipo: str,
    quantidade: float,
    permitir_negativo: bool = False,
    requisicao_id: int | None = None,
    requisicao_item_id: str | None = None,
    observacao: str = "",
    usuario_id: int | None = None,
    usuario_nome: str = "",
) -> float:
    """Registra movimento e atualiza saldo. Retorna saldo após movimento."""
    init_estoque_schema(conn)
    qtd = abs(float(quantidade))
    if qtd <= 0:
        raise ValueError("Informe uma quantidade maior que zero.")
    tipos_saida = {"saida_requisicao", "saida_manual", "saida_interna"}
    tipos_entrada = {"entrada_manual", "entrada_devolucao", "ajuste_entrada"}
    if tipo not in tipos_saida | tipos_entrada | {"ajuste"}:
        raise ValueError("Tipo de movimento inválido.")
    saldo = obter_saldo_peca(conn, catalogo_id)
    if tipo in tipos_saida:
        novo = saldo - qtd
        if novo < 0 and not permitir_negativo:
            raise ValueError(
                f"Estoque insuficiente (disponível: {_formatar_qtd(saldo)})."
            )
    elif tipo == "ajuste":
        novo = qtd
        qtd = abs(novo - saldo)
    else:
        novo = saldo + qtd
    conn.execute(
        "UPDATE catalogo SET estoque_atual = ? WHERE id = ? AND categoria = 'PEÇA'",
        (novo, int(catalogo_id)),
    )
    _registrar_movimento(
        conn,
        catalogo_id=catalogo_id,
        tipo=tipo,
        quantidade=qtd,
        saldo_apos=novo,
        requisicao_id=requisicao_id,
        requisicao_item_id=requisicao_item_id,
        observacao=observacao,
        usuario_id=usuario_id,
        usuario_nome=usuario_nome,
    )
    return novo


def listar_estoque(
    conn: sqlite3.Connection,
    *,
    termo: str = "",
    limite: int = 500,
    apenas_baixo: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    init_estoque_schema(conn)
    limite = max(1, min(int(limite), 3000))
    params: list[Any] = []
    filtro_peca = _filtro_pecas_catalogo_sql()
    where = f"WHERE {filtro_peca}"
    if apenas_baixo:
        where += " AND estoque_atual <= estoque_minimo AND estoque_minimo > 0"
    termo = (termo or "").strip()
    if termo:
        tn = f"%{normalizar_texto_busca(termo)}%"
        like = f"%{termo}%"
        conn.create_function(
            "NORM_EST", 1, normalizar_texto_busca, deterministic=True
        )
        where += """
            AND (
                NORM_EST(descricao) LIKE ?
                OR NORM_EST(IFNULL(codigo_barras, '')) LIKE ?
                OR descricao LIKE ?
                OR CAST(id AS TEXT) LIKE ?
            )
        """
        params.extend([tn, tn, like, f"{termo}%"])
    total = int(conn.execute(
        f"SELECT COUNT(*) FROM catalogo {where}", params[: len(params)]
    ).fetchone()[0])
    sql = f"""
        SELECT id, descricao, COALESCE(codigo_barras, '') AS codigo_barras,
               valor_unitario, estoque_atual, estoque_minimo,
               COALESCE(fornecedor, '') AS fornecedor
        FROM catalogo
        {where}
        ORDER BY descricao COLLATE NOCASE
        LIMIT ?
    """
    params.append(limite)
    rows = conn.execute(sql, params).fetchall()
    saida: list[dict[str, Any]] = []
    for row in rows:
        atual = float(row["estoque_atual"] or 0)
        minimo = float(row["estoque_minimo"] or 0)
        saida.append({
            "id": int(row["id"]),
            "descricao": row["descricao"] or "",
            "codigo_barras": (row["codigo_barras"] or "").strip(),
            "codigo_exibicao": (row["codigo_barras"] or "").strip() or str(row["id"]),
            "estoque_atual": atual,
            "estoque_atual_fmt": _formatar_qtd(atual),
            "estoque_minimo": minimo,
            "estoque_minimo_fmt": _formatar_qtd(minimo),
            "estoque_baixo": minimo > 0 and atual <= minimo,
            "fornecedor": (row["fornecedor"] or "").strip(),
        })
    return saida, total


def listar_movimentos(
    conn: sqlite3.Connection,
    *,
    catalogo_id: int | None = None,
    limite: int = 50,
) -> list[dict[str, Any]]:
    init_estoque_schema(conn)
    limite = max(1, min(int(limite), 200))
    sql = """
        SELECT m.*, c.descricao AS peca_descricao
        FROM estoque_movimentos m
        JOIN catalogo c ON c.id = m.catalogo_id
        WHERE 1=1
    """
    params: list[Any] = []
    if catalogo_id is not None:
        sql += " AND m.catalogo_id = ?"
        params.append(int(catalogo_id))
    sql += " ORDER BY m.id DESC LIMIT ?"
    params.append(limite)
    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": int(r["id"]),
            "catalogo_id": int(r["catalogo_id"]),
            "peca_descricao": r["peca_descricao"] or "",
            "tipo": r["tipo"],
            "quantidade": float(r["quantidade"] or 0),
            "saldo_apos": float(r["saldo_apos"] or 0),
            "requisicao_id": r["requisicao_id"],
            "observacao": r["observacao"] or "",
            "usuario_nome": r["usuario_nome"] or "",
            "criado_em": r["criado_em"] or "",
        }
        for r in rows
    ]


def definir_estoque_minimo(
    conn: sqlite3.Connection,
    catalogo_id: int,
    minimo: float,
) -> None:
    init_estoque_schema(conn)
    cur = conn.execute(
        """
        UPDATE catalogo SET estoque_minimo = ?
        WHERE id = ? AND (categoria = 'PEÇA' OR tipo = 'Peça')
        """,
        (max(0.0, float(minimo)), int(catalogo_id)),
    )
    if cur.rowcount == 0:
        raise ValueError("Peça não encontrada.")


def definir_fornecedor_peca(
    conn: sqlite3.Connection,
    catalogo_id: int,
    fornecedor: str,
) -> None:
    init_estoque_schema(conn)
    nome = (fornecedor or "").strip()
    cur = conn.execute(
        """
        UPDATE catalogo SET fornecedor = ?
        WHERE id = ? AND (categoria = 'PEÇA' OR tipo = 'Peça')
        """,
        (nome or None, int(catalogo_id)),
    )
    if cur.rowcount == 0:
        raise ValueError("Peça não encontrada.")


def obter_peca_estoque(
    conn: sqlite3.Connection,
    catalogo_id: int,
) -> dict[str, Any] | None:
    init_estoque_schema(conn)
    row = conn.execute(
        f"""
        SELECT id, descricao, COALESCE(codigo_barras, '') AS codigo_barras,
               valor_unitario, estoque_atual, estoque_minimo,
               COALESCE(fornecedor, '') AS fornecedor
        FROM catalogo
        WHERE id = ? AND {_filtro_pecas_catalogo_sql()}
        """,
        (int(catalogo_id),),
    ).fetchone()
    if row is None:
        return None
    atual = float(row["estoque_atual"] or 0)
    minimo = float(row["estoque_minimo"] or 0)
    vu = float(row["valor_unitario"] or 0)
    return {
        "id": int(row["id"]),
        "descricao": row["descricao"] or "",
        "codigo_barras": (row["codigo_barras"] or "").strip(),
        "codigo_exibicao": (row["codigo_barras"] or "").strip() or str(row["id"]),
        "valor_unitario": vu,
        "valor_unitario_fmt": _formatar_moeda_br(vu),
        "estoque_atual": atual,
        "estoque_atual_fmt": _formatar_qtd(atual),
        "estoque_minimo": minimo,
        "estoque_minimo_fmt": _formatar_qtd(minimo),
        "estoque_baixo": minimo > 0 and atual <= minimo,
        "fornecedor": (row["fornecedor"] or "").strip(),
    }


def _formatar_moeda_br(valor: float) -> str:
    txt = f"{float(valor):,.2f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def _parse_itens_req(raw: str | None) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _tipo_movimento_requisicao(tipo_requisicao: str) -> str:
    return "saida_interna" if tipo_requisicao == "interna" else "saida_requisicao"


class EstoqueInsuficienteError(ValueError):
    """Levantada quando há saldo insuficiente e liberação sem estoque não foi autorizada."""

    def __init__(self, itens: list[dict[str, Any]]):
        self.itens = itens
        partes = [
            f'"{i.get("descricao", "")}" (disp.: {i.get("disponivel_fmt", "0")})'
            for i in itens[:8]
        ]
        msg = "Estoque insuficiente"
        if partes:
            msg += ": " + ", ".join(partes)
        super().__init__(msg)


def registrar_pendencia_atualizar_estoque(
    conn: sqlite3.Connection,
    *,
    catalogo_id: int,
    descricao: str = "",
    codigo_exibicao: str = "",
    saldo_registrado: float = 0,
    req_id: int | None = None,
    numero_os: int | None = None,
    observacao: str = "",
) -> None:
    """Registra lembrete para atualizar estoque (uma entrada por peça)."""
    init_estoque_schema(conn)
    agora = _agora()
    conn.execute(
        """
        INSERT INTO estoque_atualizar_pendente (
            catalogo_id, descricao, codigo_exibicao, saldo_registrado,
            ultima_req_id, ultima_os, observacao, criado_em, atualizado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(catalogo_id) DO UPDATE SET
            descricao = excluded.descricao,
            codigo_exibicao = excluded.codigo_exibicao,
            saldo_registrado = excluded.saldo_registrado,
            ultima_req_id = excluded.ultima_req_id,
            ultima_os = excluded.ultima_os,
            observacao = excluded.observacao,
            atualizado_em = excluded.atualizado_em
        """,
        (
            int(catalogo_id),
            (descricao or "").strip(),
            (codigo_exibicao or str(catalogo_id)).strip(),
            float(saldo_registrado),
            int(req_id) if req_id else None,
            int(numero_os) if numero_os else None,
            (observacao or "").strip(),
            agora,
            agora,
        ),
    )


def remover_pendencia_atualizar_estoque(
    conn: sqlite3.Connection,
    catalogo_id: int,
) -> None:
    init_estoque_schema(conn)
    conn.execute(
        "DELETE FROM estoque_atualizar_pendente WHERE catalogo_id = ?",
        (int(catalogo_id),),
    )


def listar_pendencias_atualizar_estoque(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    init_estoque_schema(conn)
    rows = conn.execute(
        f"""
        SELECT p.catalogo_id, p.descricao, p.codigo_exibicao, p.saldo_registrado,
               p.ultima_req_id, p.ultima_os, p.observacao, p.atualizado_em,
               COALESCE(c.estoque_atual, 0) AS estoque_atual,
               COALESCE(c.estoque_minimo, 0) AS estoque_minimo,
               COALESCE(c.fornecedor, '') AS fornecedor
        FROM estoque_atualizar_pendente p
        LEFT JOIN catalogo c ON c.id = p.catalogo_id
        ORDER BY p.atualizado_em DESC, p.catalogo_id ASC
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        atual = float(row["estoque_atual"] or 0)
        saldo_reg = float(row["saldo_registrado"] or 0)
        out.append(
            {
                "catalogo_id": int(row["catalogo_id"]),
                "id": int(row["catalogo_id"]),
                "descricao": row["descricao"] or "",
                "codigo_exibicao": row["codigo_exibicao"] or str(row["catalogo_id"]),
                "saldo_registrado": saldo_reg,
                "saldo_registrado_fmt": _formatar_qtd(saldo_reg),
                "estoque_atual": atual,
                "estoque_atual_fmt": _formatar_qtd(atual),
                "estoque_minimo": float(row["estoque_minimo"] or 0),
                "fornecedor": (row["fornecedor"] or "").strip(),
                "ultima_req_id": row["ultima_req_id"],
                "ultima_os": row["ultima_os"],
                "observacao": (row["observacao"] or "").strip(),
                "atualizado_em": row["atualizado_em"] or "",
            }
        )
    return out


def liberar_itens_requisicao(
    conn_app: sqlite3.Connection,
    *,
    req_id: int,
    liberacoes: list[dict[str, Any]],
    usuario_id: int,
    usuario_nome: str,
    permitir_sem_estoque: bool = False,
) -> dict[str, Any]:
    """Libera peças selecionadas e baixa estoque."""
    from fluxo_requisicoes import (
        finalizar_interna_apos_liberacao,
        init_fluxo_tabelas,
        obter_requisicao,
    )

    init_fluxo_tabelas(conn_app)
    row = conn_app.execute(
        "SELECT * FROM requisicoes_material WHERE id = ?",
        (int(req_id),),
    ).fetchone()
    if row is None:
        raise ValueError("Requisição não encontrada.")
    tipo_req = str(row["tipo_requisicao"] if "tipo_requisicao" in row.keys() else "os")
    tipo_mov = _tipo_movimento_requisicao(tipo_req)
    numero_os = int(row["numero_os"] or 0) if "numero_os" in row.keys() else 0
    itens = _parse_itens_req(row["itens_json"])
    mapa = {str(i.get("id") or ""): i for i in itens if i.get("id")}
    agora = _agora()
    alterou = False
    fila: list[dict[str, Any]] = []

    for lib in liberacoes:
        if not isinstance(lib, dict):
            continue
        if not lib.get("liberar"):
            continue
        iid = str(lib.get("id") or "").strip()
        if not iid or iid not in mapa:
            continue
        item = mapa[iid]
        if str(item.get("tipo_item") or "peca").lower() == "mo":
            continue
        if item.get("status_item") in ("excluido", "excluir_pendente"):
            continue
        cat_id = item.get("catalogo_id")
        if not cat_id:
            raise ValueError(
                f'Peça "{item.get("descricao", "")}" não está vinculada ao catálogo.'
            )
        qtd_pedida = parse_quantidade(item.get("quantidade"))
        ja_liberado = parse_quantidade(item.get("estoque_liberado_qtd"))
        pendente = max(0.0, qtd_pedida - ja_liberado)
        if pendente <= 0:
            continue
        qtd_liberar = parse_quantidade(lib.get("quantidade"))
        if qtd_liberar <= 0:
            qtd_liberar = pendente
        if qtd_liberar > pendente:
            raise ValueError(
                f'Quantidade a liberar maior que o pendente para "{item.get("descricao", "")}".'
            )
        fila.append(
            {
                "iid": iid,
                "item": item,
                "cat_id": int(cat_id),
                "qtd_liberar": qtd_liberar,
                "ja_liberado": ja_liberado,
            }
        )

    if not fila:
        raise ValueError("Selecione ao menos uma peça para liberar.")

    with _conn_catalogo(conn_app) as conn_cat:
        init_estoque_schema(conn_cat)
        insuficientes: list[dict[str, Any]] = []
        for entrada in fila:
            saldo = obter_saldo_peca(conn_cat, entrada["cat_id"])
            if saldo < entrada["qtd_liberar"]:
                item = entrada["item"]
                insuficientes.append(
                    {
                        "id": entrada["iid"],
                        "catalogo_id": entrada["cat_id"],
                        "descricao": item.get("descricao") or "",
                        "disponivel": saldo,
                        "disponivel_fmt": _formatar_qtd(saldo),
                        "pedido": entrada["qtd_liberar"],
                        "pedido_fmt": _formatar_qtd(entrada["qtd_liberar"]),
                    }
                )
        if insuficientes and not permitir_sem_estoque:
            raise EstoqueInsuficienteError(insuficientes)

        for entrada in fila:
            item = entrada["item"]
            iid = entrada["iid"]
            cat_id = entrada["cat_id"]
            qtd_liberar = entrada["qtd_liberar"]
            ja_liberado = entrada["ja_liberado"]
            saldo_antes = obter_saldo_peca(conn_cat, cat_id)
            sem_estoque = saldo_antes < qtd_liberar
            saldo_apos = movimentar_estoque(
                conn_cat,
                catalogo_id=cat_id,
                tipo=tipo_mov,
                quantidade=qtd_liberar,
                permitir_negativo=sem_estoque and permitir_sem_estoque,
                requisicao_id=int(req_id),
                requisicao_item_id=iid,
                observacao=f"Liberação req #{req_id}",
                usuario_id=usuario_id,
                usuario_nome=usuario_nome,
            )
            if sem_estoque and permitir_sem_estoque:
                codigo = (item.get("codigo_barras") or item.get("codigo") or "").strip()
                registrar_pendencia_atualizar_estoque(
                    conn_cat,
                    catalogo_id=cat_id,
                    descricao=str(item.get("descricao") or ""),
                    codigo_exibicao=codigo or str(cat_id),
                    saldo_registrado=saldo_apos,
                    req_id=int(req_id),
                    numero_os=numero_os or None,
                    observacao=f"Liberação sem estoque (req #{req_id})",
                )
            item["estoque_liberado_qtd"] = ja_liberado + qtd_liberar
            item["estoque_liberado_em"] = agora
            alterou = True

    if not alterou:
        raise ValueError("Selecione ao menos uma peça para liberar.")

    itens_json = json.dumps(itens, ensure_ascii=False)
    cols_req = {r[1] for r in conn_app.execute("PRAGMA table_info(requisicoes_material)").fetchall()}
    if "visto_mecanico_liberacao" in cols_req and "liberacao_em" in cols_req:
        conn_app.execute(
            """
            UPDATE requisicoes_material SET
                itens_json = ?, atualizado_em = ?,
                visto_mecanico_liberacao = 0, liberacao_em = ?
            WHERE id = ?
            """,
            (itens_json, agora, agora, int(req_id)),
        )
    else:
        conn_app.execute(
            "UPDATE requisicoes_material SET itens_json = ?, atualizado_em = ? WHERE id = ?",
            (itens_json, agora, int(req_id)),
        )
    cols = {r[1] for r in conn_app.execute("PRAGMA table_info(requisicoes_material)").fetchall()}
    if "itens_rascunho_json" in cols:
        rasc = row["itens_rascunho_json"]
        if rasc and str(rasc).strip() not in ("", "[]"):
            itens_rasc = _parse_itens_req(rasc)
            mapa_rasc = {str(i.get("id") or ""): i for i in itens_rasc if i.get("id")}
            for iid, item in mapa.items():
                if iid in mapa_rasc:
                    mapa_rasc[iid]["estoque_liberado_qtd"] = item.get("estoque_liberado_qtd", 0)
                    mapa_rasc[iid]["estoque_liberado_em"] = item.get("estoque_liberado_em", "")
            conn_app.execute(
                "UPDATE requisicoes_material SET itens_rascunho_json = ? WHERE id = ?",
                (json.dumps(itens_rasc, ensure_ascii=False), int(req_id)),
            )

    finalizar_interna_apos_liberacao(conn_app, int(req_id))

    req = obter_requisicao(conn_app, int(req_id), visao="responsavel")
    return req or {}


def sincronizar_estoque_apos_alteracao_itens(
    conn_app: sqlite3.Connection,
    *,
    itens_antigos: list[dict[str, Any]],
    itens_novos: list[dict[str, Any]],
    req_id: int,
    tipo_requisicao: str,
    usuario_id: int | None,
    usuario_nome: str,
) -> None:
    """Devolve ao estoque peças liberadas que foram removidas ou reduzidas."""
    mapa_ant = {str(i.get("id") or ""): i for i in itens_antigos if i.get("id")}
    mapa_novo = {str(i.get("id") or ""): i for i in itens_novos if i.get("id")}

    with _conn_catalogo(conn_app) as conn_cat:
        init_estoque_schema(conn_cat)
        for iid, ant in mapa_ant.items():
            if str(ant.get("tipo_item") or "peca").lower() == "mo":
                continue
            liberado = parse_quantidade(ant.get("estoque_liberado_qtd"))
            if liberado <= 0:
                continue
            cat_id = ant.get("catalogo_id")
            if not cat_id:
                continue
            novo = mapa_novo.get(iid)
            if novo is None or novo.get("status_item") in ("excluido", "excluir_pendente"):
                devolver = liberado
                if novo is not None:
                    novo["estoque_liberado_qtd"] = 0
                    novo.pop("estoque_liberado_em", None)
            else:
                qtd_nova = parse_quantidade(novo.get("quantidade"))
                if qtd_nova >= liberado:
                    devolver = 0.0
                else:
                    devolver = liberado - qtd_nova
                    novo["estoque_liberado_qtd"] = qtd_nova
            if devolver > 0:
                movimentar_estoque(
                    conn_cat,
                    catalogo_id=int(cat_id),
                    tipo="entrada_devolucao",
                    quantidade=devolver,
                    requisicao_id=int(req_id),
                    requisicao_item_id=iid,
                    observacao=f"Devolução automática req #{req_id}",
                    usuario_id=usuario_id,
                    usuario_nome=usuario_nome,
                )
                if novo is not None and devolver >= liberado:
                    novo["estoque_liberado_qtd"] = 0
                    novo.pop("estoque_liberado_em", None)


def _normalizar_cor_orelha(cor: str | None) -> str:
    c = str(cor or "").strip()
    if not c:
        return "#64748b"
    if not c.startswith("#"):
        c = "#" + c
    hex_part = c[1:]
    if len(hex_part) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in hex_part):
        hex_part = "".join(ch * 2 for ch in hex_part)
        c = "#" + hex_part
    if len(hex_part) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in hex_part):
        return "#" + hex_part.lower()
    if len(hex_part) == 8 and all(ch in "0123456789abcdefABCDEF" for ch in hex_part):
        return "#" + hex_part[:6].lower()
    return "#64748b"


def _normalizar_origem_pedido(origem: str | None) -> str:
    o = str(origem or "loja").strip().lower()
    if o in ("cliente", "clientes", "os"):
        return "cliente"
    return "loja"


def listar_marcadores_ordens(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    init_estoque_schema(conn)
    rows = conn.execute(
        """
        SELECT id, nome, COALESCE(fornecedor_ref, '') AS fornecedor_ref,
               cor_orelha, ordem, criado_em
        FROM estoque_ordens_marcadores
        ORDER BY ordem ASC, id ASC
        """
    ).fetchall()
    return [
        {
            "id": int(r["id"]),
            "nome": r["nome"] or "",
            "fornecedor_ref": (r["fornecedor_ref"] or "").strip(),
            "cor_orelha": _normalizar_cor_orelha(r["cor_orelha"]),
            "ordem": int(r["ordem"] or 0),
            "criado_em": r["criado_em"] or "",
        }
        for r in rows
    ]


def criar_marcador_ordem(
    conn: sqlite3.Connection,
    *,
    nome: str,
    fornecedor_ref: str = "",
    cor_orelha: str = "#64748b",
) -> dict[str, Any]:
    init_estoque_schema(conn)
    titulo = (nome or "").strip()
    if not titulo:
        raise ValueError("Informe o nome do marcador.")
    row = conn.execute(
        "SELECT COALESCE(MAX(ordem), -1) + 1 AS prox FROM estoque_ordens_marcadores"
    ).fetchone()
    ordem = int(row["prox"] if row else 0)
    cur = conn.execute(
        """
        INSERT INTO estoque_ordens_marcadores (nome, fornecedor_ref, cor_orelha, ordem)
        VALUES (?, ?, ?, ?)
        """,
        (titulo, (fornecedor_ref or "").strip() or None, _normalizar_cor_orelha(cor_orelha), ordem),
    )
    mid = int(cur.lastrowid)
    for m in listar_marcadores_ordens(conn):
        if m["id"] == mid:
            return m
    raise ValueError("Não foi possível criar o marcador.")


def atualizar_marcador_ordem(
    conn: sqlite3.Connection,
    marcador_id: int,
    *,
    nome: str | None = None,
    fornecedor_ref: str | None = None,
    cor_orelha: str | None = None,
) -> dict[str, Any]:
    init_estoque_schema(conn)
    row = conn.execute(
        "SELECT id FROM estoque_ordens_marcadores WHERE id = ?",
        (int(marcador_id),),
    ).fetchone()
    if row is None:
        raise ValueError("Marcador não encontrado.")
    if nome is not None:
        titulo = str(nome).strip()
        if not titulo:
            raise ValueError("Informe o nome do marcador.")
        conn.execute(
            "UPDATE estoque_ordens_marcadores SET nome = ? WHERE id = ?",
            (titulo, int(marcador_id)),
        )
    if fornecedor_ref is not None:
        conn.execute(
            "UPDATE estoque_ordens_marcadores SET fornecedor_ref = ? WHERE id = ?",
            ((fornecedor_ref or "").strip() or None, int(marcador_id)),
        )
    if cor_orelha is not None:
        conn.execute(
            "UPDATE estoque_ordens_marcadores SET cor_orelha = ? WHERE id = ?",
            (_normalizar_cor_orelha(cor_orelha), int(marcador_id)),
        )
    for m in listar_marcadores_ordens(conn):
        if m["id"] == int(marcador_id):
            return m
    raise ValueError("Marcador não encontrado.")


def remover_marcador_ordem(conn: sqlite3.Connection, marcador_id: int) -> None:
    init_estoque_schema(conn)
    mid = int(marcador_id)
    conn.execute(
        "DELETE FROM estoque_ordens_pedido_itens WHERE marcador_id = ?",
        (mid,),
    )
    cur = conn.execute(
        "DELETE FROM estoque_ordens_marcadores WHERE id = ?",
        (mid,),
    )
    if cur.rowcount == 0:
        raise ValueError("Marcador não encontrado.")


def _formatar_item_pedido_marcador(row: sqlite3.Row) -> dict[str, Any]:
    qtd = float(row["quantidade"] or 0)
    return {
        "id": int(row["id"]),
        "marcador_id": int(row["marcador_id"]),
        "catalogo_id": int(row["catalogo_id"]),
        "quantidade": qtd,
        "quantidade_fmt": _formatar_qtd(qtd),
        "origem": _normalizar_origem_pedido(row["origem"]),
        "observacao": (row["observacao"] or "").strip(),
        "criado_em": row["criado_em"] or "",
        "descricao": row["descricao"] or "",
        "codigo_exibicao": (row["codigo_barras"] or "").strip() or str(row["catalogo_id"]),
        "estoque_atual_fmt": _formatar_qtd(float(row["estoque_atual"] or 0)),
        "estoque_minimo_fmt": _formatar_qtd(float(row["estoque_minimo"] or 0)),
    }


def listar_itens_pedido_marcador(
    conn: sqlite3.Connection,
    marcador_id: int,
    *,
    origem: str | None = None,
) -> list[dict[str, Any]]:
    init_estoque_schema(conn)
    mid = int(marcador_id)
    params: list[Any] = [mid]
    filtro_origem = ""
    if origem is not None:
        filtro_origem = " AND i.origem = ?"
        params.append(_normalizar_origem_pedido(origem))
    rows = conn.execute(
        f"""
        SELECT i.id, i.marcador_id, i.catalogo_id, i.quantidade, i.origem,
               i.observacao, i.criado_em,
               c.descricao, COALESCE(c.codigo_barras, '') AS codigo_barras,
               c.estoque_atual, c.estoque_minimo
        FROM estoque_ordens_pedido_itens i
        INNER JOIN catalogo c ON c.id = i.catalogo_id
        WHERE i.marcador_id = ?{filtro_origem}
        ORDER BY i.origem ASC, c.descricao COLLATE NOCASE, i.id ASC
        """,
        params,
    ).fetchall()
    return [_formatar_item_pedido_marcador(r) for r in rows]


def adicionar_item_pedido_marcador(
    conn: sqlite3.Connection,
    marcador_id: int,
    *,
    catalogo_id: int,
    quantidade: float | str = 1,
    origem: str = "loja",
    observacao: str = "",
) -> dict[str, Any]:
    init_estoque_schema(conn)
    mid = int(marcador_id)
    cid = int(catalogo_id)
    orig = _normalizar_origem_pedido(origem)
    qtd = parse_quantidade(quantidade)
    if qtd <= 0:
        raise ValueError("Informe uma quantidade válida.")
    row_m = conn.execute(
        "SELECT id FROM estoque_ordens_marcadores WHERE id = ?",
        (mid,),
    ).fetchone()
    if row_m is None:
        raise ValueError("Marcador não encontrado.")
    row_p = conn.execute(
        f"SELECT id FROM catalogo WHERE id = ? AND {_filtro_pecas_catalogo_sql()}",
        (cid,),
    ).fetchone()
    if row_p is None:
        raise ValueError("Peça não encontrada no catálogo.")
    obs = (observacao or "").strip() or None
    conn.execute(
        """
        INSERT INTO estoque_ordens_pedido_itens (
            marcador_id, catalogo_id, quantidade, origem, observacao
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(marcador_id, catalogo_id, origem) DO UPDATE SET
            quantidade = excluded.quantidade,
            observacao = COALESCE(excluded.observacao, estoque_ordens_pedido_itens.observacao)
        """,
        (mid, cid, qtd, orig, obs),
    )
    itens = listar_itens_pedido_marcador(conn, mid, origem=orig)
    for item in itens:
        if item["catalogo_id"] == cid:
            return item
    raise ValueError("Não foi possível adicionar o item.")


def atualizar_item_pedido_marcador(
    conn: sqlite3.Connection,
    item_id: int,
    *,
    quantidade: float | str | None = None,
    observacao: str | None = None,
) -> dict[str, Any]:
    init_estoque_schema(conn)
    iid = int(item_id)
    row = conn.execute(
        "SELECT id, marcador_id FROM estoque_ordens_pedido_itens WHERE id = ?",
        (iid,),
    ).fetchone()
    if row is None:
        raise ValueError("Item não encontrado.")
    if quantidade is not None:
        qtd = parse_quantidade(quantidade)
        if qtd <= 0:
            raise ValueError("Informe uma quantidade válida.")
        conn.execute(
            "UPDATE estoque_ordens_pedido_itens SET quantidade = ? WHERE id = ?",
            (qtd, iid),
        )
    if observacao is not None:
        conn.execute(
            "UPDATE estoque_ordens_pedido_itens SET observacao = ? WHERE id = ?",
            ((observacao or "").strip() or None, iid),
        )
    itens = listar_itens_pedido_marcador(conn, int(row["marcador_id"]))
    for item in itens:
        if item["id"] == iid:
            return item
    raise ValueError("Item não encontrado.")


def remover_item_pedido_marcador(conn: sqlite3.Connection, item_id: int) -> None:
    init_estoque_schema(conn)
    cur = conn.execute(
        "DELETE FROM estoque_ordens_pedido_itens WHERE id = ?",
        (int(item_id),),
    )
    if cur.rowcount == 0:
        raise ValueError("Item não encontrado.")


def importar_sugestoes_pedido_marcador(
    conn: sqlite3.Connection,
    marcador_id: int,
    *,
    origem: str = "loja",
) -> list[dict[str, Any]]:
    init_estoque_schema(conn)
    mid = int(marcador_id)
    marcadores = {m["id"]: m for m in listar_marcadores_ordens(conn)}
    marcador = marcadores.get(mid)
    if marcador is None:
        raise ValueError("Marcador não encontrado.")
    orig = _normalizar_origem_pedido(origem)
    pecas = listar_pecas_baixo_fornecedor(conn, marcador.get("fornecedor_ref") or "")
    for p in pecas:
        qtd_txt = p.get("sugerir_pedido_fmt") or "1"
        adicionar_item_pedido_marcador(
            conn,
            mid,
            catalogo_id=int(p["id"]),
            quantidade=qtd_txt,
            origem=orig,
        )
    return listar_itens_pedido_marcador(conn, mid, origem=orig)


def listar_pecas_baixo_fornecedor(
    conn: sqlite3.Connection,
    fornecedor_ref: str,
    *,
    limite: int = 200,
) -> list[dict[str, Any]]:
    init_estoque_schema(conn)
    ref = (fornecedor_ref or "").strip()
    if not ref:
        return []
    limite = max(1, min(int(limite), 500))
    conn.create_function("NORM_EST", 1, normalizar_texto_busca, deterministic=True)
    ref_n = normalizar_texto_busca(ref)
    rows = conn.execute(
        f"""
        SELECT id, descricao, COALESCE(codigo_barras, '') AS codigo_barras,
               estoque_atual, estoque_minimo, COALESCE(fornecedor, '') AS fornecedor
        FROM catalogo
        WHERE {_filtro_pecas_catalogo_sql()}
          AND estoque_minimo > 0
          AND estoque_atual <= estoque_minimo
          AND NORM_EST(COALESCE(fornecedor, '')) = ?
        ORDER BY descricao COLLATE NOCASE
        LIMIT ?
        """,
        (ref_n, limite),
    ).fetchall()
    saida: list[dict[str, Any]] = []
    for row in rows:
        atual = float(row["estoque_atual"] or 0)
        minimo = float(row["estoque_minimo"] or 0)
        falta = max(0.0, minimo - atual)
        saida.append({
            "id": int(row["id"]),
            "descricao": row["descricao"] or "",
            "codigo_exibicao": (row["codigo_barras"] or "").strip() or str(row["id"]),
            "estoque_atual_fmt": _formatar_qtd(atual),
            "estoque_minimo_fmt": _formatar_qtd(minimo),
            "sugerir_pedido_fmt": _formatar_qtd(falta if falta > 0 else minimo),
            "fornecedor": (row["fornecedor"] or "").strip(),
        })
    return saida
