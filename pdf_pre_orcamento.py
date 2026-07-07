"""PDF do Pré-Orçamento — layout alinhado à identidade da oficina."""

from __future__ import annotations

import io
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from PIL import Image

from pdf_os import _fmt_data_br, _img_dataurl, _registrar_fontes, _txt

_NAVY = (0, 56, 168)
_LIGHT_BLUE = (232, 238, 248)
_ROW_ALT = (245, 247, 250)
_TEXT_DARK = (30, 30, 30)
_TEXT_MUTED = (95, 95, 95)
_WHITE = (255, 255, 255)
_ACCENT_HEADER = (180, 210, 255)

_COL_DESC = 96.0
_COL_QTD = 18.0
_COL_VU = 30.0
_COL_SUB = 30.0
_ROW_H_MIN = 6.5
_ALTURA_FAIXA = 30.0
_AREA_LOGO_W = 40.0


def _fmt_moeda(valor: Any) -> str:
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        n = 0.0
    texto = f"{n:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_qtd(valor: Any) -> str:
    try:
        n = float(valor or 1)
    except (TypeError, ValueError):
        n = 1.0
    if abs(n - round(n)) < 0.001:
        return str(int(round(n)))
    return f"{n:.2f}".replace(".", ",")


def _logo_para_pdf(logo_dataurl: str | None) -> tuple[io.BytesIO, str, int, int] | None:
    """BytesIO + tipo + largura/altura em pixels (proporção da logo)."""
    bruto = _img_dataurl(logo_dataurl)
    if bruto is None:
        return None
    try:
        bruto.seek(0)
        with Image.open(bruto) as img:
            if img.mode in ("RGBA", "LA", "P"):
                fundo = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                fundo.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = fundo
            else:
                img = img.convert("RGB")
            iw, ih = img.size
            maior = max(iw, ih)
            if maior > 600:
                escala = 600 / maior
                img = img.resize(
                    (max(1, int(iw * escala)), max(1, int(ih * escala))),
                    Image.Resampling.LANCZOS,
                )
                iw, ih = img.size
            saida = io.BytesIO()
            img.save(saida, format="PNG")
            saida.seek(0)
            return saida, "png", iw, ih
    except (OSError, ValueError, Image.UnidentifiedImageError):
        return None


def _dims_logo_caixa(box_w: float, box_h: float, img_w: int, img_h: int) -> tuple[float, float]:
    if img_w <= 0 or img_h <= 0:
        return box_w, box_h
    ratio = img_w / img_h
    w = box_w
    h = w / ratio
    if h > box_h:
        h = box_h
        w = h * ratio
    return w, h


def _eh_item_servico(item: dict[str, Any]) -> bool:
    if str(item.get("tipo") or "peca").strip().lower() == "servico":
        return True
    desc = _txt(item.get("descricao")).upper()
    chaves = ("SERVICO", "SERVIÇO", "M.O.", "MAO DE OBRA", "MÃO DE OBRA", "VALOR DOS SERV")
    return any(ch in desc for ch in chaves)


def _separar_itens(itens: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    pecas: list[dict] = []
    servicos: list[dict] = []
    for item in itens:
        if _eh_item_servico(item):
            servicos.append(item)
        else:
            pecas.append(item)
    return pecas, servicos


class PreOrcamentoPDF(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=20)
        self.alias_nb_pages()
        self._fonte = _registrar_fontes(self)

    @property
    def epw(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def _font(self, estilo: str = "", tamanho: float = 10) -> None:
        self.set_font(self._fonte, estilo, tamanho)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_text_color(*_TEXT_MUTED)
        self._font("", 7.5)
        self.set_x(self.l_margin)
        self.cell(
            self.epw,
            4,
            "Documento informativo — sujeito a confirmacao na oficina. Nao constitui cobranca.",
            align="C",
        )
        self.ln(3.5)
        self.cell(self.epw, 4, f"Pagina {self.page_no()}/{{nb}}", align="C")


def _calc_subtotal(itens: list[dict[str, Any]]) -> float:
    return round(
        sum(
            float(item.get("quantidade") or 1) * float(item.get("valor_unitario") or 0)
            for item in itens
        ),
        2,
    )


def _numero_abaixo_faixa(pdf: PreOrcamentoPDF, y_ini: float, numero: str) -> float:
    """Número do documento entre a faixa azul e a linha separadora."""
    pdf.set_xy(pdf.l_margin, y_ini)
    pdf._font("B", 11)
    pdf.set_text_color(*_NAVY)
    pdf.cell(pdf.epw, 6, numero, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return pdf.get_y() + 2


def _desenhar_faixa_azul(
    pdf: PreOrcamentoPDF,
    y_ini: float,
    *,
    logo_dataurl: str | None,
    empresa: dict[str, str],
) -> float:
    x0 = pdf.l_margin
    y0 = y_ini

    pdf.set_fill_color(*_NAVY)
    pdf.rect(x0, y0, pdf.epw, _ALTURA_FAIXA, style="F")

    logo_ok = False
    logo_info = _logo_para_pdf(logo_dataurl)
    if logo_info:
        img_io, ext, iw, ih = logo_info
        try:
            bx = x0 + 4
            by = y0 + 3
            bw = 34.0
            bh = 24.0
            pdf.set_fill_color(*_WHITE)
            pdf.rect(bx, by, bw, bh, style="F")
            lw, lh = _dims_logo_caixa(bw - 4, bh - 4, iw, ih)
            pdf.image(
                img_io,
                x=bx + (bw - lw) / 2,
                y=by + (bh - lh) / 2,
                w=lw,
                h=lh,
                type=ext,
            )
            logo_ok = True
        except Exception:
            logo_ok = False

    if not logo_ok:
        nome = _txt(empresa.get("nome_fantasia") or empresa.get("razao_social"), "Oficina Nautica")
        pdf.set_xy(x0 + 4, y0 + 10)
        pdf.set_text_color(*_WHITE)
        pdf._font("B", 10)
        pdf.multi_cell(_AREA_LOGO_W - 2, 5, nome[:35])

    x_titulo = x0 + _AREA_LOGO_W
    largura_titulo = pdf.epw - _AREA_LOGO_W - 2

    pdf.set_xy(x_titulo, y0 + 9)
    pdf.set_text_color(*_WHITE)
    pdf._font("B", 16)
    pdf.cell(largura_titulo, 9, "PRE-ORCAMENTO", align="C")

    partes: list[str] = []
    endereco = _txt(empresa.get("endereco"))
    telefone = _txt(empresa.get("telefone"))
    if endereco:
        partes.append(endereco[:50])
    if telefone:
        partes.append(f"Tel: {telefone}")
    if partes:
        pdf.set_xy(x_titulo, y0 + 21)
        pdf.set_text_color(*_ACCENT_HEADER)
        pdf._font("", 7)
        pdf.cell(largura_titulo, 4, "  |  ".join(partes)[:85], align="C")

    pdf.set_text_color(*_TEXT_DARK)
    return y0 + _ALTURA_FAIXA + 5


def _linha_separadora(pdf: PreOrcamentoPDF, y_ini: float) -> float:
    pdf.set_draw_color(*_NAVY)
    pdf.set_line_width(0.35)
    meio = pdf.l_margin + pdf.epw / 2
    pdf.line(meio - 25, y_ini, meio + 25, y_ini)
    pdf.set_line_width(0.2)
    return y_ini + 6


def _caixa_dados_cliente(pdf: PreOrcamentoPDF, y_ini: float, pre: dict[str, Any]) -> float:
    y0 = y_ini
    altura = 22.0
    pdf.set_fill_color(*_LIGHT_BLUE)
    pdf.set_draw_color(200, 210, 230)
    pdf.rect(pdf.l_margin, y0, pdf.epw, altura, style="FD")

    campos = (
        ("CLIENTE", _txt(pre.get("cliente_nome"), "—")),
        ("MOTOR", _txt(pre.get("motor"), "—")),
        ("DATA", _fmt_data_br(pre.get("data"))),
    )
    col_w = pdf.epw / 3
    for idx, (rotulo, valor) in enumerate(campos):
        x = pdf.l_margin + 4 + idx * col_w
        pdf.set_xy(x, y0 + 3)
        pdf._font("B", 8)
        pdf.set_text_color(*_NAVY)
        pdf.cell(col_w - 6, 4, rotulo)
        pdf.set_xy(x, y0 + 8)
        pdf._font("", 10)
        pdf.set_text_color(*_TEXT_DARK)
        pdf.cell(col_w - 6, 5, valor[:42])

    return y0 + altura + 6


def _cabecalho_tabela(pdf: PreOrcamentoPDF, y_ini: float) -> float:
    pdf.set_xy(pdf.l_margin, y_ini)
    pdf._font("B", 9)
    pdf.set_text_color(*_WHITE)
    pdf.set_fill_color(*_NAVY)
    pdf.cell(_COL_DESC, 7, "Descricao", border=1, align="L", fill=True)
    pdf.cell(_COL_QTD, 7, "Qtd", border=1, align="C", fill=True)
    pdf.cell(_COL_VU, 7, "Valor un.", border=1, align="R", fill=True)
    pdf.cell(_COL_SUB, 7, "Subtotal", border=1, align="R", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_TEXT_DARK)
    return pdf.get_y()


def _linha_item_tabela(
    pdf: PreOrcamentoPDF,
    *,
    descricao: str,
    quantidade: Any,
    valor_unitario: float,
    subtotal: float,
    zebra: bool,
) -> float:
    if zebra:
        pdf.set_fill_color(*_ROW_ALT)
    else:
        pdf.set_fill_color(*_WHITE)

    y0 = pdf.get_y()
    x0 = pdf.l_margin
    pdf.set_draw_color(190, 195, 205)

    pdf.set_xy(x0 + 1.5, y0 + 1.2)
    pdf._font("", 8.5)
    pdf.multi_cell(_COL_DESC - 3, 4.2, descricao or "—", border=0)
    altura = max(_ROW_H_MIN, pdf.get_y() - y0 + 2)

    pdf.set_xy(x0, y0)
    pdf.cell(_COL_DESC, altura, "", border=1, fill=True)
    pdf.cell(_COL_QTD, altura, _fmt_qtd(quantidade), border=1, align="C", fill=True)
    pdf.cell(_COL_VU, altura, _fmt_moeda(valor_unitario), border=1, align="R", fill=True)
    pdf.cell(_COL_SUB, altura, _fmt_moeda(subtotal), border=1, align="R", fill=True)

    pdf.set_xy(x0 + 1.5, y0 + 1.2)
    pdf._font("", 8.5)
    pdf.set_text_color(*_TEXT_DARK)
    pdf.multi_cell(_COL_DESC - 3, 4.2, descricao or "—", border=0)

    y_fim = y0 + altura
    pdf.set_xy(x0, y_fim)
    return y_fim


def _renderizar_tabela_itens(
    pdf: PreOrcamentoPDF,
    y_ini: float,
    titulo_secao: str,
    itens: list[dict[str, Any]],
) -> float:
    if not itens:
        return y_ini

    pdf.set_xy(pdf.l_margin, y_ini)
    pdf._font("B", 10)
    pdf.set_text_color(*_TEXT_DARK)
    pdf.cell(0, 6, titulo_secao, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)

    y = _cabecalho_tabela(pdf, pdf.get_y())
    pdf.set_xy(pdf.l_margin, y)
    for idx, item in enumerate(itens):
        desc = _txt(item.get("descricao"))
        qtd = item.get("quantidade") or 1
        vu = float(item.get("valor_unitario") or 0)
        sub = float(qtd) * vu
        y = _linha_item_tabela(
            pdf,
            descricao=desc,
            quantidade=qtd,
            valor_unitario=vu,
            subtotal=sub,
            zebra=idx % 2 == 1,
        )
        pdf.set_xy(pdf.l_margin, y)

    return y + 2


def _bloco_total(
    pdf: PreOrcamentoPDF,
    *,
    subtotal_pecas: float,
    subtotal_servicos: float,
    total: Any,
) -> None:
    pdf.ln(2)
    x0 = pdf.l_margin + _COL_DESC + _COL_QTD
    largura = pdf.epw - _COL_DESC - _COL_QTD
    y0 = pdf.get_y()

    if subtotal_pecas > 0 and subtotal_servicos > 0:
        linhas = [
            ("Subtotal pecas:", subtotal_pecas),
            ("Subtotal servicos:", subtotal_servicos),
        ]
        altura_box = 6.5 * len(linhas) + 9
        pdf.set_fill_color(252, 252, 252)
        pdf.set_draw_color(200, 210, 230)
        pdf.rect(x0, y0, largura, altura_box, style="FD")
        y_txt = y0 + 2
        pdf._font("", 9)
        pdf.set_text_color(*_TEXT_DARK)
        for rotulo, valor in linhas:
            pdf.set_xy(x0 + 3, y_txt)
            pdf.cell(largura - 6, 5, rotulo, align="L")
            pdf.set_xy(x0 + 3, y_txt)
            pdf.cell(largura - 6, 5, _fmt_moeda(valor), align="R")
            y_txt += 6.5
        pdf.set_xy(x0 + 3, y_txt + 1)
        pdf._font("B", 11)
        pdf.set_text_color(*_NAVY)
        pdf.cell(largura - 6, 6, f"TOTAL GERAL: {_fmt_moeda(total)}", align="R")
        pdf.set_xy(pdf.l_margin, y0 + altura_box + 2)
        return

    y0 = pdf.get_y()
    altura_box = 11.0
    pdf.set_fill_color(*_LIGHT_BLUE)
    pdf.set_draw_color(*_NAVY)
    pdf.rect(x0, y0, largura, altura_box, style="FD")
    rotulo = "TOTAL GERAL" if subtotal_servicos > 0 else "TOTAL ESTIMADO"
    pdf.set_xy(x0 + 3, y0 + 2.5)
    pdf._font("B", 10)
    pdf.set_text_color(*_NAVY)
    pdf.cell(largura - 6, 6, f"{rotulo}: {_fmt_moeda(total)}", align="R")
    pdf.set_text_color(*_TEXT_DARK)
    pdf.set_xy(pdf.l_margin, y0 + altura_box + 2)


def _secao_observacoes(pdf: PreOrcamentoPDF, obs: str) -> None:
    pdf.ln(3)
    pdf._font("B", 9)
    pdf.set_text_color(*_NAVY)
    pdf.cell(0, 5, "Observacoes", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(200, 210, 230)
    pdf.set_fill_color(252, 252, 252)
    y0 = pdf.get_y()
    pdf.rect(pdf.l_margin, y0, pdf.epw, 16, style="FD")
    pdf.set_xy(pdf.l_margin + 3, y0 + 2)
    pdf._font("", 9)
    pdf.set_text_color(*_TEXT_DARK)
    pdf.multi_cell(pdf.epw - 6, 4.5, obs)
    pdf.set_xy(pdf.l_margin, y0 + 18)


def gerar_pdf_pre_orcamento(
    pre: dict[str, Any],
    *,
    logo_dataurl: str | None = None,
    empresa: dict[str, str] | None = None,
) -> bytes:
    empresa = empresa or {}
    numero = _txt(pre.get("numero"), "PRE-000")
    pdf = PreOrcamentoPDF()
    pdf.add_page()

    y = _desenhar_faixa_azul(pdf, 15.0, logo_dataurl=logo_dataurl, empresa=empresa)
    y = _numero_abaixo_faixa(pdf, y, numero)
    y = _linha_separadora(pdf, y)
    y = _caixa_dados_cliente(pdf, y, pre)

    itens = pre.get("itens") or []
    pecas, servicos = _separar_itens(itens)
    sub_pecas = _calc_subtotal(pecas)
    sub_servicos = _calc_subtotal(servicos)
    total_calc = round(sub_pecas + sub_servicos, 2)
    total_doc = float(pre.get("preco_total") or total_calc or 0)

    if not pecas and not servicos:
        pdf.set_xy(pdf.l_margin, y)
        pdf._font("", 9)
        pdf.set_text_color(*_TEXT_MUTED)
        pdf.cell(pdf.epw, 8, "Nenhum item cadastrado.", border=1, align="C")
        pdf.ln(2)
        y = pdf.get_y()
    else:
        y = _renderizar_tabela_itens(pdf, y, "Pecas", pecas)
        if servicos:
            pdf.ln(1)
            y = _renderizar_tabela_itens(pdf, y, "Servicos", servicos)

    pdf.set_xy(pdf.l_margin, y)
    _bloco_total(
        pdf,
        subtotal_pecas=sub_pecas,
        subtotal_servicos=sub_servicos,
        total=total_doc if total_doc > 0 else total_calc,
    )

    obs = _txt(pre.get("observacoes"))
    if obs:
        _secao_observacoes(pdf, obs)

    pdf.ln(4)
    pdf.set_text_color(*_TEXT_MUTED)
    pdf._font("", 8)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(
        pdf.epw,
        4,
        "Valores sujeitos a alteracao conforme disponibilidade de pecas e servicos. "
        "Este pre-orcamento nao gera obrigacao de pagamento ate aprovacao na oficina.",
        align="C",
    )

    out = pdf.output(dest="S")
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return out.encode("latin-1", errors="replace")
