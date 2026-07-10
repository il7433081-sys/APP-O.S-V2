"""Fotos enviadas pelo mecânico por O.S. — fila do responsável."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from typing import Any

_MAX_FOTOS_POR_ENVIO = 20
_MAX_BYTES_FOTO = 10_485_760


def init_os_fotos_tabelas(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS os_fotos_envio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_os INTEGER NOT NULL,
            mecanico_id INTEGER NOT NULL,
            enviado_em TEXT NOT NULL,
            pendente_responsavel INTEGER NOT NULL DEFAULT 1,
            marcado_enviado_em TEXT,
            marcado_por_id INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_os_fotos_envio_pend
        ON os_fotos_envio (pendente_responsavel, numero_os)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS os_fotos_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            envio_id INTEGER NOT NULL,
            foto TEXT NOT NULL,
            ordem INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (envio_id) REFERENCES os_fotos_envio (id) ON DELETE CASCADE
        )
        """
    )


def _agora_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def validar_foto_dataurl(foto: str, *, max_bytes: int | None = None) -> str:
    bruto = str(foto or "").strip()
    if not bruto.startswith("data:image/"):
        raise ValueError("Formato de imagem inválido.")
    limite = int(max_bytes or _MAX_BYTES_FOTO)
    if len(bruto) > limite:
        kb = max(1, limite // 1024)
        raise ValueError(f"Imagem muito grande (máx. ~{kb} KB por foto).")
    return bruto


def _resumo_os_de_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        dados = json.loads(row["dados_json"] or "{}")
    except json.JSONDecodeError:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    return {
        "numero_os": int(row["numero_os"]),
        "cliente_nome": row["cliente_nome"] or "",
        "mecanico_nome": row["mecanico_nome"] or "",
        "data_entrada": row["data_entrada"] or "",
        "embarcacao_nome": str(dados.get("embarcacao_nome") or dados.get("nome_embarcacao") or "").strip(),
        "motor": str(dados.get("motor") or dados.get("motor_modelo") or "").strip(),
    }


def salvar_fotos_os(
    conn: sqlite3.Connection,
    *,
    numero_os: int,
    mecanico_id: int,
    fotos: list[Any],
    max_fotos_por_envio: int | None = None,
    max_bytes_por_foto: int | None = None,
) -> dict[str, Any]:
    init_os_fotos_tabelas(conn)
    limite_fotos = int(max_fotos_por_envio or _MAX_FOTOS_POR_ENVIO)
    limite_bytes = int(max_bytes_por_foto or _MAX_BYTES_FOTO)
    lista = [
        validar_foto_dataurl(f, max_bytes=limite_bytes)
        for f in (fotos or [])
        if str(f or "").strip()
    ]
    if not lista:
        raise ValueError("Envie ao menos uma foto.")
    if len(lista) > limite_fotos:
        raise ValueError(f"Máximo de {limite_fotos} fotos por envio.")
    row = conn.execute(
        """
        SELECT numero_os, cliente_nome, mecanico_id, mecanico_nome, data_entrada, dados_json
        FROM ordens_servico WHERE numero_os = ?
        """,
        (int(numero_os),),
    ).fetchone()
    if row is None:
        raise ValueError("O.S. não encontrada.")
    if int(row["mecanico_id"] or 0) != int(mecanico_id):
        raise ValueError("Esta O.S. não está atribuída a você.")
    agora = _agora_local()
    cur = conn.execute(
        """
        INSERT INTO os_fotos_envio (numero_os, mecanico_id, enviado_em, pendente_responsavel)
        VALUES (?, ?, ?, 1)
        """,
        (int(numero_os), int(mecanico_id), agora),
    )
    envio_id = int(cur.lastrowid)
    for idx, foto in enumerate(lista):
        conn.execute(
            "INSERT INTO os_fotos_item (envio_id, foto, ordem) VALUES (?, ?, ?)",
            (envio_id, foto, idx),
        )
    return {
        "envio_id": envio_id,
        "numero_os": int(numero_os),
        "total_fotos": len(lista),
        "enviado_em": agora,
    }


def contar_os_fotos_pendentes(conn: sqlite3.Connection) -> int:
    init_os_fotos_tabelas(conn)
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT numero_os) AS n
        FROM os_fotos_envio
        WHERE pendente_responsavel = 1
        """
    ).fetchone()
    return int(row["n"] or 0) if row else 0


def listar_os_fotos_pendentes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    init_os_fotos_tabelas(conn)
    rows = conn.execute(
        """
        SELECT e.numero_os,
               MAX(e.enviado_em) AS ultimo_envio,
               COUNT(DISTINCT e.id) AS total_envios,
               SUM(
                   (SELECT COUNT(*) FROM os_fotos_item i WHERE i.envio_id = e.id)
               ) AS total_fotos
        FROM os_fotos_envio e
        WHERE e.pendente_responsavel = 1
        GROUP BY e.numero_os
        ORDER BY ultimo_envio DESC
        """
    ).fetchall()
    saida: list[dict[str, Any]] = []
    for r in rows:
        os_row = conn.execute(
            """
            SELECT numero_os, cliente_nome, mecanico_nome, data_entrada, dados_json
            FROM ordens_servico WHERE numero_os = ?
            """,
            (int(r["numero_os"]),),
        ).fetchone()
        if os_row is None:
            continue
        base = _resumo_os_de_row(os_row)
        base.update({
            "ultimo_envio": r["ultimo_envio"] or "",
            "total_envios": int(r["total_envios"] or 0),
            "total_fotos": int(r["total_fotos"] or 0),
        })
        saida.append(base)
    return saida


def obter_fotos_pendentes_os(
    conn: sqlite3.Connection,
    numero_os: int,
) -> dict[str, Any] | None:
    init_os_fotos_tabelas(conn)
    os_row = conn.execute(
        """
        SELECT numero_os, cliente_nome, mecanico_nome, data_entrada, dados_json
        FROM ordens_servico WHERE numero_os = ?
        """,
        (int(numero_os),),
    ).fetchone()
    if os_row is None:
        return None
    envios = conn.execute(
        """
        SELECT id, mecanico_id, enviado_em
        FROM os_fotos_envio
        WHERE numero_os = ? AND pendente_responsavel = 1
        ORDER BY enviado_em ASC, id ASC
        """,
        (int(numero_os),),
    ).fetchall()
    if not envios:
        return None
    fotos: list[dict[str, Any]] = []
    for env in envios:
        itens = conn.execute(
            """
            SELECT id, foto, ordem FROM os_fotos_item
            WHERE envio_id = ? ORDER BY ordem ASC, id ASC
            """,
            (int(env["id"]),),
        ).fetchall()
        for it in itens:
            fotos.append({
                "id": int(it["id"]),
                "envio_id": int(env["id"]),
                "foto": it["foto"],
                "ordem": int(it["ordem"] or 0),
                "enviado_em": env["enviado_em"] or "",
            })
    base = _resumo_os_de_row(os_row)
    base["fotos"] = fotos
    base["total_fotos"] = len(fotos)
    return base


def excluir_foto_os_item(
    conn: sqlite3.Connection,
    *,
    numero_os: int,
    foto_id: int,
) -> dict[str, Any]:
    init_os_fotos_tabelas(conn)
    row = conn.execute(
        """
        SELECT i.id, i.envio_id, e.numero_os, e.pendente_responsavel
        FROM os_fotos_item i
        JOIN os_fotos_envio e ON e.id = i.envio_id
        WHERE i.id = ?
        """,
        (int(foto_id),),
    ).fetchone()
    if row is None:
        raise ValueError("Foto não encontrada.")
    if int(row["numero_os"]) != int(numero_os):
        raise ValueError("Foto não pertence a esta O.S.")
    if not int(row["pendente_responsavel"]):
        raise ValueError("Esta foto já foi marcada como enviada ao cliente.")
    envio_id = int(row["envio_id"])
    conn.execute("DELETE FROM os_fotos_item WHERE id = ?", (int(foto_id),))
    restantes = conn.execute(
        "SELECT COUNT(*) AS n FROM os_fotos_item WHERE envio_id = ?",
        (envio_id,),
    ).fetchone()
    if int(restantes["n"] or 0) == 0:
        conn.execute("DELETE FROM os_fotos_envio WHERE id = ?", (envio_id,))
    total_os = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM os_fotos_item i
        JOIN os_fotos_envio e ON e.id = i.envio_id
        WHERE e.numero_os = ? AND e.pendente_responsavel = 1
        """,
        (int(numero_os),),
    ).fetchone()
    return {
        "foto_id": int(foto_id),
        "numero_os": int(numero_os),
        "total_fotos_os": int(total_os["n"] or 0) if total_os else 0,
        "total_os_pendentes": contar_os_fotos_pendentes(conn),
    }


def marcar_fotos_os_enviadas(
    conn: sqlite3.Connection,
    *,
    numero_os: int,
    usuario_id: int,
) -> int:
    init_os_fotos_tabelas(conn)
    agora = _agora_local()
    cur = conn.execute(
        """
        UPDATE os_fotos_envio
        SET pendente_responsavel = 0,
            marcado_enviado_em = ?,
            marcado_por_id = ?
        WHERE numero_os = ? AND pendente_responsavel = 1
        """,
        (agora, int(usuario_id), int(numero_os)),
    )
    return int(cur.rowcount or 0)


def nome_pasta_cliente(cliente: str, numero_os: int) -> str:
    base = re.sub(r'[<>:"/\\|?*]+', "_", str(cliente or "cliente").strip())
    base = re.sub(r"\s+", "_", base)[:60] or "cliente"
    return f"OS_{int(numero_os):04d}_{base}"
