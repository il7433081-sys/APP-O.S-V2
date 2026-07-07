"""Painel de configuracao tecnica do App O.S. Digital."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from config_app_os import (
    TEXTO_AJUDA_SUPORTE,
    alterar_senha_suporte,
    garantir_config,
    parser_para_dict,
    salvar_config,
    validar_senha_suporte,
)
from seguranca_app_os import autorizar_maquina_atual, precisa_autorizar_maquina


class DialogoSenhaSuporte(tk.Toplevel):
    def __init__(self, master: tk.Misc, install_dir: Path, on_ok: Callable[[], None]) -> None:
        super().__init__(master)
        self.install_dir = install_dir
        self.on_ok = on_ok
        self.title("Acesso tecnico")
        self.geometry("420x220")
        self.configure(bg="#0b1220")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ttk.Label(
            self,
            text="Painel de Suporte Tecnico",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", padx=18, pady=(18, 6))
        ttk.Label(
            self,
            text="Informe a senha de suporte para continuar.",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=18)

        self.campo = ttk.Entry(self, show="*", width=42, font=("Segoe UI", 11))
        self.campo.pack(padx=18, pady=14)
        self.campo.focus_set()
        self.campo.bind("<Return>", lambda _e: self._confirmar())

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=18, pady=(4, 16))
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="Entrar", command=self._confirmar).pack(side="right")

    def _confirmar(self) -> None:
        if not validar_senha_suporte(self.campo.get(), self.install_dir):
            messagebox.showerror("Acesso negado", "Senha de suporte incorreta.", parent=self)
            return
        self.destroy()
        self.on_ok()


class PainelConfiguracao(tk.Toplevel):
    def __init__(self, master: tk.Misc, install_dir: Path, on_save: Callable[[], None]) -> None:
        super().__init__(master)
        self.install_dir = install_dir
        self.on_save = on_save
        self.parser = garantir_config(install_dir)
        self.title("Configuracao do App OS Digital")
        self.geometry("860x640")
        self.minsize(820, 600)
        self.configure(bg="#0b1220")
        self.transient(master)

        topo = ttk.Frame(self, padding=(16, 14))
        topo.pack(fill="x")
        ttk.Label(
            topo,
            text="Painel de Configuracao do Desenvolvedor",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            topo,
            text="Ajuste banco, rede interna, ngrok e modo independente sem editar arquivos manualmente.",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self._aba_geral = ttk.Frame(notebook, padding=14)
        self._aba_servidor = ttk.Frame(notebook, padding=14)
        self._aba_ngrok = ttk.Frame(notebook, padding=14)
        self._aba_ajuda = ttk.Frame(notebook, padding=14)
        self._aba_seg = ttk.Frame(notebook, padding=14)
        notebook.add(self._aba_geral, text=" Geral ")
        notebook.add(self._aba_servidor, text=" Servidor ")
        notebook.add(self._aba_ngrok, text=" Ngrok ")
        notebook.add(self._aba_ajuda, text=" Ajuda ")
        notebook.add(self._aba_seg, text=" Seguranca ")

        self._montar_geral()
        self._montar_servidor()
        self._montar_ngrok()
        self._montar_ajuda()
        self._montar_seguranca()

        rodape = ttk.Frame(self, padding=(16, 10))
        rodape.pack(fill="x")
        ttk.Button(rodape, text="Cancelar", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(rodape, text="Salvar configuracao", command=self._salvar).pack(side="right")

    def _campo(self, pai: ttk.Frame, rotulo: str, linha: int, largura: int = 64) -> ttk.Entry:
        ttk.Label(pai, text=rotulo).grid(row=linha, column=0, sticky="w", pady=6)
        campo = ttk.Entry(pai, width=largura, font=("Consolas", 10))
        campo.grid(row=linha, column=1, sticky="ew", pady=6, padx=(10, 0))
        pai.columnconfigure(1, weight=1)
        return campo

    def _montar_geral(self) -> None:
        f = self._aba_geral
        self.var_indep = tk.BooleanVar(
            value=self.parser["app"].get("modo_independente", "0") in {"1", "true", "True"}
        )
        self.campo_db = self._campo(f, "Caminho do banco (.db ou pasta)", 0, 70)
        self.campo_db.insert(0, self.parser["app"].get("database_path", ""))
        ttk.Button(f, text="Procurar...", command=self._procurar_banco).grid(
            row=1, column=1, sticky="w", padx=(10, 0)
        )
        self.campo_icone = self._campo(f, "Icone da janela (.ico recomendado)", 2, 70)
        self.campo_icone.insert(0, self.parser["app"].get("icone_janela", ""))
        ttk.Button(f, text="Procurar icone...", command=self._procurar_icone).grid(
            row=3, column=1, sticky="w", padx=(10, 0)
        )
        ttk.Label(
            f,
            text="Logo da empresa na barra de titulo. Vazio = icone padrao do App OS.",
            font=("Segoe UI", 9),
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Checkbutton(
            f,
            text="Modo Independente (banco limpo local, sem Sistema Oficina)",
            variable=self.var_indep,
            command=self._toggle_independente,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(14, 4))
        ttk.Label(
            f,
            text="Quando ativo, ignora o caminho acima e usa dados/oficina_independente.db",
            font=("Segoe UI", 9),
        ).grid(row=6, column=0, columnspan=2, sticky="w")
        self._toggle_independente()

    def _montar_servidor(self) -> None:
        f = self._aba_servidor
        self.campo_host = self._campo(f, "Host interno", 0, 30)
        self.campo_host.insert(0, self.parser["servidor"].get("host", "0.0.0.0"))
        self.campo_porta = self._campo(f, "Porta", 1, 12)
        self.campo_porta.insert(0, self.parser["servidor"].get("porta", "5000"))
        ttk.Label(
            f,
            text="Use 0.0.0.0 para aceitar celular/tablet na mesma rede Wi-Fi.",
            font=("Segoe UI", 9),
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _montar_ngrok(self) -> None:
        f = self._aba_ngrok
        self.campo_domain = self._campo(f, "Dominio ngrok (sem https)", 0, 50)
        self.campo_domain.insert(0, self.parser["ngrok"].get("domain", ""))
        self.campo_public = self._campo(f, "URL publica (OS_PUBLIC_URL)", 1, 70)
        self.campo_public.insert(0, self.parser["ngrok"].get("public_url", ""))
        self.campo_token = self._campo(f, "Authtoken ngrok", 2, 70)
        self.campo_token.insert(0, self.parser["ngrok"].get("authtoken", ""))
        self.campo_ngrok_exe = self._campo(f, "Caminho ngrok.exe (opcional)", 3, 70)
        self.campo_ngrok_exe.insert(0, self.parser["ngrok"].get("exe", ""))
        ttk.Button(f, text="Procurar ngrok.exe...", command=self._procurar_ngrok).grid(
            row=4, column=1, sticky="w", padx=(10, 0)
        )

    def _montar_ajuda(self) -> None:
        texto = tk.Text(self._aba_ajuda, wrap="word", font=("Segoe UI", 10), height=24)
        texto.pack(fill="both", expand=True)
        texto.insert("1.0", TEXTO_AJUDA_SUPORTE)
        texto.configure(state="disabled")

    def _montar_seguranca(self) -> None:
        f = self._aba_seg
        status = "AUTORIZADA" if not precisa_autorizar_maquina(self.install_dir) else "PENDENTE"
        ttk.Label(f, text=f"Status desta instalacao: {status}", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(0, 10)
        )
        ttk.Label(
            f,
            text=(
                "Protecao anti-copia: a instalacao fica vinculada ao equipamento.\n"
                "Se copiar a pasta para outro PC, autorize abaixo com a senha de suporte.\n"
                "A ancora e salva na pasta de instalacao, AppData e Registro do Windows."
            ),
            justify="left",
            font=("Segoe UI", 10),
        ).pack(anchor="w")
        ttk.Button(
            f,
            text="Autorizar este computador",
            command=self._autorizar_maquina,
        ).pack(anchor="w", pady=(16, 8))

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=12)
        ttk.Label(f, text="Alterar senha de suporte", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(0, 8)
        )
        ttk.Label(
            f,
            text="Use a senha atual para definir uma nova. Minimo 4 caracteres.",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 8))

        quadro = ttk.Frame(f)
        quadro.pack(anchor="w", fill="x")
        ttk.Label(quadro, text="Senha atual").grid(row=0, column=0, sticky="w", pady=4)
        self.campo_senha_atual = ttk.Entry(quadro, show="*", width=36)
        self.campo_senha_atual.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=4)
        ttk.Label(quadro, text="Nova senha").grid(row=1, column=0, sticky="w", pady=4)
        self.campo_senha_nova = ttk.Entry(quadro, show="*", width=36)
        self.campo_senha_nova.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=4)
        ttk.Label(quadro, text="Confirmar nova").grid(row=2, column=0, sticky="w", pady=4)
        self.campo_senha_conf = ttk.Entry(quadro, show="*", width=36)
        self.campo_senha_conf.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=4)
        ttk.Button(quadro, text="Alterar senha de suporte", command=self._alterar_senha).grid(
            row=3, column=1, sticky="w", padx=(10, 0), pady=(10, 0)
        )

    def _toggle_independente(self) -> None:
        estado = "disabled" if self.var_indep.get() else "normal"
        self.campo_db.configure(state=estado)

    def _procurar_banco(self) -> None:
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecione oficina_nautica.db",
            filetypes=[("SQLite", "*.db"), ("Todos", "*.*")],
        )
        if not caminho:
            caminho = filedialog.askdirectory(parent=self, title="Ou selecione a pasta da oficina")
        if caminho:
            self.campo_db.delete(0, "end")
            self.campo_db.insert(0, caminho)

    def _procurar_ngrok(self) -> None:
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecione ngrok.exe",
            filetypes=[("Executavel", "*.exe"), ("Todos", "*.*")],
        )
        if caminho:
            self.campo_ngrok_exe.delete(0, "end")
            self.campo_ngrok_exe.insert(0, caminho)

    def _procurar_icone(self) -> None:
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecione o icone da janela",
            filetypes=[
                ("Icone Windows", "*.ico"),
                ("Imagem", "*.png *.jpg *.jpeg"),
                ("Todos", "*.*"),
            ],
        )
        if caminho:
            self.campo_icone.delete(0, "end")
            self.campo_icone.insert(0, caminho)

    def _autorizar_maquina(self) -> None:
        autorizar_maquina_atual(self.install_dir)
        messagebox.showinfo("Seguranca", "Este computador foi autorizado.", parent=self)

    def _alterar_senha(self) -> None:
        atual = self.campo_senha_atual.get()
        nova = self.campo_senha_nova.get()
        conf = self.campo_senha_conf.get()
        if nova != conf:
            messagebox.showerror("Senha", "Nova senha e confirmacao nao conferem.", parent=self)
            return
        ok, msg = alterar_senha_suporte(atual, nova, self.install_dir)
        if not ok:
            messagebox.showerror("Senha", msg, parent=self)
            return
        self.campo_senha_atual.delete(0, "end")
        self.campo_senha_nova.delete(0, "end")
        self.campo_senha_conf.delete(0, "end")
        messagebox.showinfo("Senha", msg, parent=self)

    def _salvar(self) -> None:
        dados = parser_para_dict(self.parser)
        dados["app"]["database_path"] = self.campo_db.get().strip()
        dados["app"]["icone_janela"] = self.campo_icone.get().strip()
        dados["app"]["modo_independente"] = "1" if self.var_indep.get() else "0"
        dados["servidor"]["host"] = self.campo_host.get().strip() or "0.0.0.0"
        dados["servidor"]["porta"] = self.campo_porta.get().strip() or "5000"
        dados["ngrok"]["domain"] = self.campo_domain.get().strip()
        dados["ngrok"]["public_url"] = self.campo_public.get().strip()
        dados["ngrok"]["authtoken"] = self.campo_token.get().strip()
        dados["ngrok"]["exe"] = self.campo_ngrok_exe.get().strip()
        salvar_config(dados, self.install_dir)
        messagebox.showinfo("Configuracao", "Configuracao salva com sucesso.", parent=self)
        self.on_save()
        self.destroy()


def abrir_painel_suporte(master: tk.Misc, install_dir: Path, on_save: Callable[[], None]) -> None:
    def _abrir_config() -> None:
        PainelConfiguracao(master, install_dir, on_save)

    DialogoSenhaSuporte(master, install_dir, _abrir_config)
