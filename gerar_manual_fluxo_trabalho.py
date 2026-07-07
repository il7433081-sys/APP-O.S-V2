"""
Gera PDF do fluxo de trabalho O.S. (v2.8.0): implementado vs pendente.

Execute: python gerar_manual_fluxo_trabalho.py
Saida: MANUAL_FLUXO_TRABALHO.pdf (mesma pasta)
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fpdf import FPDF

_FONT = "ArialFluxo"
_APP_DIR = Path(__file__).resolve().parent
_SAIDA = _APP_DIR / "MANUAL_FLUXO_TRABALHO.pdf"
_APP_VERSION = "2.8.0"


def _registrar_fontes(pdf: FPDF) -> str:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    regular = windir / "Fonts" / "arial.ttf"
    bold = windir / "Fonts" / "arialbd.ttf"
    if regular.is_file():
        pdf.add_font(_FONT, "", str(regular))
        pdf.add_font(_FONT, "B", str(bold if bold.is_file() else regular))
        return _FONT
    return "Helvetica"


def _txt(s: str) -> str:
    return (
        s.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2192", "->")
        .replace("\u2190", "<-")
        .replace("\u2022", "-")
    )


class DocPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(getattr(self, "_fonte", "Helvetica"), "", 8)
        self.set_text_color(100, 100, 100)
        self.cell(
            0,
            8,
            _txt(
                f"Fluxo de Trabalho O.S. v{_APP_VERSION} - "
                f"{date.today():%d/%m/%Y} - pag. {self.page_no()}"
            ),
            align="C",
        )


def _largura(pdf: DocPDF) -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin


def titulo(pdf: DocPDF, texto: str, nivel: int = 1) -> None:
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.set_x(pdf.l_margin)
    if nivel == 1:
        pdf.set_font(pdf._fonte, "B", 14)
        pdf.set_text_color(20, 60, 120)
    else:
        pdf.set_font(pdf._fonte, "B", 11)
        pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(_largura(pdf), 7, _txt(texto))
    pdf.ln(2)


def paragrafo(pdf: DocPDF, texto: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._fonte, "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(_largura(pdf), 5.5, _txt(texto))
    pdf.ln(1.5)


def item(pdf: DocPDF, texto: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._fonte, "", 10)
    pdf.multi_cell(_largura(pdf), 5.5, _txt(f"  - {texto}"))
    pdf.ln(0.5)


def caixa(pdf: DocPDF, texto: str) -> None:
    pdf.set_fill_color(245, 248, 252)
    pdf.set_draw_color(180, 200, 230)
    y = pdf.get_y()
    pdf.set_font(pdf._fonte, "", 9)
    linhas = texto.count("\n") + max(1, len(texto) // 88)
    h = linhas * 5.5 + 6
    if y + h > 275:
        pdf.add_page()
        y = pdf.get_y()
    margem = pdf.l_margin
    largura = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.rect(margem, y, largura, h, style="DF")
    pdf.set_xy(margem + 2, y + 3)
    pdf.multi_cell(largura - 4, 5.5, _txt(texto))
    pdf.set_xy(margem, y + h + 2)


def diagrama_fluxo(pdf: DocPDF) -> None:
    titulo(pdf, "Diagrama do fluxo (visao geral)", 2)
    caixa(
        pdf,
        "[Atendente/Admin] Cria O.S. e designa mecanico\n"
        "        |\n"
        "        v\n"
        "[Mecanico] Trabalha na O.S. (auto-save) + requisicao de material\n"
        "        |  cores: laranja=aguardando | vermelho=alteracao | verde=ok\n"
        "        v\n"
        "[Atendente/Admin] Responde requisicao (precos) -> envia resposta\n"
        "        |\n"
        "        v\n"
        "[Futuro] Orcamento + link assinatura -> aprovacao cliente\n"
        "        |\n"
        "        v\n"
        "[Mecanico] Finalizar servico (senha) -> O.S. pronto_mecanico\n"
        "        |\n"
        "        v\n"
        "[Futuro] Notifica Sistema Oficina para nota fiscal",
    )


def gerar() -> Path:
    pdf = DocPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf._fonte = _registrar_fontes(pdf)
    pdf.add_page()

    pdf.set_font(pdf._fonte, "B", 18)
    pdf.set_text_color(15, 50, 100)
    pdf.multi_cell(_largura(pdf), 9, _txt("Fluxo de Trabalho - Ordem de Servico"))
    pdf.set_font(pdf._fonte, "", 12)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(_largura(pdf), 7, _txt(f"Versao { _APP_VERSION } - O que ja funciona e o que falta"))
    pdf.ln(4)

    paragrafo(
        pdf,
        "Este documento descreve o fluxo acordado entre mecanicos, atendentes e "
        "administradores, o que foi implementado na versao 2.8.0 e como testar no navegador.",
    )

    diagrama_fluxo(pdf)

    titulo(pdf, "PARTE 1 - Ja implementado (v2.8.0)")
    titulo(pdf, "1. Requisicoes de material", 2)
    item(pdf, "Tabela requisicoes_material no banco SQLite (fluxo_requisicoes.py)")
    item(pdf, "Status: rascunho, aguardando_responsavel, alterada_mecanico, respondida, alterada_responsavel")
    item(pdf, "APIs: GET/POST /api/requisicoes, POST .../enviar, .../responder, .../marcar-vista")
    item(pdf, "Aba Requisicao: lista, editor de itens (descricao, qtd, preco para responsavel)")
    item(pdf, "Mecanico: Salvar + Enviar requisicao")
    item(pdf, "Atendente/Admin: editar precos + Enviar resposta")
    item(pdf, "Cores por perfil: verde (ok), laranja (aguardando), vermelho (alteracao pendente)")

    titulo(pdf, "2. Notificacoes e indicadores visuais", 2)
    item(pdf, "Barra no topo: aviso quando mecanico envia ou altera requisicao (responsavel)")
    item(pdf, "Varios mecanicos: lista suspensa para escolher qual aviso abrir")
    item(pdf, "Clique no aviso: abre perfil do mecanico e aba Requisicao; marca como visto")
    item(pdf, "Ponto laranja/vermelho no avatar do mecanico na barra lateral (responsavel)")
    item(pdf, "No perfil do mecanico: botao colorido 'Requisicao de material' em cada O.S.")

    titulo(pdf, "3. Trabalho do mecanico na O.S.", 2)
    item(pdf, "Auto-save: alteracoes nos campos permitidos sao gravadas apos ~2 s (sem clicar Salvar)")
    item(pdf, "Indicador 'Alteracoes salvas automaticamente' no cabecalho")
    item(pdf, "Botao 'Finalizar servico': pede senha e marca O.S. como pronto_mecanico")
    item(pdf, "O.S. finalizada sai da lista ativa do mecanico")

    titulo(pdf, "4. Arquivos alterados", 2)
    caixa(
        pdf,
        "fluxo_requisicoes.py - logica de requisicoes e status\n"
        "app.py - rotas API e integracao com perfis\n"
        "templates/index.html - UI, CSS, JavaScript do fluxo\n"
        "gerar_manual_fluxo_trabalho.py - este PDF",
    )

    pdf.add_page()
    titulo(pdf, "PARTE 2 - Como testar")
    titulo(pdf, "Preparacao", 2)
    item(pdf, "Inicie o servidor: python app.py ou iniciar_servidor.bat")
    item(pdf, "Acesse http://127.0.0.1:5000 e use Ctrl+F5 apos atualizar")
    item(pdf, "Usuarios de exemplo: admin, CARLOS (atendente), OTAVIO/PEDRO (mecanicos)")

    titulo(pdf, "Cenario A - Mecanico envia requisicao", 2)
    item(pdf, "1. Login como atendente: crie ou abra uma O.S. e atribua ao mecanico OTAVIO")
    item(pdf, "2. Login como OTAVIO: abra a O.S. no perfil ou lista")
    item(pdf, "3. Aba Requisicao: informe O.S., adicione itens, Salvar e Enviar")
    item(pdf, "4. Badge fica verde para o mecanico; atendente ve ponto laranja no avatar")

    titulo(pdf, "Cenario B - Responsavel responde", 2)
    item(pdf, "1. Login como CARLOS ou admin: clique no aviso no topo ou no perfil do mecanico")
    item(pdf, "2. Abra a requisicao, preencha precos, Salvar e Enviar resposta")
    item(pdf, "3. Mecanico ve notificacao e badge verde na requisicao")

    titulo(pdf, "Cenario C - Alteracao e cores", 2)
    item(pdf, "Mecanico edita itens apos envio: status alterada_mecanico -> vermelho para atendente")
    item(pdf, "Atendente edita apos responder: alterada_responsavel -> vermelho para mecanico")
    item(pdf, "Reenviar (Enviar / Enviar resposta) volta ao verde para quem recebeu")

    titulo(pdf, "Cenario D - Finalizar servico", 2)
    item(pdf, "Mecanico com O.S. aberta: botao 'Finalizar servico' no cabecalho")
    item(pdf, "Confirme com a senha do usuario mecanico")
    item(pdf, "O.S. some do perfil do mecanico; status pronto_mecanico no banco")

    titulo(pdf, "Legenda de cores (requisicao)", 2)
    caixa(
        pdf,
        "LARANJA: aguardando acao do responsavel (mecanico enviou)\n"
        "VERMELHO: houve alteracao ainda nao vista/tratada pelo outro lado\n"
        "VERDE: em dia (enviado ou respondido conforme a visao do perfil)\n"
        "CINZA: rascunho / sem envio",
    )

    pdf.add_page()
    titulo(pdf, "PARTE 3 - Ainda nao implementado (proximas etapas)")
    titulo(pdf, "Configuracoes e perfis", 2)
    item(pdf, "Mecanico criar O.S. somente se admin autorizar (config por perfil)")
    item(pdf, "Expandir quem e 'responsavel' alem de atendente e admin")

    titulo(pdf, "Checklist por etapas", 2)
    item(pdf, "Modelo de checklist configuravel conforme andamento do servico")
    item(pdf, "Salvamento incremental ja previsto via auto-save na O.S.")

    titulo(pdf, "Integracao Sistema Oficina", 2)
    item(pdf, "Enviar requisicao respondida para o modulo de estoque/compras da Oficina")
    item(pdf, "Notificar Oficina quando O.S. estiver pronto_mecanico (cliente pronto para nota)")
    item(pdf, "Configuracoes de quais eventos disparam sincronizacao")

    titulo(pdf, "Orcamento e aprovacao", 2)
    item(pdf, "Montagem do orcamento a partir da requisicao com precos")
    item(pdf, "Envio com link de assinatura para aprovacao do cliente")
    item(pdf, "Notificacao no perfil do mecanico e dos responsaveis quando aprovado")
    item(pdf, "Status aprovada na requisicao / O.S.")

    titulo(pdf, "Melhorias de UX previstas", 2)
    item(pdf, "Modal de senha mais amigavel no lugar de window.prompt")
    item(pdf, "Destaque de itens removidos pelo mecanico na edicao do responsavel")
    item(pdf, "Polling mais fino ou WebSocket para notificacoes em tempo real")

    paragrafo(
        pdf,
        "Para duvidas ou ajustes no fluxo, altere fluxo_requisicoes.py e as rotas em app.py. "
        "Regenere este PDF com: python gerar_manual_fluxo_trabalho.py",
    )

    pdf.output(str(_SAIDA))
    return _SAIDA


if __name__ == "__main__":
    path = gerar()
    print(f"PDF gerado: {path}")
