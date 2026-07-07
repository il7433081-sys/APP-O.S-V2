"""Geração de PDF — Checklist de Revisão (v2.9+)."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

from checklist_revisao import ITENS_CHECKLIST_REVISAO, normalizar_itens_salvos

_FONT = "ArialChk"


def _registrar_fontes(pdf: FPDF) -> str:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    regular = windir / "Fonts" / "arial.ttf"
    bold = windir / "Fonts" / "arialbd.ttf"
    if regular.is_file():
        pdf.add_font(_FONT, "", str(regular))
        pdf.add_font(_FONT, "B", str(bold if bold.is_file() else regular))
        return _FONT
    return "Helvetica"


def _txt(valor: Any, padrao: str = "") -> str:
    if valor is None:
        return padrao
    s = str(valor).strip()
    return s if s else padrao


def _fmt_data_br(valor: Any) -> str:
    s = _txt(valor)
    if not s:
        return "___/___/___"
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return s


def _marcador(marcado: bool) -> str:
    return "( X )" if marcado else "(   )"


def _linha_item(item_def: dict[str, Any], estado: dict[str, Any]) -> str:
    num = item_def["numero"]
    texto = item_def["texto"]
    marcado = bool(estado.get("marcado"))
    if item_def.get("sub_opcao") == "vst_carburador":
        sub = estado.get("sub_opcao")
        vst = "X" if sub == "vst" else " "
        carb = "X" if sub == "carburador" else " "
        return (
            f"{num}. {_marcador(marcado)} {texto} ( {vst} ) VST ( {carb} ) carburador"
        )
    return f"{num}. {_marcador(marcado)} {texto}"


class ChecklistRevisaoPDF(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(12, 12, 12)
        self.set_auto_page_break(auto=True, margin=12)
        self._fonte = _registrar_fontes(self)

    def texto_livre(self, altura: float, texto: str) -> None:
        self.set_x(self.l_margin)
        self.multi_cell(0, altura, texto)


def gerar_pdf_checklist_revisao(
    *,
    cabecalho: dict[str, Any],
    itens: list[dict[str, Any]],
) -> bytes:
    pdf = ChecklistRevisaoPDF()
    pdf.add_page()

    estados = {x["id"]: x for x in normalizar_itens_salvos(itens)}
    cab = cabecalho or {}

    pdf.set_font(pdf._fonte, "B", 14)
    pdf.cell(0, 8, _txt("CHECKLIST REVISAO"), ln=True, align="C")
    pdf.ln(2)

    pdf.set_font(pdf._fonte, "", 9)
    linha1 = (
        f"DATA: {_fmt_data_br(cab.get('data'))}   "
        f"EMBARCACAO: {_txt(cab.get('embarcacao'), '_______________')}   "
        f"MOTOR: {_txt(cab.get('motor'), '___________')}   "
        f"HORA DE USO: {_txt(cab.get('horas'), '____________')}"
    )
    pdf.texto_livre(4.5, linha1)
    pdf.texto_livre(
        4.5,
        f"MECANICO: {_txt(cab.get('mecanico'), '_______________')}   "
        f"CLIENTE: {_txt(cab.get('cliente'), '_______________________')}",
    )
    pdf.ln(2)

    pdf.set_font(pdf._fonte, "B", 9)
    pdf.cell(0, 5, "ALEGACOES/SOLICITACOES DO CLIENTE:", ln=True)
    pdf.set_font(pdf._fonte, "", 9)
    aleg = _txt(cab.get("alegacoes"))
    if aleg:
        pdf.texto_livre(4.5, aleg)
    else:
        for _ in range(3):
            pdf.cell(0, 5, "_" * 90, ln=True)

    pdf.ln(2)
    pdf.set_font(pdf._fonte, "B", 10)
    pdf.cell(0, 6, "ORCAMENTO", ln=True)
    pdf.set_font(pdf._fonte, "", 8.5)
    for item_def in ITENS_CHECKLIST_REVISAO:
        if item_def["secao"] != "orcamento":
            continue
        estado = estados.get(item_def["id"], {"marcado": False, "sub_opcao": None})
        pdf.texto_livre(4.2, _linha_item(item_def, estado))

    pdf.ln(2)
    pdf.set_font(pdf._fonte, "B", 10)
    pdf.cell(0, 6, "MONTAGEM REVISAO (ANTES DA PARTIDA)", ln=True)
    pdf.set_font(pdf._fonte, "", 8.5)
    for item_def in ITENS_CHECKLIST_REVISAO:
        if item_def["secao"] != "montagem":
            continue
        estado = estados.get(item_def["id"], {"marcado": False, "sub_opcao": None})
        pdf.texto_livre(4.2, _linha_item(item_def, estado))

    pdf.ln(4)
    pdf.set_font(pdf._fonte, "", 10)
    pdf.cell(0, 6, "ASSINADO:________________________", ln=True)

    return bytes(pdf.output())
