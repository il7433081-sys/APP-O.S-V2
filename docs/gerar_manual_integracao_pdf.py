#!/usr/bin/env python3
"""Gera PDF do manual de integração O.S. Digital × Sistema Oficina."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

OUT_DIR = Path(__file__).resolve().parent
OUT_PDF = OUT_DIR / "MANUAL_INTEGRACAO_OS_DIGITAL_OFICINA.pdf"

# Paleta
AZUL_ESCURO = colors.HexColor("#1e3a5f")
AZUL_MEDIO = colors.HexColor("#2563eb")
AZUL_CLARO = colors.HexColor("#dbeafe")
VERDE = colors.HexColor("#166534")
VERDE_CLARO = colors.HexColor("#bbf7d0")
LARANJA = colors.HexColor("#7c2d12")
LARANJA_CLARO = colors.HexColor("#fed7aa")
VERMELHO = colors.HexColor("#7f1d1d")
VERMELHO_CLARO = colors.HexColor("#fecaca")
CINZA = colors.HexColor("#374151")
CINZA_CLARO = colors.HexColor("#f3f4f6")
CINZA_TEXTO = colors.HexColor("#4b5563")
ROXO = colors.HexColor("#5b21b6")
ROXO_CLARO = colors.HexColor("#ede9fe")


def _header_footer(c: canvas.Canvas, doc) -> None:
    c.saveState()
    w, h = A4
    if c.getPageNumber() > 1:
        c.setFillColor(AZUL_ESCURO)
        c.rect(0, h - 18 * mm, w, 18 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(20 * mm, h - 12 * mm, "Manual — O.S. Digital × Sistema Oficina")
        c.setFont("Helvetica", 8)
        c.drawRightString(w - 20 * mm, h - 12 * mm, f"Página {c.getPageNumber()}")
    c.setStrokeColor(colors.HexColor("#e5e7eb"))
    c.setLineWidth(0.5)
    c.line(20 * mm, 15 * mm, w - 20 * mm, 15 * mm)
    c.setFillColor(CINZA_TEXTO)
    c.setFont("Helvetica", 7)
    c.drawCentredString(w / 2, 10 * mm, "Integração Requisições · Oficina · Telespectador · sáb 13 a seg")
    c.restoreState()


def _cover_page(c: canvas.Canvas, doc) -> None:
    w, h = A4
    c.saveState()
    c.setFillColor(AZUL_ESCURO)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setFillColor(AZUL_MEDIO)
    c.rect(0, h * 0.55, w, h * 0.45, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(w / 2, h - 55 * mm, "Manual de Integração")
    c.setFont("Helvetica", 16)
    c.drawCentredString(w / 2, h - 68 * mm, "O.S. Digital  ×  Sistema Oficina")

    c.setFillColor(AZUL_CLARO)
    c.roundRect(25 * mm, h - 105 * mm, w - 50 * mm, 22 * mm, 4 * mm, fill=1, stroke=0)
    c.setFillColor(AZUL_ESCURO)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(w / 2, h - 96 * mm, "Requisições · Rascunho · Orçamento · Ao vivo")

    topics = [
        "Fluxo mecânico → responsável → oficina",
        "Rascunho vs envio (sem avisar a oficina antes da hora)",
        "Vínculo requisição ↔ orçamento na oficina",
        "Modo Telespectador e aba Ao vivo",
        "Devolver O.S. ao mecânico e copiar retorno",
    ]
    y = h - 125 * mm
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 10)
    for t in topics:
        c.circle(32 * mm, y + 2.5 * mm, 2 * mm, fill=1, stroke=0)
        c.drawString(38 * mm, y, f"•  {t}")
        y -= 9 * mm

    c.setFillColor(colors.HexColor("#93c5fd"))
    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, 35 * mm, f"Período documentado: sábado 13 até {date.today().strftime('%d/%m/%Y')}")
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(w / 2, 25 * mm, "App web O.S. Digital + Sistema Oficina (desktop)")
    c.restoreState()


def _badge_cell(texto: str, bg, fg=colors.white, bold=True) -> Paragraph:
    style = ParagraphStyle(
        "badge",
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=8,
        textColor=fg,
        alignment=TA_CENTER,
        leading=10,
    )
    return Paragraph(f'<font color="{fg.hexval()}">{texto}</font>', style)


def _flow_diagram_table() -> Table:
    steps = [
        ("1", "Mecânico monta requisição", "App web — aba Requisição", AZUL_MEDIO),
        ("2", "Salvar (rascunho)", "Grava local — sem aviso", CINZA),
        ("3", "Enviar requisição", "Notifica responsável", LARANJA),
        ("4", "Responsável cota preços", "Salvar rascunho (oficina não vê)", ROXO),
        ("5", "Enviar resposta", "Publica itens + notifica todos", VERDE),
        ("6", "Oficina importa", "Gerar ou Atualizar orçamento", AZUL_ESCURO),
    ]
    data = [[
        Paragraph("<b>Etapa</b>", ParagraphStyle("h", fontSize=8, textColor=colors.white)),
        Paragraph("<b>Ação</b>", ParagraphStyle("h", fontSize=8, textColor=colors.white)),
        Paragraph("<b>Resultado</b>", ParagraphStyle("h", fontSize=8, textColor=colors.white)),
    ]]
    for num, acao, resultado, cor in steps:
        data.append([
            Paragraph(f'<b><font color="white">{num}</font></b>',
                      ParagraphStyle("n", fontSize=10, textColor=colors.white, alignment=TA_CENTER)),
            Paragraph(acao, ParagraphStyle("a", fontSize=9, textColor=colors.white)),
            Paragraph(resultado, ParagraphStyle("r", fontSize=8, textColor=colors.HexColor("#e0e7ff"))),
        ])
    t = Table(data, colWidths=[1.2 * cm, 5.5 * cm, 9.5 * cm])
    row_colors = [AZUL_ESCURO] + [cor for _, _, _, cor in steps]
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_ESCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i, cor in enumerate(row_colors[1:], start=1):
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), cor))
    t.setStyle(TableStyle(style_cmds))
    return t


def _status_table_app() -> Table:
    rows = [
        ("Laranja", "aguardando_responsavel", "Mecânico enviou — falta preço", LARANJA, LARANJA_CLARO),
        ("Vermelho", "alterada_mecanico", "Mecânico alterou após envio", VERMELHO, VERMELHO_CLARO),
        ("Verde", "respondida / em dia", "Respondida ou sem pendência", VERDE, VERDE_CLARO),
        ("Amarelo", "item novo", "Item novo a cotar", colors.HexColor("#854d0e"), colors.HexColor("#fef08a")),
        ("Cinza", "excluir_pendente", "Exclusão solicitada", CINZA, colors.HexColor("#d1d5db")),
        ("Azul M.O.", "tipo mo", "Mão de obra — só responsável", AZUL_MEDIO, AZUL_CLARO),
    ]
    data = [["Cor", "Status", "Significado"]]
    for cor_nome, status, sig, bg, fg in rows:
        data.append([
            Paragraph(f'<font color="{bg.hexval()}"><b>■</b></font> {cor_nome}',
                      ParagraphStyle("c", fontSize=8)),
            Paragraph(f'<font name="Courier" size="7">{status}</font>', ParagraphStyle("s", fontSize=8)),
            Paragraph(sig, ParagraphStyle("m", fontSize=8)),
        ])
    t = Table(data, colWidths=[3 * cm, 4.5 * cm, 8.7 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_ESCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _dual_layer_table() -> Table:
    data = [
        ["Camada", "Colunas no banco", "Quem vê", "Quando"],
        ["Publicada", "itens_json, observacao", "Mecânico + Oficina", "Após envio / resposta"],
        ["Rascunho responsável", "itens_rascunho_json, observacao_rascunho", "Só responsável", "Salvar rascunho"],
    ]
    t = Table(data, colWidths=[3 * cm, 5 * cm, 3.5 * cm, 4.7 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ROXO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, 1), AZUL_CLARO),
        ("BACKGROUND", (0, 2), (-1, 2), ROXO_CLARO),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c4b5fd")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _buttons_table() -> Table:
    data = [
        ["Botão", "Perfil", "Efeito", "Notifica oficina?"],
        ["Salvar rascunho", "Responsável", "Grava rascunho de preços", "Não"],
        ["Salvar", "Mecânico", "Grava itens em rascunho", "Não"],
        ["Enviar requisição", "Mecânico", "Status → aguardando responsável", "Não"],
        ["Enviar resposta", "Responsável", "Publica itens + respondida", "Sim"],
    ]
    t = Table(data, colWidths=[3.5 * cm, 2.5 * cm, 5.5 * cm, 3.7 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERDE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, VERDE_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#86efac")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _oficina_filters_table() -> Table:
    data = [
        ["Filtro", "O que mostra"],
        ["Todas enviadas", "Respondida + aprovada"],
        ["Sem orçamento", "Enviadas sem vínculo com servicos"],
        ["Com orçamento vinculado", "Já tem Orç. # na coluna"],
        ["Reenviadas (atualizar)", "Vínculo existe + tag ↻ REENV."],
        ["Aguardando orçamento", "Só respondida, sem orçamento"],
    ]
    t = Table(data, colWidths=[5 * cm, 11.2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_ESCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#93c5fd")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _telespectador_table() -> Table:
    data = [
        ["Perfil", "Vê Ao vivo?", "É rastreado?", "Vê quem?"],
        ["Administrador", "Sim (sempre)", "Não", "Todos exceto admin e si"],
        ["Telespectador", "Sim (se marcado)", "Sim", "Alvos ou todos"],
        ["Mecânico / Atendente", "Não", "Sim", "—"],
    ]
    t = Table(data, colWidths=[3.2 * cm, 3 * cm, 3 * cm, 6.8 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ROXO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROXO_CLARO, colors.white, CINZA_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#a78bfa")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _info_box(texto: str, bg=AZUL_CLARO, border=AZUL_MEDIO) -> Table:
    p = Paragraph(texto, ParagraphStyle(
        "infobox", fontSize=9, textColor=AZUL_ESCURO, leading=13, alignment=TA_JUSTIFY,
    ))
    t = Table([[p]], colWidths=[16.2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 1, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _section_title(texto: str, numero: str = "") -> list:
    styles = getSampleStyleSheet()
    prefix = f"{numero}. " if numero else ""
    return [
        Spacer(1, 6),
        Paragraph(
            f'<font color="{AZUL_ESCURO.hexval()}"><b>{prefix}{texto}</b></font>',
            ParagraphStyle("sect", fontSize=14, leading=18, spaceAfter=4),
        ),
        Spacer(1, 2),
        Table([[""]], colWidths=[16.2 * cm], rowHeights=[2],
              style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), AZUL_MEDIO)])),
        Spacer(1, 8),
    ]


def _body(texto: str) -> Paragraph:
    return Paragraph(texto, ParagraphStyle(
        "body", fontSize=9.5, leading=14, textColor=CINZA_TEXTO, alignment=TA_JUSTIFY, spaceAfter=6,
    ))


def _bullet(items: list[str]) -> list:
    out = []
    for item in items:
        out.append(Paragraph(
            f'• {item}',
            ParagraphStyle("bul", fontSize=9, leading=13, textColor=CINZA_TEXTO, leftIndent=12, spaceAfter=3),
        ))
    return out


def build_story() -> list:
    story = []
    story.append(NextPageTemplate("normal"))
    story.append(PageBreak())  # cover uses cover template; this starts content on page 2

    # Índice
    story += _section_title("Índice")
    indice = [
        "1. Visão geral dos sistemas",
        "2. Fluxo de requisições (mecânico → responsável → oficina)",
        "3. Rascunho vs envio — duas camadas de dados",
        "4. Botões e notificações no app web",
        "5. Sistema Oficina — aba Requisições",
        "6. Vínculo requisição ↔ orçamento",
        "7. Modo Telespectador e aba Ao vivo",
        "8. Lista de O.S. — devolver, copiar retorno, bloqueios",
        "9. Referência técnica e pendências",
    ]
    story += _bullet(indice)
    story.append(PageBreak())

    # 1
    story += _section_title("Visão geral dos sistemas", "1")
    story.append(_body(
        "Dois sistemas passaram a trabalhar integrados: o <b>App web O.S. Digital</b>, usado por "
        "mecânicos, atendentes e responsáveis no tablet ou navegador; e o <b>Sistema Oficina (desktop)</b>, "
        "onde a oficina gerencia cadastros, orçamentos e agora também recebe requisições respondidas."
    ))
    story.append(_info_box(
        "<b>Banco compartilhado:</b> a oficina acessa o mesmo SQLite da O.S. Digital "
        "(produção ou ambiente de teste, conforme config.json). "
        "A comunicação não usa API externa — a oficina lê diretamente as tabelas "
        "<font name='Courier'>requisicoes_material</font> e <font name='Courier'>ordens_servico</font>."
    ))
    sys_table = Table([
        ["Sistema", "Usuários", "Função principal"],
        ["O.S. Digital (web)", "Mecânico, Atendente, Admin", "O.S., requisições, Ao vivo"],
        ["Sistema Oficina", "Operador da oficina", "Orçamentos, cadastros, importar req."],
    ], colWidths=[4.5 * cm, 5 * cm, 6.7 * cm])
    sys_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_ESCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [AZUL_CLARO, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#93c5fd")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(sys_table)
    story.append(Spacer(1, 12))

    # 2
    story += _section_title("Fluxo de requisições", "2")
    story.append(_body(
        "O mecânico monta a lista de peças e mão de obra na O.S. O responsável coloca preços e "
        "libera para a oficina. A oficina <b>só enxerga</b> requisições com status "
        "<font name='Courier'>respondida</font> ou <font name='Courier'>aprovada</font>."
    ))
    story.append(Spacer(1, 6))
    story.append(_flow_diagram_table())
    story.append(Spacer(1, 12))
    story.append(_body("<b>Legenda de cores na lista (app web):</b>"))
    story.append(_status_table_app())
    story.append(PageBreak())

    # 3
    story += _section_title("Rascunho vs envio", "3")
    story.append(_body(
        "Problema resolvido: antes, ao salvar rascunho de preços, a oficina já via as alterações. "
        "Agora existem <b>duas camadas</b> de dados na tabela "
        "<font name='Courier'>requisicoes_material</font>:"
    ))
    story.append(Spacer(1, 6))
    story.append(_dual_layer_table())
    story.append(Spacer(1, 10))
    story.append(_info_box(
        "<b>Regra de ouro:</b> o botão <b>Salvar rascunho</b> (responsável) grava apenas em "
        "<font name='Courier'>itens_rascunho_json</font>. A oficina <b>não é notificada</b> e "
        "<b>não vê</b> essas alterações até clicar em <b>Enviar resposta (preços)</b>, que publica "
        "o rascunho em <font name='Courier'>itens_json</font> e muda o status para "
        "<font name='Courier'>respondida</font>.",
        bg=VERDE_CLARO, border=VERDE,
    ))
    story.append(Spacer(1, 10))
    story.append(_body("<b>Estados da requisição:</b>"))
    estados = [
        "<b>rascunho</b> — mecânico salvou, não enviou",
        "<b>aguardando_responsavel</b> — mecânico enviou; falta preço",
        "<b>alterada_mecanico</b> — mecânico alterou itens após envio",
        "<b>respondida</b> — responsável enviou resposta (oficina vê)",
        "<b>aprovada</b> — orçamento aprovado (fluxo futuro)",
    ]
    story += _bullet(estados)

    # 4
    story += _section_title("Botões e notificações no app web", "4")
    story.append(_buttons_table())
    story.append(Spacer(1, 10))
    story.append(_body("<b>Notificações na barra superior (app web):</b>"))
    notif = [
        "Mecânico <b>Enviar requisição</b> → responsável vê aviso (poll ~45 s)",
        "Mecânico altera itens após envio → responsável vê alteração pendente",
        "Responsável <b>Enviar resposta</b> → mecânico vê «Orçamento respondido»",
        "<b>Salvar rascunho</b> (qualquer perfil) → <b>não gera notificação</b>",
    ]
    story += _bullet(notif)
    story.append(PageBreak())

    # 5
    story += _section_title("Sistema Oficina — aba Requisições", "5")
    story.append(_body(
        "Nova aba no desktop com lista de requisições respondidas. Melhorias de interface: "
        "coluna <b>Itens</b> com resumo (ex.: «2 peça(s), 1 M.O.»), botão "
        "<b>Ver itens e M.O.</b> com popup completo, coluna <b>Orçamento</b> com vínculo."
    ))
    story.append(Spacer(1, 8))
    story.append(_body("<b>Indicadores visuais na lista:</b>"))
    tags = [
        "★ NOVA — requisição nova desde última visita à aba",
        "↻ REENV. — mesma requisição com alteração (timestamp mudou)",
        "✓ PRONTA — pronta para gerar orçamento",
    ]
    story += _bullet(tags)
    story.append(Spacer(1, 8))
    story.append(_body(
        "Quando você está em <b>outra aba</b> e chega requisição, aparece barra azul no topo "
        "e 🔔 no título da janela. Ao abrir a aba Requisições, os avisos são limpos."
    ))
    story.append(Spacer(1, 8))
    story.append(_body("<b>Filtros disponíveis:</b>"))
    story.append(_oficina_filters_table())

    # 6
    story += _section_title("Vínculo requisição ↔ orçamento", "6")
    story.append(_body(
        "Ao registrar orçamento a partir de uma requisição, o sistema grava na tabela "
        "<font name='Courier'>servicos</font> as colunas "
        "<font name='Courier'>requisicao_os_id</font> e "
        "<font name='Courier'>numero_os_digital</font>. Isso permite saber qual orçamento "
        "corresponde a qual requisição/O.S."
    ))
    story.append(Spacer(1, 8))
    fluxo_orc = Table([
        ["Situação", "Botão", "Ação"],
        ["Primeira vez", "Gerar orçamento da selecionada", "Preenche Novo Orçamento + registra vínculo"],
        ["Já tem orçamento", "Atualizar Orç. #…", "Atualiza documento existente (não cria outro)"],
        ["Reenviada", "Atualizar Orç. #…", "Sincroniza itens alterados pelo responsável"],
        ["Orçamento trancado", "—", "Atualização bloqueada até destrancar"],
    ], colWidths=[3.5 * cm, 5.5 * cm, 7.2 * cm])
    fluxo_orc.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERDE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, VERDE_CLARO, LARANJA_CLARO, VERMELHO_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#86efac")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(fluxo_orc)
    story.append(Spacer(1, 10))
    story.append(_info_box(
        "<b>Mecânico app ↔ oficina:</b> os IDs de mecânico são diferentes nos dois sistemas. "
        "Na importação, o sistema resolve pelo <b>nome</b> (exato, depois parecido). "
        "Mantenha o <b>nome exibido</b> no app igual ao <b>nome</b> no cadastro da oficina.",
        bg=LARANJA_CLARO, border=LARANJA,
    ))
    story.append(PageBreak())

    # 7
    story += _section_title("Modo Telespectador e aba Ao vivo", "7")
    story.append(_body(
        "Permite acompanhar em tempo quase real quem está logado no app e o que cada pessoa "
        "está fazendo (aba aberta, O.S. em edição, perfil de mecânico, requisição, etc.). "
        "O painel «Ao vivo» saiu do canto do menu e virou uma <b>aba dedicada</b>, separada de "
        "«Perfis em atividade»."
    ))
    story.append(Spacer(1, 8))
    story.append(_telespectador_table())
    story.append(Spacer(1, 10))
    story.append(_body("<b>Como usar a aba Ao vivo:</b>"))
    ao_vivo = [
        "Abra <b>Ao vivo</b> no menu lateral (ícone de olho)",
        "Lista todos os perfis permitidos com badge <b>Online</b> (verde) ou <b>Offline</b> (cinza)",
        "Clique na linha para expandir: aba, módulo, contexto, O.S., perfil observado",
        "Atualização automática a cada 8 s (só com a aba aberta)",
        "Configurar em <b>Configurações → Usuários</b>: checkbox Telespectador + alvos opcionais",
    ]
    story += _bullet(ao_vivo)
    story.append(Spacer(1, 8))
    tech = Table([
        ["Parâmetro", "Valor", "Função"],
        ["TTL online", "45 segundos", "Sem heartbeat → offline"],
        ["Heartbeat", "12 segundos", "Usuário rastreado envia presença"],
        ["Poll monitor", "8 segundos", "Aba Ao vivo consulta servidor"],
    ], colWidths=[4 * cm, 3 * cm, 9.2 * cm])
    tech.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ROXO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROXO_CLARO, colors.white, CINZA_CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#a78bfa")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tech)

    # 8
    story += _section_title("Lista de O.S. — ações e bloqueios", "8")
    story.append(_body("<b>Devolver ao mecânico</b> (responsável):"))
    devolver = [
        "Disponível quando O.S. está <b>Pronto (mecânico)</b> ou <b>Cliente avisado</b>",
        "Volta status para <b>Em serviço</b>, mantendo o mesmo mecânico",
        "Exige confirmação com <b>senha</b> (popover integrado na tela)",
    ]
    story += _bullet(devolver)
    story.append(Spacer(1, 6))
    story.append(_body("<b>Copiar para retorno</b>:"))
    copiar = [
        "Copia cliente e motor/embarcação para nova O.S. (retorno do cliente)",
        "Não copia assinaturas — preencha dados da nova visita",
        "Registra origem em <font name='Courier'>os_retorno_de</font>",
    ]
    story += _bullet(copiar)
    story.append(Spacer(1, 6))
    story.append(_body("<b>Bloqueio de troca de mecânico</b> na lista quando status é:"))
    story += _bullet(["pronto_mecanico", "cliente_avisado", "entregue"])
    story.append(PageBreak())

    # 9
    story += _section_title("Referência técnica e pendências", "9")
    story.append(_body("<b>Arquivos principais:</b>"))
    arquivos = [
        "app_ordem_servico/fluxo_requisicoes.py — lógica de requisições e devolver O.S.",
        "app_ordem_servico/presenca_telespectador.py — presença e telespectador",
        "app_ordem_servico/app.py — APIs REST",
        "app_ordem_servico/templates/index.html — interface web",
        "Sistema_Oficina/requisicoes_os.py — dados da lista na oficina",
        "Sistema_Oficina/importar_requisicao_orcamento.py — importação de orçamento",
        "Sistema_Oficina/requisicoes_notificacao.py — detecção novas/reenviadas",
        "Sistema_Oficina/main.py — UI aba Requisições",
        "Sistema_Oficina/database.py — colunas de vínculo",
    ]
    story += _bullet(arquivos)
    story.append(Spacer(1, 10))
    story.append(_info_box(
        "<b>Pendências (não implementado ainda):</b><br/>"
        "• Fluxo completo orçamento aprovado + assinatura → status <font name='Courier'>aprovada</font><br/>"
        "• Rastreamento do administrador no Ao vivo (hoje admin não é rastreado de propósito)",
        bg=VERMELHO_CLARO, border=VERMELHO,
    ))
    story.append(Spacer(1, 12))
    story.append(_body("<b>Dicas de uso:</b>"))
    dicas = [
        "Mecânico sem internet estável: salvar rascunho e enviar depois",
        "Responsável: use Salvar rascunho várias vezes; Enviar resposta só com preços certos",
        "Oficina não vê nada até Enviar resposta — é intencional",
        "Reenvio: use Atualizar orçamento quando aparecer ↻ REENV.",
        "Alinhe nomes de mecânico entre app e cadastro da oficina",
        "Reinicie o Flask após mudanças no backend do app web",
    ]
    story += _bullet(dicas)
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f'<font color="{CINZA_TEXTO.hexval()}"><i>Documento gerado em {date.today().strftime("%d/%m/%Y")} '
        f'— Manual Integração O.S. Digital × Sistema Oficina</i></font>',
        ParagraphStyle("foot", fontSize=8, alignment=TA_CENTER),
    ))
    return story


def main() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUT_PDF),
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=28 * mm,
        bottomMargin=22 * mm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 8 * mm, id="normal")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=frame, onPage=_cover_page),
        PageTemplate(id="normal", frames=frame, onPage=_header_footer),
    ])
    story = [NextPageTemplate("cover"), PageBreak()]
    story += build_story()
    doc.build(story)
    print(f"PDF gerado: {OUT_PDF}")
    return OUT_PDF


if __name__ == "__main__":
    main()
