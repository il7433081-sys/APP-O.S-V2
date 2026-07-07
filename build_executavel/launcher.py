from __future__ import annotations

import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import Canvas, Tk, messagebox
from tkinter import ttk

from config_app_os import (
    garantir_config,
    preparar_ambiente_instalacao,
    resolver_icone_janela,
    resumo_config,
)
from painel_suporte import abrir_painel_suporte
from seguranca_app_os import autorizar_maquina_atual, verificar_instalacao
from werkzeug.serving import WSGIRequestHandler


class _HandlerSilenciosoAssinatura(WSGIRequestHandler):
    def log_request(self, code: str = "-", size: str = "-") -> None:
        if (
            self.command == "GET"
            and str(code) == "200"
            and self.path.startswith("/api/assinatura/")
        ):
            return
        super().log_request(code, size)


def _code_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _code_dir()


def _preparar_imports() -> Path:
    install = _install_dir()
    code = _code_dir()
    for pasta in (code, install):
        txt = str(pasta)
        if txt not in sys.path:
            sys.path.insert(0, txt)
    build = code / "build_executavel"
    if build.is_dir() and str(build) not in sys.path:
        sys.path.insert(0, str(build))
    preparar_ambiente_instalacao(install)
    return install


def _resolver_ngrok(cfg_domain: str, cfg_exe: str) -> str | None:
    candidatos = [
        cfg_exe.strip(),
        os.getenv("NGROK_EXE", "").strip(),
        shutil.which("ngrok") or "",
        str(Path.home() / "AppData/Local/ngrok/ngrok.exe"),
        str(Path.home() / "AppData/Local/Programs/ngrok/ngrok.exe"),
    ]
    for c in candidatos:
        if c and Path(c).is_file():
            return c
    return None


def _ip_local() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except OSError:
        return "127.0.0.1"


def _aguardar_servidor(porta: int, timeout: float = 90.0) -> bool:
    """Espera o Flask responder em 127.0.0.1 (IPv4) antes do ngrok conectar."""
    url = f"http://127.0.0.1:{porta}/"
    fim = time.time() + timeout
    while time.time() < fim:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if int(getattr(resp, "status", 200) or 200) < 500:
                    return True
        except Exception:
            time.sleep(0.6)
    return False


class LauncherJanela:
    CORES = {
        "bg_top": "#0a1022",
        "bg_bottom": "#121f3f",
        "card": "#15213a",
        "card_hover": "#1b2c4f",
        "accent": "#4cc9f0",
        "accent2": "#7b5cff",
        "text": "#eaf2ff",
        "muted": "#9eb4d8",
        "ok": "#5dffb1",
        "warn": "#ffbe5c",
    }

    def __init__(self) -> None:
        self.install_dir = _preparar_imports()
        self.cfg = garantir_config(self.install_dir)
        self.resumo = resumo_config(self.cfg, self.install_dir)
        self.eventos: queue.Queue[tuple[str, str]] = queue.Queue()
        self.ngrok_proc: subprocess.Popen[str] | None = None
        self.url_publica: str | None = self.resumo.get("public_url") or None
        self.servidor_iniciado = False
        self.modo_atual = ""
        self.host = self.resumo.get("host", "0.0.0.0")
        self.porta = self.resumo.get("porta", "5000")

        self.root = Tk()
        self.root.title("OS Digital — Central de Inicializacao")
        self.root.geometry("1040x700")
        self.root.minsize(980, 660)
        self.root.configure(bg=self.CORES["bg_top"])
        self.root.protocol("WM_DELETE_WINDOW", self._fechar_aplicacao)
        self.root.bind("<Control-Shift-C>", lambda _e: self._abrir_suporte())

        self._configurar_estilos()
        self._verificar_seguranca_inicial()
        self._desenhar_fundo()
        self._montar_ui()
        self._aplicar_icone_janela()
        self._garantir_ui_acima_fundo()
        self._atualizar_resumo_ui()
        self._atualizar_fila()

    def _aplicar_icone_janela(self) -> None:
        icone = resolver_icone_janela(self.install_dir, self.cfg)
        if not icone:
            return
        try:
            self.root.iconbitmap(default=str(icone))
        except tk.TclError:
            try:
                img = tk.PhotoImage(file=str(icone))
                self.root.iconphoto(True, img)
                self._icone_ref = img
            except tk.TclError:
                pass

    def _garantir_ui_acima_fundo(self) -> None:
        if hasattr(self, "shell"):
            self.shell.lift()
        self.root.update_idletasks()

    def _configurar_estilos(self) -> None:
        self.estilo = ttk.Style(self.root)
        try:
            self.estilo.theme_use("clam")
        except Exception:
            pass
        self.estilo.configure("Shell.TFrame", background=self.CORES["bg_top"])
        self.estilo.configure("Hero.TLabel", background=self.CORES["bg_top"], foreground=self.CORES["text"], font=("Segoe UI", 24, "bold"))
        self.estilo.configure("Sub.TLabel", background=self.CORES["bg_top"], foreground=self.CORES["muted"], font=("Segoe UI", 11))
        self.estilo.configure("CardTitle.TLabel", background=self.CORES["card"], foreground=self.CORES["text"], font=("Segoe UI", 15, "bold"))
        self.estilo.configure("CardBody.TLabel", background=self.CORES["card"], foreground=self.CORES["muted"], font=("Segoe UI", 10))
        self.estilo.configure("Status.TLabel", background=self.CORES["bg_top"], foreground=self.CORES["ok"], font=("Consolas", 10, "bold"))
        self.estilo.configure("Info.TLabel", background=self.CORES["bg_top"], foreground=self.CORES["muted"], font=("Consolas", 10))
        self.estilo.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), padding=(14, 10))
        self.estilo.configure("Ghost.TButton", font=("Segoe UI", 10), padding=(8, 6))
        self.estilo.configure("Cards.TFrame", background=self.CORES["bg_top"])
        self.estilo.configure("Rodape.TFrame", background=self.CORES["bg_top"])

    def _verificar_seguranca_inicial(self) -> None:
        ok, msg = verificar_instalacao(self.install_dir)
        if ok:
            return
        messagebox.showwarning(
            "Protecao anti-copia",
            msg + "\n\nUse a engrenagem ou Ctrl+Shift+C para autorizar este PC.",
        )

    def _desenhar_fundo(self) -> None:
        self.bg_canvas = Canvas(self.root, highlightthickness=0, bd=0, bg=self.CORES["bg_top"])
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        def redesenhar(_event=None) -> None:
            w = max(self.root.winfo_width(), 1)
            h = max(self.root.winfo_height(), 1)
            self.bg_canvas.delete("grad")
            steps = 28
            for i in range(steps):
                ratio = i / max(steps - 1, 1)
                cor = self._interp_color(self.CORES["bg_top"], self.CORES["bg_bottom"], ratio)
                y0 = int(h * ratio)
                y1 = int(h * (ratio + 1 / steps)) + 1
                self.bg_canvas.create_rectangle(0, y0, w, y1, fill=cor, outline=cor, tags="grad")
            self.bg_canvas.create_oval(w * 0.62, -80, w * 1.05, h * 0.42, fill="#1a2d57", outline="", tags="grad")
            self.bg_canvas.create_oval(-120, h * 0.55, w * 0.35, h * 1.2, fill="#182746", outline="", tags="grad")
            self._garantir_ui_acima_fundo()

        self._redesenhar_fundo = redesenhar
        self.root.bind("<Configure>", redesenhar, add="+")
        redesenhar()

    @staticmethod
    def _interp_color(c1: str, c2: str, t: float) -> str:
        def hx(c: str) -> tuple[int, int, int]:
            c = c.lstrip("#")
            return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

        r1, g1, b1 = hx(c1)
        r2, g2, b2 = hx(c2)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _montar_ui(self) -> None:
        self.shell = ttk.Frame(self.root, style="Shell.TFrame", padding=22)
        self.shell.place(relx=0, rely=0, relwidth=1, relheight=1)

        topo = ttk.Frame(self.shell, style="Shell.TFrame")
        topo.pack(fill="x")
        ttk.Label(topo, text="Ordem de Servico Digital", style="Hero.TLabel").pack(side="left", anchor="w")
        ttk.Button(topo, text="Config", style="Ghost.TButton", width=8, command=self._abrir_suporte).pack(
            side="right"
        )

        ttk.Label(
            self.shell,
            text="Escolha o modo de operacao. As configuracoes de banco, IP e ngrok sao lidas do config.ini local.",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(8, 18))

        cards = ttk.Frame(self.shell, style="Cards.TFrame")
        cards.pack(fill="both", expand=True)
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)

        self.card_interno = self._criar_card(
            cards,
            "Modo Interno",
            "Servidor na rede local.\nIdeal para PC, tablet e celular na mesma Wi-Fi.",
            "Iniciar Interno",
            lambda: self._iniciar("interno"),
            col=0,
            badge="REDE LOCAL",
        )
        self.card_externo = self._criar_card(
            cards,
            "Modo Externo",
            "Servidor + tunel ngrok.\nCompartilhe link/QR por WhatsApp ou 4G.",
            "Iniciar Externo",
            lambda: self._iniciar("externo"),
            col=1,
            badge="ACESSO PUBLICO",
        )

        self.status_txt = ttk.Label(self.shell, text="Pronto para iniciar.", style="Status.TLabel")
        self.status_txt.pack(anchor="w", pady=(18, 4))
        self.info_txt = ttk.Label(self.shell, text="", style="Info.TLabel")
        self.info_txt.pack(anchor="w")

        botoes = ttk.Frame(self.shell, style="Rodape.TFrame")
        botoes.pack(anchor="w", pady=(16, 0))
        self.btn_abrir_local = ttk.Button(botoes, text="Abrir local", command=self._abrir_local, state="disabled")
        self.btn_abrir_local.grid(row=0, column=0, padx=(0, 8))
        self.btn_abrir_publico = ttk.Button(
            botoes, text="Abrir publico", command=self._abrir_publico, state="disabled"
        )
        self.btn_abrir_publico.grid(row=0, column=1, padx=(0, 8))
        self.btn_parar = ttk.Button(botoes, text="Encerrar", command=self._fechar_aplicacao, state="disabled")
        self.btn_parar.grid(row=0, column=2)

    def _criar_card(
        self,
        pai: ttk.Frame,
        titulo: str,
        descricao: str,
        rotulo_botao: str,
        comando,
        *,
        col: int,
        badge: str,
    ) -> ttk.Frame:
        wrap = ttk.Frame(pai, padding=(0, 0, 10 if col == 0 else 0, 0))
        wrap.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 8 if col == 0 else 0))
        card = tk.Frame(wrap, bg=self.CORES["card"], highlightthickness=1, highlightbackground="#24365f")
        card.pack(fill="both", expand=True, ipadx=18, ipady=18)

        tk.Label(card, text=badge, bg="#22345f", fg=self.CORES["accent"], font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(
            anchor="w"
        )
        tk.Label(card, text=titulo, bg=self.CORES["card"], fg=self.CORES["text"], font=("Segoe UI", 16, "bold")).pack(
            anchor="w", pady=(10, 6)
        )
        tk.Label(
            card,
            text=descricao,
            bg=self.CORES["card"],
            fg=self.CORES["muted"],
            font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w", pady=(0, 18))
        tk.Button(
            card,
            text=rotulo_botao,
            bg=self.CORES["accent2"],
            fg="white",
            activebackground="#6949ff",
            activeforeground="white",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            padx=16,
            pady=10,
            cursor="hand2",
            command=comando,
        ).pack(anchor="w")
        return card

    def _atualizar_resumo_ui(self) -> None:
        db = self.resumo.get("database_path", "")
        existe = self.resumo.get("database_existe", "nao")
        indep = self.resumo.get("modo_independente", "0") in {"1", "true", "True"}
        modo_db = "Independente" if indep else "Compartilhado"
        self.info_txt.configure(
            text=(
                f"Banco ({modo_db}): {db} [{'OK' if existe == 'sim' else 'NAO ENCONTRADO'}]  |  "
                f"Servidor: {self.host}:{self.porta}  |  IP local: {_ip_local()}"
            )
        )

    def _abrir_suporte(self) -> None:
        def _reload() -> None:
            self.cfg = garantir_config(self.install_dir)
            self.resumo = resumo_config(self.cfg, self.install_dir)
            self.host = self.resumo.get("host", "0.0.0.0")
            self.porta = self.resumo.get("porta", "5000")
            self.url_publica = self.resumo.get("public_url") or None
            preparar_ambiente_instalacao(self.install_dir)
            self._aplicar_icone_janela()
            self._atualizar_resumo_ui()

        abrir_painel_suporte(self.root, self.install_dir, _reload)

    def _validar_antes_de_iniciar(self) -> bool:
        ok, msg = verificar_instalacao(self.install_dir)
        if not ok:
            if messagebox.askyesno(
                "Instalacao nao autorizada",
                msg + "\n\nDeseja abrir o painel de suporte para autorizar agora?",
            ):
                self._abrir_suporte()
            return False

        self.cfg = garantir_config(self.install_dir)
        self.resumo = resumo_config(self.cfg, self.install_dir)
        preparar_ambiente_instalacao(self.install_dir)

        if self.resumo.get("database_existe") != "sim":
            messagebox.showerror(
                "Banco de dados",
                "Banco nao encontrado. Abra o painel de suporte (engrenagem) e configure o caminho "
                "ou ative o Modo Independente.",
            )
            return False
        return True

    def _iniciar(self, modo: str) -> None:
        if self.servidor_iniciado:
            return
        if not self._validar_antes_de_iniciar():
            return

        self.modo_atual = modo
        self.servidor_iniciado = True
        self.btn_parar.configure(state="normal")
        self.btn_abrir_local.configure(state="normal")
        self.host = self.resumo.get("host", "0.0.0.0")
        self.porta = self.resumo.get("porta", "5000")
        self.status_txt.configure(text=f"Iniciando modo {modo}...")
        self.info_txt.configure(
            text=(
                f"Local: http://127.0.0.1:{self.porta}  |  "
                f"Rede: http://{_ip_local()}:{self.porta}"
            )
        )

        threading.Thread(target=self._subir_servidor, daemon=True).start()
        threading.Thread(
            target=self._confirmar_servidor_e_ngrok,
            args=(modo,),
            daemon=True,
        ).start()

    def _confirmar_servidor_e_ngrok(self, modo: str) -> None:
        porta = int(os.getenv("SERVIDOR_PORTA", self.porta) or "5000")
        self.eventos.put(("status", f"Aguardando servidor em http://127.0.0.1:{porta} ..."))
        if not _aguardar_servidor(porta):
            self.eventos.put(
                (
                    "erro",
                    "O servidor Flask nao respondeu em http://127.0.0.1:"
                    f"{porta}. Verifique banco e configuracao no painel Config.",
                )
            )
            return
        self.eventos.put(("status", f"Servidor ativo em http://127.0.0.1:{porta}"))
        if modo == "externo":
            self._subir_ngrok()

    def _subir_servidor(self) -> None:
        try:
            preparar_ambiente_instalacao(self.install_dir)
            import app as app_mod

            host = os.getenv("SERVIDOR_HOST", self.host) or "0.0.0.0"
            porta = int(os.getenv("SERVIDOR_PORTA", self.porta) or "5000")
            app_mod.app.run(
                debug=False,
                host=host,
                port=porta,
                use_reloader=False,
                request_handler=_HandlerSilenciosoAssinatura,
            )
        except Exception as exc:
            self.eventos.put(("erro", f"Falha ao iniciar servidor: {exc}"))

    def _subir_ngrok(self) -> None:
        dominio = self.cfg["ngrok"].get("domain", "").strip()
        token = self.cfg["ngrok"].get("authtoken", "").strip()
        ngrok = _resolver_ngrok(dominio, self.cfg["ngrok"].get("exe", ""))
        if not ngrok:
            self.eventos.put(
                ("erro", "ngrok nao encontrado. Configure o caminho no painel de suporte."),
            )
            return

        porta = os.getenv("SERVIDOR_PORTA", self.porta) or "5000"
        alvo = f"127.0.0.1:{porta}"
        cmd = [ngrok, "http", alvo]
        if token:
            try:
                subprocess.run(
                    [ngrok, "config", "add-authtoken", token],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except Exception:
                pass
            cmd = [ngrok, "http", alvo]
        if dominio:
            cmd = [ngrok, "http", f"--url=https://{dominio}", "--pooling-enabled", alvo]

        try:
            self.ngrok_proc = subprocess.Popen(
                cmd,
                cwd=str(self.install_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if dominio:
                self.url_publica = f"https://{dominio}"
                self.eventos.put(("publico", self.url_publica))
            padrao_url = re.compile(
                r"https://[a-zA-Z0-9\-]+\.ngrok(?:-free)?\.app|https://[a-zA-Z0-9\-]+\.ngrok-free\.dev"
            )
            assert self.ngrok_proc.stdout is not None
            for linha in self.ngrok_proc.stdout:
                m = padrao_url.search(linha)
                if m:
                    self.url_publica = m.group(0)
                    self.eventos.put(("publico", self.url_publica))
                    break
        except Exception as exc:
            self.eventos.put(("erro", f"Falha ao iniciar ngrok: {exc}"))

    def _abrir_local(self) -> None:
        porta = os.getenv("SERVIDOR_PORTA", self.porta) or "5000"
        webbrowser.open(f"http://127.0.0.1:{porta}")

    def _abrir_publico(self) -> None:
        if self.url_publica:
            webbrowser.open(self.url_publica)

    def _atualizar_fila(self) -> None:
        try:
            while True:
                tipo, msg = self.eventos.get_nowait()
                if tipo == "status":
                    self.status_txt.configure(text=msg)
                elif tipo == "publico":
                    self.url_publica = msg
                    self.status_txt.configure(text=f"Link publico ativo: {msg}")
                    self.btn_abrir_publico.configure(state="normal")
                elif tipo == "erro":
                    self.status_txt.configure(text=msg)
                    messagebox.showerror("Inicializador OS Digital", msg)
        except queue.Empty:
            pass
        self.root.after(250, self._atualizar_fila)

    def _fechar_aplicacao(self) -> None:
        try:
            if self.ngrok_proc and self.ngrok_proc.poll() is None:
                self.ngrok_proc.terminate()
        except Exception:
            pass
        self.root.destroy()
        os._exit(0)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    LauncherJanela().run()


if __name__ == "__main__":
    main()
