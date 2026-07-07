"""
Gera PDF de referência: login (passo 1), compartilhamento de dados e como
deixar o app web independente do Sistema Oficina no futuro.

Execute: python gerar_manual_auth_independencia.py
Saída: MANUAL_AUTH_E_INDEPENDENCIA.pdf (mesma pasta)
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fpdf import FPDF

_FONT = "ArialAuth"
_APP_DIR = Path(__file__).resolve().parent
_SAIDA = _APP_DIR / "MANUAL_AUTH_E_INDEPENDENCIA.pdf"
_DIAGRAMA_PNG = _APP_DIR / "diagrama_auth_independencia.png"


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
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(getattr(self, "_fonte", "Helvetica"), "", 8)
        self.set_text_color(100, 100, 100)
        self.cell(
            0,
            8,
            _txt(
                f"Ordem de Servico Digital - auth e independencia - "
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


def _gerar_diagrama_png() -> Path | None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    largura, altura = 900, 520
    img = Image.new("RGB", (largura, altura), "#f8fafc")
    draw = ImageDraw.Draw(img)

    try:
        font_titulo = ImageFont.truetype("arial.ttf", 22)
        font_caixa = ImageFont.truetype("arial.ttf", 18)
        font_peq = ImageFont.truetype("arial.ttf", 15)
    except OSError:
        font_titulo = ImageFont.load_default()
        font_caixa = font_titulo
        font_peq = font_titulo

    azul = "#1f6aa5"
    cinza = "#64748b"
    verde = "#15803d"
    laranja = "#c2410c"

    def caixa(x1, y1, x2, y2, texto, cor_borda, cor_fill="#ffffff"):
        draw.rounded_rectangle([x1, y1, x2, y2], radius=12, fill=cor_fill, outline=cor_borda, width=3)
        bbox = draw.textbbox((0, 0), texto, font=font_caixa)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = x1 + (x2 - x1 - tw) / 2
        ty = y1 + (y2 - y1 - th) / 2
        draw.text((tx, ty), texto, fill="#1e293b", font=font_caixa)

    def seta(x1, y1, x2, y2, cor=azul):
        draw.line([x1, y1, x2, y2], fill=cor, width=3)
        if x2 > x1:
            draw.polygon([(x2, y2), (x2 - 12, y2 - 7), (x2 - 12, y2 + 7)], fill=cor)
        elif x2 < x1:
            draw.polygon([(x2, y2), (x2 + 12, y2 - 7), (x2 + 12, y2 + 7)], fill=cor)
        elif y2 > y1:
            draw.polygon([(x2, y2), (x2 - 7, y2 - 12), (x2 + 7, y2 - 12)], fill=cor)

    draw.text((30, 18), "Como os programas se conectam hoje e no futuro", fill=azul, font=font_titulo)

    draw.text((40, 58), "HOJE - interligados (mesmo banco)", fill=cinza, font=font_peq)
    caixa(60, 85, 300, 145, "Sistema Oficina", azul, "#e8f4fc")
    caixa(60, 175, 300, 235, "app.py (Flask)", azul, "#e8f4fc")
    caixa(500, 115, 820, 205, "oficina_nautica.db", "#334155", "#f1f5f9")
    seta(300, 115, 500, 155)
    seta(300, 205, 500, 175)

    draw.text((40, 265), "FUTURO - app sozinho (sem Oficina)", fill=laranja, font=font_peq)
    caixa(60, 292, 340, 352, "app.py (Flask)", laranja, "#fff7ed")
    caixa(500, 292, 820, 352, "banco_proprio.db", verde, "#f0fdf4")
    seta(340, 322, 500, 322, laranja)

    draw.text(
        (40, 390),
        "Nao ha import de codigo entre os apps. So o caminho DATABASE_PATH no .env define o banco.",
        fill="#475569",
        font=font_peq,
    )

    img.save(_DIAGRAMA_PNG)
    return _DIAGRAMA_PNG


def _diagrama_fallback_pdf(pdf: DocPDF) -> None:
    if pdf.get_y() > 200:
        pdf.add_page()
    y0 = pdf.get_y()
    pdf.set_font(pdf._fonte, "B", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, _txt("Figura - Arquitetura (resumo)"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    def bloco(x, y, w, h, rotulo, cor_rgb):
        pdf.set_fill_color(*cor_rgb)
        pdf.set_draw_color(31, 106, 165)
        pdf.rect(x, y, w, h, style="DF")
        pdf.set_xy(x, y + h / 2 - 3)
        pdf.set_font(pdf._fonte, "B", 9)
        pdf.set_text_color(20, 20, 20)
        pdf.cell(w, 6, _txt(rotulo), align="C")

    x0 = pdf.l_margin
    bloco(x0, y0 + 8, 50, 14, "Oficina", (232, 244, 252))
    bloco(x0, y0 + 28, 50, 14, "Flask", (232, 244, 252))
    bloco(x0 + 70, y0 + 18, 55, 22, "oficina_nautica.db", (241, 245, 249))
    pdf.set_draw_color(31, 106, 165)
    pdf.line(x0 + 50, y0 + 15, x0 + 70, y0 + 24)
    pdf.line(x0 + 50, y0 + 35, x0 + 70, y0 + 34)

    bloco(x0, y0 + 58, 50, 14, "Flask", (255, 247, 237))
    bloco(x0 + 70, y0 + 58, 55, 14, "banco_proprio.db", (240, 253, 244))
    pdf.line(x0 + 50, y0 + 65, x0 + 70, y0 + 65)

    pdf.set_xy(pdf.l_margin, y0 + 78)
    pdf.ln(4)


def _inserir_diagrama(pdf: DocPDF) -> None:
    png = _gerar_diagrama_png()
    if png and png.is_file():
        if pdf.get_y() > 175:
            pdf.add_page()
        y = pdf.get_y()
        pdf.set_font(pdf._fonte, "B", 10)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 6, _txt("Figura 1 - Arquitetura: hoje (interligados) e futuro (app sozinho)"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        largura_img = _largura(pdf)
        pdf.image(str(png), x=pdf.l_margin, y=pdf.get_y(), w=largura_img)
        pdf.ln(largura_img * 0.52 + 4)
    else:
        _diagrama_fallback_pdf(pdf)


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
    pdf.multi_cell(
        _largura(pdf),
        7,
        _txt("Login, configuracoes compartilhadas e como rodar o app sozinho"),
    )
    pdf.ln(3)

    paragrafo(
        pdf,
        "DOCUMENTO DE REFERENCIA - Consulte este PDF para entender o Passo 1 (login) "
        "ja implementado, o que sera feito no Passo 2 (usuarios na aba Configuracao) "
        "e o procedimento para separar o app web do Sistema Oficina no futuro.",
    )

    titulo(pdf, "1. Principio: conversam pelo banco, nao pelo codigo")
    paragrafo(
        pdf,
        "O app web (app.py) NAO importa arquivos do Sistema Oficina. Os dois programas "
        "sao independentes no codigo. Quando usam o mesmo arquivo SQLite "
        "(oficina_nautica.db via DATABASE_PATH no .env), compartilham dados: "
        "clientes, ordens de servico, usuarios, etc.",
    )
    paragrafo(
        pdf,
        "Para o app funcionar sozinho no futuro, basta apontar o .env para outro arquivo "
        ".db e copiar ou recriar o que for necessario. Nao e preciso alterar o codigo do Flask.",
    )
    _inserir_diagrama(pdf)

    titulo(pdf, "2. O que cada tabela / config controla")
    item(pdf, "usuarios - logins (admin/operador, permissoes). Compartilhada se mesmo .db")
    item(pdf, "app_os_config - configuracoes SO do app web (exibir_tipo_os, exigir_login)")
    item(pdf, "empresa_config - dados da empresa no PDF (nome, endereco). Opcional para o Flask")
    item(pdf, "ordens_servico, clientes, assinaturas_remotas - dados operacionais da O.S.")
    caixa(
        pdf,
        "Regra importante:\n"
        "- exigir_login do APP WEB fica em app_os_config (nao depende da Oficina depois da 1a vez).\n"
        "- Na primeira execucao com banco compartilhado, o app COPIA exigir_login da oficina "
        "se ainda nao tiver valor proprio.\n"
        "- Depois disso, cada programa pode ter login obrigatorio ou nao, de forma independente.",
    )

    titulo(pdf, "3. Passo 1 - Login (JA IMPLEMENTADO)")
    paragrafo(pdf, "Versao do app: 2.5.0+. Arquivos alterados: app.py, templates/login.html, templates/index.html")

    titulo(pdf, "3.1 Como funciona", 2)
    item(pdf, "Tela /login - usuario e senha; mostra o nome ao digitar o login")
    item(pdf, "POST /api/login - autentica e abre sessao (cookie seguro)")
    item(pdf, "POST /api/logout - encerra sessao")
    item(pdf, "GET /api/auth/status - informa se exigir_login esta ativo e quem esta logado")
    item(pdf, "GET /api/login/preview?usuario=... - preview do nome (como na Oficina)")
    item(pdf, "Menu lateral: Trocar usuario e Sair (ativos quando exigir_login = ligado)")

    titulo(pdf, "3.2 Quando pede login", 2)
    item(pdf, "Se exigir_login = 1 em app_os_config: todas as rotas exigem sessao")
    item(pdf, "Se exigir_login = 0: app abre direto (acesso livre); menu de usuario fica desabilitado")
    item(pdf, "Rotas PUBLICAS (sem login): /login, /assinar/<token>, /api/assinatura/..., /api/auth/...")
    paragrafo(
        pdf,
        "Cliente no celular que assina pelo QR NAO precisa de login - a rota /assinar/ continua aberta.",
    )

    titulo(pdf, "3.3 Usuario padrao (banco novo ou vazio)", 2)
    caixa(pdf, "Usuario: admin\nSenha: 123\nPerfil: administrador (todas as permissoes)")
    paragrafo(
        pdf,
        "Se a tabela usuarios ja existir (banco compartilhado com a Oficina), "
        "valem os mesmos logins cadastrados la. Nao ha senha separada para o app web.",
    )

    titulo(pdf, "3.4 Como testar agora", 2)
    item(pdf, "1. Inicie: iniciar_servidor.bat")
    item(pdf, "2. Abra http://127.0.0.1:5000/api/auth/status - veja exigir_login true/false")
    item(pdf, "3. Se exigir_login = false, o app abre sem senha (estado atual se a Oficina desligou login)")
    item(pdf, "4. Para forcar login: no Passo 2 havera switch na Config; ou edite app_os_config no SQLite")
    item(pdf, "5. Acesse /login e entre com admin / 123 (ou usuario cadastrado na Oficina)")

    titulo(pdf, "4. Passo 2 - Proximo (usuarios na Configuracao)")
    paragrafo(pdf, "Ainda NAO implementado. Sera adicionado na aba Configuracao do app web:")
    item(pdf, "Switch Exigir login (grava em app_os_config, independente da Oficina)")
    item(pdf, "Listar, criar, editar e desativar usuarios (tabela usuarios)")
    item(pdf, "Apenas admin ou quem tem permissao_config pode gerenciar")
    item(pdf, "Alteracoes em usuarios refletem nos dois apps ENQUANTO usarem o mesmo .db")

    titulo(pdf, "5. Passo a passo: app funcionando SOZINHO (sem Sistema Oficina)")
    paragrafo(
        pdf,
        "Use este roteiro quando voce sair da empresa, levar o Sistema Oficina "
        "e deixar (ou levar tambem) apenas o app web. Nao e necessario desinstalar nada - "
        "apenas separar pastas e banco.",
    )

    titulo(pdf, "5.1 Antes de sair - preparacao (recomendado)", 2)
    item(pdf, "1. Copie a pasta completa app_ordem_servico/ para o destino final")
    item(pdf, "2. Garanta que Python e dependencias estao instalados (pip install -r requirements.txt)")
    item(pdf, "3. No Passo 2, cadastre todos os usuarios necessarios pelo app web")
    item(pdf, "4. Na Config, ligue Exigir login e teste /login")
    item(pdf, "5. Anote dados da empresa para o PDF (se nao for copiar empresa_config)")

    titulo(pdf, "5.2 Separar o banco de dados", 2)
    item(pdf, "1. Feche o Sistema Oficina e pare o servidor Flask (feche a janela do .bat)")
    item(pdf, "2. Copie oficina_nautica.db para dentro de app_ordem_servico/ com novo nome, ex.:")
    caixa(pdf, "app_ordem_servico/dados/app_os.db")
    item(pdf, "3. Edite o arquivo .env na pasta app_ordem_servico:")
    caixa(
        pdf,
        "DATABASE_PATH=./dados/app_os.db\n"
        "PDF_ORIENTACAO=horizontal\n"
        "# ngrok (se usar acesso externo):\n"
        "NGROK_DOMAIN=seu-dominio.ngrok-free.dev\n"
        "OS_PUBLIC_URL=https://seu-dominio.ngrok-free.dev",
    )
    item(pdf, "4. O app NAO precisa da pasta Crotrole_adm/ nem do Sistema_Oficina/")
    item(pdf, "5. Inicie iniciar_servidor.bat e teste salvar O.S., PDF e login")

    titulo(pdf, "5.3 O que vai junto no .db copiado", 2)
    item(pdf, "usuarios - logins continuam iguais")
    item(pdf, "app_os_config - exigir_login, exibir_tipo_os")
    item(pdf, "ordens_servico, clientes, motores, assinaturas_remotas")
    item(pdf, "empresa_config - se existir no arquivo copiado, PDF usa nome/endereco da empresa")

    titulo(pdf, "5.4 Banco novo do zero (sem copiar o .db antigo)", 2)
    item(pdf, "1. Crie pasta dados/ e defina DATABASE_PATH=./dados/app_os.db no .env")
    item(pdf, "2. Ao iniciar o app, ele cria tabelas automaticamente")
    item(pdf, "3. Usuario inicial: admin / 123 (troque no Passo 2)")
    item(pdf, "4. PDF da empresa: sem empresa_config, usa texto padrao 'Oficina Nautica'")
    item(pdf, "5. Clientes e O.S. comecam vazios - importe depois se precisar")

    titulo(pdf, "5.5 Checklist final (app sozinho)", 2)
    item(pdf, "[ ] .env aponta para .db proprio (nao para pasta da Oficina)")
    item(pdf, "[ ] iniciar_servidor.bat abre sem erro")
    item(pdf, "[ ] Login funciona (se exigir_login ligado)")
    item(pdf, "[ ] Salvar e abrir O.S. na Lista")
    item(pdf, "[ ] PDF gera com orientacao correta")
    item(pdf, "[ ] QR de assinatura abre no celular (/assinar/ sem login)")
    item(pdf, "[ ] Opcional: iniciar_acesso_externo.bat + ngrok configurado")

    titulo(pdf, "6. Arquivos uteis")
    item(pdf, "app.py - servidor e autenticacao")
    item(pdf, "templates/login.html - tela de entrada")
    item(pdf, "templates/index.html - app principal + menu usuario")
    item(pdf, ".env - DATABASE_PATH e URLs (nao vai para o Git)")
    item(pdf, ".flask_secret - chave de sessao (gerada automaticamente; nao compartilhar)")
    item(pdf, "gerar_manual_auth_independencia.py - este PDF")
    if _DIAGRAMA_PNG.name:
        item(pdf, f"{_DIAGRAMA_PNG.name} - diagrama de arquitetura (gerado junto com o PDF)")

    titulo(pdf, "7. Como pedir ajuda na nova conversa")
    paragrafo(
        pdf,
        "Envie este PDF e diga o que precisa. Exemplos: "
        "'Implementar Passo 2 (usuarios na Config)'; "
        "'Separar o app do Sistema Oficina'; "
        "'Login nao esta pedindo senha'.",
    )

    pdf.output(str(_SAIDA))
    return _SAIDA


if __name__ == "__main__":
    caminho = gerar()
    print(f"PDF gerado: {caminho}")
    if _DIAGRAMA_PNG.is_file():
        print(f"Diagrama PNG: {_DIAGRAMA_PNG}")
