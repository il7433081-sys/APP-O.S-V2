"""PDF com fotos enviadas pelo mecânico."""

from __future__ import annotations

import base64
import io
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from PIL import Image

from pdf_os import _fmt_data_br, _img_dataurl, _registrar_fontes, _txt

_FOTO_COLS = 2
_FOTO_BOX_W = 88.0
_FOTO_BOX_H = 66.0
_FOTO_GAP = 6.0
_FOTO_LEGENDA_H = 5.0
_FOTO_ROW_H = _FOTO_BOX_H + _FOTO_GAP + _FOTO_LEGENDA_H
_LABEL_W = 22.0


class _PdfFotosOs(FPDF):
    @property
    def epw(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def footer(self) -> None:
        self.set_y(-12)
        fam = getattr(self, "_familia_fonte", "Helvetica")
        self.set_font(fam, "", 8)
        self.set_text_color(120, 120, 120)
        self.set_x(self.l_margin)
        self.cell(self.epw, 8, f"Pagina {self.page_no()}/{{nb}}", align="C")


def _img_dataurl_para_pdf(dataurl: str, *, max_px: int = 1800) -> io.BytesIO | None:
    """Reduz imagens grandes para caber no PDF sem distorcer o layout."""
    bruto = _img_dataurl(dataurl)
    if bruto is None:
        return None
    try:
        bruto.seek(0)
        with Image.open(bruto) as img:
            img = img.convert("RGB")
            largura, altura = img.size
            if largura <= 0 or altura <= 0:
                return None
            maior = max(largura, altura)
            if maior > max_px:
                escala = max_px / maior
                img = img.resize(
                    (max(1, int(largura * escala)), max(1, int(altura * escala))),
                    Image.Resampling.LANCZOS,
                )
            saida = io.BytesIO()
            img.save(saida, format="JPEG", quality=88)
            saida.seek(0)
            return saida
    except (OSError, ValueError, Image.UnidentifiedImageError):
        return None


def _rotulo_valor(pdf: _PdfFotosOs, fam: str, rotulo: str, valor: str) -> None:
    pdf.set_x(pdf.l_margin)
    y_ini = pdf.get_y()
    pdf.set_font(fam, "B", 9)
    pdf.cell(_LABEL_W, 5, rotulo + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font(fam, "", 9)
    largura_valor = max(10.0, pdf.w - pdf.r_margin - pdf.get_x())
    pdf.multi_cell(largura_valor, 5, valor)
    if pdf.get_y() < y_ini + 5:
        pdf.set_y(y_ini + 5)


def _cabecalho_pdf(
    pdf: _PdfFotosOs,
    fam: str,
    dados_os: dict[str, Any],
    *,
    logo_dataurl: str | None,
    empresa: dict[str, str],
) -> None:
    tem_logo = False
    if logo_dataurl:
        img_logo = _img_dataurl_para_pdf(logo_dataurl, max_px=400)
        if img_logo:
            try:
                pdf.image(img_logo, x=pdf.l_margin, y=12, w=28)
                tem_logo = True
            except Exception:
                pass

    x_titulo = pdf.l_margin + 35 if tem_logo else pdf.l_margin
    largura_titulo = max(20.0, pdf.w - pdf.r_margin - x_titulo)
    pdf.set_xy(x_titulo, 12)
    pdf.set_font(fam, "B", 14)
    pdf.set_text_color(20, 20, 20)
    fantasia = _txt(empresa.get("nome_fantasia") or empresa.get("razao_social"), "Oficina")
    pdf.multi_cell(largura_titulo, 7, fantasia)
    pdf.set_x(x_titulo)
    pdf.set_font(fam, "B", 11)
    pdf.multi_cell(largura_titulo, 6, "Registro fotografico - Ordem de Servico")

    y_meta = max(pdf.get_y() + 4, 46 if tem_logo else pdf.get_y() + 2)
    pdf.set_xy(pdf.l_margin, y_meta)
    pdf.set_text_color(40, 40, 40)

    data_os = _fmt_data_br(dados_os.get("data_entrada"))
    numero_os = str(dados_os.get("numero_os") or "-")
    cliente = _txt(dados_os.get("cliente_nome"), "-")
    motor = _txt(dados_os.get("motor"), "-")
    embarcacao = _txt(dados_os.get("embarcacao_nome"), "-")

    pdf.set_x(pdf.l_margin)
    y_linha = pdf.get_y()
    pdf.set_font(fam, "B", 9)
    pdf.cell(14, 5, "Data:", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font(fam, "", 9)
    pdf.cell(34, 5, data_os, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font(fam, "B", 9)
    pdf.cell(18, 5, "O.S. n.:", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font(fam, "", 9)
    resto = max(10.0, pdf.w - pdf.r_margin - pdf.get_x())
    pdf.cell(resto, 5, numero_os, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if pdf.get_y() < y_linha + 5:
        pdf.set_y(y_linha + 5)

    _rotulo_valor(pdf, fam, "Cliente", cliente)
    _rotulo_valor(pdf, fam, "Motor", f"{motor} - {embarcacao}")
    pdf.ln(3)


def _desenhar_fotos(pdf: _PdfFotosOs, fam: str, fotos: list[str]) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font(fam, "B", 10)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(pdf.epw, 6, f"Fotos ({len(fotos)})", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    y_grid = pdf.get_y()
    slot = 0
    limite_y = pdf.h - pdf.b_margin - _FOTO_BOX_H - _FOTO_LEGENDA_H

    for idx, foto in enumerate(fotos, start=1):
        img = _img_dataurl_para_pdf(foto)
        if not img:
            continue

        col = slot % _FOTO_COLS
        if col == 0 and slot > 0:
            y_grid += _FOTO_ROW_H

        if y_grid + _FOTO_BOX_H > limite_y:
            pdf.add_page()
            y_grid = pdf.t_margin + 4
            slot = 0
            col = 0

        x = pdf.l_margin + col * (_FOTO_BOX_W + _FOTO_GAP)
        y = y_grid

        try:
            with Image.open(img) as pil_img:
                iw, ih = pil_img.size
            img.seek(0)
            ratio = iw / ih if ih else 1.0
            draw_w = _FOTO_BOX_W
            draw_h = draw_w / ratio
            if draw_h > _FOTO_BOX_H:
                draw_h = _FOTO_BOX_H
                draw_w = draw_h * ratio
            off_x = x + (_FOTO_BOX_W - draw_w) / 2
            off_y = y + (_FOTO_BOX_H - draw_h) / 2
            pdf.image(img, x=off_x, y=off_y, w=draw_w, h=draw_h)
        except Exception:
            pdf.set_xy(x, y)
            pdf.set_font(fam, "", 8)
            pdf.cell(_FOTO_BOX_W, 8, f"Foto {idx} indisponivel")

        pdf.set_xy(x, y + _FOTO_BOX_H + 1)
        pdf.set_font(fam, "", 7)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(_FOTO_BOX_W, 4, f"Foto {idx}", align="C")

        slot += 1


def gerar_pdf_fotos_os(
    dados_os: dict[str, Any],
    fotos: list[str],
    *,
    logo_dataurl: str | None = None,
    empresa: dict[str, str] | None = None,
) -> bytes:
    empresa = empresa or {}
    pdf = _PdfFotosOs(orientation="P", unit="mm", format="A4")
    fam = _registrar_fontes(pdf)
    pdf._familia_fonte = fam
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    _cabecalho_pdf(pdf, fam, dados_os, logo_dataurl=logo_dataurl, empresa=empresa)

    if not fotos:
        pdf.set_x(pdf.l_margin)
        pdf.set_font(fam, "", 10)
        pdf.cell(pdf.epw, 8, "Nenhuma foto disponivel.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        _desenhar_fotos(pdf, fam, fotos)

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def fotos_para_zip(fotos: list[str]) -> list[tuple[str, bytes]]:
    saida: list[tuple[str, bytes]] = []
    for idx, foto in enumerate(fotos, start=1):
        if not foto or not str(foto).startswith("data:image/"):
            continue
        try:
            header, b64 = str(foto).split(",", 1)
            ext = "jpg"
            if "png" in header:
                ext = "png"
            elif "webp" in header:
                ext = "webp"
            dados = base64.b64decode(b64)
            saida.append((f"foto_{idx:02d}.{ext}", dados))
        except (ValueError, base64.binascii.Error):
            continue
    return saida
