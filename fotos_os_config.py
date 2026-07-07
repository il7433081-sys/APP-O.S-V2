"""Limites opcionais de fotos por O.S. (app_os_config) — só admin altera."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

_CHAVE = "fotos_os_config"

_PRINCIPAL_DB_PATH: Path | None = None

# Padrão do app quando limites personalizados estão desligados.
# Limite no tamanho da string base64 enviada (≈33% maior que o arquivo JPEG).
_PADRAO_INTERNO_MAX_FOTOS = 20
_PADRAO_INTERNO_MAX_KB = 10240

_PADRAO_LIMITES_PERSONALIZADOS = False
_PADRAO_CFG_MAX_FOTOS = 20
_PADRAO_CFG_MAX_KB = 10240
_MIN_MAX_FOTOS = 1
_MAX_MAX_FOTOS = 50
_MIN_MAX_KB = 50
_MAX_MAX_KB = 15360


def configurar_banco_principal(caminho: Path | str) -> None:
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


def _bool_valor(valor: Any, *, padrao: bool) -> bool:
    if valor is None:
        return padrao
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in ("1", "true", "sim", "yes", "on")


def _int_limite(valor: Any, *, padrao: int, minimo: int, maximo: int) -> int:
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return padrao
    return max(minimo, min(maximo, n))


def _defaults() -> dict[str, Any]:
    return {
        "limites_personalizados": _PADRAO_LIMITES_PERSONALIZADOS,
        "max_fotos_por_envio": _PADRAO_CFG_MAX_FOTOS,
        "max_kb_por_foto": _PADRAO_CFG_MAX_KB,
    }


def _ler_salvos(conn: sqlite3.Connection) -> dict[str, Any]:
    padroes = _defaults()
    try:
        row = conn.execute(
            "SELECT valor FROM app_os_config WHERE chave = ?",
            (_CHAVE,),
        ).fetchone()
    except sqlite3.OperationalError:
        return padroes
    if row is None:
        return padroes
    try:
        bruto = json.loads(str(row["valor"] or "{}"))
    except json.JSONDecodeError:
        return padroes
    if not isinstance(bruto, dict):
        return padroes
    lim_pers = bruto.get("limites_personalizados")
    if lim_pers is None and "ativo" in bruto:
        lim_pers = bruto.get("ativo")
    return {
        "limites_personalizados": _bool_valor(
            lim_pers, padrao=padroes["limites_personalizados"]
        ),
        "max_fotos_por_envio": _int_limite(
            bruto.get("max_fotos_por_envio"),
            padrao=padroes["max_fotos_por_envio"],
            minimo=_MIN_MAX_FOTOS,
            maximo=_MAX_MAX_FOTOS,
        ),
        "max_kb_por_foto": _int_limite(
            bruto.get("max_kb_por_foto"),
            padrao=padroes["max_kb_por_foto"],
            minimo=_MIN_MAX_KB,
            maximo=_MAX_MAX_KB,
        ),
    }


def limites_efetivos_fotos_os(cfg: dict[str, Any]) -> dict[str, Any]:
    """Limites usados no envio: internos (padrão) ou personalizados pelo admin."""
    if cfg.get("limites_personalizados"):
        max_kb = int(cfg.get("max_kb_por_foto") or _PADRAO_CFG_MAX_KB)
        return {
            "limites_personalizados": True,
            "max_fotos_por_envio": int(cfg.get("max_fotos_por_envio") or _PADRAO_CFG_MAX_FOTOS),
            "max_kb_por_foto": max_kb,
            "max_bytes_por_foto": max_kb * 1024,
        }
    return {
        "limites_personalizados": False,
        "max_fotos_por_envio": _PADRAO_INTERNO_MAX_FOTOS,
        "max_kb_por_foto": _PADRAO_INTERNO_MAX_KB,
        "max_bytes_por_foto": _PADRAO_INTERNO_MAX_KB * 1024,
    }


def _montar_resposta(cfg: dict[str, Any]) -> dict[str, Any]:
    eff = limites_efetivos_fotos_os(cfg)
    return {
        "limites_personalizados": bool(cfg["limites_personalizados"]),
        "max_fotos_por_envio": int(cfg["max_fotos_por_envio"]),
        "max_kb_por_foto": int(cfg["max_kb_por_foto"]),
        "limites_efetivos": eff,
        "limites": {
            "max_fotos_min": _MIN_MAX_FOTOS,
            "max_fotos_max": _MAX_MAX_FOTOS,
            "max_kb_min": _MIN_MAX_KB,
            "max_kb_max": _MAX_MAX_KB,
            "interno_max_fotos": _PADRAO_INTERNO_MAX_FOTOS,
            "interno_max_kb": _PADRAO_INTERNO_MAX_KB,
        },
        "dicas": {
            "limites_personalizados": (
                "Desligado por padrão: o app usa limites internos (20 fotos, até ~10 MB por foto no envio). "
                "Ligue para definir valores próprios abaixo."
            ),
            "max_fotos_por_envio": (
                "Só vale com limites personalizados ligados. "
                f"Máximo de imagens por envio (entre {_MIN_MAX_FOTOS} e {_MAX_MAX_FOTOS})."
            ),
            "max_kb_por_foto": (
                "Só vale com limites personalizados ligados. "
                f"Tamanho máximo da imagem no envio (base64), entre {_MIN_MAX_KB} e {_MAX_MAX_KB} KB. "
                "Fotos de 6–7 MB da câmera costumam caber em ~8–10 MB no envio."
            ),
        },
    }


def carregar_fotos_os_config(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    cfg_conn, fechar = _obter_conn_config(conn)
    try:
        return _montar_resposta(_ler_salvos(cfg_conn))
    finally:
        if fechar:
            cfg_conn.close()


def salvar_fotos_os_config(
    conn: sqlite3.Connection | None = None,
    *,
    alteracoes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg_conn, fechar = _obter_conn_config(conn)
    try:
        _garantir_tabela_config(cfg_conn)
        atual = _ler_salvos(cfg_conn)
        if alteracoes:
            if "limites_personalizados" in alteracoes:
                atual["limites_personalizados"] = _bool_valor(
                    alteracoes["limites_personalizados"],
                    padrao=atual["limites_personalizados"],
                )
            if "ativo" in alteracoes:
                atual["limites_personalizados"] = _bool_valor(
                    alteracoes["ativo"],
                    padrao=atual["limites_personalizados"],
                )
            if "max_fotos_por_envio" in alteracoes:
                atual["max_fotos_por_envio"] = _int_limite(
                    alteracoes["max_fotos_por_envio"],
                    padrao=atual["max_fotos_por_envio"],
                    minimo=_MIN_MAX_FOTOS,
                    maximo=_MAX_MAX_FOTOS,
                )
            if "max_kb_por_foto" in alteracoes:
                atual["max_kb_por_foto"] = _int_limite(
                    alteracoes["max_kb_por_foto"],
                    padrao=atual["max_kb_por_foto"],
                    minimo=_MIN_MAX_KB,
                    maximo=_MAX_MAX_KB,
                )
        salvar = {
            "limites_personalizados": atual["limites_personalizados"],
            "max_fotos_por_envio": atual["max_fotos_por_envio"],
            "max_kb_por_foto": atual["max_kb_por_foto"],
        }
        cfg_conn.execute(
            "INSERT OR REPLACE INTO app_os_config (chave, valor) VALUES (?, ?)",
            (_CHAVE, json.dumps(salvar, ensure_ascii=False)),
        )
        if fechar:
            cfg_conn.commit()
        return _montar_resposta(atual)
    finally:
        if fechar:
            cfg_conn.close()
