#!/usr/bin/env python3
"""
Importa / atualiza kits de revisão no módulo Pré-Orçamentos.

Cruza os nomes abaixo com a tabela `catalogo` do banco principal (oficina_nautica.db)
via busca SQL LIKE. Se achar, usa descrição e preço do catálogo; senão R$ 0,00 + aviso.

Uso (na pasta do app):
    python importar_kits_exemplo.py
    python importar_kits_exemplo.py --dry-run
    python importar_kits_exemplo.py --somente-yamaha
    python importar_kits_exemplo.py --somente-mercury
    python importar_kits_exemplo.py --somente-suzuki
    python importar_kits_exemplo.py --kit "YAMAHA F60"

Kits já existentes com o mesmo modelo são ATUALIZADOS (não duplica).
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from typing import Any

INSTALL_DIR = Path(__file__).resolve().parent
if str(INSTALL_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALL_DIR))

from config_app_os import preparar_ambiente_instalacao, resolver_caminho_banco
from pre_orcamentos import (
    caminho_banco_pre_orcamentos,
    garantir_banco_pre_orcamentos,
    importar_kits_motor_lote,
    init_pre_orcamentos_tabelas,
)

# ---------------------------------------------------------------------------
# Como cadastrar um kit novo:
#   KITS_REVISAO.append(
#       definir_kit(
#           "NOME DO MOTOR",
#           "opcional: nota sobre o motor",
#           ("Nome exato da peça no catálogo", quantidade),
#           ("Outra peça", 1),
#       )
#   )
# ---------------------------------------------------------------------------


def definir_kit(
    modelo_motor: str,
    nota: str = "",
    *itens: tuple[str, float],
) -> dict[str, Any]:
    lista: list[dict[str, Any]] = []
    for entrada in itens:
        if len(entrada) < 2:
            continue
        descricao = str(entrada[0]).strip()
        qtd = float(entrada[1])
        if not descricao or qtd <= 0:
            continue
        lista.append(
            {
                "descricao": descricao,
                "quantidade": qtd,
                "valor_unitario": 0.0,
                "tipo": "peca",
            }
        )
    return {
        "modelo_motor": modelo_motor.strip(),
        "nota": nota.strip(),
        "lista_pecas": lista,
    }


# Químicos / consumíveis reutilizados em vários kits
_Q_F60_4T = (
    ("Desengraxante Express", 1),
    ("Desengripante", 1),
    ("Limpa Contato", 1),
    ("Silicone Spray", 1),
)

_Q_2T = (
    ("Descarbonizante", 1),
    ("Desengraxante Express", 1),
    ("Silicone Spray", 1),
)

_Q_MERCURY_4T = (
    ("Desengraxante", 1),
    ("Silicone Spray", 1),
)

KITS_REVISAO: list[dict[str, Any]] = [
    # --- Kits base (nomes da oficina) ----------------------------------------
    definir_kit(
        "YAMAHA F60 (4 Tempos)",
        "Revisão 4 tempos — F60",
        ("Óleo de Motor 20W-50 (5L)", 1),
        ("Filtro de Óleo 5GH", 1),
        ("Elemento do Filtro de Combustível 6D8", 1),
        ("Filtro de Linha 6C5", 1),
        ("Elemento Separador de Combustível", 1),
        ("Filtro da Bomba de Alta Pressão", 1),
        ("Velas de Ignição DPR6B-91", 4),
        *_Q_F60_4T,
    ),
    definir_kit(
        "YAMAHA 40 (2 Tempos)",
        "Revisão 2 tempos — 40 HP",
        ("Óleo da Rabeta SAE-90", 1),
        ("Gaxetas do Bujão da Rabeta", 2),
        ("Velas de Ignição BR7HS-10", 2),
        ("Anodo da Cabeça de Força", 1),
        ("Diafragma da Bomba de Combustível", 1),
        ("Capa do Botão de Partida", 1),
        ("Bulbo de Combustível 5/16", 1),
        *_Q_2T,
    ),
    definir_kit(
        "MERCURY F60 (4 Tempos - EFI)",
        "Revisão 4T EFI — F60",
        ("Filtro de Linha", 1),
        ("Elemento Papel Filtro 68V", 1),
        ("Filtro da Bomba Interna FSM", 1),
        ("Junta da Cuba do FSM", 1),
        ("Kit Reparo da Bomba Flutuadora", 1),
        ("Velas de Ignição Champion RA8HC", 4),
        ("Óleo Hidráulico (Trim)", 1),
        ("Limpeza de Bico (Fluido)", 1),
        ("Abraçadeiras Plásticas", 4),
        *_Q_MERCURY_4T,
    ),
    definir_kit(
        "MERCURY 30",
        "Revisão 2 tempos — 30 HP",
        ("Válvula Termoestática", 1),
        ("Junta da Válvula Termoestática", 1),
        ("Óleo de Rabeta", 1),
        ("Gaxetas dos Bujões da Rabeta", 2),
        ("Protetor de Polo de Bateria", 1),
        ("Descarbonizante", 1),
        ("Silicone Spray", 1),
    ),
    # --- Kits adicionais (mesmo padrão de revisão) ---------------------------
    definir_kit(
        "YAMAHA F90 (4 Tempos)",
        "Revisão 4T — F90",
        ("Óleo de Motor 20W-50 (5L)", 1),
        ("Filtro de Óleo 5GH", 1),
        ("Elemento do Filtro de Combustível 6D8", 1),
        ("Filtro de Linha 6C5", 1),
        ("Elemento Separador de Combustível", 1),
        ("Velas de Ignição DPR6B-91", 4),
        *_Q_F60_4T,
    ),
    definir_kit(
        "YAMAHA F115 (4 Tempos)",
        "Revisão 4T — F115",
        ("Óleo de Motor 20W-50 (5L)", 2),
        ("Filtro de Óleo 5GH", 1),
        ("Elemento do Filtro de Combustível 6D8", 1),
        ("Filtro de Linha 6C5", 1),
        ("Elemento Separador de Combustível", 1),
        ("Filtro da Bomba de Alta Pressão", 1),
        ("Velas de Ignição DPR6B-91", 4),
        *_Q_F60_4T,
    ),
    definir_kit(
        "YAMAHA 25 (2 Tempos)",
        "Revisão 2T — 25 HP",
        ("Óleo da Rabeta SAE-90", 1),
        ("Gaxetas do Bujão da Rabeta", 2),
        ("Velas de Ignição BR7HS-10", 1),
        ("Anodo da Cabeça de Força", 1),
        ("Diafragma da Bomba de Combustível", 1),
        ("Bulbo de Combustível 5/16", 1),
        *_Q_2T,
    ),
    definir_kit(
        "MERCURY 40 HP (2 Tempos)",
        "Revisão 2T — 40 HP",
        ("Óleo de Rabeta", 1),
        ("Gaxetas dos Bujões da Rabeta", 2),
        ("Velas de Ignição BR7HS-10", 2),
        ("Válvula Termoestática", 1),
        ("Junta da Válvula Termoestática", 1),
        ("Protetor de Polo de Bateria", 1),
        ("Descarbonizante", 1),
        ("Silicone Spray", 1),
    ),
    definir_kit(
        "MERCURY 90 HP (4 Tempos EFI)",
        "Revisão 4T EFI — 90 HP",
        ("Filtro de Linha", 1),
        ("Elemento Papel Filtro 68V", 1),
        ("Filtro da Bomba Interna FSM", 1),
        ("Junta da Cuba do FSM", 1),
        ("Kit Reparo da Bomba Flutuadora", 1),
        ("Velas de Ignição Champion RA8HC", 4),
        ("Óleo Hidráulico (Trim)", 1),
        ("Limpeza de Bico (Fluido)", 1),
        ("Abraçadeiras Plásticas", 4),
        *_Q_MERCURY_4T,
    ),
    definir_kit(
        "SUZUKI DF40 (4 Tempos)",
        "Revisão 4T — DF40",
        ("Óleo de Motor 20W-50 (5L)", 1),
        ("Filtro de Óleo Suzuki A31", 1),
        ("Elemento Filtro Suzuki", 1),
        ("Filtro de Linha", 1),
        ("Velas de Ignição DPR6B-91", 4),
        ("Desengraxante Express", 1),
        ("Silicone Spray", 1),
    ),
    definir_kit(
        "SUZUKI DF60 (4 Tempos)",
        "Revisão 4T — DF60",
        ("Óleo de Motor 20W-50 (5L)", 1),
        ("Filtro de Óleo Suzuki A31", 1),
        ("Elemento Filtro Suzuki", 1),
        ("Filtro de Linha", 1),
        ("Elemento Separador de Combustível", 1),
        ("Velas de Ignição DPR6B-91", 4),
        ("Desengraxante Express", 1),
        ("Limpa Contato", 1),
        ("Silicone Spray", 1),
    ),
    definir_kit(
        "SUZUKI DF90 (4 Tempos)",
        "Revisão 4T — DF90",
        ("Óleo de Motor 20W-50 (5L)", 2),
        ("Filtro de Óleo Suzuki A31", 1),
        ("Elemento Filtro Suzuki", 1),
        ("Filtro de Linha", 1),
        ("Elemento Separador de Combustível", 1),
        ("Filtro da Bomba de Alta Pressão", 1),
        ("Velas de Ignição DPR6B-91", 4),
        ("Desengraxante Express", 1),
        ("Desengripante", 1),
        ("Silicone Spray", 1),
    ),
]


def _normalizar_busca(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", texto or "")
    sem_acentos = "".join(ch for ch in sem_acentos if not unicodedata.combining(ch))
    return sem_acentos.casefold()


def _tokens_busca(nome: str) -> list[str]:
    """Gera termos para LIKE a partir do nome informado no kit."""
    base = re.sub(r"\s*\([^)]*\)", "", nome or "").strip()
    tokens: list[str] = []
    if base:
        tokens.append(base)
    partes = re.split(r"[,/\-–]+", base)
    for p in partes:
        p = p.strip()
        if len(p) >= 4:
            tokens.append(p)
    for palavra in re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", nome or ""):
        if palavra.isdigit() and len(palavra) < 3:
            continue
        tokens.append(palavra)
    vistos: set[str] = set()
    saida: list[str] = []
    for t in tokens:
        chave = _normalizar_busca(t)
        if chave and chave not in vistos:
            vistos.add(chave)
            saida.append(t)
    return saida


def _registrar_funcao_norm(conn: sqlite3.Connection) -> None:
    conn.create_function("NORM", 1, _normalizar_busca, deterministic=True)


def _buscar_linha_catalogo_like(
    conn: sqlite3.Connection,
    termo: str,
) -> sqlite3.Row | None:
    termo = (termo or "").strip()
    if not termo:
        return None
    like = f"%{termo}%"
    norm = f"%{_normalizar_busca(termo)}%"
    return conn.execute(
        """
        SELECT id, descricao, valor_unitario
        FROM catalogo
        WHERE (categoria = 'PEÇA' OR categoria = 'PECA' OR UPPER(categoria) LIKE '%PE%')
          AND (
                descricao LIKE ? COLLATE NOCASE
             OR NORM(descricao) LIKE ?
             OR codigo_barras LIKE ? COLLATE NOCASE
          )
        ORDER BY
            CASE
                WHEN NORM(descricao) = NORM(?) THEN 0
                WHEN descricao LIKE ? COLLATE NOCASE THEN 1
                WHEN NORM(descricao) LIKE ? THEN 2
                ELSE 3
            END,
            length(descricao) ASC
        LIMIT 1
        """,
        (like, norm, like, termo, termo, norm),
    ).fetchone()


def resolver_item_catalogo_like(
    conn: sqlite3.Connection,
    nome_kit: str,
) -> tuple[dict[str, Any], bool, str]:
    """
    Busca preço no catálogo. Retorna (item, encontrou, mensagem_aviso).
    Mantém o nome do kit se não achar; usa descrição do catálogo se achar.
    """
    item: dict[str, Any] = {
        "descricao": nome_kit.strip(),
        "quantidade": 1,
        "valor_unitario": 0.0,
        "tipo": "peca",
    }
    for termo in _tokens_busca(nome_kit):
        row = _buscar_linha_catalogo_like(conn, termo)
        if row is not None:
            item["catalogo_id"] = int(row["id"])
            item["descricao"] = str(row["descricao"] or nome_kit).strip()
            item["valor_unitario"] = round(float(row["valor_unitario"] or 0), 2)
            return item, True, ""
    aviso = f"AVISO: não encontrado no catálogo — '{nome_kit}' (ficou R$ 0,00)"
    return item, False, aviso


def montar_kit_com_precos(
    conn_cat: sqlite3.Connection,
    kit_def: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    avisos: list[str] = []
    itens_saida: list[dict[str, Any]] = []
    for bruto in kit_def.get("lista_pecas") or []:
        nome = str(bruto.get("descricao") or "").strip()
        qtd = float(bruto.get("quantidade") or 1)
        item, ok, aviso = resolver_item_catalogo_like(conn_cat, nome)
        item["quantidade"] = qtd
        item["tipo"] = str(bruto.get("tipo") or "peca")
        itens_saida.append(item)
        if aviso:
            avisos.append(aviso)
        elif not ok:
            avisos.append(f"AVISO: sem preço — '{nome}'")
    total = round(
        sum(float(i.get("quantidade") or 0) * float(i.get("valor_unitario") or 0) for i in itens_saida),
        2,
    )
    return (
        {
            "modelo_motor": kit_def["modelo_motor"],
            "lista_pecas": itens_saida,
            "preco_base": total,
        },
        avisos,
    )


def filtrar_kits(
    *,
    somente_yamaha: bool = False,
    somente_mercury: bool = False,
    somente_suzuki: bool = False,
    modelo_kit: str | None = None,
) -> list[dict[str, Any]]:
    saida = list(KITS_REVISAO)
    if somente_yamaha:
        saida = [k for k in saida if k["modelo_motor"].upper().startswith("YAMAHA")]
    elif somente_mercury:
        saida = [k for k in saida if k["modelo_motor"].upper().startswith("MERCURY")]
    elif somente_suzuki:
        saida = [k for k in saida if k["modelo_motor"].upper().startswith("SUZUKI")]
    if modelo_kit:
        alvo = modelo_kit.strip().casefold()
        saida = [k for k in saida if k["modelo_motor"].strip().casefold() == alvo]
    return saida


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importa/atualiza kits de revisão no Pré-Orçamentos."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Só mostra o que seria gravado, sem alterar o banco.",
    )
    parser.add_argument("--somente-yamaha", action="store_true")
    parser.add_argument("--somente-mercury", action="store_true")
    parser.add_argument("--somente-suzuki", action="store_true")
    parser.add_argument(
        "--kit",
        metavar="MODELO",
        help='Importa só um kit, ex.: --kit "YAMAHA F60 (4 Tempos)"',
    )
    parser.add_argument(
        "--listar",
        action="store_true",
        help="Lista os modelos de kit definidos no script e sai.",
    )
    args = parser.parse_args()

    if args.listar:
        print("Kits definidos no script:\n")
        for k in KITS_REVISAO:
            n = len(k.get("lista_pecas") or [])
            nota = k.get("nota") or ""
            print(f"  • {k['modelo_motor']} ({n} itens)" + (f" — {nota}" if nota else ""))
        return 0

    preparar_ambiente_instalacao(INSTALL_DIR)
    db_principal = resolver_caminho_banco(INSTALL_DIR)
    db_pre = caminho_banco_pre_orcamentos(INSTALL_DIR)

    if not db_principal.is_file():
        print(f"ERRO: banco principal não encontrado: {db_principal}")
        return 1

    garantir_banco_pre_orcamentos(db_pre)

    selecionados = filtrar_kits(
        somente_yamaha=args.somente_yamaha,
        somente_mercury=args.somente_mercury,
        somente_suzuki=args.somente_suzuki,
        modelo_kit=args.kit,
    )
    if not selecionados:
        print("Nenhum kit corresponde ao filtro.")
        return 1

    conn_cat = sqlite3.connect(db_principal, timeout=30)
    conn_cat.row_factory = sqlite3.Row
    _registrar_funcao_norm(conn_cat)

    kits_prontos: list[dict[str, Any]] = []
    todos_avisos: list[str] = []

    try:
        print(f"Banco catálogo: {db_principal}")
        print(f"Banco pré-orçamentos: {db_pre}")
        print(f"Kits a processar: {len(selecionados)}\n")

        for kit_def in selecionados:
            kit, avisos = montar_kit_com_precos(conn_cat, kit_def)
            kits_prontos.append(kit)
            todos_avisos.extend(avisos)
            com_preco = sum(1 for i in kit["lista_pecas"] if float(i.get("valor_unitario") or 0) > 0)
            print(
                f"  • {kit['modelo_motor']}: {len(kit['lista_pecas'])} itens, "
                f"{com_preco} com preço — total R$ {kit['preco_base']:.2f}"
            )
            for av in avisos:
                print(f"      {av}")
            print()
    finally:
        conn_cat.close()

    if args.dry_run:
        print("(dry-run — nada gravado)")
        if todos_avisos:
            print(f"\nResumo: {len(todos_avisos)} item(ns) sem correspondência no catálogo.")
        return 0

    conn_pre = sqlite3.connect(db_pre, timeout=30)
    conn_pre.row_factory = sqlite3.Row
    try:
        init_pre_orcamentos_tabelas(conn_pre)
        res = importar_kits_motor_lote(conn_pre, kits_prontos)
        conn_pre.commit()
    finally:
        conn_pre.close()

    print(f"Concluído: {res['criados']} criado(s), {res['atualizados']} atualizado(s).")
    if res.get("erros"):
        print("Erros:")
        for e in res["erros"]:
            print(f"  - {e}")
    if todos_avisos:
        print(f"\n{len(todos_avisos)} aviso(s) de peça não encontrada — revise no terminal acima.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
