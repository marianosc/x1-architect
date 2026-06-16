# Construye docs/desarrollo.html AUTOCONTENIDO: incrusta los PNG como base64
# data-URIs para que se vea en CUALQUIER contexto (panel de preview, doble
# click, localhost) sin depender de la raíz del server ni de rutas relativas.
#
# La PLANTILLA editable vive FUERA de docs/ (tools/desarrollo_template.html) para
# que el panel de preview NUNCA la abra por error (tiene refs a archivo, que en
# el panel se ven rotas). En docs/ solo queda el desarrollo.html autocontenido.
# Flujo: editar tools/desarrollo_template.html -> correr este script.
import base64, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
TEMPLATE = os.path.join(ROOT, "tools", "desarrollo_template.html")
OUT = os.path.join(DOCS, "desarrollo.html")
_OLD_SRC = os.path.join(DOCS, "desarrollo.src.html")  # migración del lugar viejo

if not os.path.exists(TEMPLATE):
    boot = _OLD_SRC if os.path.exists(_OLD_SRC) else OUT
    with open(boot, encoding="utf-8") as f:
        open(TEMPLATE, "w", encoding="utf-8").write(f.read())
    print(f"Plantilla migrada a: {TEMPLATE}")

html = open(TEMPLATE, encoding="utf-8").read()


def inline(m):
    rel = m.group(1)
    path = os.path.join(DOCS, rel)
    if not os.path.exists(path):
        print(f"  ! falta {rel}"); return m.group(0)
    b64 = base64.b64encode(open(path, "rb").read()).decode("ascii")
    return f'src="data:image/png;base64,{b64}"'


html2, n = re.subn(r'src="(desarrollo/[^"]+\.png)"', inline, html)
open(OUT, "w", encoding="utf-8").write(html2)
print(f"OK  {OUT} autocontenido con {n} imágenes embebidas ({os.path.getsize(OUT)//1024} KB)")
