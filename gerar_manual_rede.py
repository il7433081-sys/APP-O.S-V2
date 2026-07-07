"""
Gera o manual em PDF: acesso na rede local e acesso externo (ngrok).
Execute: python gerar_manual_rede.py
Saída: manual_acesso_rede.pdf (mesma pasta)
"""

from __future__ import annotations

import os
from pathlib import Path

from fpdf import FPDF

_FONT = "ArialPDF"
_APP_DIR = Path(__file__).resolve().parent
_SAIDA = _APP_DIR / "manual_acesso_rede.pdf"


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

  def link_item(self, rotulo: str, url: str) -> None:
    self.set_x(self.l_margin)
    self.set_font(self._familia, "", 10)
    self.set_text_color(0, 82, 155)
    self.write(5.5, f"  •  {rotulo}: ")
    self.set_text_color(0, 0, 200)
    self.write(5.5, url, link=url)
    self.set_text_color(0, 0, 0)
    self.ln(7)

  def tabela_modos(self) -> None:
    self.set_x(self.l_margin)
    col_w = [52, 42, 42, 44]
    headers = ["Modo de início", "Rede local", "Mesma Wi-Fi", "4G / outra rede"]
    rows = [
      ("iniciar_servidor.bat", "Sim", "Sim", "Não"),
      ("iniciar_acesso_externo.bat", "Sim", "Sim", "Sim"),
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
  pdf.multi_cell(0, 10, "Manual de Acesso\nOrdem de Serviço Digital")
  pdf.ln(2)
  pdf.set_x(pdf.l_margin)
  pdf.set_font(pdf._familia, "", 11)
  pdf.set_text_color(80, 80, 80)
  pdf.multi_cell(0, 6, "Como usar na oficina, no celular e com clientes fora da rede.")
  pdf.set_text_color(0, 0, 0)
  pdf.ln(4)

  pdf.titulo_secao("1. Visão geral")
  pdf.paragrafo(
    "O sistema roda no PC da oficina. O celular ou o cliente acessam pelo navegador. "
    "Existem dois jeitos de iniciar o servidor — você não precisa alternar entre eles "
    "no dia a dia se usar sempre o modo externo quando precisar de QR Code ou link fora da rede."
  )
  pdf.tabela_modos()
  pdf.paragrafo(
    "Importante: o modo externo (ngrok) inclui tudo do modo interno. "
    "Na mesma Wi-Fi da oficina, ambos continuam funcionando normalmente."
  )

  pdf.titulo_secao("2. Acesso na mesma rede (oficina)")
  pdf.subtitulo("Como iniciar")
  pdf.item("Execute: iniciar_servidor.bat (pasta app_ordem_servico)")
  pdf.item("No PC: http://127.0.0.1:5000")
  pdf.item("No celular/tablet (mesma Wi-Fi): http://192.168.x.x:5000")
  pdf.item("O IP aparece na janela do servidor ou no cmd: ipconfig")
  pdf.ln(2)
  pdf.subtitulo("Checklist — celular na oficina")
  pdf.item("Wi-Fi ligado (não usar 4G/5G para acesso local)")
  pdf.item("Mesma rede do PC (ou hotspot do PC)")
  pdf.item("Servidor rodando (janela do .bat aberta)")
  pdf.item("Endereço com http:// no início")
  pdf.item("Após atualizar o sistema: Ctrl+F5 no navegador")

  pdf.titulo_secao("3. Acesso externo — cliente em 4G ou outra rede")
  pdf.paragrafo(
    "Use quando o cliente não estiver na Wi-Fi da oficina. "
    "O QR Code e o link de assinatura passam a funcionar por WhatsApp, 4G/5G ou qualquer rede. "
    "Serviço gratuito: ngrok."
  )
  pdf.subtitulo("Configuração única (uma vez por PC)")
  pdf.item("Execute: configurar_ngrok.bat")
  pdf.link_item("Criar conta gratuita", "https://dashboard.ngrok.com/signup")
  pdf.link_item("Copiar Authtoken", "https://dashboard.ngrok.com/get-started/your-authtoken")
  pdf.item("Cole o token quando o script pedir")
  pdf.ln(2)
  pdf.subtitulo("Uso no dia a dia")
  pdf.item("Execute: iniciar_acesso_externo.bat")
  pdf.item("Mantenha as duas janelas abertas: servidor Flask + ngrok")
  pdf.item("No sistema, clique em QR Code ou Gerar link")
  pdf.item("Envie ao cliente — o app detecta a URL do ngrok automaticamente")
  pdf.item("Não é necessário editar o arquivo .env")
  pdf.ln(2)
  pdf.subtitulo("Validade das assinaturas remotas")
  pdf.item("QR Code: válido por 4 horas")
  pdf.item("Link: válido por 7 dias (ideal para WhatsApp)")
  pdf.item("PC da oficina deve permanecer ligado até o cliente assinar")

  pdf.titulo_secao("4. QR Code e link de assinatura")
  pdf.paragrafo(
    "No formulário da Ordem de Serviço, cada campo de assinatura tem os botões "
    "QR Code e Gerar link. O cliente abre a página, desenha a assinatura no celular "
    "e ela volta automaticamente para o sistema na oficina."
  )
  pdf.item("Responsável — Alegações do cliente")
  pdf.item("Analista técnico — Diagnóstico")
  pdf.item("Cliente — Recepção, entrega e aprovação do orçamento")
  pdf.ln(2)
  pdf.paragrafo(
    "Sem ngrok: só funciona na mesma rede da oficina. "
    "Com ngrok (iniciar_acesso_externo.bat): funciona de qualquer lugar."
  )

  pdf.titulo_secao("5. Problemas comuns na rede local")
  pdf.subtitulo("Solução 1 — Rede privada (recomendado)")
  pdf.item("Windows + I → Rede e Internet → Wi-Fi")
  pdf.item("Clique na rede conectada → Perfil de rede → Privada")
  pdf.item("Execute liberar_acesso_rede.bat como Administrador (uma vez)")
  pdf.item("Inicie iniciar_servidor.bat")
  pdf.ln(2)
  pdf.subtitulo("Solução 2 — Hotspot do PC")
  pdf.item("Configurações → Rede → Zona sem fio móvel → Ligar")
  pdf.item("Celular conecta no hotspot do PC (não no roteador)")
  pdf.item("No PC: ipconfig → IPv4 do adaptador Conexão Local*")
  pdf.item("Geralmente: http://192.168.137.1:5000")
  pdf.ln(2)
  pdf.subtitulo("Solução 3 — Firewall")
  pdf.item("Clique direito em liberar_acesso_rede.bat → Executar como administrador")

  pdf.titulo_secao("6. Git e dados do sistema")
  pdf.paragrafo(
    "O comando git pull atualiza apenas o código do programa, não os dados da oficina. "
    "O banco de dados (oficina_nautica.db) fica em cada PC separadamente e não vai para o GitHub. "
    "Cada computador pode ter cadastros diferentes — isso é normal."
  )
  pdf.paragrafo(
    "Após git pull: reinicie o servidor para carregar mudanças de código. "
    "Os dados locais (clientes, OS, peças) permanecem como estão neste PC."
  )

  pdf.titulo_secao("7. Arquivos úteis (pasta app_ordem_servico)")
  pdf.item("iniciar_servidor.bat — rede local (oficina)")
  pdf.item("iniciar_acesso_externo.bat — rede local + internet (ngrok)")
  pdf.item("configurar_ngrok.bat — configuração única do ngrok")
  pdf.item("liberar_acesso_rede.bat — libera firewall (admin)")
  pdf.item("LEIA-ME-REDE.txt — referência rápida em texto")

  pdf.ln(6)
  pdf.set_x(pdf.l_margin)
  pdf.set_font(pdf._familia, "", 9)
  pdf.set_text_color(100, 100, 100)
  pdf.multi_cell(
    0,
    5,
    f"Gerado automaticamente — {Path(__file__).name}\n"
    "Ordem de Serviço Digital — Manual de acesso e rede",
    align="C",
  )

  pdf.output(str(_SAIDA))
  return _SAIDA


if __name__ == "__main__":
  caminho = gerar_manual()
  print(f"Manual gerado: {caminho}")
