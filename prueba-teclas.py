# -*- coding: utf-8 -*-
"""Diagnóstico: cuenta las teclas que el sistema ve durante 10 segundos.
Uso: venv\\Scripts\\python prueba-teclas.py
Si cuenta 0, ejecútalo de nuevo COMO ADMINISTRADOR."""
import keyboard, time

print("Diagnóstico de teclado: pulsa varias teclas (F9, T, Fn+F9...) durante 10 segundos...")
nombres = []
t0 = time.time()
def on(e):
    if e.event_type == "down" and e.name:
        nombres.append(e.name)
        print(f"  [{time.time()-t0:4.1f}s] {e.name}")
keyboard.hook(on)
while time.time() - t0 < 10:
    time.sleep(0.1)
print(f"\nTotal de teclas detectadas: {len(nombres)}")
if not nombres:
    print("⚠️ 0 teclas: Windows no nos está dejando ver el teclado.")
    print("   → Cierra y ejecuta este script COMO ADMINISTRADOR y repite.")
else:
    unicas = sorted(set(nombres))
    print("Teclas vistas:", ", ".join(unicas))
