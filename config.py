"""
Константы и динамическое состояние раскладки.

Размер окна фиксирован, размер игрового поля (число клеток) выбирается
пользователем. Из него пересчитывается размер клетки CELL и смещения
OFFSET_X/OFFSET_Y, чтобы поле было отцентровано в окне.
"""

# --- Окно (фиксированное) -------------------------------------------

PANEL_H = 56
GAME_AREA_PX = 672                # сторона квадратной игровой зоны
WIN_W = GAME_AREA_PX
WIN_H = GAME_AREA_PX + PANEL_H

FPS = 60

# --- Доступные размеры поля -----------------------------------------

SIZES        = [12, 16, 20, 24, 28]
DEFAULT_SIZE = 20

# --- Динамическая раскладка -----------------------------------------
# Эти значения МУТИРУЮТСЯ функцией apply_size() в зависимости от
# выбранного размера поля. Все модули обращаются к ним через config.X
# (а не через `from config import X`), иначе значения "застынут" на
# момент импорта и не обновятся при смене размера.

COLS     = DEFAULT_SIZE
ROWS     = DEFAULT_SIZE
CELL     = GAME_AREA_PX // DEFAULT_SIZE
OFFSET_X = (GAME_AREA_PX - CELL * DEFAULT_SIZE) // 2
OFFSET_Y = PANEL_H + (GAME_AREA_PX - CELL * DEFAULT_SIZE) // 2


def apply_size(size):
    """Применяет выбранный размер поля: пересчитывает CELL и смещения."""
    global COLS, ROWS, CELL, OFFSET_X, OFFSET_Y
    COLS = size
    ROWS = size
    CELL = GAME_AREA_PX // size
    margin = (GAME_AREA_PX - CELL * size) // 2
    OFFSET_X = margin
    OFFSET_Y = PANEL_H + margin


# --- Тач-управление: режимы ------------------------------------------
# Крестовина рисуется HTML-наложением снаружи canvas (см. patch_html.py).
# В pygame её больше нет — это упрощает геометрию и позволяет ставить
# крестовину в любое место экрана независимо от размера canvas.

TOUCH_MODES        = ["swipes", "dpad"]
TOUCH_MODE_LABELS  = {"swipes": "Свайпы", "dpad": "Крестовина"}
DEFAULT_TOUCH_MODE = "swipes"


# --- Направления ----------------------------------------------------

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

# --- Цвета ----------------------------------------------------------

C_GRID_A   = (106, 168,  79)
C_GRID_B   = ( 97, 158,  72)
C_GRID_BG  = ( 70, 130,  60)   # заливка вокруг центрованного поля
C_SNAKE    = ( 70, 130, 190)
C_SNAKE_D  = ( 45,  95, 150)
C_EYE      = (255, 255, 255)
C_PUPIL    = ( 20,  50,  90)

C_FOOD     = (210,  60,  40)
C_FOOD_HL  = (240, 100,  70)
C_GOLDEN   = (235, 195,  50)
C_GOLDEN_HL= (255, 230, 130)
C_SLOW     = ( 70, 170, 220)
C_SLOW_HL  = (140, 220, 255)

C_TEXT     = (255, 255, 255)
C_DIM      = (200, 230, 200)
C_PANEL    = ( 50,  90,  40)

C_WALL     = ( 60,  60,  70)
C_WALL_HL  = ( 95,  95, 110)

C_BTN      = ( 70, 120,  60)
C_BTN_HOV  = ( 95, 155,  80)
C_BTN_BRD  = ( 30,  60,  25)
C_BTN_ACT  = (200, 130,  50)
C_BTN_ACTH = (230, 160,  70)

# --- Сложности и препятствия ----------------------------------------

DIFFICULTIES = {
    # У "chill" start == max — скорость не меняется при поедании.
    "chill":    {"name": "Чилл",    "start":  6, "max":  6, "step": 5},
    "easy":     {"name": "Лёгко",   "start":  6, "max": 14, "step": 5},
    "medium":   {"name": "Средне",  "start":  8, "max": 20, "step": 5},
    "hard":     {"name": "Сложно",  "start": 12, "max": 28, "step": 3},
    "hardcore": {"name": "Хардкор", "start": 14, "max": 30, "step": 3},
}
DIFFICULTY_ORDER = ["chill", "easy", "medium", "hard", "hardcore"]

WALLS_COUNT = 12

# --- Состояния ------------------------------------------------------

STATE_MAIN_MENU         = "main_menu"
STATE_SETTINGS          = "settings"
STATE_PLAYING           = "playing"
STATE_PAUSED            = "paused"
STATE_DYING             = "dying"
STATE_REVIVAL_OFFER     = "revival_offer"
STATE_REVIVAL_COUNTDOWN = "revival_countdown"
STATE_REVIVAL_MATH      = "revival_math"
STATE_GAMEOVER          = "gameover"

DYING_DURATION = 0.7

# --- Возрождение ---------------------------------------------------

REVIVAL_LENGTH_PENALTY = 3    # на сколько клеток укорачивается змейка
REVIVAL_SCORE_PENALTY  = 3    # на сколько уменьшается счёт
REVIVAL_INVINCIBLE_SEC = 3.0  # длительность неуязвимости после возрождения
REVIVAL_TIMER_SEC      = 5.0  # сколько секунд даётся на решение
REVIVAL_COUNTDOWN_SEC  = 3.0  # длительность отсчёта 3-2-1 перед примером

# Глитч-эффект на крупных множителях длины (×5 и выше): змейка
# кратковременно окрашивается в золотой.
GLITCH_THRESHOLD = 5     # с какого множителя срабатывает
GLITCH_DURATION  = 0.45  # сек — общая длительность вспышки

# --- Типы еды -------------------------------------------------------

FOOD_NORMAL = "normal"
FOOD_GOLDEN = "golden"
FOOD_SLOW   = "slow"

GOLDEN_TTL    = 35
SLOW_TTL      = 35
BONUS_CHANCE  = 0.30
SLOW_DELTA    = 2
