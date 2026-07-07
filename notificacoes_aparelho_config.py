"""Configuração global de notificações no aparelho (Web Notification API)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

_CHAVE = "notificacoes_aparelho"

_PRINCIPAL_DB_PATH: Path | None = None

_ITENS: dict[str, dict[str, Any]] = {
    "aparelho_ativo": {
        "rotulo": "Notificações no aparelho (celular / computador)",
        "dica": (
            "Permite avisos do sistema quando o app está em segundo plano. "
            "Cada usuário ainda precisa autorizar no navegador na primeira vez."
        ),
        "padrao": True,
    },
    "cliente_aprovou": {
        "rotulo": "Cliente aprovou o orçamento",
        "dica": "Avisa o mecânico e o responsável quando a assinatura de aprovação for registrada.",
        "padrao": True,
    },
    "pecas_separadas": {
        "rotulo": "Peças separadas / liberadas do estoque",
        "dica": "Avisa o mecânico quando o estoque liberar itens da requisição.",
        "padrao": True,
    },
    "orcamento_respondido": {
        "rotulo": "Orçamento respondido pelo responsável",
        "dica": "Avisa o mecânico quando a requisição receber preços e resposta.",
        "padrao": True,
    },
    "requisicao_nova": {
        "rotulo": "Nova requisição ou alteração do mecânico",
        "dica": "Avisa o responsável quando o mecânico enviar ou alterar uma requisição.",
        "padrao": True,
    },
}


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


def _defaults_ativos() -> dict[str, bool]:
    return {chave: bool(meta["padrao"]) for chave, meta in _ITENS.items()}


def _ler_salvos(conn: sqlite3.Connection) -> dict[str, bool]:
    padroes = _defaults_ativos()
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
    saida = dict(padroes)
    for chave in _ITENS:
        if chave in bruto:
            saida[chave] = _bool_valor(bruto[chave], padrao=padroes[chave])
    return saida


def _montar_resposta(ativos: dict[str, bool]) -> dict[str, Any]:
    itens: dict[str, Any] = {}
    for chave, meta in _ITENS.items():
        itens[chave] = {
            "ativo": bool(ativos.get(chave, meta["padrao"])),
            "rotulo": str(meta["rotulo"]),
            "dica": str(meta["dica"]),
        }
    return {"itens": itens}


def carregar_notificacoes_aparelho(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    cfg, fechar = _obter_conn_config(conn)
    try:
        return _montar_resposta(_ler_salvos(cfg))
    finally:
        if fechar:
            cfg.close()


def salvar_notificacoes_aparelho(
    conn: sqlite3.Connection | None = None,
    *,
    alteracoes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg, fechar = _obter_conn_config(conn)
    try:
        _garantir_tabela_config(cfg)
        ativos = _ler_salvos(cfg)
        if alteracoes:
            for chave, valor in alteracoes.items():
                if chave not in _ITENS:
                    continue
                ativos[chave] = _bool_valor(valor, padrao=_ITENS[chave]["padrao"])
        cfg.execute(
            "INSERT OR REPLACE INTO app_os_config (chave, valor) VALUES (?, ?)",
            (_CHAVE, json.dumps(ativos, ensure_ascii=False)),
        )
        if fechar:
            cfg.commit()
        return _montar_resposta(ativos)
    finally:
        if fechar:
            cfg.close()


def evento_notificacao_habilitado(
    evento: str,
    conn: sqlite3.Connection | None = None,
) -> bool:
    cfg = carregar_notificacoes_aparelho(conn)
    itens = cfg.get("itens") or {}
    master = (itens.get("aparelho_ativo") or {}).get("ativo", True)
    if not master:
        return False
    item = itens.get(str(evento or ""))
    if item is None:
        return True
    return bool(item.get("ativo", True))


def mapa_eventos_ativos(conn: sqlite3.Connection | None = None) -> dict[str, bool]:
    cfg = carregar_notificacoes_aparelho(conn)
    itens = cfg.get("itens") or {}
    master = bool((itens.get("aparelho_ativo") or {}).get("ativo", True))
    saida: dict[str, bool] = {"aparelho_ativo": master}
    for chave in _ITENS:
        if chave == "aparelho_ativo":
            continue
        saida[chave] = master and bool((itens.get(chave) or {}).get("ativo", True))
    return saida
