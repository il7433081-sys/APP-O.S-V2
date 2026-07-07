"""Toggles de navegação automática após ações no app O.S."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

_CHAVE = "nav_pos_acao"

_PRINCIPAL_DB_PATH: Path | None = None

_GRUPOS: dict[str, str] = {
    "lista_perfil": "Lista e perfil do mecânico",
    "requisicoes": "Requisições",
    "notificacoes": "Notificações",
    "ordem": "Ordem de serviço",
}

_ITENS: dict[str, dict[str, Any]] = {
    "apos_pausa_os_perfil": {
        "rotulo": "Após pausar O.S. na lista, abrir o perfil do mecânico",
        "dica": (
            "Agiliza conferir as O.S. em espera do mecânico logo após marcar a pausa. "
            "Desligado: apenas atualiza as listas na tela atual."
        ),
        "grupo": "lista_perfil",
        "padrao": False,
    },
    "apos_retomar_os_perfil": {
        "rotulo": "Após retomar O.S. em espera, abrir o perfil do mecânico",
        "dica": (
            "Mostra imediatamente o perfil com a O.S. de volta à fila do mecânico. "
            "Desligado: permanece na lista de O.S."
        ),
        "grupo": "lista_perfil",
        "padrao": False,
    },
    "apos_finalizar_servico_perfil": {
        "rotulo": "Após finalizar serviço pelo perfil, voltar ao perfil do mecânico",
        "dica": (
            "Recarrega o perfil após marcar a O.S. como pronta. "
            "Desligado: atualiza dados em segundo plano se você já estiver no perfil."
        ),
        "grupo": "lista_perfil",
        "padrao": False,
    },
    "apos_salvar_foto_perfil": {
        "rotulo": "Após salvar foto do perfil, recarregar a tela do perfil",
        "dica": (
            "Força atualização completa do perfil após trocar a foto. "
            "Desligado: atualiza a foto no lugar se o perfil já estiver aberto."
        ),
        "grupo": "lista_perfil",
        "padrao": False,
    },
    "apos_salvar_requisicao_editor_perfil": {
        "rotulo": "Após salvar rascunho no módulo Requisições, abrir o perfil do mecânico",
        "dica": (
            "Útil se você alterna entre requisição e acompanhamento no perfil do mecânico. "
            "Desligado: permanece na aba Requisições."
        ),
        "grupo": "requisicoes",
        "padrao": False,
    },
    "apos_enviar_req_perfil_inline": {
        "rotulo": "Após enviar requisição pelo painel inline do perfil, recarregar o perfil",
        "dica": (
            "Volta ao perfil com a lista atualizada após o envio. "
            "Desligado: atualiza em segundo plano se o perfil já estiver visível."
        ),
        "grupo": "requisicoes",
        "padrao": False,
    },
    "perfil_req_sem_edicao_abre_requisicao": {
        "rotulo": "No perfil, abrir requisição sem edição inline no módulo Requisições",
        "dica": (
            "Quando o responsável não edita requisição no perfil, o clique no botão "
            "Requisição leva ao módulo Requisições. Desligado: não troca de módulo."
        ),
        "grupo": "requisicoes",
        "padrao": True,
    },
    "notificacao_abre_perfil": {
        "rotulo": "Ao clicar em notificação, abrir o perfil do mecânico",
        "dica": (
            "Atalho para o responsável ver o mecânico ligado à requisição. "
            "Desligado: apenas marca a notificação como vista."
        ),
        "grupo": "notificacoes",
        "padrao": True,
    },
    "notificacao_abre_requisicao": {
        "rotulo": "Ao clicar em notificação, ir ao módulo Requisições",
        "dica": (
            "Abre a requisição correspondente na aba certa (ativas, internas ou finalizadas). "
            "Desligado: não troca de módulo."
        ),
        "grupo": "notificacoes",
        "padrao": True,
    },
    "copiar_os_abre_ordem": {
        "rotulo": "Após copiar O.S., abrir o módulo Ordem de Serviço",
        "dica": (
            "Leva ao formulário da nova O.S. copiada para revisão imediata. "
            "Desligado: copia os dados mas mantém a tela atual."
        ),
        "grupo": "ordem",
        "padrao": True,
    },
    "abrir_os_edicao_ordem": {
        "rotulo": "Ao abrir O.S. da lista para editar, ir ao módulo Ordem de Serviço",
        "dica": (
            "Comportamento esperado ao clicar em uma O.S. salva: abre o formulário completo. "
            "Desligado: carrega os dados sem trocar de módulo."
        ),
        "grupo": "ordem",
        "padrao": True,
    },
    "nova_os_abre_ordem": {
        "rotulo": "Ao clicar em Nova O.S., ir ao módulo Ordem de Serviço",
        "dica": (
            "Mostra o formulário em branco para começar o preenchimento. "
            "Desligado: limpa o formulário sem mudar de aba."
        ),
        "grupo": "ordem",
        "padrao": True,
    },
    "agendamento_gerar_os_ordem": {
        "rotulo": "Ao gerar O.S. a partir de agendamento, ir ao módulo Ordem de Serviço",
        "dica": (
            "Preenche o formulário com dados do agendamento e abre a aba Ordem para gravar. "
            "Desligado: preenche em segundo plano na tela atual."
        ),
        "grupo": "ordem",
        "padrao": True,
    },
    "agendamento_novo_cliente_ordem": {
        "rotulo": "Ao cadastrar cliente novo pelo agendamento, ir ao módulo Ordem de Serviço",
        "dica": (
            "Abre Entrada/Cliente para cadastrar o cliente e depois voltar ao agendamento. "
            "Desligado: não troca de módulo automaticamente."
        ),
        "grupo": "ordem",
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
        grupo = str(meta["grupo"])
        itens[chave] = {
            "ativo": bool(ativos.get(chave, meta["padrao"])),
            "rotulo": str(meta["rotulo"]),
            "dica": str(meta["dica"]),
            "grupo": grupo,
            "grupo_rotulo": _GRUPOS.get(grupo, grupo),
        }
    return {"itens": itens, "grupos": dict(_GRUPOS)}


def carregar_nav_pos_acao(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    cfg, fechar = _obter_conn_config(conn)
    try:
        return _montar_resposta(_ler_salvos(cfg))
    finally:
        if fechar:
            cfg.close()


def salvar_nav_pos_acao(
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
