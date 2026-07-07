"""Marcadores rápidos e tipos de pausa configuráveis na lista de O.S."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

_CHAVE_MARCADORES = "os_marcadores_lista"
_CHAVE_PAUSAS = "os_pausas_tipos"

_PRINCIPAL_DB_PATH: Path | None = None

_DEFAULT_MARCADORES: list[dict[str, Any]] = [
    {"id": "na_agua", "rotulo": "Na água", "cor": "#0369a1"},
    {"id": "puxada", "rotulo": "Puxada", "cor": "#7c3aed"},
]

_DEFAULT_PAUSAS: list[dict[str, Any]] = [
    {
        "id": "garantia",
        "slug": "garantia",
        "rotulo": "Garantia",
        "cor": "pausa-garantia",
    },
    {
        "id": "retifica",
        "slug": "retifica",
        "rotulo": "Retífica",
        "cor": "pausa-retifica",
    },
    {
        "id": "pecas",
        "slug": "pecas",
        "rotulo": "Peças",
        "cor": "pausa-pecas",
    },
]

_SLUG_RE = re.compile(r"^[a-z0-9_]{2,32}$")


def configurar_banco_principal(caminho: Path | str) -> None:
    """Banco onde fica app_os_config (compartilhado com Sistema Oficina)."""
    global _PRINCIPAL_DB_PATH
    _PRINCIPAL_DB_PATH = Path(caminho).resolve()


def _tem_tabela_config(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'app_os_config'"
        ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False


def _garantir_tabela_config(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_os_config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
        """
    )


def _obter_conn_config(conn: sqlite3.Connection | None) -> tuple[sqlite3.Connection, bool]:
    """Retorna conexão com app_os_config e se deve ser fechada ao terminar."""
    if conn is not None and _tem_tabela_config(conn):
        return conn, False
    if _PRINCIPAL_DB_PATH and _PRINCIPAL_DB_PATH.is_file():
        cfg = sqlite3.connect(_PRINCIPAL_DB_PATH, timeout=30)
        cfg.row_factory = sqlite3.Row
        _garantir_tabela_config(cfg)
        return cfg, True
    if conn is not None:
        return conn, False
    raise RuntimeError(
        "Banco de configuração não disponível. "
        "Chame configurar_banco_principal() ao iniciar o app."
    )


def _normalizar_slug(texto: str) -> str:
    bruto = unicodedata.normalize("NFKD", str(texto or "").strip().lower())
    sem_acento = "".join(c for c in bruto if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "_", sem_acento).strip("_")
    return slug[:32]


def status_pausa_de_slug(slug: str) -> str:
    s = _normalizar_slug(slug)
    if not s or not _SLUG_RE.match(s):
        raise ValueError("Identificador de pausa inválido.")
    return f"aguardando_{s}"


def slug_de_status_pausa(status: str | None) -> str | None:
    st = str(status or "").strip()
    if not st.startswith("aguardando_"):
        return None
    slug = st[len("aguardando_") :]
    return slug if slug and _SLUG_RE.match(slug) else None


def _ler_json_lista(conn: sqlite3.Connection, chave: str, padrao: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        row = conn.execute(
            "SELECT valor FROM app_os_config WHERE chave = ?",
            (chave,),
        ).fetchone()
    except sqlite3.OperationalError:
        return [dict(x) for x in padrao]
    if row is None:
        return [dict(x) for x in padrao]
    try:
        bruto = json.loads(str(row["valor"] or "[]"))
    except json.JSONDecodeError:
        return [dict(x) for x in padrao]
    if not isinstance(bruto, list):
        return [dict(x) for x in padrao]
    return bruto


def _salvar_json_lista(conn: sqlite3.Connection, chave: str, lista: list[dict[str, Any]]) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO app_os_config (chave, valor) VALUES (?, ?)",
        (chave, json.dumps(lista, ensure_ascii=False)),
    )


def _sanitizar_marcadores(lista: list[Any]) -> list[dict[str, Any]]:
    saida: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in lista:
        if not isinstance(item, dict):
            continue
        rid = _normalizar_slug(str(item.get("id") or item.get("rotulo") or ""))
        if not rid or rid in vistos:
            continue
        rotulo = str(item.get("rotulo") or rid).strip()[:40]
        if not rotulo:
            continue
        cor = str(item.get("cor") or "#6b7280").strip()[:20]
        vistos.add(rid)
        saida.append({"id": rid, "rotulo": rotulo, "cor": cor})
    if not saida:
        return [dict(x) for x in _DEFAULT_MARCADORES]
    return saida


def _sanitizar_pausas(lista: list[Any]) -> list[dict[str, Any]]:
    saida: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in lista:
        if not isinstance(item, dict):
            continue
        slug = _normalizar_slug(str(item.get("slug") or item.get("id") or item.get("rotulo") or ""))
        if not slug or slug in vistos or not _SLUG_RE.match(slug):
            continue
        rid = _normalizar_slug(str(item.get("id") or slug))
        rotulo = str(item.get("rotulo") or slug).strip()[:40]
        if not rotulo:
            continue
        cor = str(item.get("cor") or "pausa-garantia").strip()[:32]
        vistos.add(slug)
        saida.append({"id": rid, "slug": slug, "rotulo": rotulo, "cor": cor})
    if not saida:
        return [dict(x) for x in _DEFAULT_PAUSAS]
    return saida


def carregar_marcadores_lista(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    cfg, fechar = _obter_conn_config(conn)
    try:
        return _sanitizar_marcadores(_ler_json_lista(cfg, _CHAVE_MARCADORES, _DEFAULT_MARCADORES))
    finally:
        if fechar:
            cfg.close()


def carregar_pausas_tipos(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    cfg, fechar = _obter_conn_config(conn)
    try:
        return _sanitizar_pausas(_ler_json_lista(cfg, _CHAVE_PAUSAS, _DEFAULT_PAUSAS))
    finally:
        if fechar:
            cfg.close()


def salvar_personalizacao_lista_os(
    conn: sqlite3.Connection | None = None,
    *,
    marcadores: list[Any] | None = None,
    pausas: list[Any] | None = None,
) -> dict[str, Any]:
    cfg, fechar = _obter_conn_config(conn)
    try:
        _garantir_tabela_config(cfg)
        atual_m = carregar_marcadores_lista(cfg)
        atual_p = carregar_pausas_tipos(cfg)
        if marcadores is not None:
            atual_m = _sanitizar_marcadores(marcadores)
            _salvar_json_lista(cfg, _CHAVE_MARCADORES, atual_m)
        if pausas is not None:
            atual_p = _sanitizar_pausas(pausas)
            _salvar_json_lista(cfg, _CHAVE_PAUSAS, atual_p)
        if fechar:
            cfg.commit()
        return {"marcadores": atual_m, "pausas": atual_p}
    finally:
        if fechar:
            cfg.close()


def pausas_status_ativos(pausas: list[dict[str, Any]]) -> frozenset[str]:
    return frozenset(status_pausa_de_slug(str(p["slug"])) for p in pausas if p.get("slug"))


def os_status_em_pausa_config(status: str | None, pausas: list[dict[str, Any]]) -> bool:
    st = str(status or "").strip()
    return st in pausas_status_ativos(pausas)


def meta_pausa_por_status(
    status: str | None,
    pausas: list[dict[str, Any]],
) -> dict[str, Any] | None:
    slug = slug_de_status_pausa(status)
    if not slug:
        return None
    for p in pausas:
        if str(p.get("slug") or "") == slug:
            codigo = status_pausa_de_slug(slug)
            return {
                "codigo": codigo,
                "rotulo": f"Aguard. {p.get('rotulo') or slug}",
                "cor": str(p.get("cor") or "pausa-garantia"),
                "clicavel": False,
                "acao": None,
                "dica": f"Serviço pausado — {p.get('rotulo') or slug} (marcado pelo responsável).",
                "pausa": True,
                "pausa_filtro": slug,
            }
    return None


def mapa_filtro_pausa(pausas: list[dict[str, Any]]) -> dict[str, str]:
    return {str(p["slug"]): status_pausa_de_slug(str(p["slug"])) for p in pausas if p.get("slug")}


def mapa_marcadores(marcadores: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(m["id"]): m for m in marcadores if m.get("id")}


def extrair_info_lista_os(dados_json: str | None) -> dict[str, str]:
    try:
        dados = json.loads(dados_json or "{}")
    except json.JSONDecodeError:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    return {
        "marcador_lista_os": str(dados.get("marcador_lista_os") or "").strip(),
        "obs_lista_os": str(dados.get("obs_lista_os") or "").strip(),
    }


def aplicar_info_lista_os_payload(
    dados_json: str | None,
    *,
    marcador_id: str | None = None,
    obs: str | None = None,
) -> str:
    try:
        dados = json.loads(dados_json or "{}")
    except json.JSONDecodeError:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    if marcador_id is not None:
        mid = str(marcador_id or "").strip()
        if mid:
            dados["marcador_lista_os"] = mid
        else:
            dados.pop("marcador_lista_os", None)
    if obs is not None:
        txt = str(obs or "").strip()
        if txt:
            dados["obs_lista_os"] = txt[:500]
        else:
            dados.pop("obs_lista_os", None)
    return json.dumps(dados, ensure_ascii=False)
