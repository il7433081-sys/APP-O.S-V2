"""Âncora anti-cópia do App O.S. Digital (vínculo ao equipamento)."""

from __future__ import annotations

import hashlib
import json
import secrets
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from config_app_os import diretorio_instalacao

ANCHOR_FILENAME = ".app_os_instalacao.json"
ANCHOR_VERSAO = 1
_REGISTRY_VALUE = "AppOsAnchor"


def obter_identificador_maquina() -> str:
    import platform

    partes = [platform.node().strip().casefold()]
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            ) as chave:
                guid, _ = winreg.QueryValueEx(chave, "MachineGuid")
                partes.append(str(guid).strip())
        except OSError:
            pass
    bruto = "|".join(p for p in partes if p)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()[:32]


def _registry_key_path(install_dir: Path) -> str:
    digest = hashlib.sha256(str(install_dir.resolve()).casefold().encode("utf-8")).hexdigest()[:12]
    return rf"Software\AppOSDigital\{{{digest}}}"


def _app_data_anchor(install_dir: Path) -> Path:
    base = Path.home() / "AppData" / "Local" / "AppOSDigital"
    digest = hashlib.sha256(str(install_dir.resolve()).casefold().encode("utf-8")).hexdigest()[:16]
    return base / digest / ANCHOR_FILENAME


def _resolver_caminhos(install_dir: Path) -> tuple[Path, Path]:
    primario = (install_dir / ANCHOR_FILENAME).resolve()
    backup = _app_data_anchor(install_dir).resolve()
    return primario, backup


def _dados_validos(data: Any) -> bool:
    return isinstance(data, dict) and bool(data.get("versao") and data.get("instalacao_uuid"))


def _ler_arquivo(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if _dados_validos(data) else None


def _ler_registry(install_dir: Path) -> dict[str, Any] | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _registry_key_path(install_dir)) as chave:
            texto, _ = winreg.QueryValueEx(chave, _REGISTRY_VALUE)
        data = json.loads(str(texto))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return data if _dados_validos(data) else None


def _gravar_registry(install_dir: Path, dados: dict[str, Any]) -> None:
    if sys.platform != "win32":
        return
    try:
        import winreg

        payload = dict(dados)
        payload["install_dir"] = str(install_dir.resolve())
        chave = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _registry_key_path(install_dir))
        winreg.SetValueEx(
            chave,
            _REGISTRY_VALUE,
            0,
            winreg.REG_SZ,
            json.dumps(payload, ensure_ascii=False),
        )
        winreg.CloseKey(chave)
    except OSError:
        pass


def _gravar_arquivos(install_dir: Path, dados: dict[str, Any]) -> None:
    primario, backup = _resolver_caminhos(install_dir)
    texto = json.dumps(dados, ensure_ascii=False, indent=2)
    primario.parent.mkdir(parents=True, exist_ok=True)
    backup.parent.mkdir(parents=True, exist_ok=True)
    primario.write_text(texto, encoding="utf-8")
    backup.write_text(texto, encoding="utf-8")


def _gravar_anchor(install_dir: Path, dados: dict[str, Any]) -> None:
    _gravar_arquivos(install_dir, dados)
    _gravar_registry(install_dir, dados)


def ler_anchor(install_dir: Path | None = None, *, restaurar: bool = True) -> dict[str, Any] | None:
    install = diretorio_instalacao(install_dir)
    primario, backup = _resolver_caminhos(install)
    for path in (primario, backup):
        data = _ler_arquivo(path)
        if data is not None:
            return data
    registro = _ler_registry(install)
    if registro is not None and restaurar:
        _gravar_arquivos(install, registro)
    return registro


def anchor_existe(install_dir: Path | None = None) -> bool:
    return ler_anchor(install_dir) is not None


def registrar_instalacao(install_dir: Path | None = None) -> dict[str, Any]:
    install = diretorio_instalacao(install_dir)
    existente = ler_anchor(install, restaurar=False) or {}
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dados = {
        "versao": ANCHOR_VERSAO,
        "instalacao_uuid": str(existente.get("instalacao_uuid") or secrets.token_hex(16)),
        "install_dir": str(install.resolve()),
        "maquina_id": obter_identificador_maquina(),
        "criado_em": str(existente.get("criado_em") or agora),
        "anti_copia_ativo": 1,
        "anti_copia_dias": max(1, int(existente.get("anti_copia_dias") or 5)),
        "anti_copia_ultimo_acesso": agora,
    }
    _gravar_anchor(install, dados)
    return dados


def registrar_acesso(install_dir: Path | None = None) -> None:
    install = diretorio_instalacao(install_dir)
    data = ler_anchor(install)
    if data is None:
        registrar_instalacao(install)
        return
    data["anti_copia_ultimo_acesso"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _gravar_anchor(install, data)


def precisa_autorizar_maquina(install_dir: Path | None = None) -> bool:
    install = diretorio_instalacao(install_dir)
    data = ler_anchor(install)
    if data is None:
        return False
    mid = str(data.get("maquina_id") or "").strip()
    if not mid:
        return False
    return mid != obter_identificador_maquina()


def autorizar_maquina_atual(install_dir: Path | None = None) -> None:
    install = diretorio_instalacao(install_dir)
    data = ler_anchor(install)
    if data is None:
        registrar_instalacao(install)
        return
    data["maquina_id"] = obter_identificador_maquina()
    data["install_dir"] = str(install.resolve())
    data["anti_copia_ultimo_acesso"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _gravar_anchor(install, data)


def verificar_instalacao(install_dir: Path | None = None) -> tuple[bool, str]:
    install = diretorio_instalacao(install_dir)
    if not anchor_existe(install):
        registrar_instalacao(install)
        return True, "Instalacao registrada neste equipamento."
    if precisa_autorizar_maquina(install):
        return (
            False,
            "Esta copia do App OS Digital nao esta autorizada neste computador. "
            "Abra o painel de suporte (engrenagem) e autorize com a senha tecnica.",
        )
    registrar_acesso(install)
    return True, "Instalacao autorizada."
