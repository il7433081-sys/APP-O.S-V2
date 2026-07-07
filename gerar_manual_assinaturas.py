"""
Gera o manual em PDF: assinaturas remotas (QR Code e link).
Execute: python gerar_manual_assinaturas.py
Saída: manual_assinaturas_remotas.pdf (mesma pasta)
"""

from __future__ import annotations

import os
from pathlib import Path

from fpdf import FPDF

_FONT = "ArialPDF"
_APP_DIR = Path(__file__).resolve().parent
_SAIDA = _APP_DIR / "manual_assinaturas_remotas.pdf"


def _registrar_fontes(pdf: FPDF) -> str:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    regular = windir / "Fonts" / "arial.ttf"
    bold = windir / "Fonts" / "arialbd.ttf"
    if regular.is_file():
        pdf.add_font(_FONT, "", str(regular))
        pdf.add_font(_FONT, "B", str(bold if bold.is_file() else regular))
        return _FONT
    return "Helvetica"


class ManualPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self._familia = _registrar_fontes(self)
        self.set_auto_page_break(auto=True, margin=18)

    def titulo_secao(self, texto: str) -> None:
        self.ln(4)
        self.set_x(self.l_margin)
        self.set_font(self._familia, "B", 13)
        self.set_text_color(30, 64, 120)
        self.multi_cell(0, 8, texto)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def subtitulo(self, texto: str) -> None:
        self.set_x(self.l_margin)
        self.set_font(self._familia, "B", 11)
        self.multi_cell(0, 7, texto)
        self.ln(1)

    def paragrafo(self, texto: str) -> None:
        self.set_x(self.l_margin)
        self.set_font(self._familia, "", 10)
        self.multi_cell(0, 5.5, texto)
        self.ln(1)

    def item(self, texto: str) -> None:
        self.set_x(self.l_margin)
        self.set_font(self._familia, "", 10)
        self.multi_cell(0, 5.5, f"  •  {texto}")

    def destaque(self, texto: str) -> None:
        self.set_x(self.l_margin)
        self.set_font(self._familia, "B", 10)
        self.set_text_color(120, 60, 0)
        self.multi_cell(0, 5.5, texto)
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def tabela_qr_link(self) -> None:
        self.set_x(self.l_margin)
        col_w = [40, 50, 50, 50]
        headers = ["Recurso", "Validade", "Ideal para", "Cliente precisa"]
        rows = [
            ("QR Code", "4 horas", "Cliente na oficina", "Escanear com câmera"),
            ("Gerar link", "7 dias", "WhatsApp / e-mail", "Abrir o link no navegador"),
        ]
        self.set_font(self._familia, "B", 9)
        for i, h in enumerate(headers):
            self.cell(col_w[i], 8, h, border=1, align="C")
        self.ln()
        self.set_font(self._familia, "", 9)
        for row in rows:
            for i, val in enumerate(row):
                self.cell(col_w[i], 8, val, border=1, align="C")
            self.ln()
        self.ln(3)


def gerar_manual() -> Path:
    pdf = ManualPDF()
    pdf.add_page()

    pdf.set_font(pdf._familia, "B", 20)
    pdf.set_text_color(20, 50, 100)
    pdf.multi_cell(0, 10, "Manual de Assinaturas Remotas\nOrdem de Serviço Digital")
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._familia, "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 6, "QR Code, link de assinatura e recebimento automático na O.S. salva.")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    pdf.titulo_secao("1. O que são assinaturas remotas?")
    pdf.paragrafo(
        "Permite que o cliente (ou outra pessoa) assine no celular, sem usar o mouse "
        "no computador da oficina. Cada campo de assinatura do formulário tem dois botões: "
        "QR Code e Gerar link."
    )
    pdf.item("Responsável — Alegações do cliente")
    pdf.item("Analista técnico — Diagnóstico")
    pdf.item("Cliente — Recepção do veículo")
    pdf.item("Cliente — Entrega do veículo")
    pdf.item("Cliente — Aprovação do orçamento")
    pdf.ln(2)
    pdf.paragrafo(
        "O cliente abre a página no celular, desenha a assinatura com o dedo e envia. "
        "A assinatura volta para o sistema da oficina automaticamente."
    )

    pdf.titulo_secao("2. QR Code x Link")
    pdf.tabela_qr_link()
    pdf.paragrafo(
        "Ambos abrem a mesma página de assinatura. A diferença é o tempo de validade "
        "e a forma de enviar ao cliente."
    )

    pdf.titulo_secao("3. Antes de gerar o QR ou o link")
    pdf.destaque("IMPORTANTE: salve a O.S. antes de gerar o QR ou o link.")
    pdf.paragrafo(
        "Use o botão Salvar O.S. (ou Atualizar O.S.) para gravar no banco. "
        "Assim a assinatura fica vinculada ao número correto da Ordem de Serviço."
    )
    pdf.item("Sem salvar: a assinatura pode não ir para a O.S. certa")
    pdf.item("Com O.S. salva: a assinatura é gravada automaticamente nela")
    pdf.ln(2)
    pdf.subtitulo("Rede do cliente")
    pdf.item("Mesma Wi-Fi da oficina: use iniciar_servidor.bat")
    pdf.item("4G, outra Wi-Fi ou WhatsApp: use iniciar_acesso_externo.bat (ngrok)")
    pdf.item("Consulte também: manual_acesso_rede.pdf")

    pdf.titulo_secao("4. Passo a passo — fluxo recomendado")
    pdf.item("Preencha os dados da O.S. no formulário")
    pdf.item("Clique em Salvar O.S. e anote o número gerado")
    pdf.item("Na aba Diagnóstico e Fechamento, localize o campo de assinatura desejado")
    pdf.item("Clique em QR Code (cliente presente) ou Gerar link (enviar por WhatsApp)")
    pdf.item("Confira o endereço exibido — para 4G deve começar com https://")
    pdf.item("Envie o QR ou o link ao cliente")
    pdf.item("Pode fechar a janela do QR e continuar trabalhando")
    pdf.item("Quando o cliente assinar, aparece um aviso no topo da tela")
    pdf.item("Abra a O.S. na Lista de O.S. para conferir a assinatura no PDF/formulário")

    pdf.titulo_secao("5. Fechar o QR e continuar trabalhando")
    pdf.paragrafo(
        "Você NÃO precisa ficar com a janela do QR aberta esperando. "
        "Pode fechar o modal, trocar de aba, salvar outra O.S. ou iniciar uma nova."
    )
    pdf.item("O sistema continua aguardando a assinatura em segundo plano")
    pdf.item("Os códigos no terminal (se aparecerem) são normais — verificação automática")
    pdf.item("Ao receber, um alerta verde aparece no topo da página")
    pdf.ln(2)
    pdf.subtitulo("Se estiver editando OUTRA O.S. quando o cliente assinar")
    pdf.paragrafo(
        "A assinatura é gravada na O.S. correta (a que estava salva quando você gerou o QR). "
        "O sistema avisa: Assinatura gravada na O.S. nº X — abra na Lista para conferir."
    )

    pdf.titulo_secao("6. O que o cliente faz no celular")
    pdf.item("Escaneia o QR Code ou abre o link recebido")
    pdf.item("Se usar ngrok grátis, pode aparecer Visit Site — toque para continuar")
    pdf.item("Lê o título do tipo de assinatura (ex.: Cliente — Recepção)")
    pdf.item("Desenha a assinatura na área indicada")
    pdf.item("Toca em Enviar assinatura")
    pdf.item("Vê mensagem de confirmação — pode fechar o navegador")

    pdf.titulo_secao("7. Botões e opções do modal")
    pdf.item("QR Code — exibe código para escanear (válido 4 horas)")
    pdf.item("Gerar link — copia URL para WhatsApp (válido 7 dias)")
    pdf.item("Copiar link — ícone de clipboard ao lado do campo de link")
    pdf.item("Cancelar espera desta assinatura — só use se NÃO quiser mais receber")
    pdf.ln(2)
    pdf.destaque("Fechar o modal (X) NÃO cancela a espera — a assinatura ainda pode chegar.")
    pdf.paragrafo(
        "Use Cancelar espera apenas quando desistir daquela assinatura específica."
    )

    pdf.titulo_secao("8. Onde a assinatura fica gravada")
    pdf.paragrafo(
        "Quando o cliente envia pelo celular, o sistema grava em dois lugares:"
    )
    pdf.item("Na tabela de assinaturas remotas (registro da sessão)")
    pdf.item("Na O.S. salva (dados_json + campos de assinatura no banco)")
    pdf.ln(2)
    pdf.paragrafo(
        "Ao abrir a O.S. na Lista de O.S., a assinatura aparece no formulário "
        "e entra no PDF quando você gerar/visualizar."
    )

    pdf.titulo_secao("9. Problemas comuns")
    pdf.subtitulo("QR não abre no celular (4G)")
    pdf.item("Use iniciar_acesso_externo.bat — não o iniciar_servidor.bat")
    pdf.item("Mantenha as duas janelas abertas: servidor + ngrok")
    pdf.item("URL no modal deve ser https://... (não 192.168.x.x)")
    pdf.ln(2)
    pdf.subtitulo("Erro endpoint offline (ngrok)")
    pdf.item("A janela do ngrok fechou — abra iniciar_acesso_externo.bat de novo")
    pdf.item("Atualize o ngrok se pedir versão antiga")
    pdf.ln(2)
    pdf.subtitulo("Assinatura não apareceu")
    pdf.item("A O.S. foi salva antes de gerar o QR?")
    pdf.item("O link expirou? (4 h QR / 7 dias link) — gere outro")
    pdf.item("Abra a O.S. correta na Lista de O.S.")
    pdf.ln(2)
    pdf.subtitulo("Aviso amarelo no modal")
    pdf.item("Indica que o endereço é da rede local — não funciona em 4G")
    pdf.item("Solução: iniciar_acesso_externo.bat com ngrok ativo")

    pdf.titulo_secao("10. Resumo rápido")
    pdf.item("Salvar O.S. → Gerar QR ou link → Cliente assina no celular")
    pdf.item("Pode fechar o QR e trabalhar em outra coisa")
    pdf.item("Assinatura vai para a O.S. salva automaticamente")
    pdf.item("4G/WhatsApp: iniciar_acesso_externo.bat")
    pdf.item("Wi-Fi da oficina: iniciar_servidor.bat")

    pdf.ln(6)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._familia, "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        0,
        5,
        f"Gerado automaticamente — {Path(__file__).name}\n"
        "Ordem de Serviço Digital — Manual de assinaturas remotas",
        align="C",
    )

    pdf.output(str(_SAIDA))
    return _SAIDA


if __name__ == "__main__":
    caminho = gerar_manual()
    print(f"Manual gerado: {caminho}")
