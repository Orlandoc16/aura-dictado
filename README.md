# 🎙️ dictado-local

Dictado por voz **100% local** estilo Wispr Flow: pulsa el botón, habla, suelta —
el texto aparece donde esté el foco, **con puntuación y mayúsculas automáticas**.
Sin nube, sin cuentas, sin coste.

> Construido siguiendo la metodología del teardown con REA de
> [wispr-flow-rea-teardown](https://github.com/az9713/wispr-flow-rea-teardown),
> que documentó con Ghidra el pipeline interno de Wispr Flow.

## Uso

**Doble clic en `IniciarDictadoVentana.bat`** → espera el verde "Listo" →
**mantén pulsado el botón 🎤 y habla** → suelta → texto pegado donde tengas el foco.

- El texto también queda en el **historial de la ventana** y en tu portapapeles
- `📋 Copiar todo` copia el historial completo
- La versión con tecla (hotkey global) está en `dictado.py` (usa `venv\Scripts\python dictado.py`)

## Características

- **Modelo:** faster-whisper `small` multilingüe (español incluido), CPU int8 — ya cacheado
- **Puntuación por voz:** di "punto", "coma", "nueva línea", "dos puntos", "punto y aparte"…
- **Mayúsculas automáticas** al inicio y tras cada punto
- **Punto final automático**
- Historial de la sesión + copiar todo
- Portapapeles restaurado tras pegar; reglas especiales para VS Code/Cursor (Shift+Insert)
- Todo el audio se procesa en tu máquina
- **Límite de seguridad:** la grabación se detiene sola a los **30 minutos** (protege la memoria);
  los comandos de voz solo se reconocen como **palabras completas** ("empuntar" no se convierte en "empun.tar")

## Configuración (arriba de `dictado-gui.py`)

| Clave | Valor | Efecto |
|---|---|---|
| `model_size` | `"small"` | `"base"` más rápido · `"large-v3"` máxima calidad (1,5 GB) |
| `language` | `None` | `"es"` fuerza español (evita cambios de idioma) |
| `voice_commands` | `True` | puntuación hablada |
| `auto_capitalize` | `True` | mayúsculas |
| `final_period` | `True` | punto final |

## Requisitos

Windows · micrófono · venv incluido (`venv\`, Python 3.11 con
`faster-whisper sounddevice keyboard pyperclip numpy`).

## Instalación

```powershell
git clone https://github.com/orlandoc16/aura-dictado.git
cd aura-dictado
python -m venv venv
venv\Scripts\pip install -r requirements.txt
.\IniciarDictadoVentana.bat
```

Requisitos: Windows 10/11, Python 3.10-3.12 y micrófono. La primera ejecución
descarga el modelo de Whisper (~460 MB) a tu caché de HuggingFace; después
funciona 100% sin conexión.

## Solución de problemas

La ventana muestra el motivo exacto de cada fallo (micrófono en silencio, audio corto,
error de transcripción…) y todo queda en `gui.log`.
Si pegar no funciona en una app elevada, ejecuta el dictado también elevado.
Si se desconecta el micrófono en mitad de una grabación, la app lo detecta y avisa;
reiníciala tras reconectarlo. El modelo usa la caché de HuggingFace estándar
(`%USERPROFILE%\.cache\huggingface`); si la mueves, define `HF_HOME`.
