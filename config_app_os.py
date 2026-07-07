"""Configuração local do App O.S. (config.ini + sincronização com .env)."""

from __future__ import annotations

import configparser
import hashlib
import os
import secrets
import sys
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "config.ini"
ENV_FILENAME = ".env"
SENHA_SUPORTE_PADRAO = "suporte"
_PBKDF2_ITER = 120_000

SECOES_PADRAO: dict[str, dict[str, str]] = {
    "app": {
        "database_path": "",
        "modo_independente": "0",
        "instalacao_modo": "inno",
        "icone_janela": "",
    },
    "servidor": {
        "host": "0.0.0.0",
        "porta": "5000",
    },
    "ngrok": {
        "domain": "",
        "authtoken": "",
        "public_url": "",
        "exe": "",
    },
    "suporte": {
        "senha_salt": "",
        "senha_hash": "",
    },
}


def diretorio_instalacao(base: Path | None = None) -> Path:
    if base is not None:
        return base.resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def diretorio_recursos() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return Path(__file__).resolve().parent


def caminho_config(install_dir: Path | None = None) -> Path:
    return diretorio_instalacao(install_dir) / CONFIG_FILENAME


def _hash_senha(senha: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, _PBKDF2_ITER)
    return digest.hex()


def _aplicar_hash_senha(parser: configparser.ConfigParser, senha: str) -> None:
    if "suporte" not in parser:
        parser["suporte"] = {}
    salt = secrets.token_hex(16)
    parser["suporte"]["senha_salt"] = salt
    parser["suporte"]["senha_hash"] = _hash_senha(senha, salt)


def _garantir_senha_suporte(parser: configparser.ConfigParser) -> bool:
    """Garante hash da senha. Retorna True se criou hash novo (ambiente dev)."""
    if "suporte" not in parser:
        parser["suporte"] = {}
    salt = parser["suporte"].get("senha_salt", "").strip()
    digest = parser["suporte"].get("senha_hash", "").strip()
    if salt and digest:
        return False
    _aplicar_hash_senha(parser, SENHA_SUPORTE_PADRAO)
    return True


def definir_senha_suporte(
    senha: str,
    install_dir: Path | None = None,
    parser: configparser.ConfigParser | None = None,
) -> None:
    texto = (senha or "").strip()
    if len(texto) < 4:
        raise ValueError("A senha de suporte deve ter pelo menos 4 caracteres.")
    install = diretorio_instalacao(install_dir)
    cfg = parser or configparser.ConfigParser()
    if not parser:
        path = install / CONFIG_FILENAME
        if path.is_file():
            cfg.read(path, encoding="utf-8")
        for secao, valores in SECOES_PADRAO.items():
            if secao not in cfg:
                cfg[secao] = {}
            for chave, padrao in valores.items():
                cfg[secao].setdefault(chave, padrao)
    _aplicar_hash_senha(cfg, texto)
    salvar_config(cfg, install)


def alterar_senha_suporte(
    senha_atual: str,
    senha_nova: str,
    install_dir: Path | None = None,
) -> tuple[bool, str]:
    if not validar_senha_suporte(senha_atual, install_dir):
        return False, "Senha atual incorreta."
    try:
        definir_senha_suporte(senha_nova, install_dir)
    except ValueError as exc:
        return False, str(exc)
    return True, "Senha de suporte alterada com sucesso."


def ler_senha_suporte_build(raiz_projeto: Path | None = None) -> str:
    """Le senha definida em barquiboboriginal/suporte_build.json para o instalador."""
    raiz = (raiz_projeto or Path(__file__).resolve().parent).resolve()
    json_path = raiz / "barquiboboriginal" / "suporte_build.json"
    env_path = raiz / "barquiboboriginal" / "suporte_build.env"
    if json_path.is_file():
        import json

        dados = json.loads(json_path.read_text(encoding="utf-8"))
        senha = str(dados.get("senha_suporte") or "").strip()
        if senha:
            return senha
        raise ValueError(f"Campo 'senha_suporte' vazio em {json_path}")
    if env_path.is_file():
        for linha in env_path.read_text(encoding="utf-8").splitlines():
            bruta = linha.strip()
            if not bruta or bruta.startswith("#"):
                continue
            if bruta.upper().startswith("SENHA_SUPORTE="):
                senha = bruta.split("=", 1)[1].strip().strip('"').strip("'")
                if senha:
                    return senha
        raise ValueError(f"SENHA_SUPORTE nao encontrada em {env_path}")
    raise FileNotFoundError(
        "Crie barquiboboriginal/suporte_build.json (ou suporte_build.env) "
        "com a senha usada na geracao do instalador."
    )


def preparar_config_instalador(
    config_ini: Path,
    senha_suporte: str,
    *,
    sobrescrever: bool = True,
) -> None:
    """Grava config.ini do instalador com hash da senha de suporte (sem texto puro)."""
    config_ini = config_ini.resolve()
    parser = configparser.ConfigParser()
    if config_ini.is_file() and not sobrescrever:
        parser.read(config_ini, encoding="utf-8")
    for secao, valores in SECOES_PADRAO.items():
        if secao not in parser:
            parser[secao] = {}
        for chave, padrao in valores.items():
            if secao == "suporte" and chave in {"senha_salt", "senha_hash"}:
                continue
            parser[secao].setdefault(chave, padrao)
    _aplicar_hash_senha(parser, senha_suporte)
    config_ini.parent.mkdir(parents=True, exist_ok=True)
    with config_ini.open("w", encoding="utf-8") as fh:
        parser.write(fh)


def garantir_config(install_dir: Path | None = None) -> configparser.ConfigParser:
    install = diretorio_instalacao(install_dir)
    path = install / CONFIG_FILENAME
    parser = configparser.ConfigParser()
    if path.is_file():
        parser.read(path, encoding="utf-8")
    for secao, valores in SECOES_PADRAO.items():
        if secao not in parser:
            parser[secao] = {}
        for chave, padrao in valores.items():
            parser[secao].setdefault(chave, padrao)
    senha_nova = _garantir_senha_suporte(parser)
    if not path.is_file() or senha_nova:
        salvar_config(parser, install)
    return parser


def parser_para_dict(parser: configparser.ConfigParser) -> dict[str, dict[str, str]]:
    return {secao: dict(parser[secao]) for secao in parser.sections()}


def dict_para_parser(dados: dict[str, Any]) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    for secao, valores in dados.items():
        if not isinstance(valores, dict):
            continue
        parser[secao] = {str(k): str(v) for k, v in valores.items()}
    _garantir_senha_suporte(parser)
    return parser

def salvar_config(
    parser: configparser.ConfigParser | dict[str, Any],
    install_dir: Path | None = None,
) -> Path:
    install = diretorio_instalacao(install_dir)
    if isinstance(parser, dict):
        parser = dict_para_parser(parser)
    _garantir_senha_suporte(parser)
    path = install / CONFIG_FILENAME
    install.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        parser.write(fh)
    sincronizar_env(install, parser)
    aplicar_variaveis_ambiente(parser, install)
    return path


def validar_senha_suporte(senha: str, install_dir: Path | None = None) -> bool:
    parser = garantir_config(install_dir)
    salt = parser["suporte"].get("senha_salt", "").strip()
    esperado = parser["suporte"].get("senha_hash", "").strip()
    if not salt or not esperado:
        return False
    return secrets.compare_digest(_hash_senha(senha or "", salt), esperado)


def caminho_banco_independente(install_dir: Path | None = None) -> Path:
    pasta = diretorio_instalacao(install_dir) / "dados"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / "oficina_independente.db"


def resolver_caminho_banco(
    install_dir: Path | None = None,
    parser: configparser.ConfigParser | None = None,
) -> Path:
    install = diretorio_instalacao(install_dir)
    cfg = parser or garantir_config(install)
    if cfg["app"].get("modo_independente", "0").strip() in {"1", "true", "True", "sim"}:
        from banco_independente import garantir_banco_independente

        destino = caminho_banco_independente(install)
        garantir_banco_independente(destino)
        return destino.resolve()

    bruto = cfg["app"].get("database_path", "").strip()
    if bruto:
        candidato = Path(bruto)
        if not candidato.is_absolute():
            candidato = (install / candidato).resolve()
        else:
            candidato = candidato.resolve()
        if candidato.is_dir():
            candidato = (candidato / "oficina_nautica.db").resolve()
        return candidato

    # fallback dev: pasta irmã Crotrole_adm
    fallback = (install.parent / "Crotrole_adm" / "oficina_nautica.db").resolve()
    return fallback


def aplicar_variaveis_ambiente(
    parser: configparser.ConfigParser,
    install_dir: Path | None = None,
) -> None:
    install = diretorio_instalacao(install_dir)
    db = resolver_caminho_banco(install, parser)
    os.environ["DATABASE_PATH"] = str(db)
    os.environ["SERVIDOR_HOST"] = parser["servidor"].get("host", "0.0.0.0").strip() or "0.0.0.0"
    os.environ["SERVIDOR_PORTA"] = parser["servidor"].get("porta", "5000").strip() or "5000"
    dominio = parser["ngrok"].get("domain", "").strip()
    public_url = parser["ngrok"].get("public_url", "").strip()
    if dominio and not public_url:
        public_url = f"https://{dominio}"
    if dominio:
        os.environ["NGROK_DOMAIN"] = dominio
    else:
        os.environ.pop("NGROK_DOMAIN", None)
    if public_url:
        os.environ["OS_PUBLIC_URL"] = public_url.rstrip("/")
    else:
        os.environ.pop("OS_PUBLIC_URL", None)
    token = parser["ngrok"].get("authtoken", "").strip()
    if token:
        os.environ["NGROK_AUTHTOKEN"] = token
    exe = parser["ngrok"].get("exe", "").strip()
    if exe:
        os.environ["NGROK_EXE"] = exe


def sincronizar_env(
    install_dir: Path | None = None,
    parser: configparser.ConfigParser | None = None,
) -> Path:
    install = diretorio_instalacao(install_dir)
    cfg = parser or garantir_config(install)
    linhas = [
        f"DATABASE_PATH={resolver_caminho_banco(install, cfg)}",
        f"SERVIDOR_HOST={cfg['servidor'].get('host', '0.0.0.0')}",
        f"SERVIDOR_PORTA={cfg['servidor'].get('porta', '5000')}",
    ]
    dominio = cfg["ngrok"].get("domain", "").strip()
    public_url = cfg["ngrok"].get("public_url", "").strip()
    token = cfg["ngrok"].get("authtoken", "").strip()
    exe = cfg["ngrok"].get("exe", "").strip()
    if dominio:
        linhas.append(f"NGROK_DOMAIN={dominio}")
    if public_url:
        linhas.append(f"OS_PUBLIC_URL={public_url.rstrip('/')}")
    elif dominio:
        linhas.append(f"OS_PUBLIC_URL=https://{dominio}")
    if token:
        linhas.append(f"NGROK_AUTHTOKEN={token}")
    if exe:
        linhas.append(f"NGROK_EXE={exe}")
    destino = install / ENV_FILENAME
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return destino


def preparar_ambiente_instalacao(install_dir: Path | None = None) -> configparser.ConfigParser:
    install = diretorio_instalacao(install_dir)
    parser = garantir_config(install)
    sincronizar_env(install, parser)
    aplicar_variaveis_ambiente(parser, install)
    return parser


def resumo_config(parser: configparser.ConfigParser, install_dir: Path | None = None) -> dict[str, str]:
    install = diretorio_instalacao(install_dir)
    db = resolver_caminho_banco(install, parser)
    return {
        "database_path": str(db),
        "database_existe": "sim" if db.is_file() else "nao",
        "modo_independente": parser["app"].get("modo_independente", "0"),
        "host": parser["servidor"].get("host", "0.0.0.0"),
        "porta": parser["servidor"].get("porta", "5000"),
        "ngrok_domain": parser["ngrok"].get("domain", ""),
        "public_url": parser["ngrok"].get("public_url", ""),
        "icone_janela": parser["app"].get("icone_janela", ""),
    }


def resolver_icone_janela(
    install_dir: Path | None = None,
    parser: configparser.ConfigParser | None = None,
) -> Path | None:
    """Retorna caminho do .ico da janela (configuravel ou padrao embutido)."""
    install = diretorio_instalacao(install_dir)
    cfg = parser or garantir_config(install)
    personalizado = cfg["app"].get("icone_janela", "").strip()
    if personalizado:
        caminho = Path(personalizado)
        if not caminho.is_absolute():
            caminho = (install / caminho).resolve()
        if caminho.is_file():
            return caminho

    recursos = diretorio_recursos()
    padroes = [
        install / "icone_os_digital.ico",
        install / "icone_janela.ico",
        recursos / "icone_os_digital.ico",
        Path(__file__).resolve().parent / "build_executavel" / "icone_os_digital.ico",
    ]
    for candidato in padroes:
        if candidato.is_file():
            return candidato.resolve()
    return None


TEXTO_AJUDA_SUPORTE = """COMO ENCONTRAR AS INFORMACOES

1) Caminho do banco (oficina_nautica.db)
   - Normalmente fica na pasta do Sistema Oficina.
   - Exemplo: C:\\Program Files\\Sistema Oficina\\oficina_nautica.db
   - Ou em AppData do usuario, dependendo da instalacao.
   - Use [Procurar] e selecione o arquivo .db ou a pasta da oficina.

2) IP interno (rede Wi-Fi)
   - Abra o Prompt de Comando e digite: ipconfig
   - Procure "IPv4" na rede Wi-Fi/Ethernet ativa.
   - O app ficara em: http://SEU_IP:PORTA
   - No mesmo computador use: http://127.0.0.1:PORTA

3) Ngrok (acesso externo / 4G)
   - Crie conta em https://dashboard.ngrok.com
   - Authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
   - Dominio fixo gratuito: https://dashboard.ngrok.com/domains
   - Cole o dominio (sem https) em NGROK Domain.
   - URL publica completa vai em OS Public URL (ex: https://meu-dominio.ngrok-free.dev)

4) Modo Independente
   - Use quando NAO houver Sistema Oficina neste PC.
   - O app cria banco limpo em dados/oficina_independente.db.

5) Senha do painel de suporte
   - Definida na geracao do instalador (pasta barquiboboriginal do projeto).
   - Nunca aparece em texto puro no PC do cliente (somente hash no config.ini).
   - Para alterar depois: painel Config > aba Seguranca > Alterar senha de suporte.
   - Guarde a senha em local seguro; nao ha recuperacao automatica.

6) Anti-copia
   - A instalacao fica vinculada ao equipamento.
   - Copiar a pasta para outro PC exige autorizacao com senha de suporte.

7) Icone da janela (logo da empresa)
   - No painel de suporte, aba Geral, campo Icone da janela.
   - Selecione um arquivo .ico (recomendado) ou .png.
   - Se vazio, usa o icone padrao do App OS Digital.
   - O icone aparece na barra de titulo e na barra de tarefas.
"""
