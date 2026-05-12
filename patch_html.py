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
# При SCALE=2 в config.py получается 1344×1456. JS использует их только для
# соотношения сторон при подгонке canvas под viewport — абсолютные числа
# не важны, важна пропорция.
WIN_W = 1344
WIN_H = 1456

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
    /* Тёмно-зелёный фон под игру — совпадает с тоном панели в config.py. */
    background-color: #325a28 !important;
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

  /* Перебиваем pygbag-овский кричащий зелёный квадрат с синим текстом. */
  #infobox {{
    position: fixed !important;
    top: 50% !important;
    left: 50% !important;
    transform: translate(-50%, -50%) !important;
    background: rgba(20, 30, 16, 0.92) !important;
    color: #ffffff !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "DejaVu Sans", sans-serif !important;
    font-size: 17px !important;
    font-weight: 500 !important;
    letter-spacing: 0.3px !important;
    text-align: center !important;
    padding: 22px 36px !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 14px !important;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45) !important;
    min-width: 220px !important;
    z-index: 10 !important;
    animation: snakeloader-pulse 1.6s ease-in-out infinite !important;
  }}

  @keyframes snakeloader-pulse {{
    0%, 100% {{ opacity: 1.0; }}
    50%      {{ opacity: 0.55; }}
  }}

  /* Скрываем дефолтный progress bar / status строку pygbag-а. */
  #transfer {{ background: transparent !important; }}

  /* Тач-крестовина: 4 кнопки в форме + поверх страницы. */
  #snake-dpad {{
    position: fixed;
    z-index: 100;
    width: 200px;
    height: 200px;
    pointer-events: none;        /* контейнер сам по себе не кликабельный */
    display: none;               /* по умолчанию скрыт — включается из JS */
    touch-action: none;
    -webkit-user-select: none;
    user-select: none;
  }}
  #snake-dpad .dbtn {{
    position: absolute;
    width: 64px;
    height: 64px;
    background: rgba(240, 240, 240, 0.5);
    border: 2px solid rgba(255, 255, 255, 0.75);
    border-radius: 14px;
    pointer-events: auto;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }}
  #snake-dpad .dbtn:active {{
    background: rgba(255, 255, 255, 0.7);
  }}
  #snake-dpad .dbtn::before {{
    content: '';
    display: block;
    width: 0; height: 0;
    border-style: solid;
  }}
  #snake-dpad .dup    {{ top: 0;   left: 68px; }}
  #snake-dpad .ddown  {{ top: 136px; left: 68px; }}
  #snake-dpad .dleft  {{ top: 68px; left: 0; }}
  #snake-dpad .dright {{ top: 68px; left: 136px; }}
  #snake-dpad .dup::before    {{ border-width: 0 12px 16px 12px; border-color: transparent transparent #333 transparent; }}
  #snake-dpad .ddown::before  {{ border-width: 16px 12px 0 12px; border-color: #333 transparent transparent transparent; }}
  #snake-dpad .dleft::before  {{ border-width: 12px 16px 12px 0; border-color: transparent #333 transparent transparent; }}
  #snake-dpad .dright::before {{ border-width: 12px 0 12px 16px; border-color: transparent transparent transparent #333; }}
</style>
"""

JS = """
<script>
  // === 0. Переводим pygbag-овские "Loading..." / "Ready to start..." на русский ===
  // + после первого тапа меняем текст на "Подготовка...", иначе "Ready to start"
  //   висит на экране всё время пока подгружается WASM-рантайм.
  var userClicked = false;
  function ruify(text) {
    if (!text) return text;
    if (userClicked)                           return 'Подготовка...';
    if (text.indexOf('Ready to start') !== -1) return 'Нажмите экран, чтобы начать';
    if (text.indexOf('Loading') !== -1)        return 'Загрузка...';
    return text;
  }
  function patchInfobox() {
    var box = document.getElementById('infobox');
    if (!box) return;
    var current = box.textContent.trim();
    var translated = ruify(current);
    if (translated !== current) box.textContent = translated;
  }
  document.addEventListener('DOMContentLoaded', patchInfobox);
  new MutationObserver(patchInfobox).observe(document.body, {
    subtree: true, childList: true, characterData: true
  });
  function markClicked() {
    if (userClicked) return;
    userClicked = true;
    patchInfobox();
  }
  document.addEventListener('click',      markClicked, { capture: true });
  document.addEventListener('touchstart', markClicked, { capture: true });

  // === 0.5. Подгонка размера canvas под viewport с сохранением пропорций ===
  // CSS-подход через min()/calc() работает не везде одинаково, поэтому
  // дублируем расчёт в JS: на каждый resize вычисляем точные пиксели и
  // выставляем inline-стили на canvas. Это перекрывает любой CSS извне.
  var GAME_W = 1344;
  var GAME_H = 1456;
  // Когда активна крестовина — резервируем столько px снизу,
  // и canvas центрируется только в верхней части viewport.
  var DPAD_RESERVE = 240;

  function isDpadMode() {
    try { return localStorage.getItem('snake_touch_mode') === 'dpad'; }
    catch (e) { return false; }
  }

  function fitCanvas() {
    var canvas = document.getElementById('canvas');
    if (!canvas) return;
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var reserveBottom = isDpadMode() ? DPAD_RESERVE : 0;
    var availH = Math.max(100, vh - reserveBottom);
    var scale = Math.min(vw / GAME_W, availH / GAME_H);
    var w = Math.floor(GAME_W * scale);
    var h = Math.floor(GAME_H * scale);
    var left = Math.floor((vw - w) / 2);
    var top  = Math.floor((availH - h) / 2);
    var setI = function(prop, val) {
      canvas.style.setProperty(prop, val, 'important');
    };
    setI('position', 'fixed');
    setI('left', left + 'px');
    setI('top',  top  + 'px');
    setI('width',  w + 'px');
    setI('height', h + 'px');
    setI('transform', 'none');
    setI('margin', '0');
    setI('right', 'auto');
    setI('bottom', 'auto');
  }
  window.addEventListener('resize', fitCanvas);
  window.addEventListener('load', fitCanvas);
  // pygbag может создать/изменить canvas позднее — перепроверяем периодически.
  setInterval(fitCanvas, 500);

  // === 1. Блокируем скролл/зум страницы ===
  document.addEventListener('touchmove', function(e){ e.preventDefault(); }, { passive: false });
  document.addEventListener('gesturestart', function(e){ e.preventDefault(); }, { passive: false });
  document.addEventListener('dblclick', function(e){ e.preventDefault(); }, { passive: false });

  // === 2. Детект свайпов по всему экрану — эмулируем стрелки клавиатуры ===
  // Pygame получает события касания только от canvas. Серые поля по бокам —
  // вне canvas, оттуда свайпы не доходят. Поэтому слушаем тач на документе
  // и шлём канвасу синтетический keydown — pygame подхватит его через KEY_MAP.

  var swipeStart = null;
  var THRESHOLD  = 30;  // пиксели

  function fireKey(key, code) {
    var canvas = document.getElementById('canvas');
    if (!canvas) return;
    var init = { key: key, code: key, keyCode: code, which: code,
                 bubbles: true, cancelable: true };
    canvas.dispatchEvent(new KeyboardEvent('keydown', init));
    // keyup тоже — SDL ждёт пару, и иначе клавиша считается зажатой.
    canvas.dispatchEvent(new KeyboardEvent('keyup', init));
  }

  function classify(dx, dy) {
    if (Math.abs(dx) > Math.abs(dy)) {
      return dx > 0 ? ['ArrowRight', 39] : ['ArrowLeft', 37];
    }
    return dy > 0 ? ['ArrowDown', 40] : ['ArrowUp', 38];
  }

  document.addEventListener('touchstart', function(e){
    if (e.touches.length !== 1) { swipeStart = null; return; }
    swipeStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
  }, { passive: false });

  function swipesEnabled() {
    // Python пишет 'dpad' или 'swipes' в localStorage. В режиме крестовины
    // синтезировать стрелки от свайпов не нужно — управление только кнопками.
    try { return localStorage.getItem('snake_touch_mode') !== 'dpad'; }
    catch (e) { return true; }
  }

  document.addEventListener('touchmove', function(e){
    if (!swipeStart || e.touches.length !== 1) return;
    if (!swipesEnabled()) return;
    var t = e.touches[0];
    var dx = t.clientX - swipeStart.x;
    var dy = t.clientY - swipeStart.y;
    if (Math.abs(dx) > THRESHOLD || Math.abs(dy) > THRESHOLD) {
      var k = classify(dx, dy);
      fireKey(k[0], k[1]);
      // Сдвигаем "начало" к текущей точке — серию свайпов внутри одного
      // касания (зигзаг) ловим без отрыва пальца.
      swipeStart = { x: t.clientX, y: t.clientY };
    }
  }, { passive: false });

  document.addEventListener('touchend',    function(){ swipeStart = null; }, { passive: false });
  document.addEventListener('touchcancel', function(){ swipeStart = null; }, { passive: false });

  // === 3. Тач-крестовина (HTML-наложение под canvas) ===
  // Кнопки рендерим как обычные DOM-элементы и позиционируем под canvas.
  // При нажатии стреляем тем же fireKey, что и для свайпов.
  function ensureDpadElement() {
    if (document.getElementById('snake-dpad')) return;
    var pad = document.createElement('div');
    pad.id = 'snake-dpad';
    pad.innerHTML =
      '<div class="dbtn dup"    data-dir="up"></div>' +
      '<div class="dbtn ddown"  data-dir="down"></div>' +
      '<div class="dbtn dleft"  data-dir="left"></div>' +
      '<div class="dbtn dright" data-dir="right"></div>';
    document.body.appendChild(pad);
    var keyMap = {
      up:    ['ArrowUp',    38],
      down:  ['ArrowDown',  40],
      left:  ['ArrowLeft',  37],
      right: ['ArrowRight', 39],
    };
    Array.prototype.forEach.call(pad.querySelectorAll('.dbtn'), function(btn){
      var dir = btn.getAttribute('data-dir');
      var k = keyMap[dir];
      function press(e) {
        e.preventDefault();
        e.stopPropagation();
        fireKey(k[0], k[1]);
      }
      btn.addEventListener('touchstart', press, { passive: false });
      btn.addEventListener('mousedown',  press);
    });
  }

  function placeDpad() {
    var pad = document.getElementById('snake-dpad');
    if (!pad) return;
    if (!isDpadMode()) {
      pad.style.display = 'none';
      return;
    }
    // Крестовина прижимается к низу окна — это устойчиво на всех экранах.
    // Игровая зона сама поднимается выше (см. DPAD_RESERVE в fitCanvas).
    var padW = 200, padH = 200;
    var vh = window.innerHeight;
    var vw = window.innerWidth;
    var top  = vh - padH - 20;
    var left = Math.floor((vw - padW) / 2);
    pad.style.top  = top  + 'px';
    pad.style.left = left + 'px';
    pad.style.display = 'block';
  }

  window.addEventListener('load', function(){ ensureDpadElement(); placeDpad(); });
  window.addEventListener('resize', placeDpad);
  // Перепроверяем — крестовина может включаться/выключаться из настроек,
  // canvas может ресайзиться pygbag-ом независимо.
  setInterval(function(){ ensureDpadElement(); placeDpad(); }, 500);
</script>
"""

MARK_CSS = "/* PYGBAG_PATCH_CSS */"
MARK_JS  = "/* PYGBAG_PATCH_JS */"


import re


def _strip_old(src, mark):
    """Удаляет старый блок патча с этим маркером (если он есть)."""
    # Блок начинается на <!-- {mark} --> и заканчивается на следующий </style>
    # или </script> в зависимости от типа.
    pattern = re.compile(
        rf"<!--\s*{re.escape(mark)}\s*-->\s*<(style|script)>.*?</\1>\s*",
        re.DOTALL,
    )
    return pattern.sub("", src)


def patch(path):
    p = Path(path)
    src = p.read_text(encoding="utf-8")

    # Чистим старые вставки (если есть), вставляем свежие.
    src = _strip_old(src, MARK_CSS)
    src = _strip_old(src, MARK_JS)

    css_block = f"<!-- {MARK_CSS} -->{CSS}"
    js_block  = f"<!-- {MARK_JS} -->{JS}"

    src = src.replace("</head>", css_block + "</head>", 1)
    src = src.replace("</body>", js_block + "</body>", 1)

    p.write_text(src, encoding="utf-8")
    print(f"Patched: {p}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "docs/index.html"
    patch(target)
