# -*- coding: utf-8 -*-
"""dictado-local: mantén F9, habla, suelta — el texto se pega donde esté el foco.
Pipeline inspirado en el teardown de Wispr Flow (REA): hotkey -> mic 16 kHz -> ASR local -> clipboard + pegado -> restaurar.
Todo local, sin nube. Modelo: faster-whisper small (multilingüe, ya cacheado).

  python dictado.py                ejecutar (Ctrl+C para salir)
  python dictado.py --test audio.wav   transcribir un WAV 16 kHz mono y imprimirlo (sin pegar)
  python dictado.py --selftest     probar las reglas de pegado (sin mic ni modelo)
"""
import sys, time, wave, ctypes, threading
from ctypes import wintypes

RATE, KEY = 16000, "t"  # mantener T para hablar; las pulsaciones cortas (<0,25 s) se ignoran
MAX_SEG = 30 * 60  # límite de seguridad de grabación (30 min) para no agotar la memoria
# Reglas del helper de Wispr (pasado Ghidra): Shift+Insert solo en editores tipo VS Code
SHIFT_INSERT_APPS = {"code", "cursor", "windsurf"}
# Restauración tardía por app: escritorio remoto 5 s, Office/WhatsApp 3 s, resto 0,5 s
SLOW_RESTORE = ((5.0, ("vncviewer", "tvnviewer", "mstsc", "msrdc", "wfica32", "vmware-view", "rdcman", "anydesk", "teamviewer")),
                (3.0, ("outlook", "olk", "winword", "whatsapp")))
MODIFIERS = ("ctrl", "shift", "alt", "left windows", "right windows")

MODEL_SIZE = "small"   # multilingüe (español); ya está en la caché de HuggingFace


def load_model():
    from faster_whisper import WhisperModel
    try:
        return WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")
    except Exception as e:
        print(f"CUDA no disponible ({e}); usando CPU", flush=True)
        return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe(model, audio):
    import numpy as np
    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    segs, _ = model.transcribe(audio, vad_filter=True)
    return " ".join(s.text.strip() for s in segs).strip()


def record():
    import numpy as np, sounddevice as sd
    chunks = []
    with sd.InputStream(samplerate=RATE, channels=1, dtype="float32",
                        callback=lambda d, *_: chunks.append(d.copy())):
        import keyboard
        t0 = time.perf_counter()
        while keyboard.is_pressed(KEY) and time.perf_counter() - t0 < MAX_SEG:
            time.sleep(0.02)
    return np.concatenate(chunks)[:, 0] if chunks else np.zeros(0, np.float32)


def foreground_process():
    """Nombre del proceso de la ventana enfocada sin '.exe'."""
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(u32.GetForegroundWindow(), ctypes.byref(pid))
    h = k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return "unknown"
    buf, n = ctypes.create_unicode_buffer(260), wintypes.DWORD(260)
    ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
    k32.CloseHandle(h)
    return buf.value.rsplit("\\", 1)[-1].rsplit(".", 1)[0] if ok else "unknown"


def pick_keys(proc):
    return ("shift", "insert") if proc.lower() in SHIFT_INSERT_APPS else ("ctrl", "v")


def restore_delay(proc):
    p = proc.lower()
    return next((d for d, names in SLOW_RESTORE if p.startswith(names)), 0.5)


def paste(text):
    import pyperclip
    import keyboard
    proc = foreground_process()
    keys, delay = pick_keys(proc), restore_delay(proc)
    for _ in range(100):  # no pegar mientras se mantiene un modificador (regla de Wispr)
        if not any(keyboard.is_pressed(m) for m in MODIFIERS):
            break
        time.sleep(0.02)
    try:
        old = pyperclip.paste()  # puede lanzar si el portapapeles tiene imágenes/archivos
    except Exception:
        old = None
    pyperclip.copy(text)
    for k in keys:
        keyboard.press(k)
    time.sleep(0.05)
    for k in reversed(keys):
        keyboard.release(k)
    time.sleep(0.05)
    # Restaurar el portapapeles después, solo si nadie lo cambió mientras tanto
    def _restaurar():
        try:
            if old is not None and pyperclip.paste() == text:
                pyperclip.copy(old)
        except Exception:
            pass
    threading.Timer(delay, _restaurar).start()
    return proc, "+".join(keys), delay


def selftest():
    assert pick_keys("Code") == ("shift", "insert") and pick_keys("Cursor") == ("shift", "insert")
    assert pick_keys("python") == ("ctrl", "v") and pick_keys("chrome") == ("ctrl", "v")
    assert restore_delay("mstsc") == 5.0 and restore_delay("AnyDesk") == 5.0
    assert restore_delay("WINWORD") == 3.0 and restore_delay("olk") == 3.0
    assert restore_delay("notepad") == 0.5
    print("selftest ok")


def probe():
    """Muestra el nombre interno de cada tecla que pulses (Ctrl+C para salir)."""
    import keyboard
    print("Modo prueba de teclas: pulsa F9 (con y sin Fn) y verás qué nombre recibe. Ctrl+C para salir.", flush=True)
    keyboard.hook(lambda e: print(f"  tecla: {e.name!r} {'↓' if e.event_type == 'down' else '↑'}", flush=True))
    keyboard.wait("esc")


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    if sys.argv[1:] == ["--probe"]:
        return probe()
    model = load_model()
    if len(sys.argv) == 3 and sys.argv[1] == "--test":
        import numpy as np
        with wave.open(sys.argv[2]) as w:
            assert w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2
            audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        print(transcribe(model, audio))
        return
    import keyboard
    try:  # pitido de confirmación: el modelo ya cargó y puedes hablar
        import winsound
        winsound.Beep(880, 120)
    except Exception:
        pass
    print(f" Listo. Mantén {KEY.upper()} y habla. Ctrl+C para salir.", flush=True)
    print(" (¿no pasa nada al pulsar la tecla? Prueba: python dictado.py --probe)", flush=True)
    while True:
        keyboard.wait(KEY)
        try: winsound.Beep(1200, 60)
        except Exception: pass
        try:
            audio = record()
        except Exception as e:
            print(f"error de micrófono: {e!r} — reintentando", flush=True)
            time.sleep(0.5)
            continue
        if len(audio) < RATE // 4:
            continue  # pulsación demasiado corta
        t1 = time.perf_counter()
        try:
            text = transcribe(model, audio)
        except Exception as e:
            print(f"error transcribiendo: {e!r}", flush=True)
            continue
        asr = time.perf_counter() - t1
        if text:
            try:
                proc, keys, delay = paste(text + " ")
            except Exception as e:
                print(f"error pegando: {e!r} (texto solo en consola): {text!r}", flush=True)
                continue
            print(f"{len(audio)/RATE:.1f}s audio, {asr:.2f}s ASR, {proc} -> {keys}: {text!r}", flush=True)
        else:
            print(f"{len(audio)/RATE:.1f}s audio, {asr:.2f}s ASR: sin texto", flush=True)


if __name__ == "__main__":
    main()
