"""
Постпроцессор сгенерированного pygbag-ом docs/index.html:
- вставляет CSS, отключающий браузерный скролл и масштабирующий canvas
  под viewport с сохранением пропорций игры;
- вставляет JS, который через preventDefault блокирует ситуативные жесты
  (скролл от touchmove, pinch-zoom, double-tap-zoom).

Запускается из deploy.bat после pygbag --build и копирования в docs/.
"""

import sys
from pathlib import Path

# Размеры игрового окна — должны совпадать с config.WIN_W / config.WIN_H.
WIN_W = 672
WIN_H = 728

CSS = f"""
<style>
  /* Запрещаем браузеру обрабатывать тач как скролл/зум. */
  html, body {{
    margin: 0;
    padding: 0;
    overflow: hidden;
    overscroll-behavior: none;
    touch-action: none;
    height: 100%;
    width: 100%;
    -webkit-user-select: none;
    user-select: none;
  }}
  /* Растягиваем canvas во viewport, сохраняя пропорции игры. */
  canvas.emscripten {{
    position: fixed !important;
    top: 50% !important;
    left: 50% !important;
    transform: translate(-50%, -50%) !important;
    width: min(100vw, calc(100vh * {WIN_W} / {WIN_H})) !important;
    height: min(100vh, calc(100vw * {WIN_H} / {WIN_W})) !important;
    z-index: 5 !important;
  }}
  canvas {{ touch-action: none !important; }}
</style>
"""

JS = """
<script>
  // Блокируем скролл/зум страницы на тач — все жесты уходят в игру.
  document.addEventListener('touchmove', function(e){ e.preventDefault(); }, { passive: false });
  document.addEventListener('gesturestart', function(e){ e.preventDefault(); }, { passive: false });
  document.addEventListener('dblclick', function(e){ e.preventDefault(); }, { passive: false });
</script>
"""

MARK_CSS = "/* PYGBAG_PATCH_CSS */"
MARK_JS  = "/* PYGBAG_PATCH_JS */"


def patch(path):
    p = Path(path)
    src = p.read_text(encoding="utf-8")

    css_block = f"<!-- {MARK_CSS} -->{CSS}"
    js_block  = f"<!-- {MARK_JS} -->{JS}"

    if MARK_CSS not in src:
        src = src.replace("</head>", css_block + "</head>", 1)
    if MARK_JS not in src:
        src = src.replace("</body>", js_block + "</body>", 1)

    p.write_text(src, encoding="utf-8")
    print(f"Patched: {p}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "docs/index.html"
    patch(target)
