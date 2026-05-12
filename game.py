"""
Игровая модель: змейка, еда, бонусы, стены.
Чистая логика, без рисования.
"""

import os
import json
import random
from collections import deque

import config
from config import (
    RIGHT, OPPOSITE,
    FOOD_NORMAL, FOOD_GOLDEN, FOOD_SLOW,
    GOLDEN_TTL, SLOW_TTL, BONUS_CHANCE,
    DEFAULT_SIZE, SIZES,
    TOUCH_MODES, DEFAULT_TOUCH_MODE,
)


_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE   = os.path.join(_DIR, "save.json")
LEGACY_BEST = os.path.join(_DIR, "highscore.txt")

DEFAULT_DATA = {
    "best":              0,
    "best_with_revival": 0,
    "best_milestone":    1,
    "difficulty":        "medium",
    "obstacles":         False,
    "bonuses":           True,
    "revivals":          True,
    "board_size":        DEFAULT_SIZE,
    "touch_mode":        DEFAULT_TOUCH_MODE,
}


def _validate(data):
    """Подчищает значения, чтобы файл не мог сломать игру."""
    from config import DIFFICULTIES
    if data.get("difficulty") not in DIFFICULTIES:
        data["difficulty"] = DEFAULT_DATA["difficulty"]
    if data.get("board_size") not in SIZES:
        data["board_size"] = DEFAULT_DATA["board_size"]
    if data.get("touch_mode") not in TOUCH_MODES:
        data["touch_mode"] = DEFAULT_DATA["touch_mode"]
    data["obstacles"] = bool(data.get("obstacles", False))
    data["bonuses"]   = bool(data.get("bonuses", True))
    data["revivals"]  = bool(data.get("revivals", True))
    try:
        data["best"] = max(0, int(data.get("best", 0)))
    except (TypeError, ValueError):
        data["best"] = 0
    try:
        data["best_milestone"] = max(1, int(data.get("best_milestone", 1)))
    except (TypeError, ValueError):
        data["best_milestone"] = 1
    try:
        data["best_with_revival"] = max(0, int(data.get("best_with_revival", 0)))
    except (TypeError, ValueError):
        data["best_with_revival"] = 0
    return data


def _is_mobile_device():
    """
    Эвристика «мобильное устройство ли это».
    Работает только в pygbag-сборке (platform.window — это JS window).
    На локальном Python возвращает False.
    """
    try:
        import platform as _pf
        if not hasattr(_pf, "window"):
            return False
        nav = _pf.window.navigator
        # Тачскрин на iPad/iPhone/Android.
        try:
            if int(nav.maxTouchPoints or 0) > 0:
                return True
        except Exception:
            pass
        ua = str(nav.userAgent or "").lower()
        for kw in ("iphone", "ipad", "ipod", "android", "mobile"):
            if kw in ua:
                return True
        return False
    except Exception:
        return False


def _fresh_defaults():
    """
    Дефолтные настройки при первом запуске (когда save-файла ещё нет).
    На мобильных устройствах сразу включаем крестовину, поле 12×12 и
    сложность «легко» — с большими клетками и щадящей скоростью.
    """
    data = dict(DEFAULT_DATA)
    if _is_mobile_device():
        data["board_size"] = 12
        data["touch_mode"] = "dpad"
        data["difficulty"] = "easy"
    return data


def load_data():
    """Читает save.json. Если файла нет — пробует подхватить старый highscore.txt."""
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_DATA)
        merged.update({k: v for k, v in data.items() if k in DEFAULT_DATA})
        return _validate(merged)
    except (OSError, ValueError):
        pass
    # Миграция со старого формата.
    try:
        with open(LEGACY_BEST, "r", encoding="utf-8") as f:
            best = int(f.read().strip())
        merged = _fresh_defaults()
        merged["best"] = best
        return _validate(merged)
    except (OSError, ValueError):
        return _validate(_fresh_defaults())


def save_data(data):
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


class Game:
    def reset(self, walls_count=0, bonuses_enabled=True):
        # Стартовая змейка: 5 клеток в горизонтальный ряд, по центру поля.
        # Голова смещена ВПРАВО от центра, чтобы оставить путь для разгона.
        cy = config.ROWS // 2
        cx = config.COLS // 2
        self.snake = [(cx + 1 - i, cy) for i in range(5)]
        self.dir   = RIGHT
        # Очередь поворотов на 1-2 хода вперёд: серия быстрых нажатий
        # (например, "вверх → влево" в один тик) не теряется.
        self.queue = deque(maxlen=2)
        self.walls = self._make_walls(walls_count)
        self.bonuses_enabled = bonuses_enabled
        self.bonus = None              # {"pos", "type", "ttl"} или None
        self.food  = self._random_free_cell()
        self.score = 0
        self.apples_eaten = 0          # для шага ускорения
        self.over  = False
        self.death_pos = None          # клетка, где змейка погибла
        self.invincible = False        # неуязвимость после возрождения

    def _make_walls(self, n):
        # Не ставим стены в стартовой полосе перед змейкой и в самих
        # клетках змейки — иначе можно умереть на первом же тике.
        forbidden = set(self.snake)
        head_x, head_y = self.snake[0]
        for dx in range(1, 8):
            forbidden.add((head_x + dx, head_y))
        walls = set()
        attempts = 0
        while len(walls) < n and attempts < n * 50:
            attempts += 1
            p = (random.randint(0, config.COLS - 1),
                 random.randint(0, config.ROWS - 1))
            if p not in forbidden and p not in walls:
                walls.add(p)
        return walls

    def _random_free_cell(self):
        bonus_pos = self.bonus["pos"] if self.bonus else None
        food_pos  = getattr(self, "food", None)
        while True:
            p = (random.randint(0, config.COLS - 1),
                 random.randint(0, config.ROWS - 1))
            if (p not in self.snake
                    and p not in self.walls
                    and p != bonus_pos
                    and p != food_pos):
                return p

    def _maybe_spawn_bonus(self):
        if not self.bonuses_enabled:
            return
        if self.bonus is not None:
            return
        if random.random() >= BONUS_CHANCE:
            return
        kind = random.choice([FOOD_GOLDEN, FOOD_SLOW])
        ttl  = GOLDEN_TTL if kind == FOOD_GOLDEN else SLOW_TTL
        self.bonus = {
            "pos":  self._random_free_cell(),
            "type": kind,
            "ttl":  ttl,
        }

    def steer(self, d):
        # Сравниваем с последним запланированным направлением, а не с текущим:
        # это позволяет принять "вверх" даже если уже едем вверх в очереди.
        last = self.queue[-1] if self.queue else self.dir
        if d != OPPOSITE[last] and d != last:
            self.queue.append(d)

    def tick(self):
        """Возвращает None / тип съеденной еды (FOOD_NORMAL / FOOD_GOLDEN / FOOD_SLOW)."""
        if self.over:
            return None
        if self.queue:
            self.dir = self.queue.popleft()

        hx, hy = self.snake[0]
        dx, dy = self.dir
        head = (hx + dx, hy + dy)

        if self.invincible:
            # На время неуязвимости змейка проходит сквозь себя, стены и
            # обёртывается по краям поля. Никаких смертей.
            head = (head[0] % config.COLS, head[1] % config.ROWS)
        else:
            if (not (0 <= head[0] < config.COLS and 0 <= head[1] < config.ROWS)
                    or head in self.snake
                    or head in self.walls):
                # Запоминаем место удара — для анимации смерти. Если врезались в
                # стенку поля, кламп точки внутрь поля, чтобы эффект был виден.
                self.death_pos = (
                    max(0, min(config.COLS - 1, head[0])),
                    max(0, min(config.ROWS - 1, head[1])),
                )
                self.over = True
                return None

        self.snake.insert(0, head)

        # Истечение срока бонуса.
        if self.bonus is not None:
            self.bonus["ttl"] -= 1
            if self.bonus["ttl"] <= 0:
                self.bonus = None

        eaten = None

        if head == self.food:
            self.score        += 1
            self.apples_eaten += 1
            eaten              = FOOD_NORMAL
            self.food          = self._random_free_cell()
            self._maybe_spawn_bonus()
        elif self.bonus is not None and head == self.bonus["pos"]:
            kind = self.bonus["type"]
            if kind == FOOD_GOLDEN:
                self.score += 3
            else:
                self.score += 1
            self.apples_eaten += 1
            eaten              = kind
            self.bonus         = None

        if eaten is None:
            self.snake.pop()

        return eaten
