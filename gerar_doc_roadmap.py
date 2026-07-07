"""Gera PDF de referência: roadmap do app O.S., rede local e acesso externo."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fpdf import FPDF

_FONT = "ArialDoc"

SAIDA = Path(__file__).resolve().parent / "ROADMAP_APP_OS_REDE_E_DESKTOP.pdf"


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
    return s.replace("\u2014", "-").replace("\u2013", "-")


class DocPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(getattr(self, "_fonte", "Helvetica"), "", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"Ordem de Servico Digital - referencia interna - {date.today():%d/%m/%Y} - pag. {self.page_no()}", align="C")


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
    x, y = pdf.get_x(), pdf.get_y()
    pdf.set_font(pdf._fonte, "", 9)
    linhas = texto.count("\n") + max(1, len(texto) // 95)
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


def gerar() -> Path:
    pdf = DocPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf._fonte = _registrar_fontes(pdf)
    pdf.add_page()

    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._fonte, "B", 18)
    pdf.set_text_color(15, 50, 100)
    pdf.multi_cell(_largura(pdf), 9, _txt("Ordem de Servico Digital"))
    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._fonte, "", 12)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(_largura(pdf), 7, _txt("Roadmap: parecer app no PC, rede local e acesso externo"))
    pdf.ln(4)

    paragrafo(
        pdf,
        "DOCUMENTO DE REFERENCIA — Envie este PDF em uma nova conversa com o assistente "
        "de IA quando mudar de pasta ou quando a conversa anterior tiver sido apagada. "
        "Ele resume o que foi discutido, o que ja esta no GitHub e o que ainda falta fazer.",
    )

    titulo(pdf, "1. Contexto do projeto")
    paragrafo(
        pdf,
        "Existem dois programas separados na mesma pasta Projetos_Python:\n"
        "  - Sistema_Oficina/ — app desktop (CustomTkinter), abre com python main.py\n"
        "  - app_ordem_servico/ — app web (Flask), abre com iniciar_servidor.bat + navegador\n"
        "Ambos compartilham o banco SQLite oficina_nautica.db (via DATABASE_PATH no .env).",
    )
    paragrafo(
        pdf,
        "Branch Git: teste-pre-orcamento. Commit cc2db2b ja enviou app_ordem_servico ao GitHub. "
        "O arquivo .env NAO vai para o Git (esta no .gitignore).",
    )

    titulo(pdf, "2. Pergunta original do usuario (jun/2026)")
    paragrafo(
        pdf,
        "O app hoje roda no navegador (web). O Sistema Oficina abre/fecha como janela de programa. "
        "Seria melhor o app de O.S. tambem parecer um app de verdade no PC? "
        "E ainda funcionar no tablet/celular, com assinatura por QR, mesmo sem internet externa "
        "(so Wi-Fi local / roteador)?",
    )
    paragrafo(pdf, "Resposta acordada: NAO refazer tudo em Tkinter. Usar caminho HIBRIDO.")

    titulo(pdf, "3. Roadmap em fases (ordem recomendada)")
    item(pdf, "Fase A — Parecer app no PC (PENDENTE, prioridade alta)")
    item(pdf, "Envolver o Flask em PyWebView ou flaskwebgui: um .bat abre JANELA sem parecer navegador.")
    item(pdf, "Servidor roda em background; fechar a janela encerra o app. Mesma tela web, zero reescrita.")
    item(pdf, "Opcional depois: PyInstaller para gerar .exe (Fase D).")
    pdf.ln(2)
    item(pdf, "Fase B — Assinatura remota QR + link (JA IMPLEMENTADA na versao 2.5.0)")
    item(pdf, "Rotas: /assinar/<token>, /api/assinatura/... QR valido 4h; link de aprovacao 7 dias.")
    item(pdf, "Funciona na rede local sem internet externa.")
    pdf.ln(2)
    item(pdf, "Fase C — Tablet como app (OPCIONAL): PWA — Adicionar a tela inicial no Chrome/Safari.")
    item(pdf, "Fase D — Empacotar .exe (OPCIONAL): PyInstaller + servidor embutido.")

    titulo(pdf, "4. Rede LOCAL — como conectar PC, tablet e celular")
    paragrafo(
        pdf,
        "O servidor Flask escuta em host=0.0.0.0 porta 5000 (app.py). "
        "Nao precisa de internet da operadora — basta Wi-Fi local ou hotspot.",
    )

    titulo(pdf, "4.1 Solucao MAIS FACIL (recomendada primeiro)", 2)
    paragrafo(pdf, "Arquivo: app_ordem_servico/LEIA-ME-REDE.txt")
    item(pdf, "Win + I -> Rede e Internet -> Wi-Fi")
    item(pdf, "Clique na rede conectada (ex.: JoxSuel)")
    item(pdf, "Perfil de rede -> escolha PRIVADA (nao Publica)")
    item(pdf, "Motivo: Windows bloqueia conexoes de outros aparelhos quando a Wi-Fi esta como Rede Publica.")
    item(pdf, "Depois: iniciar_servidor.bat e no celular http://SEU_IP:5000 (ipconfig no PC)")

    titulo(pdf, "4.2 Scripts auxiliares", 2)
    item(pdf, "iniciar_servidor.bat — mata processos na porta 5000, mostra IP, inicia python app.py")
    item(pdf, "liberar_acesso_rede.bat — libera porta 5000 no Firewall (executar como Administrador)")
    item(pdf, "Versao atual do .bat: profile=any (Privada + Publica)")

    titulo(pdf, "4.3 Alternativa: Hotspot do PC", 2)
    item(pdf, "Configuracoes -> Zona sem fio movel -> LIGAR")
    item(pdf, "Celular conecta no hotspot do PC (nao na Wi-Fi do roteador)")
    item(pdf, "Endereco tipico: http://192.168.137.1:5000")

    titulo(pdf, "4.4 Checklist celular", 2)
    item(pdf, "Wi-Fi ligado (nao usar 4G/5G para acessar o PC)")
    item(pdf, "Mesma rede do PC (ou hotspot do PC)")
    item(pdf, "Servidor rodando (janela do iniciar_servidor.bat aberta)")
    item(pdf, "Abrir pelo IP da rede, NAO por localhost, para QR Code funcionar no celular")
    item(pdf, "Ctrl+F5 no navegador apos atualizar codigo")

    titulo(pdf, "5. Acesso EXTERNO (cliente fora da oficina)")
    paragrafo(
        pdf,
        "Metodo escolhido e configurado no pendrive: ngrok (gratuito), com dominio fixo "
        "e scripts .bat para abrir servidor + tunel automaticamente.",
    )
    paragrafo(pdf, "Configuracao unica (uma vez por PC): configurar_ngrok.bat")
    paragrafo(pdf, "Uso no dia a dia (4G, WhatsApp, outra rede): iniciar_acesso_externo.bat")
    paragrafo(pdf, "Uso so na oficina (mesma Wi-Fi): iniciar_servidor.bat")
    caixa(
        pdf,
        "# Exemplo do .env no pendrive (nao vai para o Git):\n"
        "DATABASE_PATH=../Crotrole_adm/oficina_nautica.db\n"
        "PDF_ORIENTACAO=horizontal\n"
        "NGROK_DOMAIN=seu-dominio.ngrok-free.dev\n"
        "OS_PUBLIC_URL=https://seu-dominio.ngrok-free.dev",
    )
    paragrafo(
        pdf,
        "O app.py do pendrive tambem detecta a URL do ngrok automaticamente "
        "(API local http://127.0.0.1:4040/api/tunnels), alem do OS_PUBLIC_URL no .env.",
    )

    titulo(pdf, "5.1 Diferenca: rede local vs externo", 2)
    item(pdf, "LOCAL: iniciar_servidor.bat + http://192.168.x.x:5000 — mesma Wi-Fi; rede Privada no Windows ajuda")
    item(pdf, "EXTERNO: iniciar_acesso_externo.bat + ngrok — QR e link em 4G/WhatsApp; manter janelas abertas")
    item(pdf, "Modo externo (ngrok) inclui o local: na mesma Wi-Fi os dois modos funcionam")

    titulo(pdf, "6. O que NAO fazer")
    item(pdf, "Nao reescrever o app inteiro em CustomTkinter — perde tablet, assinaturas e PDF ja prontos")
    item(pdf, "Nao compartilhar o .db em pasta de rede com dois PCs escrevendo ao mesmo tempo (risco SQLite)")
    item(pdf, "Cenario ideal: um PC central com banco + Flask; demais dispositivos acessam por Wi-Fi")

    titulo(pdf, "7. Status atual (o que ja esta pronto)")
    item(pdf, "Formulario completo com abas, dark mode, salvamento e edicao de O.S.")
    item(pdf, "PDF horizontal e vertical (nao alterar mais o vertical)")
    item(pdf, "Assinaturas locais + remotas (QR e link) nos 5 campos")
    item(pdf, "Pagina mobile /assinar/<token> para cliente assinar no celular")
    item(pdf, "Rede local: host 0.0.0.0, iniciar_servidor.bat, LEIA-ME-REDE.txt")
    item(pdf, "Pendrive (D:): ngrok completo — configurar_ngrok.bat, iniciar_acesso_externo.bat, deteccao automatica de URL")
    item(pdf, "Git (Desktop): versao anterior sem scripts ngrok — sincronizar ao mover pasta do pendrive")
    item(pdf, "PENDENTE: terminar todas as funcoes e configs do app (prioridade do usuario)")
    item(pdf, "PENDENTE DEPOIS: Fase A (janela desktop tipo Sistema Oficina)")
    item(pdf, "PENDENTE: integrar link de aprovacao no PDF do Sistema_Oficina (futuro)")

    titulo(pdf, "8. Ordem de trabalho acordada")
    paragrafo(
        pdf,
        "Primeiro: concluir o app e todas as funcoes/configuracoes. "
        "Depois: Fase A (parecer app no PC) e demais fases opcionais.",
    )
    item(pdf, "1. Mover pasta completa do pendrive para o local definitivo")
    item(pdf, "2. Conferir .env (DATABASE_PATH e ngrok) na nova pasta")
    item(pdf, "3. Continuar desenvolvimento do app ate funcoes e configs finalizadas")
    item(pdf, "4. So entao: Fase A — PyWebView ou flaskwebgui + abrir_app_os.bat")
    item(pdf, "5. Opcional depois: PWA no tablet; .exe com PyInstaller")

    titulo(pdf, "9. Configuracao externa — PREENCHIDO (pendrive jun/2026)")
    caixa(
        pdf,
        "Metodo de acesso externo configurado no pendrive:\n"
        "[X] OS_PUBLIC_URL no .env\n"
        "    valor: https://seu-dominio.ngrok-free.dev\n"
        "[ ] Port forwarding no roteador — NAO utilizado\n"
        "[X] ngrok (dominio fixo gratuito .ngrok-free.dev)\n"
        "    NGROK_DOMAIN=seu-dominio.ngrok-free.dev\n"
        "[ ] IP publico fixo ou DDNS — NAO utilizado\n"
        "\n"
        "Arquivos adicionados/alterados no pendrive:\n"
        "  - configurar_ngrok.bat (configuracao unica: conta + authtoken)\n"
        "  - iniciar_acesso_externo.bat (servidor Flask + tunel ngrok)\n"
        "  - _resolver_ngrok.bat (localiza executavel ngrok)\n"
        "  - gerar_manual_rede.py / gerar_manual_assinaturas.py\n"
        "  - app.py (_obter_url_tunel_local + deteccao ngrok)\n"
        "  - templates/index.html (alerta quando URL e local, nao funciona em 4G)\n"
        "  - LEIA-ME-REDE.txt (secao ngrok + rede local)\n"
        "\n"
        "Observacoes:\n"
        "  - Config unica: configurar_ngrok.bat | Dia a dia externo: iniciar_acesso_externo.bat\n"
        "  - Dia a dia local (oficina): iniciar_servidor.bat + Wi-Fi em Rede Privada\n"
        "  - Modo externo inclui local; manter janelas servidor + ngrok abertas\n"
        "  - DATABASE_PATH no pendrive: ../Crotrole_adm/oficina_nautica.db\n"
        "  - Conta ngrok fica no PC; pasta pode ser movida inteira",
    )

    titulo(pdf, "10. Como pedir ajuda na nova conversa")
    paragrafo(
        pdf,
        "Envie este PDF e diga o que precisa. Exemplos: "
        "'Continuar funcoes do app' (antes da Fase A); "
        "'Implementar Fase A do roadmap' (so depois de terminar o app); "
        "'Problema no ngrok' ou 'celular nao abre na rede local'.",
    )

    pdf.output(str(SAIDA))
    return SAIDA


if __name__ == "__main__":
    caminho = gerar()
    print(f"PDF gerado: {caminho}")
