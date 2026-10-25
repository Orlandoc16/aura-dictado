# -*- coding: utf-8 -*-
"""dictado-local: dictación por voz con interfaz moderna (dark + onda en vivo).
Botón circular: clic inicia, clic detiene. Sin límite de duración. 100% local.
"""
import threading, time, ctypes, queue, math, re
import tkinter as tk
from ctypes import wintypes

CONFIG = {
    "model_size": "small",
    "rate": 16000,
    "language": None,
    "voice_commands": True,
    "auto_capitalize": True,
    "final_period": True,
}

COMANDOS = [
    ("nueva línea", "\n"), ("nuevo párrafo", "\n\n"),
    ("punto y aparte", ".\n"), ("punto y coma", ";"), ("dos puntos", ":"),
    ("punto", "."), ("coma", ","), ("signo de interrogación", "?"),
    ("abrir interrogación", "¿"), ("signo de exclamación", "!"), ("abrir exclamación", "¡"),
]

MAX_SEG = 30 * 60  # auto-stop de seguridad a los 30 min de grabación

def postproceso(text):
    if CONFIG["voice_commands"]:
        # \b evita tragarse palabras que contienen el comando (p.ej. "empuntar")
        for palabra, signo in COMANDOS:
            text = re.sub(rf"\b{re.escape(palabra)}\b", signo, text, flags=re.IGNORECASE)
        text = re.sub(r" +([.,;:?!])", r"\1", text)     # espacio antes de signo
        text = re.sub(r"([.,;:?!])(?=[^\s\n\d.,;:?!])", r"\1 ", text)  # falta espacio después
    text = " ".join(text.split()) if "\n" not in text else "\n".join(
        " ".join(l.split()) for l in text.split("\n"))
    if CONFIG["auto_capitalize"]:
        partes = []
        for linea in text.split("\n"):
            # mayúscula tras . ¿ ? ¡ ! …
            frag = re.split(r"([.¿?¡!…])", linea)
            out = []
            cap = True
            for f in frag:
                if f and f in ".¿?¡!…":
                    out.append(f)
                    cap = True
                else:
                    f2 = f.strip()
                    out.append((" " * (len(f) - len(f2)) + f2[:1].upper() + f2[1:]) if (cap and f2) else f)
                    if f2:
                        cap = False
            partes.append("".join(out))
        text = "\n".join(partes)
    if CONFIG["final_period"] and text and text[-1] not in ".?!…\n":
        text += "."
    return text

def load_model():
    from faster_whisper import WhisperModel
    try:
        return WhisperModel(CONFIG["model_size"], device="cuda", compute_type="float16")
    except Exception:
        return WhisperModel(CONFIG["model_size"], device="cpu", compute_type="int8")

def transcribe(model, audio):
    import numpy as np
    arrs = [np.atleast_1d(c).reshape(-1).astype(np.float32) for c in audio
            if c is not None and np.size(c) > 0]
    data = np.concatenate(arrs) if arrs else np.zeros(0, np.float32)
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    kwargs = {"vad_filter": True}
    if CONFIG["language"]:
        kwargs["language"] = CONFIG["language"]
    segs, _ = model.transcribe(data, **kwargs)
    return " ".join(s.text.strip() for s in segs).strip()

RATE = CONFIG["rate"]
AUDIO_Q = queue.Queue(maxsize=RATE)   # ~1 min de colchón; evita memoria ilimitada si la transcripción va lenta
NIVELES = []          # niveles recientes (0..1) para la onda en vivo
UI_Q = queue.Queue()  # llamadas a la interfaz pendientes desde hilos secundarios

def recorder():
    import numpy as np, sounddevice as sd
    def cb(indata, frames, t, status):
        if APP_STATE["grabando"]:
            try:
                AUDIO_Q.put_nowait(indata.copy())
            except queue.Full:
                try: AUDIO_Q.get_nowait()  # descarta el chunk más viejo
                except queue.Empty: pass
                try: AUDIO_Q.put_nowait(indata.copy())
                except queue.Full: pass
            NIVELES.append(float(np.nanmax(np.abs(indata))))
            del NIVELES[:-90]  # mantener ~90 barras
        else:
            NIVELES.append(0.0)
            del NIVELES[:-90]
    try:
        with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", callback=cb):
            while APP_STATE["vivo"]:
                time.sleep(0.05)
    except Exception as e:
        if APP_STATE["vivo"]:
            APP_STATE["vivo"] = False
            APP_STATE["error_audio"] = repr(e)  # la UI lo mostrará en su sondeo

APP_STATE = {"grabando": False, "vivo": True, "modelo": None}

def send_ctrl_v():
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]
    class INPUT(ctypes.Structure):
        class _I(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]
        _anonymous_ = ("i",)
        _fields_ = [("type", wintypes.DWORD), ("i", _I)]
    def key(vk, up=False):
        i = INPUT(type=1)
        i.ki = KEYBDINPUT(vk, 0, 2 if up else 0, 0, None)
        ctypes.windll.user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))
    VK_CTRL, VK_V = 0x11, 0x56
    key(VK_CTRL); key(VK_V); time.sleep(0.05); key(VK_V, up=True); key(VK_CTRL, up=True)

# ---------- Tema ----------
BG      = "#0b0e17"
PANEL   = "#12172a"
BORDE   = "#232a41"
TXT     = "#e8ecf8"
DIM     = "#7c86a6"
ACENTO  = "#7c5cff"   # violeta
ACENTO2 = "#2ea6ff"   # azul
ROJO    = "#ff4d6d"
VERDE   = "#2ee6a8"

class App:
    def __init__(self, root):
        self.root = root
        root.title("◈ Aura · Dictado local")
        root.configure(bg=BG)
        root.geometry("460x640")

        # Cabecera
        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(head, text="◈ Aura", font=("Segoe UI", 20, "bold"),
                 bg=BG, fg=TXT).pack(side="left")
        tk.Label(head, text="dictado local · whisper · sin nube",
                 font=("Segoe UI", 9), bg=BG, fg=DIM).pack(side="right", pady=(10, 0))

        # Botón circular + onda
        self.canvas = tk.Canvas(root, width=412, height=250, bg=BG,
                                highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.toggle_rec)
        self.btn_circ = None
        self._pulse = 0

        # Estado (píldora)
        self.status = tk.Label(root, text="● Cargando modelo…", font=("Segoe UI", 11),
                               bg=PANEL, fg=DIM, padx=14, pady=6)
        self.status.pack(padx=24, fill="x", ipady=2)

        # Historial (tarjetas)
        tk.Label(root, text="TRANSCRIPCIONES", font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=DIM).pack(anchor="w", padx=24, pady=(18, 4))
        hist_frame = tk.Frame(root, bg=PANEL, highlightbackground=BORDE,
                              highlightcolor=BORDE, highlightthickness=1)
        hist_frame.pack(fill="both", expand=True, padx=24)
        self.historial = tk.Text(hist_frame, font=("Segoe UI", 11), wrap="word",
                                 bg=PANEL, fg=TXT, relief="flat", padx=14, pady=10,
                                 state="disabled", spacing3=4)
        sb = tk.Scrollbar(hist_frame, command=self.historial.yview, width=10)
        self.historial.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.historial.pack(side="left", fill="both", expand=True)

        # Barra inferior
        barra = tk.Frame(root, bg=BG)
        barra.pack(fill="x", padx=24, pady=10)
        tk.Button(barra, text="⧉ Copiar todo", font=("Segoe UI", 10), bg=PANEL, fg=TXT,
                  activebackground=BORDE, relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self.copiar_todo).pack(side="left")
        tk.Button(barra, text="✕ Limpiar", font=("Segoe UI", 10), bg=PANEL, fg=DIM,
                  activebackground=BORDE, relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self.limpiar).pack(side="left", padx=8)
        self.timer_lbl = tk.Label(barra, text="", font=("Segoe UI", 11, "bold"),
                                  bg=BG, fg=ACENTO2)
        self.timer_lbl.pack(side="right")

        threading.Thread(target=self.init_model, daemon=True).start()
        threading.Thread(target=recorder, daemon=True).start()
        self.root.after(50, self._animar)
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar)

    # ---------- Onda + botón circular ----------
    def _circulo(self, r, color, width=3, outline=""):
        c = self.canvas
        cx, cy = 206, 125
        return c.create_oval(cx - r, cy - r, cx + r, cy + r,
                             outline=outline or color, width=width)

    def _animar(self):
        c = self.canvas
        c.delete("all")
        cx, cy = 206, 125
        grabando = APP_STATE["grabando"]
        listo = APP_STATE.get("modelo") is not None

        # error de micrófono / hilo de audio
        if APP_STATE.pop("error_audio", None):
            grabando = False
            APP_STATE["grabando"] = False
            self.status.config(text="⚠ micrófono no disponible o desconectado — reinicia la app", fg=ROJO)

        # llamada pendientes desde hilos secundarios (tkinter no es thread-safe)
        while True:
            try: fn = UI_Q.get_nowait()
            except queue.Empty: break
            try: fn()
            except Exception as e: self.log("ERROR ui: " + repr(e))

        # anillos pulsantes al grabar
        if grabando:
            self._pulse = (self._pulse + 6) % 40
            for extra in (0, 18, 36):
                r = 62 + self._pulse + extra - 40
                if r > 62:
                    fade = max(1, int(3 - (r - 62) / 15))
                    c.create_oval(cx - r, cy - r, cx + r, cy + r,
                                  outline=ROJO, width=fade)
            color_btn, texto = ROJO, "■  DETENER"
        elif listo:
            color_btn, texto = ACENTO, "●  INICIAR"
        else:
            color_btn, texto = "#3a4059", "···"

        # onda de barras alrededor/abajo
        base_y = 235
        n = len(NIVELES) or 1
        bw = 412 / max(n, 40)
        for i, lvl in enumerate(NIVELES[-90:]):
            h = max(2, min(70, lvl * 300))
            x = i * (412 / 90)
            color = ROJO if grabando else ACENTO2
            c.create_rectangle(x, base_y - h, x + bw - 2, base_y,
                               fill=color, width=0)
        c.create_line(0, base_y + 1, 412, base_y + 1, fill=BORDE)

        # botón circular
        c.create_oval(cx - 62, cy - 62, cx + 62, cy + 62, fill=PANEL,
                      outline=color_btn, width=3)
        c.create_oval(cx - 46, cy - 46, cx + 46, cy + 46, fill=color_btn, width=0)
        if not grabando:
            # icono de micrófono simplificado
            c.create_oval(cx - 10, cy - 30, cx + 10, cy - 6, fill=BG, width=0)
            c.create_rectangle(cx - 4, cy - 8, cx + 4, cy + 8, fill=BG, width=0)
            c.create_arc(cx - 18, cy - 18, cx + 18, cy + 18, start=180,
                         extent=180, style="arc", outline=BG, width=4)
            c.create_line(cx, cy + 18, cx, cy + 28, fill=BG, width=4)
            c.create_line(cx - 10, cy + 28, cx + 10, cy + 28, fill=BG, width=4)
        else:
            c.create_rectangle(cx - 16, cy - 16, cx + 16, cy + 16, fill=BG, width=0)

        # texto del botón
        c.create_text(cx, cy + 84, text=texto, fill=color_btn,
                      font=("Segoe UI", 13, "bold"))

        # cronómetro + auto-stop de seguridad a los 30 min
        if grabando:
            seg = int(time.time() - self.t_inicio)
            self.timer_lbl.config(text=f"● REC {seg//60}:{seg%60:02d}", fg=ROJO)
            if seg >= MAX_SEG:
                self.stop_rec()
                self.status.config(text="⏱ 30 min alcanzados — grabación detenida automáticamente", fg=ROJO)
        self.root.after(50, self._animar)

    # ---------- Eventos ----------
    def toggle_rec(self, _=None):
        if APP_STATE.get("modelo") is None and not APP_STATE["grabando"]:
            self.status.config(text="⏳ el modelo aún se está cargando — espera unos segundos", fg=DIM)
            return
        if APP_STATE["grabando"]:
            self.stop_rec()
        else:
            self.start_rec()

    def start_rec(self):
        while not AUDIO_Q.empty():
            AUDIO_Q.get_nowait()
        APP_STATE["grabando"] = True
        self.t_inicio = time.time()
        self.status.config(text="● Grabando… pulsa de nuevo para terminar (sin límite)", fg=ROJO)

    def stop_rec(self):
        if not APP_STATE["grabando"]:
            return
        APP_STATE["grabando"] = False
        seg = int(time.time() - self.t_inicio)
        est = f"~{int(seg*0.4)}s en CPU" if seg > 30 else "1-3 s"
        self.status.config(text=f"⏳ Transcribiendo {seg}s de audio ({est})…", fg=ACENTO2)
        self.timer_lbl.config(text="")
        chunks = []
        while not AUDIO_Q.empty():
            chunks.append(AUDIO_Q.get_nowait())
        threading.Thread(target=self.procesar, args=(chunks,), daemon=True).start()

    def procesar(self, chunks):
        import numpy as np
        audio = np.concatenate(chunks)[:, 0] if chunks else np.zeros(0, np.float32)
        dur = len(audio) / RATE
        pico = float(np.max(np.abs(audio))) * 100 if len(audio) else 0
        self.log(f"audio: {dur:.1f}s, nivel pico: {pico:.0f}%")
        if dur < 0.4:
            self.ui(self.estado_corto)
            return
        if pico < 1:
            self.ui(lambda: self.status.config(
                text="⚠ Silencio: revisa el micrófono de Windows", fg=ROJO))
            return
        model = getattr(self, "model", None) or APP_STATE.get("modelo")
        if model is None:
            self.ui(lambda: self.status.config(
                text="el modelo aún cargaba — prueba otra vez", fg=DIM))
            return
        try:
            t1 = time.perf_counter()
            crudo = transcribe(model, audio).strip()
            asr = time.perf_counter() - t1
        except Exception as e:
            self.log("ERROR transcribiendo: " + repr(e))
            self.ui(lambda: self.status.config(text=f"error: {e}", fg=ROJO))
            return
        text = postproceso(crudo) if crudo else ""
        self.log(f"transcripción ({asr:.1f}s): {text!r}")

        def fin():
            if text:
                try:
                    import pyperclip
                    pyperclip.copy(text + " ")
                except Exception as e:
                    self.log("ERROR portapapeles: " + repr(e))
                    self.status.config(text=f"✓ Transcrito ({asr:.1f}s) · error copiando al portapapeles", fg=ROJO)
                    self.historial.config(state="normal")
                    self.historial.insert("end", text + "\n\n")
                    self.historial.see("end")
                    self.historial.config(state="disabled")
                    return
                try: send_ctrl_v()
                except Exception as e: self.log("ERROR pegando: " + repr(e))
                self.status.config(text=f"✓ Pegado ({asr:.1f}s) · también en el portapapeles", fg=VERDE)
                self.historial.config(state="normal")
                self.historial.insert("end", text + "\n\n")
                self.historial.see("end")
                self.historial.config(state="disabled")
            else:
                self.status.config(text="no se detectó voz — habla más cerca y fuerte", fg=DIM)
        self.ui(fin)

    def estado_corto(self):
        self.status.config(text="demasiado corto — graba al menos un par de segundos", fg=DIM)

    # ---------- Utilidades ----------
    def init_model(self):
        try:
            m = load_model()
            self.model = m
            APP_STATE["modelo"] = m
            self.ui(lambda: self.status.config(text="● Listo — pulsa INICIAR y habla", fg=VERDE))
        except Exception as e:
            self.log("ERROR cargando modelo: " + repr(e))
            self.ui(lambda: self.status.config(text=f"error cargando modelo: {e}", fg=ROJO))

    def copiar_todo(self):
        import pyperclip
        pyperclip.copy(self.historial.get("1.0", "end").strip())

    def limpiar(self):
        self.historial.config(state="normal")
        self.historial.delete("1.0", "end")
        self.historial.config(state="disabled")

    def log(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        try:
            with open(__file__.rsplit("\\", 1)[0] + r"\gui.log", "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def ui(self, fn):
        """Encola fn para ejecutarse en el hilo de la interfaz (tkinter no es thread-safe)."""
        UI_Q.put(fn)

    def cerrar(self):
        APP_STATE["vivo"] = False   # detiene el hilo del recorder y cierra el InputStream
        self.root.after(80, self.root.destroy)  # margen para que el recorder salga del sleep


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
