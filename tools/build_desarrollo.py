# Construye docs/desarrollo.html AUTOCONTENIDO: incrusta los PNG como base64
# data-URIs para que se vea en CUALQUIER contexto (panel de preview, doble
# click, localhost) sin depender de la raíz del server ni de rutas relativas.
#
# Flujo: se edita la PLANTILLA docs/desarrollo.src.html (con <img src="desarrollo/..">)
# y este script genera docs/desarrollo.html con las imágenes embebidas.
# Primera vez: si no existe la plantilla, la crea desde el desarrollo.html actual.
import base64, os, re

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
SRC = os.path.join(DOCS, "desarrollo.src.html")
OUT = os.path.join(DOCS, "desarrollo.html")

if not os.path.exists(SRC):
    # bootstrap: la plantilla es el desarrollo.html actual (con refs a archivo)
    with open(OUT, encoding="utf-8") as f:
        open(SRC, "w", encoding="utf-8").write(f.read())
    print(f"Plantilla creada: {SRC}")

html = open(SRC, encoding="utf-8").read()


def inline(m):
    rel = m.group(1)
    path = os.path.join(DOCS, rel)
    if not os.path.exists(path):
        print(f"  ! falta {rel}"); return m.group(0)
    b64 = base64.b64encode(open(path, "rb").read()).decode("ascii")
    return f'src="data:image/png;base64,{b64}"'


html2, n = re.subn(r'src="(desarrollo/[^"]+\.png)"', inline, html)
open(OUT, "w", encoding="utf-8").write(html2)
print(f"OK  {OUT} autocontenido con {n} imágenes embebidas "
      f"({os.path.getsize(OUT)//1024} KB)")
