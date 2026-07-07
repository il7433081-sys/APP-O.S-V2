"""
Gera PDF: resumo das atualizacoes (v2.5 / v2.6) + tutorial de uso.

Execute: python gerar_manual_atualizacoes_v26.py
Saida: MANUAL_ATUALIZACOES_E_TUTORIAL.pdf (mesma pasta)
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fpdf import FPDF

_FONT = "ArialAtual"
_APP_DIR = Path(__file__).resolve().parent
_SAIDA = _APP_DIR / "MANUAL_ATUALIZACOES_E_TUTORIAL.pdf"
_APP_VERSION = "2.6.0"


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
    )


class DocPDF(FPDF):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._secao_rodape = "atualizacoes"

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(getattr(self, "_fonte", "Helvetica"), "", 8)
        self.set_text_color(100, 100, 100)
        rotulo = "tutorial" if self._secao_rodape == "tutorial" else "atualizacoes"
        self.cell(
            0,
            8,
            _txt(
                f"Ordem de Servico Digital - {rotulo} - "
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
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(_largura(pdf), 5.5, _txt(f"  - {texto}"))
    pdf.ln(0.5)


def caixa(pdf: DocPDF, texto: str) -> None:
    pdf.set_fill_color(245, 248, 252)
    pdf.set_draw_color(180, 200, 230)
    y = pdf.get_y()
    pdf.set_font(pdf._fonte, "", 9)
    linhas = texto.count("\n") + max(1, len(texto) // 92)
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


def pagina_tutorial(pdf: DocPDF) -> None:
    """Nova pagina dedicada ao tutorial (separada do resumo)."""
    pdf.add_page()
    pdf._secao_rodape = "tutorial"
    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._fonte, "B", 18)
    pdf.set_text_color(15, 50, 100)
    pdf.multi_cell(_largura(pdf), 9, _txt("Tutorial - Como usar"))
    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._fonte, "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(
        _largura(pdf),
        6,
        _txt("Guia pratico do login, perfis, atribuicao de O.S. e configuracoes."),
    )
    pdf.ln(4)


def gerar() -> Path:
    pdf = DocPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf._fonte = _registrar_fontes(pdf)
    pdf._secao_rodape = "atualizacoes"
    pdf.add_page()

    # ------------------------------------------------------------------ capa
    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._fonte, "B", 18)
    pdf.set_text_color(15, 50, 100)
    pdf.multi_cell(_largura(pdf), 9, _txt("Ordem de Servico Digital"))
    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._fonte, "", 12)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        _largura(pdf),
        7,
        _txt(f"Resumo das atualizacoes (ate v{_APP_VERSION})"),
    )
    pdf.ln(3)
    paragrafo(
        pdf,
        "DOCUMENTO DE REFERENCIA - Parte 1: o que foi implementado. "
        "Parte 2 (proxima pagina): tutorial de uso no dia a dia.",
    )

    # ------------------------------------------------------------------ parte 1
    titulo(pdf, "PARTE 1 - O que foi feito")
    paragrafo(
        pdf,
        "Atualizacoes no app web (app.py / Flask), compartilhando o banco SQLite "
        "oficina_nautica.db com o Sistema Oficina quando DATABASE_PATH aponta para ele. "
        "O codigo do app NAO importa o Sistema Oficina - apenas le o mesmo .db.",
    )

    titulo(pdf, "1. Versao 2.5.0 - Login e sessao (Passo 1)", 2)
    item(pdf, "Tela /login com usuario, senha e preview do nome")
    item(pdf, "Sessao Flask (cookie seguro); menu Trocar usuario e Sair")
    item(pdf, "APIs: /api/login, /api/logout, /api/auth/status, /api/login/preview")
    item(pdf, "exigir_login gravado em app_os_config (independente da Oficina apos 1a sync)")
    item(pdf, "Rotas publicas: /assinar/<token> e /api/assinatura/... (cliente no celular sem login)")
    item(pdf, "Usuario padrao se banco vazio: admin / 123")
    item(pdf, "Arquivo de referencia: MANUAL_AUTH_E_INDEPENDENCIA.pdf")

    titulo(pdf, "2. Versao 2.5.0 - Usuarios na Configuracao (Passo 2)", 2)
    item(pdf, "Switch Exigir login na aba Configuracao")
    item(pdf, "Listar, cadastrar e excluir usuarios (admin ou permissao Config)")
    item(pdf, "APIs: GET/POST /api/usuarios, DELETE /api/usuarios/<id>")
    item(pdf, "Usuarios na tabela usuarios do .db - aparecem tambem no Sistema Oficina")

    titulo(pdf, f"3. Versao {_APP_VERSION} - Perfis, edicao e atribuicao de O.S.", 2)
    item(pdf, "Novos perfis: administrador, atendente/estoque, mecanico, operador (legado)")
    item(pdf, "Editar usuario: senha (opcional), nome, perfil, permissoes - PUT /api/usuarios/<id>")
    item(pdf, "Config recolhivel: icones na lateral (engrenagem + escudo); clique abre/fecha")
    item(pdf, "Campo Mecanico atribuido na O.S. (colunas mecanico_id e mecanico_nome no banco)")
    item(pdf, "Lista de O.S.: coluna Mecanico; quadro de atribuicoes na aba Lista")
    item(pdf, "Mecanico: ve so O.S. atribuidas; edita campos tecnicos; nao cria O.S. nova")
    item(pdf, "Atendente/admin: ve todas as O.S.; delega mecanico; quadro de andamento")
    item(pdf, "APIs: GET /api/mecanicos, GET /api/quadro-os")
    item(pdf, "Migracao automatica da tabela usuarios para aceitar novos perfis")

    titulo(pdf, "4. Arquivos principais alterados", 2)
    caixa(
        pdf,
        "app.py - autenticacao, perfis, APIs de usuarios e atribuicao\n"
        "templates/login.html - tela de entrada\n"
        "templates/index.html - Config, formulario O.S., permissoes por perfil\n"
        "gerar_manual_auth_independencia.py - manual auth/independencia\n"
        "gerar_manual_atualizacoes_v26.py - este PDF",
    )

    titulo(pdf, "5. O que ainda NAO foi feito (proximas etapas)", 2)
    item(pdf, "Aba Requisicao completa (fluxo mecanico pede -> atendente processa)")
    item(pdf, "Fase A do roadmap: janela desktop (PyWebView) sem parecer navegador")
    item(pdf, "Bloqueio fino de campos por permissao customizada (alem do perfil mecanico)")
    item(pdf, "Integracao de link de aprovacao no PDF do Sistema_Oficina")

    titulo(pdf, "6. Tabela de perfis (resumo tecnico)", 2)
    caixa(
        pdf,
        "admin        -> tudo + gerenciar usuarios e config\n"
        "atendente    -> O.S. completa, atribuir mecanico, quadro, lista geral\n"
        "mecanico     -> so O.S. atribuidas; campos tecnicos + requisicoes (textarea)\n"
        "operador     -> legado; tratado como atendente no app web",
    )

    # ------------------------------------------------------------------ parte 2 tutorial (nova pagina)
    pagina_tutorial(pdf)

    titulo(pdf, "1. Iniciar o servidor")
    item(pdf, "Na pasta app_ordem_servico: iniciar_servidor.bat")
    item(pdf, "PC: http://127.0.0.1:5000 | Celular na mesma Wi-Fi: http://SEU_IP:5000")
    item(pdf, "Acesso externo (4G): iniciar_acesso_externo.bat + ngrok (ver MANUAL_AUTH...)")

    titulo(pdf, "2. Login e exigir senha", 2)
    paragrafo(
        pdf,
        "Se exigir_login estiver DESLIGADO, o app abre direto (acesso livre). "
        "Para exigir senha: entre como admin -> Configuracao -> icone escudo -> "
        "ative Exigir login.",
    )
    item(pdf, "Menu do usuario (icone lateral) -> Trocar usuario -> /login")
    item(pdf, "Usuario inicial: admin / 123 (troque apos primeiro acesso)")
    item(pdf, "Assinatura remota pelo celular (/assinar/...) NAO pede login do funcionario")

    titulo(pdf, "3. Configuracao recolhivel", 2)
    paragrafo(
        pdf,
        "Na aba Configuracao, a esquerda aparecem icones. Por padrao as secoes "
        "ficam fechadas para manter a tela limpa.",
    )
    item(pdf, "Icone engrenagem: opcoes do app (ex.: Tipo de O.S. no PDF)")
    item(pdf, "Icone escudo: login e usuarios (so admin ou permissao Config)")
    item(pdf, "Clique no icone: abre a secao; clique de novo: fecha")
    item(pdf, "Clique no titulo da secao: recolhe/expande o conteudo")

    titulo(pdf, "4. Cadastrar e editar usuarios", 2)
    item(pdf, "1. Entre como administrador")
    item(pdf, "2. Configuracao -> icone escudo -> Login e usuarios")
    item(pdf, "3. Novo usuario: preencha login, nome, senha, perfil -> Cadastrar")
    item(pdf, "4. Editar: clique no lapis na linha do usuario -> altere -> Salvar alteracoes")
    item(pdf, "5. Senha em branco na edicao = mantem a senha atual")
    item(pdf, "Usuarios ficam no .db compartilhado - visiveis no Sistema Oficina tambem")

    titulo(pdf, "5. Perfis no dia a dia", 2)

    titulo(pdf, "5.1 Administrador", 3)
    item(pdf, "Acesso total: O.S., Config, usuarios, atribuicao de mecanico")
    item(pdf, "Pode ligar/desligar exigir login e cadastrar todos os perfis")

    titulo(pdf, "5.2 Atendente / Estoque", 3)
    item(pdf, "Cria e edita O.S. normalmente")
    item(pdf, "No formulario (aba Entrada): escolhe Mecanico atribuido antes de salvar")
    item(pdf, "Na aba Lista: ve Quadro de atribuicoes (quem esta com qual O.S.)")
    item(pdf, "Ve todas as O.S. na lista")

    titulo(pdf, "5.3 Mecanico", 3)
    item(pdf, "Entra com seu login; ve APENAS as O.S. atribuidas a ele")
    item(pdf, "Nao cria O.S. nova (botao Nova O.S. oculto)")
    item(pdf, "Abre a O.S. -> vai direto para aba Diagnostico e Fechamento")
    item(pdf, "Pode editar: diagnostico, assinatura tecnico, analise/conclusao, requisicoes (texto)")
    item(pdf, "Nao ve dados de outro mecanico")

    titulo(pdf, "6. Fluxo recomendado: delegar servico", 2)
    item(pdf, "1. Atendente cria ou abre a O.S. e preenche cliente/embarcacao")
    item(pdf, "2. Em Mecanico atribuido, seleciona o mecanico responsavel")
    item(pdf, "3. Salva a O.S.")
    item(pdf, "4. Mecanico faz login, abre a O.S. na Lista e preenche diagnostico")
    item(pdf, "5. Atendente acompanha no Quadro de atribuicoes (aba Lista)")

    titulo(pdf, "7. App sozinho no futuro (sem Sistema Oficina)", 2)
    paragrafo(
        pdf,
        "Para rodar apenas o app web: copie a pasta app_ordem_servico, "
        "copie o .db para dados/app_os.db e altere o .env:",
    )
    caixa(pdf, "DATABASE_PATH=./dados/app_os.db")
    paragrafo(
        pdf,
        "Detalhes completos no arquivo MANUAL_AUTH_E_INDEPENDENCIA.pdf "
        "(passo a passo ao sair da empresa).",
    )

    titulo(pdf, "8. Problemas comuns", 2)
    item(pdf, "So aparece admin na lista: ainda nao cadastrou outros usuarios")
    item(pdf, "Mecanico nao ve O.S.: verifique se foi atribuido e se salvou com atendente/admin")
    item(pdf, "Config de usuarios nao aparece: entre como admin (Trocar usuario)")
    item(pdf, "Celular nao abre: mesma Wi-Fi, iniciar_servidor.bat, rede Privada no Windows")
    item(pdf, "Apos atualizar codigo: reinicie o servidor (feche e abra o .bat)")

    titulo(pdf, "9. Como pedir ajuda na proxima conversa", 2)
    paragrafo(
        pdf,
        "Envie este PDF e diga o que precisa. Exemplos: "
        "'Implementar aba Requisicao'; 'Mecanico nao abre O.S.'; "
        "'Fase A janela desktop'.",
    )

    pdf.output(str(_SAIDA))
    return _SAIDA


if __name__ == "__main__":
    caminho = gerar()
    print(f"PDF gerado: {caminho}")
