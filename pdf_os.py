"""
Geração de PDF da Ordem de Serviço Digital (layout OS_MODELO_NOVO).

Padrão: paisagem (horizontal), 2 páginas — frente (entrada/cliente/alegações)
e verso (check-list, fechamento, constatação, análise).
Use orientacao="vertical" ou PDF_ORIENTACAO=vertical no .env para retrato.
"""

from __future__ import annotations

import base64
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF
from PIL import Image

from checklist_revisao import preparar_campos_diagnostico_os_para_impressao

_FONT = "ArialPDF"
_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_DIAGRAMAS_DIR = _ASSETS_DIR / "diagramas"
_INSPECAO_ITENS = (
    ("insp_certificado_garantia", "Solicitar certificado de garantia"),
    ("insp_capo", "Verificar estado de conservação do capô"),
    ("insp_documento", "Verificar documento do veículo"),
    ("insp_rabeta", "Verificar rabeta completa"),
    ("insp_helice", "Verificar hélice"),
    ("insp_manche", "Verificar manche"),
    ("insp_cordao_partida", "Verificar cordão de partida"),
)
_ACESSORIOS = (
    ("acessorio_capa", "Capa de proteção do capô"),
    ("acessorio_tanque", "Tanque de combustível"),
    ("acessorio_mangueira", "Mangueira de combustível"),
    ("acessorio_cordao_seg", "Cordão de segurança"),
    ("acessorio_carrinho", "Carrinho de transporte"),
)
_TIPOS_OS = (
    ("cliente", "Cliente"),
    ("garantia", "Garantia"),
    ("seguro", "Seguro"),
    ("orcamento", "Orçamento"),
    ("interna", "Interna"),
    ("externa", "Externa"),
    ("outro", "Outro"),
)
_LEGENDA_INSPECAO = (
    "Legenda: OK Conforme | R Riscado | A Amassado | M Manchado | E Enferrujado | O Outros"
)


def normalizar_orientacao(valor: str | None = None) -> str:
    """Retorna 'L' (horizontal/paisagem) ou 'P' (vertical/retrato)."""
    raw = (valor or os.environ.get("PDF_ORIENTACAO", "horizontal")).strip().lower()
    if raw in ("vertical", "portrait", "p", "retrato", "portrait"):
        return "P"
    return "L"


def _registrar_fontes(pdf: FPDF) -> str:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    regular = windir / "Fonts" / "arial.ttf"
    bold = windir / "Fonts" / "arialbd.ttf"
    if regular.is_file():
        pdf.add_font(_FONT, "", str(regular))
        if bold.is_file():
            pdf.add_font(_FONT, "B", str(bold))
        else:
            pdf.add_font(_FONT, "B", str(regular))
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
        return "___/___/____"
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return s


_NOMES_ASSINANTE_PDF: dict[str, str] = {
    "responsavel": "responsavel_assinante_nome",
    "recepcao": "recepcao_assinante_nome",
    "entrega": "entrega_assinante_nome",
    "aprovacao": "aprovacao_assinante_nome",
}


def _nome_assinante_pdf(dados: dict[str, Any], contexto: str) -> str:
    chave = _NOMES_ASSINANTE_PDF.get(contexto, "")
    return _txt(dados.get(chave)) if chave else ""


def _fmt_moeda(valor: Any) -> str:
    s = _txt(valor, "0")
    s = s.replace(".", "").replace(",", ".") if "," in s and s.count(",") == 1 else s
    try:
        n = float(s)
        return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except ValueError:
        return s or "0,00"


def _lista_os_tipo(dados: dict[str, Any]) -> list[str]:
    raw = dados.get("os_tipo")
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if raw:
        return [str(raw)]
    return []


def _marcado(dados: dict[str, Any], chave: str, valor: str) -> bool:
    v = dados.get(chave)
    if isinstance(v, list):
        return valor in v
    return str(v or "") == valor


def _img_dataurl(dataurl: str | None) -> io.BytesIO | None:
    if not dataurl or not isinstance(dataurl, str) or not dataurl.startswith("data:image"):
        return None
    try:
        _, b64 = dataurl.split(",", 1)
        return io.BytesIO(base64.b64decode(b64))
    except (ValueError, base64.binascii.Error):
        return None


def _arquivo_diagrama(nome: str) -> Path | None:
    caminho = _DIAGRAMAS_DIR / f"{nome}.png"
    return caminho if caminho.is_file() else None


def _pdf_imagem_arquivo(
    pdf: "OrdemServicoPDF",
    caminho: Path,
    x: float,
    y: float,
    max_w: float,
    max_h: float,
) -> tuple[float, float]:
    """Insere PNG no PDF preservando proporção; retorna (largura, altura) usadas."""
    with Image.open(caminho) as img:
        iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return 0.0, 0.0
    ratio = iw / ih
    w = max_w
    h = w / ratio
    if h > max_h:
        h = max_h
        w = h * ratio
    pdf.image(str(caminho), x=x + (max_w - w) / 2, y=y + (max_h - h) / 2, w=w, h=h)
    return w, h


def _diagramas_inspecao_vertical(pdf: "OrdemServicoPDF") -> None:
    """Rodapé da pág. 2 — vistas do motor de popa e da moto aquática para marcação."""
    arquivos = {
        "motor_esq": _arquivo_diagrama("motor_esq"),
        "motor_dir": _arquivo_diagrama("motor_dir"),
        "motor_topo": _arquivo_diagrama("motor_topo"),
        "jet_esq": _arquivo_diagrama("jet_esq"),
        "jet_dir": _arquivo_diagrama("jet_dir"),
    }
    if not any(arquivos.values()):
        return

    y0 = pdf.get_y() + 1.2
    limite = pdf.h - pdf.b_margin - 1
    if limite - y0 < 28:
        return

    pdf._font("B", 5.5)
    pdf.set_xy(pdf.l_margin, y0)
    pdf.cell(0, 3.2, "DIAGRAMAS PARA REGISTRO DE AVARIAS", ln=True)
    pdf.ln(0.3)

    y = pdf.get_y()
    col = pdf.epw / 2 - 1.5
    gap = 3.0
    row_h = min(18.5, (limite - y) / 3.2)

    x_esq = pdf.l_margin
    x_dir = pdf.l_margin + col + gap

    if arquivos["motor_esq"]:
        _pdf_imagem_arquivo(pdf, arquivos["motor_esq"], x_esq, y, col, row_h)
    if arquivos["motor_dir"]:
        _pdf_imagem_arquivo(pdf, arquivos["motor_dir"], x_dir, y, col, row_h)
    y += row_h + 0.8

    if arquivos["motor_topo"]:
        _pdf_imagem_arquivo(pdf, arquivos["motor_topo"], x_esq, y, col, row_h)
    y += row_h + 0.8

    if arquivos["jet_esq"]:
        _pdf_imagem_arquivo(pdf, arquivos["jet_esq"], x_esq, y, col, row_h)
    if arquivos["jet_dir"]:
        _pdf_imagem_arquivo(pdf, arquivos["jet_dir"], x_dir, y, col, row_h)
    pdf.set_y(y + row_h + 0.5)


def _diagramas_inspecao_horizontal(pdf: "OrdemServicoPDF") -> None:
    """Rodapé pág. 2 paisagem — cinco vistas em linha."""
    nomes = ("motor_esq", "motor_dir", "motor_topo", "jet_esq", "jet_dir")
    arquivos = [_arquivo_diagrama(n) for n in nomes]
    if not any(arquivos):
        return

    y0 = pdf.get_y() + 0.5
    limite = pdf.h - pdf.b_margin - 1
    if limite - y0 < 16:
        return

    pdf._font("B", 5.5)
    pdf.set_xy(pdf.l_margin, y0)
    pdf.cell(0, 2.8, "DIAGRAMAS PARA REGISTRO DE AVARIAS", ln=True)

    y = pdf.get_y() + 0.2
    n = len(nomes)
    gap = 1.5
    col_w = (pdf.epw - gap * (n - 1)) / n
    row_h = min(24, limite - y - 0.5)
    x = pdf.l_margin
    for path in arquivos:
        if path:
            _pdf_imagem_arquivo(pdf, path, x, y, col_w, row_h)
        x += col_w + gap
    pdf.set_y(y + row_h + 0.5)


def _config_bool(config: dict[str, Any] | None, chave: str, padrao: bool = False) -> bool:
    if not config:
        return padrao
    val = config.get(chave, padrao)
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "sim", "yes", "on")


def _qualificacao_entrega_rotulos(dados: dict[str, Any]) -> tuple[bool, bool, bool, str]:
    qual = _txt(dados.get("qualificacao_entrega"))
    outro_txt = _txt(dados.get("qual_outro_texto"))
    return (
        qual == "proprietario" or (not qual and _marcado(dados, "qualificacao_entrega", "proprietario")),
        qual == "marinheiro",
        qual == "outro",
        outro_txt,
    )


class OrdemServicoPDF(FPDF):
    def __init__(
        self,
        empresa: dict[str, str] | None = None,
        *,
        orientacao: str = "L",
    ) -> None:
        ori = "L" if orientacao.upper().startswith("L") else "P"
        super().__init__(orientation=ori, unit="mm", format="A4")
        self.empresa = empresa or {}
        self._familia = _registrar_fontes(self)
        self.orientacao = ori
        self.set_auto_page_break(auto=True, margin=8)
        self.set_margins(8, 8, 8)

    @property
    def epw(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def _font(self, estilo: str = "", tamanho: float = 9) -> None:
        self.set_font(self._familia, estilo, tamanho)

    def _quebrar_texto_em_largura(self, texto: str, largura: float) -> list[str]:
        """Quebra texto em linhas que cabem na largura (mm), respeitando \\n explícitos."""
        linhas: list[str] = []
        for paragrafo in str(texto or "").split("\n"):
            palavras = paragrafo.split()
            if not palavras:
                if linhas and linhas[-1]:
                    linhas.append("")
                continue
            atual = ""
            for palavra in palavras:
                candidato = f"{atual} {palavra}".strip()
                if not atual or self.get_string_width(candidato) <= largura:
                    atual = candidato
                else:
                    linhas.append(atual)
                    atual = palavra
            if atual:
                linhas.append(atual)
        return linhas

    def _renderizar_texto_em_caixa(
        self,
        x: float,
        y_box: float,
        largura: float,
        num_linhas: int,
        altura_linha: float,
        texto: str,
        *,
        tamanho_fonte: float = 7.5,
    ) -> None:
        """Renderiza texto alinhado às linhas pautadas da caixa (mesmo passo vertical)."""
        conteudo = _txt(texto)
        if not conteudo or num_linhas < 1:
            return

        linhas: list[str] = []
        tamanho_usado = tamanho_fonte
        for tamanho in (tamanho_fonte, tamanho_fonte - 0.5, tamanho_fonte - 1.0):
            if tamanho < 5.0:
                break
            self._font("", tamanho)
            candidatas = self._quebrar_texto_em_largura(conteudo, largura)
            linhas = candidatas
            tamanho_usado = tamanho
            if len(candidatas) <= num_linhas:
                break

        self._font("", tamanho_usado)
        altura_celula = max(2.5, altura_linha - 0.45)
        margem_topo = 0.35

        if len(linhas) > num_linhas:
            linhas = linhas[:num_linhas]
            ultima = linhas[-1]
            while ultima and self.get_string_width(f"{ultima}…") > largura and len(ultima) > 1:
                ultima = ultima[:-1]
            linhas[-1] = f"{ultima}…" if ultima else "…"

        for i, linha in enumerate(linhas):
            y = y_box + i * altura_linha + margem_topo
            self.set_xy(x, y)
            self.cell(largura, altura_celula, linha, border=0)

    def _titulo_secao(
        self,
        texto: str,
        tamanho: float = 7,
        *,
        x_ini: float | None = None,
        largura: float | None = None,
    ) -> None:
        self._font("B", tamanho)
        self.set_fill_color(220, 220, 220)
        w = largura if largura is not None else self.epw
        if x_ini is not None:
            self.set_x(x_ini)
        self.cell(w, 5, f" {texto}", ln=True, fill=True)
        self.ln(0.8)

    def _linha(self, rotulo: str, valor: str, largura_rotulo: float = 32) -> None:
        self._font("", 7)
        self.cell(largura_rotulo, 4, rotulo, border=0)
        self.cell(0, 4, valor or "-", ln=True)

    def _linha_escrita(
        self,
        rotulo: str,
        valor: str = "",
        *,
        x_ini: float | None = None,
        largura_total: float | None = None,
        altura: float = 7,
        espaco_apos: float = 1.2,
    ) -> None:
        """Campo com linha colada ao rótulo (ex.: NOME:__________)."""
        w_total = largura_total or self.epw
        x0 = x_ini if x_ini is not None else self.get_x()
        y = self.get_y()
        self._font("", 7.5)
        w_rot = self.get_string_width(rotulo) + 0.8
        self.set_xy(x0, y)
        self.cell(w_rot, 4.5, rotulo, border=0)
        texto = _txt(valor)
        x_lin_ini = x0 + w_rot
        x_fim = x0 + w_total
        if texto:
            self.set_xy(x_lin_ini, y)
            self.cell(max(x_fim - x_lin_ini, 1), 4.5, texto, border=0)
        else:
            self.line(x_lin_ini, y + 4, x_fim, y + 4)
        self.set_xy(x0, y + altura)
        self.ln(espaco_apos)

    def _linha_campos(
        self,
        campos: list[tuple[str, str, float]],
        *,
        x_ini: float | None = None,
        largura_total: float | None = None,
        altura: float = 7,
        espaco_apos: float = 1.2,
    ) -> None:
        """Vários campos na mesma linha, linha colada a cada rótulo."""
        w_total = largura_total or self.epw
        x0 = x_ini if x_ini is not None else self.l_margin
        y = self.get_y()
        self._font("", 7.5)
        total_peso = sum(c[2] for c in campos) or 1.0
        x = x0
        for rotulo, valor, peso in campos:
            w_slot = w_total * (peso / total_peso)
            w_rot = self.get_string_width(rotulo) + 0.8
            self.set_xy(x, y)
            self.cell(w_rot, 4.5, rotulo, border=0)
            texto = _txt(valor)
            x_lin = x + w_rot
            x_end = x + w_slot - 0.5
            if texto:
                self.set_xy(x_lin, y)
                self.cell(max(x_end - x_lin, 1), 4.5, texto, border=0)
            elif x_end > x_lin:
                self.line(x_lin, y + 4, x_end, y + 4)
            x += w_slot
        self.set_xy(x0, y + altura)
        self.ln(espaco_apos)

    def _titulos_secao_lado_a_lado(self, esquerda: str, direita: str | None = None) -> float:
        """Barra de seção em uma ou duas colunas. Retorna Y após os títulos."""
        if direita:
            meio = self.epw / 2 - 2
            self._font("B", 7)
            self.set_fill_color(220, 220, 220)
            self.cell(meio, 5, f" {esquerda}", fill=True, border=0)
            self.cell(4, 5, "", border=0)
            self.cell(meio, 5, f" {direita}", fill=True, ln=True)
        else:
            self._titulo_secao(esquerda)
        self.ln(0.8)
        return self.get_y()

    def _caixa_linhas_manuscrito(
        self,
        titulo: str,
        conteudo: str = "",
        *,
        num_linhas: int = 7,
        altura_linha: float = 7,
        espaco_apos: float = 2,
        x_ini: float | None = None,
        largura_total: float | None = None,
    ) -> None:
        """Caixa com linhas horizontais para escrita à mão."""
        x0 = x_ini if x_ini is not None else self.l_margin
        w_box = largura_total if largura_total is not None else self.epw
        self._titulo_secao(titulo, tamanho=7, x_ini=x0, largura=w_box)
        y0 = self.get_y()
        altura_total = num_linhas * altura_linha + 2
        self.rect(x0, y0, w_box, altura_total)
        self.set_draw_color(190, 190, 190)
        for i in range(1, num_linhas):
            y = y0 + i * altura_linha
            self.line(x0 + 1, y, x0 + w_box - 1, y)
        self.set_draw_color(0, 0, 0)
        if _txt(conteudo):
            self._renderizar_texto_em_caixa(
                x0 + 2, y0, w_box - 4, num_linhas, altura_linha, conteudo,
                tamanho_fonte=7.5,
            )
        self.set_y(y0 + altura_total + espaco_apos)

    def _bloco_tipo_os_direita(
        self,
        dados: dict[str, Any],
        *,
        x: float,
        y: float,
        largura: float,
    ) -> float:
        """TIPO DE O.S. em 2 colunas compactas (modelo horizontal)."""
        tipos = _lista_os_tipo(dados)
        self.set_xy(x, y)
        self._font("", 6.5)
        col_w = largura / 2 - 1
        meio = (len(_TIPOS_OS) + 1) // 2
        y_base = y
        for i, (val, rot) in enumerate(_TIPOS_OS):
            ok = val in tipos or _marcado(dados, "os_tipo", val)
            if i < meio:
                px, row = x, i
            else:
                px, row = x + col_w + 2, i - meio
            py = y_base + row * 4.3
            self.set_xy(px, py)
            self.cell(col_w, 4.2, f"{'(X)' if ok else '( )'} {rot}")
        return y_base + meio * 4.3 + 1

    def _linha_qualificacao_entrega(
        self,
        dados: dict[str, Any],
        *,
        x_ini: float | None = None,
        largura_total: float | None = None,
        outro_abaixo: bool = False,
    ) -> None:
        prop, marin, outro, outro_txt = _qualificacao_entrega_rotulos(dados)
        x0 = x_ini if x_ini is not None else self.get_x()
        w_total = largura_total or self.epw
        y = self.get_y()
        self._font("", 7.5)
        rot = "QUALIFICAÇÃO:"
        w_rot = self.get_string_width(rot) + 0.8
        self.set_xy(x0, y)
        self.cell(w_rot, 4.5, rot, border=0)

        if outro_abaixo:
            linha1 = (
                f"{'(X)' if prop else '( )'} PROPRIETÁRIO     "
                f"{'(X)' if marin else '( )'} MARINHEIRO"
            )
            self.set_xy(x0 + w_rot, y)
            self.cell(w_total - w_rot, 4.5, linha1, border=0)
            y2 = y + 5.2
            rot_outro = f"{'(X)' if outro else '( )'} OUTRO:"
            w_outro = self.get_string_width(rot_outro) + 0.8
            self.set_xy(x0 + w_rot, y2)
            self.cell(w_outro, 4.5, rot_outro, border=0)
            if outro_txt:
                self.cell(w_total - w_rot - w_outro, 4.5, outro_txt, border=0)
            else:
                x_lin = x0 + w_rot + w_outro
                self.line(x_lin, y2 + 4, x0 + w_total, y2 + 4)
            self.set_xy(x0, y2 + 7)
            self.ln(1)
            return

        rot_checks = (
            f"{'(X)' if prop else '( )'} PROPRIETÁRIO  "
            f"{'(X)' if marin else '( )'} MARINHEIRO  "
            f"{'(X)' if outro else '( )'} OUTRO:"
        )
        self.set_xy(x0 + w_rot, y)
        w_checks = self.get_string_width(rot_checks) + 0.8
        self.cell(w_checks, 4.5, rot_checks, border=0)
        if outro_txt:
            self.cell(w_total - w_rot - w_checks, 4.5, outro_txt, border=0)
        else:
            x_lin = x0 + w_rot + w_checks
            self.line(x_lin, y + 4, x0 + w_total, y + 4)
        self.set_xy(x0, y + 7)
        self.ln(1)

    def _campo_grade(self, campos: list[tuple[str, str, float]]) -> None:
        """Campos lado a lado: (rótulo, valor, largura_relativa 0-1)."""
        self._font("", 6.5)
        total = sum(c[2] for c in campos) or 1.0
        for rotulo, valor, peso in campos:
            w = self.epw * (peso / total)
            self.cell(w, 4, f"{rotulo} {valor or '_______________'}", border=0)
        self.ln(4)

    def _caixa_texto(
        self,
        titulo: str,
        conteudo: str,
        *,
        altura: float = 28,
        tamanho_fonte: float = 7,
    ) -> None:
        """Caixa com borda para textos longos (alegações, constatação, análise)."""
        self._titulo_secao(titulo, tamanho=6.5)
        y = self.get_y()
        self.rect(self.l_margin, y, self.epw, altura)
        self.set_xy(self.l_margin + 1.5, y + 1.5)
        self._font("", tamanho_fonte)
        texto = _txt(conteudo) or " "
        self.multi_cell(self.epw - 3, 3.2, texto, border=0)
        self.set_y(y + altura + 1.5)

    def _checkbox(self, texto: str, marcado: bool, largura: float = 0) -> None:
        w = largura or 0
        caixa = "(X)" if marcado else "( )"
        self.cell(w, 3.8, f"{caixa} {texto}", border=0)

    def _cabecalho_empresa(self, numero_os: int | str) -> None:
        nome = _txt(
            self.empresa.get("nome_fantasia") or self.empresa.get("razao_social"),
            "Oficina Náutica",
        )
        self._font("B", 11)
        self.cell(0, 5, nome, ln=True, align="C")
        endereco = _txt(self.empresa.get("endereco"))
        tel = _txt(self.empresa.get("telefone"))
        if endereco or tel:
            self._font("", 7)
            sub = " | ".join(p for p in (endereco, f"Tel: {tel}" if tel else "") if p)
            self.cell(0, 3.5, sub, ln=True, align="C")
        self.ln(1)
        self._font("B", 13)
        self.cell(0, 6, "ORDEM DE SERVIÇO", ln=True, align="C")
        self._font("B", 9)
        self.cell(0, 5, f"N° {numero_os}", ln=True, align="C")
        self.ln(1)


def _pagina_frente_horizontal(
    pdf: OrdemServicoPDF,
    dados: dict[str, Any],
    numero_os: int | str,
    *,
    exibir_tipo_os: bool = False,
) -> None:
    """Frente paisagem — mesmo conteúdo da pág. 1 vertical, layout compacto."""
    pdf.add_page()
    pdf._cabecalho_empresa(numero_os)
    pdf.ln(0.5)

    data_ent = _txt(dados.get("data_entrada"))
    pdf._linha_campos([
        ("DATA DE ENTRADA:", _fmt_data_br(data_ent) if data_ent else "", 0.28),
        ("NOME DO ATENDENTE:", _txt(dados.get("nome_atendente")), 0.42),
        ("ORÇAMENTO N°:", _txt(dados.get("orcamento_numero")), 0.30),
    ], espaco_apos=1, altura=5)

    meio = pdf.epw / 2 - 2
    w_ent = meio if exibir_tipo_os else pdf.epw
    y_sec = pdf._titulos_secao_lado_a_lado(
        "DADOS DA ENTREGA",
        "TIPO DE O.S." if exibir_tipo_os else None,
    )

    pdf.set_xy(pdf.l_margin, y_sec)
    pdf._linha_escrita(
        "ENTREGUE POR:", _txt(dados.get("entregue_por")),
        x_ini=pdf.l_margin, largura_total=w_ent, espaco_apos=0.4, altura=5,
    )
    pdf.set_x(pdf.l_margin)
    pdf._linha_qualificacao_entrega(
        dados, x_ini=pdf.l_margin, largura_total=w_ent, outro_abaixo=exibir_tipo_os,
    )
    pdf.set_x(pdf.l_margin)
    pdf._linha_escrita(
        "TELEFONE:", _txt(dados.get("entrega_telefone")),
        x_ini=pdf.l_margin, largura_total=w_ent, espaco_apos=0.3, altura=5,
    )
    y_fim_ent = pdf.get_y()

    y_fim_tipo = y_sec
    if exibir_tipo_os:
        y_fim_tipo = pdf._bloco_tipo_os_direita(
            dados, x=pdf.l_margin + meio + 4, y=y_sec, largura=meio,
        )

    pdf.set_y(max(y_fim_ent, y_fim_tipo) + 1)

    pdf._titulo_secao("DADOS DO CLIENTE", tamanho=6.5)
    pf = _marcado(dados, "tipo_pessoa", "pf")
    pj = _marcado(dados, "tipo_pessoa", "pj")
    pdf._linha_escrita("NOME:", _txt(dados.get("cliente_nome")), espaco_apos=0.4, altura=5)
    pdf._font("", 7)
    pdf.cell(0, 4, f"PESSOA:  {'(X)' if pf else '( )'} FÍSICA     {'(X)' if pj else '( )'} JURÍDICA", ln=True)
    pdf.ln(0.5)
    pdf._linha_escrita("ENDEREÇO:", _txt(dados.get("cliente_endereco")), espaco_apos=0.4, altura=5)
    pdf._linha_campos([
        ("N°:", _txt(dados.get("cliente_numero")), 0.10),
        ("BAIRRO:", _txt(dados.get("cliente_bairro")), 0.28),
        ("CIDADE:", _txt(dados.get("cliente_cidade")), 0.28),
        ("UF:", _txt(dados.get("cliente_estado")), 0.10),
        ("CEP:", _txt(dados.get("cliente_cep")), 0.24),
    ], espaco_apos=0.4, altura=5)
    pdf._linha_campos([
        ("CPF/CNPJ:", _txt(dados.get("cliente_cpf_cnpj")), 0.36),
        ("RG:", _txt(dados.get("cliente_rg")), 0.22),
        ("TEL:", _txt(dados.get("cliente_telefone")), 0.21),
        ("CEL:", _txt(dados.get("cliente_celular")), 0.21),
    ], espaco_apos=1, altura=5)

    pdf._titulo_secao("DADOS DA EMBARCAÇÃO", tamanho=6.5)
    tipo_emb = _txt(dados.get("tipo_embarcacao"))
    popa = tipo_emb == "motor_popa"
    moto = tipo_emb == "moto_aquatica"
    pdf._font("", 7)
    y_t = pdf.get_y()
    rot_t = "TIPO:"
    w_rot = pdf.get_string_width(rot_t) + 0.8
    pdf.set_xy(pdf.l_margin, y_t)
    pdf.cell(w_rot, 4, rot_t, border=0)
    pdf.cell(0, 4, f"{'(X)' if popa else '( )'} MOTOR DE POPA     {'(X)' if moto else '( )'} MOTO AQUÁTICA", ln=True)
    pdf.ln(0.5)
    pdf._linha_escrita("NOME:", _txt(dados.get("embarcacao_nome")), espaco_apos=0.4, altura=5)
    pdf._linha_campos([
        ("FABRICANTE:", _txt(dados.get("fabricante")), 0.34),
        ("MODELO:", _txt(dados.get("modelo")), 0.33),
        ("N° CHASSI:", _txt(dados.get("num_chassi")), 0.33),
    ], espaco_apos=0.4, altura=5)
    pdf._linha_campos([
        ("ANO/MOD:", _txt(dados.get("ano_modelo")), 0.50),
        ("N° MOTOR:", _txt(dados.get("num_motor")), 0.50),
    ], espaco_apos=0.4, altura=5)
    pdf._linha_escrita("MARINA:", _txt(dados.get("marina")), espaco_apos=1, altura=5)

    pdf._caixa_linhas_manuscrito(
        "ALEGAÇÕES / SOLICITAÇÕES DO CLIENTE",
        _txt(dados.get("alegacoes_cliente")),
        num_linhas=10,
        altura_linha=5,
        espaco_apos=0.5,
    )
    pdf._font("", 7)
    y_f = pdf.get_y()
    x0 = pdf.l_margin
    rot_data = "Data:"
    w_rot_data = pdf.get_string_width(rot_data) + 0.8
    pdf.set_xy(x0, y_f)
    pdf.cell(w_rot_data, 4, rot_data, border=0)
    pdf.cell(52 - w_rot_data, 4, _fmt_data_br(dados.get("alegacoes_data")), border=0)
    rot_sig = "Assinatura do responsável:"
    x_sig = x0 + 58
    w_sig = pdf.get_string_width(rot_sig) + 0.8
    pdf.set_xy(x_sig, y_f)
    pdf.cell(w_sig, 4, rot_sig, border=0)
    sig_x = x_sig + w_sig
    sig_w = x0 + pdf.epw - sig_x
    nome_resp = _nome_assinante_pdf(dados, "responsavel")
    if nome_resp:
        pdf.set_xy(sig_x, y_f - 3.5)
        pdf._font("", 6)
        pdf.cell(sig_w, 3, nome_resp, border=0)
    img_resp = _img_dataurl(dados.get("assinatura_responsavel"))
    if img_resp:
        pdf.rect(sig_x, y_f - 1, sig_w, 8)
        pdf.image(img_resp, x=sig_x + 0.5, y=y_f, w=sig_w - 1, h=7)
    else:
        pdf.line(sig_x, y_f + 3.5, x0 + pdf.epw, y_f + 3.5)


def _pagina_verso_horizontal(
    pdf: OrdemServicoPDF,
    dados: dict[str, Any],
    *,
    assinatura_tecnico: str | None,
    assinatura_cliente: str | None,
    assinatura_cliente_entrega: str | None,
) -> None:
    """Verso paisagem — fluxo igual ao PDF vertical, compacto para caber na folha."""
    pdf.add_page()

    _secao_checklist_acessorios_vertical(pdf, dados)

    meio = pdf.epw / 2 - 2
    y_rec = pdf.get_y()
    x_ent = pdf.l_margin + meio + 4
    pdf._font("B", 6.5)
    pdf.cell(meio, 3.5, "RECEPÇÃO", border=0)
    pdf.cell(4, 3.5, "", border=0)
    pdf.cell(meio, 3.5, "ENTREGA", ln=True)
    pdf._font("", 5.5)
    pdf.set_xy(pdf.l_margin, y_rec + 3.5)
    pdf.multi_cell(meio, 2.5, "Declaro ter deixado o veículo nas condições informadas nesta folha.", border=0)
    pdf.set_xy(x_ent, y_rec + 3.5)
    pdf.multi_cell(meio, 2.5, "Declaro ter recebido o veículo nas condições informadas nesta folha.", border=0)
    img_cli = _img_dataurl(assinatura_cliente)
    img_ent = _img_dataurl(assinatura_cliente_entrega)
    y_sig = y_rec + 10
    pdf.rect(pdf.l_margin, y_sig, meio, 10)
    pdf.rect(x_ent, y_sig, meio, 10)
    if img_cli:
        pdf.image(img_cli, x=pdf.l_margin + 1, y=y_sig + 1, w=meio - 2, h=8)
    if img_ent:
        pdf.image(img_ent, x=x_ent + 1, y=y_sig + 1, w=meio - 2, h=8)
    pdf.set_y(y_sig + 11)
    pdf._font("", 5.5)
    nome_rec = _nome_assinante_pdf(dados, "recepcao")
    nome_ent = _nome_assinante_pdf(dados, "entrega")
    pdf.cell(meio, 3, nome_rec or "Assinatura do cliente", border=0)
    pdf.cell(4, 3, "", border=0)
    pdf.cell(meio, 3, nome_ent or "Assinatura do cliente", ln=True)
    pdf.cell(meio, 3, f"Data: {_fmt_data_br(dados.get('recepcao_data'))}", border=0)
    pdf.cell(4, 3, "", border=0)
    pdf.cell(meio, 3, f"Data: {_fmt_data_br(dados.get('entrega_data'))}", ln=True)
    pdf.ln(0.5)

    meio_col = pdf.epw / 2 - 2
    gap_col = 4
    x_dir_col = pdf.l_margin + meio_col + gap_col
    alt_linha = 4.0
    num_lin = 5
    alt_caixa = num_lin * alt_linha + 2

    pdf._font("B", 5.5)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(meio_col, 3.8, " CONSTATAÇÃO DA SOLICITAÇÃO DO CLIENTE E DIAGNÓSTICO", fill=True, border=0)
    pdf.cell(gap_col, 3.8, "", border=0)
    pdf.cell(
        meio_col, 3.8,
        " ANÁLISE DOS REPAROS EFETUADOS E CONCLUSÃO / ORIENTAÇÕES AO CLIENTE",
        fill=True, ln=True,
    )
    pdf.ln(0.15)
    y_box = pdf.get_y()
    for x_off, conteudo in (
        (pdf.l_margin, _txt(dados.get("constatacao_diagnostico"))),
        (x_dir_col, _txt(dados.get("analise_reparos"))),
    ):
        pdf.rect(x_off, y_box, meio_col, alt_caixa)
        pdf.set_draw_color(190, 190, 190)
        for i in range(1, num_lin):
            pdf.line(x_off + 1, y_box + i * alt_linha, x_off + meio_col - 1, y_box + i * alt_linha)
        pdf.set_draw_color(0, 0, 0)
        if conteudo:
            pdf._renderizar_texto_em_caixa(
                x_off + 1.5, y_box, meio_col - 3, num_lin, alt_linha, conteudo,
                tamanho_fonte=5.5,
            )

    y_rod = y_box + alt_caixa + 0.25
    gar = _txt(dados.get("diag_garantia"))
    gar_txt = "(X) Sim ( ) Não" if gar == "sim" else ("( ) Sim (X) Não" if gar == "nao" else "( ) Sim ( ) Não")
    pdf.set_xy(pdf.l_margin, y_rod)
    pdf._font("", 5.5)
    pdf.multi_cell(
        meio_col, 2.4,
        f"Analista: {_txt(dados.get('diag_analista_nome'))}   "
        f"Data: {_fmt_data_br(dados.get('diag_data'))}   Garantia: {gar_txt}",
        border=0,
    )
    y_rod_dir = y_rod
    pdf.set_xy(x_dir_col, y_rod_dir)
    pdf.multi_cell(
        meio_col, 2.4,
        f"Analista: {_txt(dados.get('conclusao_analista_nome'))}   "
        f"Data: {_fmt_data_br(dados.get('conclusao_data'))}",
        border=0,
    )
    y_fim_diag = max(pdf.get_y(), y_rod + 2.4)
    img_tec = _img_dataurl(assinatura_tecnico)
    if img_tec:
        pdf.rect(pdf.l_margin, y_fim_diag, 48, 8)
        pdf.image(img_tec, x=pdf.l_margin + 1, y=y_fim_diag + 1, w=46, h=6)
        y_fim_diag += 9
    pdf.set_y(y_fim_diag + 0.3)

    pdf._font("", 5.5)
    pdf.multi_cell(
        0, 2.5,
        "Obs: Autorizo a realização dos serviços ora relacionados e tenho ciência de que tais "
        "serviços correrão às minhas expensas. (Art. 39 VI do CDC)",
    )
    pdf.ln(0.3)

    pdf._titulo_secao("FECHAMENTO DA ORDEM DE SERVIÇO", tamanho=6)
    pdf._font("", 5.5)
    valores = (
        ("M.O.:", dados.get("valor_mao_obra")),
        ("PEÇAS:", dados.get("valor_pecas")),
        ("ACESS.:", dados.get("valor_acessorios")),
        ("LUBRIF.:", dados.get("valor_lubrificantes")),
        ("OUTROS:", dados.get("valor_outros")),
    )
    partes = [f"{n} R$ {_fmt_moeda(v)}" for n, v in valores]
    total_txt = f"TOTAL: R$ {_fmt_moeda(dados.get('valor_total'))}"
    data_ret = f"Data retirada: {_fmt_data_br(dados.get('data_retirada'))}"
    pdf.cell(0, 3.2, f"{'   '.join(partes)}   {total_txt}   {data_ret}", ln=True)
    pdf.ln(0.2)

    _caixas_lado_a_lado_vertical(
        pdf,
        ("HISTÓRICO DE DOCUMENTOS", _txt(dados.get("historico_documentos"))),
        ("REQUISIÇÕES DE PEÇAS / VISTO CAIXA", _txt(dados.get("requisicoes_pecas"))),
        num_linhas=3,
        altura_linha=4,
        espaco_apos=0.8,
    )

    y_rodape = pdf.get_y()
    pdf._font("", 6)
    rot_sig = "Assinatura do cliente:"
    w_sig = pdf.get_string_width(rot_sig) + 0.8
    pdf.set_xy(pdf.l_margin, y_rodape)
    pdf.cell(w_sig, 3.5, rot_sig, border=0)
    sig_x = pdf.l_margin + w_sig
    sig_w = meio_col * 0.48
    sig_h = 7
    nome_aprov = _nome_assinante_pdf(dados, "aprovacao")
    if nome_aprov:
        pdf.set_xy(sig_x, y_rodape - 3.2)
        pdf._font("", 5.5)
        pdf.cell(sig_w, 3, nome_aprov, border=0)
    img_aprov = _img_dataurl(dados.get("assinatura_cliente_aprovacao"))
    if img_aprov:
        pdf.rect(sig_x, y_rodape - 0.5, sig_w, sig_h)
        pdf.image(img_aprov, x=sig_x + 0.4, y=y_rodape + 0.2, w=sig_w - 0.8, h=sig_h - 1.2)
    else:
        pdf.line(sig_x, y_rodape + 3, sig_x + sig_w, y_rodape + 3)
    rot_ap = "Data aprovação:"
    x_ap = sig_x + sig_w + 2
    w_ap = pdf.get_string_width(rot_ap) + 0.8
    pdf.set_xy(x_ap, y_rodape)
    pdf.cell(w_ap, 3.5, rot_ap, border=0)
    pdf.cell(meio_col - (x_ap - pdf.l_margin), 3.5, _fmt_data_br(dados.get("data_aprovacao")), border=0)

    y_orc = y_rodape
    rot_orc = "ORÇAMENTO N°:"
    w_orc = pdf.get_string_width(rot_orc) + 0.8
    pdf.set_xy(x_dir_col, y_orc)
    pdf.cell(w_orc, 3.5, rot_orc, border=0)
    orc_num = _txt(dados.get("orcamento_numero"))
    x_num = x_dir_col + w_orc
    w_num = 18
    if orc_num:
        pdf.cell(w_num, 3.5, orc_num, border=0)
    else:
        pdf.line(x_num, y_orc + 3, x_num + w_num, y_orc + 3)
    rot_elab = "DATA ELABORAÇÃO:"
    x_elab = x_num + w_num + 3
    w_elab = pdf.get_string_width(rot_elab) + 0.8
    pdf.set_xy(x_elab, y_orc)
    pdf.cell(w_elab, 3.5, rot_elab, border=0)
    pdf.cell(0, 3.5, _fmt_data_br(dados.get("data_elaboracao")), border=0)

    pdf.set_y(max(y_rodape + sig_h, y_orc + 3.5) + 0.3)

    _diagramas_inspecao_horizontal(pdf)


def _pagina1_vertical(
    pdf: OrdemServicoPDF,
    dados: dict[str, Any],
    numero_os: int | str,
    *,
    exibir_tipo_os: bool,
) -> None:
    """Página 1 retrato — ordem igual ao horizontal, linhas para escrita manual."""
    pdf.add_page()
    pdf._cabecalho_empresa(numero_os)
    pdf.ln(1.5)

    data_ent = _txt(dados.get("data_entrada"))
    pdf._linha_campos([
        ("DATA DE ENTRADA:", _fmt_data_br(data_ent) if data_ent else "", 0.28),
        ("NOME DO ATENDENTE:", _txt(dados.get("nome_atendente")), 0.42),
        ("ORÇAMENTO N°:", _txt(dados.get("orcamento_numero")), 0.30),
    ], espaco_apos=2)

    meio = pdf.epw / 2 - 2
    w_ent = meio if exibir_tipo_os else pdf.epw
    y_sec = pdf._titulos_secao_lado_a_lado(
        "DADOS DA ENTREGA",
        "TIPO DE O.S." if exibir_tipo_os else None,
    )

    pdf.set_xy(pdf.l_margin, y_sec)
    pdf._linha_escrita("ENTREGUE POR:", _txt(dados.get("entregue_por")), x_ini=pdf.l_margin, largura_total=w_ent, espaco_apos=0.8)
    pdf.set_x(pdf.l_margin)
    pdf._linha_qualificacao_entrega(
        dados,
        x_ini=pdf.l_margin,
        largura_total=w_ent,
        outro_abaixo=exibir_tipo_os,
    )
    pdf.set_x(pdf.l_margin)
    pdf._linha_escrita("TELEFONE:", _txt(dados.get("entrega_telefone")), x_ini=pdf.l_margin, largura_total=w_ent, espaco_apos=0.5)
    y_fim_ent = pdf.get_y()

    y_fim_tipo = y_sec
    if exibir_tipo_os:
        y_fim_tipo = pdf._bloco_tipo_os_direita(
            dados,
            x=pdf.l_margin + meio + 4,
            y=y_sec,
            largura=meio,
        )

    pdf.set_y(max(y_fim_ent, y_fim_tipo) + 2)

    pdf._titulo_secao("DADOS DO CLIENTE")
    pf = _marcado(dados, "tipo_pessoa", "pf")
    pj = _marcado(dados, "tipo_pessoa", "pj")
    pdf._linha_escrita("NOME:", _txt(dados.get("cliente_nome")), espaco_apos=0.8)
    pdf._font("", 7.5)
    y_p = pdf.get_y()
    pdf.set_xy(pdf.l_margin, y_p)
    pdf.cell(0, 4.5, f"PESSOA:  {'(X)' if pf else '( )'} FÍSICA     {'(X)' if pj else '( )'} JURÍDICA", ln=True)
    pdf.ln(1.2)
    pdf._linha_escrita("ENDEREÇO:", _txt(dados.get("cliente_endereco")), espaco_apos=0.8)
    pdf._linha_campos([
        ("N°:", _txt(dados.get("cliente_numero")), 0.10),
        ("BAIRRO:", _txt(dados.get("cliente_bairro")), 0.28),
        ("CIDADE:", _txt(dados.get("cliente_cidade")), 0.28),
        ("UF:", _txt(dados.get("cliente_estado")), 0.10),
        ("CEP:", _txt(dados.get("cliente_cep")), 0.24),
    ], espaco_apos=0.8)
    pdf._linha_campos([
        ("CPF/CNPJ:", _txt(dados.get("cliente_cpf_cnpj")), 0.36),
        ("RG:", _txt(dados.get("cliente_rg")), 0.22),
        ("TEL:", _txt(dados.get("cliente_telefone")), 0.21),
        ("CEL:", _txt(dados.get("cliente_celular")), 0.21),
    ], espaco_apos=2)

    pdf._titulo_secao("DADOS DA EMBARCAÇÃO")
    tipo_emb = _txt(dados.get("tipo_embarcacao"))
    popa = tipo_emb == "motor_popa"
    moto = tipo_emb == "moto_aquatica"
    pdf._font("", 7.5)
    y_t = pdf.get_y()
    pdf.set_xy(pdf.l_margin, y_t)
    rot_t = "TIPO:"
    w_rot = pdf.get_string_width(rot_t) + 0.8
    pdf.cell(w_rot, 4.5, rot_t, border=0)
    pdf.cell(0, 4.5, f"{'(X)' if popa else '( )'} MOTOR DE POPA     {'(X)' if moto else '( )'} MOTO AQUÁTICA", ln=True)
    pdf.ln(1.2)
    pdf._linha_escrita("NOME:", _txt(dados.get("embarcacao_nome")), espaco_apos=0.8)
    pdf._linha_campos([
        ("FABRICANTE:", _txt(dados.get("fabricante")), 0.34),
        ("MODELO:", _txt(dados.get("modelo")), 0.33),
        ("N° CHASSI:", _txt(dados.get("num_chassi")), 0.33),
    ], espaco_apos=0.8)
    pdf._linha_campos([
        ("ANO/MOD:", _txt(dados.get("ano_modelo")), 0.50),
        ("N° MOTOR:", _txt(dados.get("num_motor")), 0.50),
    ], espaco_apos=0.8)
    pdf._linha_escrita("MARINA:", _txt(dados.get("marina")), espaco_apos=2)

    pdf._caixa_linhas_manuscrito(
        "ALEGAÇÕES / SOLICITAÇÕES DO CLIENTE",
        _txt(dados.get("alegacoes_cliente")),
        num_linhas=9,
        altura_linha=7,
    )
    pdf._font("", 7.5)
    y_f = pdf.get_y()
    x0 = pdf.l_margin
    rot_data = "Data:"
    w_rot_data = pdf.get_string_width(rot_data) + 0.8
    pdf.set_xy(x0, y_f)
    pdf.cell(w_rot_data, 4.5, rot_data, border=0)
    pdf.set_xy(x0 + w_rot_data, y_f)
    pdf.cell(52 - w_rot_data, 4.5, _fmt_data_br(dados.get("alegacoes_data")), border=0)
    rot_sig = "Assinatura do responsável:"
    x_sig = x0 + 58
    pdf.set_xy(x_sig, y_f)
    w_sig = pdf.get_string_width(rot_sig) + 0.8
    pdf.cell(w_sig, 4.5, rot_sig, border=0)
    sig_x = x_sig + w_sig
    sig_w = x0 + pdf.epw - sig_x
    nome_resp = _nome_assinante_pdf(dados, "responsavel")
    if nome_resp:
        pdf.set_xy(sig_x, y_f - 3.5)
        pdf._font("", 6)
        pdf.cell(sig_w, 3, nome_resp, border=0)
    img_resp = _img_dataurl(dados.get("assinatura_responsavel"))
    if img_resp:
        pdf.rect(sig_x, y_f - 1, sig_w, 10)
        pdf.image(img_resp, x=sig_x + 0.5, y=y_f, w=sig_w - 1, h=9)
        pdf.set_y(y_f + 10)
    else:
        pdf.line(sig_x, y_f + 4, x0 + pdf.epw, y_f + 4)
        pdf.set_y(y_f + 5)


def _secao_checklist_acessorios_vertical(pdf: OrdemServicoPDF, dados: dict[str, Any]) -> None:
    """Topo da pág. 2 retrato — check-list compacto + acessórios lado a lado."""
    col_chk = pdf.epw * 0.58
    col_acc = pdf.epw - col_chk - 3
    x_acc = pdf.l_margin + col_chk + 3
    y0 = pdf.get_y()

    pdf._font("B", 6.5)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(col_chk, 4.5, " CHECK-LIST DE INSPEÇÃO", fill=True, border=0)
    pdf.cell(3, 4.5, "", border=0)
    pdf.cell(col_acc, 4.5, " ACOMPANHA ACESSÓRIOS", fill=True, ln=True)
    pdf.ln(0.4)

    y_start = pdf.get_y()
    pdf._font("", 5)
    pdf.set_xy(pdf.l_margin, y_start)
    pdf.multi_cell(col_chk, 2.4, _LEGENDA_INSPECAO, border=0)
    pdf.ln(0.15)

    w_item = col_chk * 0.66
    w_col = (col_chk - w_item) / 6
    pdf._font("B", 5.5)
    pdf.cell(w_item, 3.5, "Item", border=1)
    for letra in ("OK", "R", "A", "M", "E", "O"):
        pdf.cell(w_col, 3.5, letra, border=1, align="C")
    pdf.ln()

    pdf._font("", 5.5)
    for chave, rotulo in _INSPECAO_ITENS:
        val = _txt(dados.get(chave)).upper()
        pdf.cell(w_item, 3.4, rotulo[:40], border=1)
        for op in ("OK", "R", "A", "M", "E", "O"):
            pdf.cell(w_col, 3.4, "X" if val == op else "", border=1, align="C")
        pdf.ln()
    y_fim_chk = pdf.get_y()

    pdf.set_xy(x_acc, y_start)
    pdf._font("", 6)
    for chave, rotulo in _ACESSORIOS:
        v = _txt(dados.get(chave))
        sim = v == "sim"
        nao = v == "nao"
        pdf.set_x(x_acc)
        lbl = rotulo if len(rotulo) <= 26 else rotulo[:25] + "…"
        pdf.cell(col_acc * 0.58, 3.6, lbl, border=0)
        pdf._checkbox("Sim", sim, 10)
        pdf._checkbox("Não", nao, 10)
        pdf.ln(3.6)
    pdf.set_x(x_acc)
    rot_o = "Outro:"
    w_o = pdf.get_string_width(rot_o) + 0.5
    y_o = pdf.get_y()
    pdf.cell(w_o, 3.6, rot_o, border=0)
    outro = _txt(dados.get("acessorio_outro"))
    if outro:
        pdf.cell(col_acc - w_o, 3.6, outro, border=0)
    else:
        pdf.line(x_acc + w_o, y_o + 3, x_acc + col_acc, y_o + 3)
    y_fim_acc = pdf.get_y() + 4

    pdf.set_y(max(y_fim_chk, y_fim_acc) + 0.8)
    pdf._linha_escrita("Observações:", _txt(dados.get("checklist_observacoes")), espaco_apos=1.2)


def _caixas_lado_a_lado_vertical(
    pdf: OrdemServicoPDF,
    esq: tuple[str, str],
    dir_: tuple[str, str],
    *,
    num_linhas: int = 3,
    altura_linha: float = 5.5,
    espaco_apos: float = 1.5,
) -> None:
    """Duas caixas pautadas na mesma linha (histórico / requisições)."""
    meio = pdf.epw / 2 - 2
    titulo_e, conteudo_e = esq
    titulo_d, conteudo_d = dir_
    y0 = pdf.get_y()
    altura = num_linhas * altura_linha + 2

    pdf._font("B", 6)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(meio, 4, f" {titulo_e}", fill=True, border=0)
    pdf.cell(4, 4, "", border=0)
    pdf.cell(meio, 4, f" {titulo_d}", fill=True, ln=True)
    pdf.ln(0.3)

    y_box = pdf.get_y()
    for x_off, conteudo in ((pdf.l_margin, conteudo_e), (pdf.l_margin + meio + 4, conteudo_d)):
        pdf.rect(x_off, y_box, meio, altura)
        pdf.set_draw_color(190, 190, 190)
        for i in range(1, num_linhas):
            pdf.line(x_off + 1, y_box + i * altura_linha, x_off + meio - 1, y_box + i * altura_linha)
        pdf.set_draw_color(0, 0, 0)
        if _txt(conteudo):
            pdf._renderizar_texto_em_caixa(
                x_off + 1.5, y_box, meio - 3, num_linhas, altura_linha, conteudo,
                tamanho_fonte=6,
            )
    pdf.set_y(y_box + altura + espaco_apos)


def _pagina2_vertical(
    pdf: OrdemServicoPDF,
    dados: dict[str, Any],
    *,
    assinatura_tecnico: str | None,
    assinatura_cliente: str | None,
    assinatura_cliente_entrega: str | None,
) -> None:
    pdf.add_page()

    _secao_checklist_acessorios_vertical(pdf, dados)

    meio = pdf.epw / 2 - 2
    y_rec = pdf.get_y()
    x_ent = pdf.l_margin + meio + 4
    pdf._font("B", 6.5)
    pdf.cell(meio, 4, "RECEPÇÃO", border=0)
    pdf.cell(4, 4, "", border=0)
    pdf.cell(meio, 4, "ENTREGA", ln=True)
    pdf._font("", 5.5)
    pdf.set_xy(pdf.l_margin, y_rec + 4)
    pdf.multi_cell(meio, 2.8, "Declaro ter deixado o veículo nas condições informadas nesta folha.", border=0)
    pdf.set_xy(x_ent, y_rec + 4)
    pdf.multi_cell(meio, 2.8, "Declaro ter recebido o veículo nas condições informadas nesta folha.", border=0)
    img_cli = _img_dataurl(assinatura_cliente)
    img_ent = _img_dataurl(assinatura_cliente_entrega)
    y_sig = y_rec + 12
    pdf.rect(pdf.l_margin, y_sig, meio, 12)
    pdf.rect(x_ent, y_sig, meio, 12)
    if img_cli:
        pdf.image(img_cli, x=pdf.l_margin + 1, y=y_sig + 1, w=meio - 2, h=10)
    if img_ent:
        pdf.image(img_ent, x=x_ent + 1, y=y_sig + 1, w=meio - 2, h=10)
    pdf.set_y(y_sig + 14)
    pdf._font("", 6)
    nome_rec = _nome_assinante_pdf(dados, "recepcao")
    nome_ent = _nome_assinante_pdf(dados, "entrega")
    pdf.cell(meio, 3.5, nome_rec or "Assinatura do cliente", border=0)
    pdf.cell(4, 3.5, "", border=0)
    pdf.cell(meio, 3.5, nome_ent or "Assinatura do cliente", ln=True)
    pdf.cell(meio, 3.5, f"Data: {_fmt_data_br(dados.get('recepcao_data'))}", border=0)
    pdf.cell(4, 3.5, "", border=0)
    pdf.cell(meio, 3.5, f"Data: {_fmt_data_br(dados.get('entrega_data'))}", ln=True)
    pdf.ln(1)

    pdf._caixa_linhas_manuscrito(
        "CONSTATAÇÃO DA SOLICITAÇÃO DO CLIENTE E DIAGNÓSTICO",
        _txt(dados.get("constatacao_diagnostico")),
        num_linhas=6,
        altura_linha=5,
        espaco_apos=0.5,
    )
    gar = _txt(dados.get("diag_garantia"))
    gar_txt = "(X) Sim ( ) Não" if gar == "sim" else ("( ) Sim (X) Não" if gar == "nao" else "( ) Sim ( ) Não")
    pdf._font("", 6.5)
    pdf.cell(0, 4,
             f"Analista: {_txt(dados.get('diag_analista_nome'))}   "
             f"Data: {_fmt_data_br(dados.get('diag_data'))}   Garantia: {gar_txt}",
             ln=True)
    img_tec = _img_dataurl(assinatura_tecnico)
    if img_tec:
        y = pdf.get_y() + 0.5
        pdf.rect(pdf.l_margin, y, 55, 11)
        pdf.image(img_tec, x=pdf.l_margin + 1, y=y + 1, w=53, h=9)
        pdf.set_y(y + 12)
    pdf.ln(0.8)

    pdf._caixa_linhas_manuscrito(
        "ANÁLISE DOS REPAROS EFETUADOS E CONCLUSÃO / ORIENTAÇÕES AO CLIENTE",
        _txt(dados.get("analise_reparos")),
        num_linhas=6,
        altura_linha=5,
        espaco_apos=0.5,
    )
    pdf._font("", 6.5)
    pdf.cell(
        0, 4,
        f"Analista: {_txt(dados.get('conclusao_analista_nome'))}   "
        f"Data: {_fmt_data_br(dados.get('conclusao_data'))}",
        ln=True,
    )
    pdf.ln(0.8)

    pdf._linha_campos([
        ("ORÇAMENTO N°:", _txt(dados.get("orcamento_numero")), 0.50),
        ("DATA ELABORAÇÃO:", _fmt_data_br(dados.get("data_elaboracao")), 0.50),
    ], espaco_apos=0.5)
    pdf._font("", 6)
    pdf.multi_cell(
        0, 3,
        "Obs: Autorizo a realização dos serviços ora relacionados e tenho ciência de que tais "
        "serviços correrão às minhas expensas. (Art. 39 VI do CDC)",
    )
    pdf.ln(0.8)

    pdf._titulo_secao("FECHAMENTO DA ORDEM DE SERVIÇO", tamanho=6.5)
    pdf._font("", 6.5)
    valores = (
        ("M.O.:", dados.get("valor_mao_obra")),
        ("PEÇAS:", dados.get("valor_pecas")),
        ("ACESS.:", dados.get("valor_acessorios")),
        ("LUBRIF.:", dados.get("valor_lubrificantes")),
        ("OUTROS:", dados.get("valor_outros")),
    )
    partes = [f"{n} R$ {_fmt_moeda(v)}" for n, v in valores]
    pdf.cell(0, 4, "   ".join(partes), ln=True)
    pdf._font("B", 7.5)
    pdf.cell(0, 4.5, f"TOTAL: R$ {_fmt_moeda(dados.get('valor_total'))}", ln=True)
    pdf._font("", 6.5)
    pdf.cell(0, 4, f"Data retirada: {_fmt_data_br(dados.get('data_retirada'))}", ln=True)
    pdf.ln(0.5)

    _caixas_lado_a_lado_vertical(
        pdf,
        ("HISTÓRICO DE DOCUMENTOS", _txt(dados.get("historico_documentos"))),
        ("REQUISIÇÕES DE PEÇAS / VISTO CAIXA", _txt(dados.get("requisicoes_pecas"))),
        num_linhas=3,
    )

    pdf._font("", 6.5)
    y_f = pdf.get_y()
    rot_sig = "Assinatura do cliente:"
    w_sig = pdf.get_string_width(rot_sig) + 0.8
    pdf.set_xy(pdf.l_margin, y_f)
    pdf.cell(w_sig, 4, rot_sig, border=0)
    sig_x = pdf.l_margin + w_sig
    sig_w = pdf.epw * 0.24
    sig_h = 7.5
    nome_aprov = _nome_assinante_pdf(dados, "aprovacao")
    if nome_aprov:
        pdf.set_xy(sig_x, y_f - 3)
        pdf._font("", 6)
        pdf.cell(sig_w, 3, nome_aprov, border=0)
    img_aprov = _img_dataurl(dados.get("assinatura_cliente_aprovacao"))
    if img_aprov:
        pdf.rect(sig_x, y_f - 0.5, sig_w, sig_h)
        pdf.image(img_aprov, x=sig_x + 0.4, y=y_f + 0.2, w=sig_w - 0.8, h=sig_h - 1.2)
    else:
        pdf.line(sig_x, y_f + 3.2, sig_x + sig_w, y_f + 3.2)
    rot_ap = "Data aprovação:"
    x_data = sig_x + sig_w + 3
    w_ap = pdf.get_string_width(rot_ap) + 0.8
    pdf.set_xy(x_data, y_f)
    pdf.cell(w_ap, 4, rot_ap, border=0)
    pdf.cell(0, 4, _fmt_data_br(dados.get("data_aprovacao")), border=0)
    pdf.set_y(max(y_f + sig_h, y_f + 4) + 0.8)

    _diagramas_inspecao_vertical(pdf)


def _montar_pdf_vertical(
    pdf: OrdemServicoPDF,
    dados: dict[str, Any],
    numero_os: int | str,
    *,
    assinatura_tecnico: str | None,
    assinatura_cliente: str | None,
    assinatura_cliente_entrega: str | None,
    exibir_tipo_os: bool = False,
) -> None:
    _pagina1_vertical(pdf, dados, numero_os, exibir_tipo_os=exibir_tipo_os)
    _pagina2_vertical(
        pdf,
        dados,
        assinatura_tecnico=assinatura_tecnico,
        assinatura_cliente=assinatura_cliente,
        assinatura_cliente_entrega=assinatura_cliente_entrega,
    )


def gerar_pdf_ordem_servico(
    dados: dict[str, Any],
    *,
    numero_os: int | str = "-",
    assinatura_tecnico: str | None = None,
    assinatura_cliente: str | None = None,
    assinatura_cliente_entrega: str | None = None,
    empresa: dict[str, str] | None = None,
    orientacao: str | None = None,
    config: dict[str, Any] | None = None,
    itens_checklist: list[dict[str, Any]] | None = None,
) -> bytes:
    """Monta o PDF em memória a partir do dicionário do formulário."""
    dados = preparar_campos_diagnostico_os_para_impressao(dados, itens=itens_checklist)
    assinatura_tecnico = assinatura_tecnico or dados.get("assinatura_tecnico")
    assinatura_cliente = assinatura_cliente or dados.get("assinatura_cliente")
    assinatura_cliente_entrega = assinatura_cliente_entrega or dados.get("assinatura_cliente_entrega")
    exibir_tipo_os = _config_bool(config, "exibir_tipo_os", False)

    ori = normalizar_orientacao(orientacao)
    pdf = OrdemServicoPDF(empresa=empresa, orientacao=ori)

    if ori == "L":
        _pagina_frente_horizontal(pdf, dados, numero_os, exibir_tipo_os=exibir_tipo_os)
        _pagina_verso_horizontal(
            pdf,
            dados,
            assinatura_tecnico=assinatura_tecnico,
            assinatura_cliente=assinatura_cliente,
            assinatura_cliente_entrega=assinatura_cliente_entrega,
        )
    else:
        _montar_pdf_vertical(
            pdf,
            dados,
            numero_os,
            assinatura_tecnico=assinatura_tecnico,
            assinatura_cliente=assinatura_cliente,
            assinatura_cliente_entrega=assinatura_cliente_entrega,
            exibir_tipo_os=exibir_tipo_os,
        )

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def dados_os_de_registro(
    row: Any,
    assinatura_tecnico: str | None = None,
    assinatura_cliente: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Extrai payload JSON + número da O.S. a partir de sqlite3.Row."""
    dados = json.loads(row["dados_json"] or "{}")
    dados.pop("pdf_orientacao", None)
    if assinatura_tecnico:
        dados["assinatura_tecnico"] = assinatura_tecnico
    if assinatura_cliente:
        dados["assinatura_cliente"] = assinatura_cliente
    return dados, int(row["numero_os"])
