"""
Рисование: сетка, стены, еда, змейка, панель, оверлеи, кнопки, дропдауны.
Никакой игровой логики — только пиксели.

Все функции, которые рисуют по клеткам, берут текущую раскладку (CELL,
OFFSET_X/Y, COLS/ROWS) из модуля config через `config.X` — НЕ через
`from config import X`. Иначе значения "застынут" на момент импорта и
не обновятся при смене размера поля в настройках.
"""

import math
import pygame

import config
from config import (
    PANEL_H, WIN_W, WIN_H,
    C_GRID_A, C_GRID_B, C_GRID_BG, C_SNAKE, C_SNAKE_D, C_EYE, C_PUPIL,
    C_FOOD, C_FOOD_HL, C_GOLDEN, C_GOLDEN_HL, C_SLOW, C_SLOW_HL,
    C_TEXT, C_DIM, C_PANEL,
    C_WALL, C_WALL_HL,
    C_BTN, C_BTN_HOV, C_BTN_BRD, C_BTN_ACT, C_BTN_ACTH,
    FOOD_GOLDEN, FOOD_SLOW,
    DIFFICULTY_ORDER, DIFFICULTIES,
    SIZES,
)


# ============================================================
# ВСПОМОГАТЕЛЬНОЕ
# ============================================================

def lerp(a, b, t):
    return a + (b - a) * t


def _blend(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _cell_to_px(cx_cell, cy_cell):
    """Левый верхний угол клетки в пикселях с учётом текущего смещения."""
    return (cx_cell * config.CELL + config.OFFSET_X,
            cy_cell * config.CELL + config.OFFSET_Y)


# ============================================================
# СЕТКА И ОБЪЕКТЫ ИГРЫ
# ============================================================

def draw_grid(surface):
    cell = config.CELL
    ox, oy = config.OFFSET_X, config.OFFSET_Y
    # Заливка фона под/вокруг центрованного поля (если оно меньше окна).
    surface.fill(C_GRID_BG, pygame.Rect(0, PANEL_H, WIN_W, WIN_H - PANEL_H))
    for x in range(config.COLS):
        for y in range(config.ROWS):
            color = C_GRID_A if (x + y) % 2 == 0 else C_GRID_B
            pygame.draw.rect(surface, color,
                             pygame.Rect(ox + x * cell, oy + y * cell,
                                         cell, cell))


def draw_walls(surface, walls):
    cell = config.CELL
    inset = max(2, cell // 16)
    for wx, wy in walls:
        px, py = _cell_to_px(wx, wy)
        rect = pygame.Rect(px + inset, py + inset,
                           cell - 2 * inset, cell - 2 * inset)
        pygame.draw.rect(surface, C_WALL, rect, border_radius=cell // 8)
        pygame.draw.rect(surface, C_WALL_HL, rect,
                         width=2, border_radius=cell // 8)


def draw_food(surface, food):
    cell = config.CELL
    px, py = _cell_to_px(*food)
    fx = px + cell // 2
    fy = py + cell // 2
    r  = cell // 2 - max(2, cell // 12)
    pygame.draw.circle(surface, (80, 40, 20), (fx + 2, fy + 3), r)
    pygame.draw.circle(surface, C_FOOD, (fx, fy), r)
    pygame.draw.circle(surface, C_FOOD_HL, (fx - r // 3, fy - r // 3), r // 3)
    pygame.draw.line(surface, (60, 140, 40),
                     (fx, fy - r), (fx + 4, fy - r - 5), 2)


def draw_bonus(surface, bonus, frame):
    """Бонусная еда — пульсирует и моргает в конце жизни."""
    cell = config.CELL
    px, py = _cell_to_px(*bonus["pos"])
    bx = px + cell // 2
    by = py + cell // 2
    base_r = cell // 2 - max(2, cell // 12)

    pulse = 1.0 + 0.08 * math.sin(frame * 0.18)
    r = max(2, int(base_r * pulse))

    if bonus["ttl"] <= 6 and (frame // 4) % 2 == 0:
        return

    if bonus["type"] == FOOD_GOLDEN:
        body, hl = C_GOLDEN, C_GOLDEN_HL
    elif bonus["type"] == FOOD_SLOW:
        body, hl = C_SLOW, C_SLOW_HL
    else:
        body, hl = C_FOOD, C_FOOD_HL

    pygame.draw.circle(surface, (40, 40, 40), (bx + 2, by + 3), r)
    pygame.draw.circle(surface, body, (bx, by), r)
    pygame.draw.circle(surface, hl, (bx - r // 3, by - r // 3), r // 3)


# ============================================================
# ЗМЕЙКА (см. подробное объяснение в чате — гибридный рендер)
# ============================================================

def _corners(has_n, has_s, has_w, has_e, r):
    return (
        0 if (has_n or has_w) else r,
        0 if (has_n or has_e) else r,
        0 if (has_s or has_w) else r,
        0 if (has_s or has_e) else r,
    )


def _draw_cell(surface, color, px, py, tl, tr, bl, br):
    cell = config.CELL
    rect = pygame.Rect(int(round(px)), int(round(py)), cell, cell)
    pygame.draw.rect(
        surface, color, rect,
        border_top_left_radius=tl,
        border_top_right_radius=tr,
        border_bottom_left_radius=bl,
        border_bottom_right_radius=br,
    )


def draw_snake(surface, snake, prev_snake, t, dying=0.0, glitch=0.0, visible=True):
    """visible=False — пропустить рисование (для мигания при неуязвимости)."""
    if not visible:
        return
    n = len(snake)
    if n < 1:
        return

    if dying > 0:
        body_c = _blend(C_SNAKE, (220, 60, 50), min(1.0, dying * 1.2))
    elif glitch > 0:
        # Премиум-глитч на крупных множителях: подмешиваем золотой.
        body_c = _blend(C_SNAKE, C_GOLDEN, min(1.0, glitch))
    else:
        body_c = C_SNAKE

    cell = config.CELL
    ox, oy = config.OFFSET_X, config.OFFSET_Y
    R = cell // 3

    # 1. Фантомный хвост — съезжает со старой позиции хвоста к новой.
    #    Запоминаем направление к нему от клетки snake[n-1], чтобы потом
    #    та клетка стыковалась с фантомом без "зарубок" на скруглённых углах.
    phantom_dir_for_tail = None  # (dx, dy) от snake[n-1] К фантому
    if prev_snake and len(prev_snake) == n and t < 1.0:
        old_tail = prev_snake[n - 1]
        new_tail = snake[n - 1]
        if old_tail != new_tail:
            phx = lerp(old_tail[0], new_tail[0], t) * cell + ox
            phy = lerp(old_tail[1], new_tail[1], t) * cell + oy
            dx = new_tail[0] - old_tail[0]
            dy = new_tail[1] - old_tail[1]
            tl, tr, bl, br = _corners(dy == -1, dy == 1, dx == -1, dx == 1, R)
            _draw_cell(surface, body_c, phx, phy, tl, tr, bl, br)
            # Фантом находится в направлении -dx, -dy от snake[n-1].
            phantom_dir_for_tail = (-dx, -dy)

    # 2. Тело: клетки 1..n-1 в целочисленных позициях.
    for i in range(n - 1, 0, -1):
        cx_cell, cy_cell = snake[i]
        has_n = has_s = has_w = has_e = False
        for j in (i - 1, i + 1):
            if 0 <= j < n:
                dx = snake[j][0] - cx_cell
                dy = snake[j][1] - cy_cell
                if   dx ==  1: has_e = True
                elif dx == -1: has_w = True
                elif dy ==  1: has_s = True
                elif dy == -1: has_n = True
        # Пока фантомный хвост в кадре, клетка snake[n-1] должна вести себя
        # как обычная серединная клетка: добавляем "виртуального соседа"
        # со стороны фантома, иначе её задняя сторона скруглится и оставит
        # видимые щели на стыке.
        if i == n - 1 and phantom_dir_for_tail is not None:
            dx, dy = phantom_dir_for_tail
            if   dx ==  1: has_e = True
            elif dx == -1: has_w = True
            elif dy ==  1: has_s = True
            elif dy == -1: has_n = True
        tl, tr, bl, br = _corners(has_n, has_s, has_w, has_e, R)
        px, py = _cell_to_px(cx_cell, cy_cell)
        _draw_cell(surface, body_c, px, py, tl, tr, bl, br)

    # 3. Голова: интерполированная позиция.
    if prev_snake and len(prev_snake) > 0:
        head_x = lerp(prev_snake[0][0], snake[0][0], t)
        head_y = lerp(prev_snake[0][1], snake[0][1], t)
    else:
        head_x, head_y = snake[0]

    has_n = has_s = has_w = has_e = False
    if n >= 2:
        dx = snake[1][0] - snake[0][0]
        dy = snake[1][1] - snake[0][1]
        if   dx ==  1: has_e = True
        elif dx == -1: has_w = True
        elif dy ==  1: has_s = True
        elif dy == -1: has_n = True
    tl, tr, bl, br = _corners(has_n, has_s, has_w, has_e, R)
    _draw_cell(surface, body_c,
               head_x * cell + ox, head_y * cell + oy,
               tl, tr, bl, br)

    # 4. Глаза.
    head_cx = head_x * cell + ox + cell // 2
    head_cy = head_y * cell + oy + cell // 2
    if n >= 2:
        fdx = snake[0][0] - snake[1][0]
        fdy = snake[0][1] - snake[1][1]
    else:
        fdx, fdy = 1, 0
    if fdx == 0 and fdy == 0:
        fdx = 1

    perp_x, perp_y = -fdy, fdx
    eye_off_side   = cell * 0.20
    eye_off_fwd    = cell * 0.18
    eye_r          = max(2, cell // 8)
    pupil_r        = max(1, eye_r - 1)
    for sign in (+1, -1):
        ex = head_cx + perp_x * eye_off_side * sign + fdx * eye_off_fwd
        ey = head_cy + perp_y * eye_off_side * sign + fdy * eye_off_fwd
        pygame.draw.circle(surface, C_EYE, (int(ex), int(ey)), eye_r)
        pygame.draw.circle(surface, C_PUPIL,
                           (int(ex + fdx * 1.5), int(ey + fdy * 1.5)),
                           pupil_r)


# ============================================================
# ПАНЕЛЬ И ОВЕРЛЕИ
# ============================================================

def draw_panel(surface, score, best, difficulty_name,
               cur_mult, best_mult, fb, fs):
    surface.fill(C_PANEL, pygame.Rect(0, 0, WIN_W, PANEL_H))

    # ---- Слева: "Счёт: N  ×M" ----
    score_surf = fb.render(f"Счёт: {score}", True, C_TEXT)
    surface.blit(score_surf, (14, 12))
    if cur_mult > 1:
        mult_surf = fs.render(f"×{cur_mult}", True, C_GOLDEN)
        surface.blit(mult_surf, (14 + score_surf.get_width() + 8, 18))

    # ---- По центру: название сложности ----
    diff_txt = fs.render(difficulty_name, True, C_DIM)
    surface.blit(diff_txt,
                 ((WIN_W - diff_txt.get_width()) // 2, 18))

    # ---- Справа: "×M  Рекорд: B" ----
    best_str  = f"Рекорд: {best}"
    best_surf = fs.render(best_str, True, C_DIM)
    bx = WIN_W - best_surf.get_width() - 14
    surface.blit(best_surf, (bx, 18))
    if best_mult > 1:
        bm_surf = fs.render(f"×{best_mult}", True, C_GOLDEN)
        surface.blit(bm_surf, (bx - bm_surf.get_width() - 8, 18))


def draw_overlay_bg(surface, alpha=170):
    ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    ov.fill((0, 0, 0, alpha))
    surface.blit(ov, (0, 0))


def draw_title(surface, title, subtitle, y_title, fb, fs):
    s1 = fb.render(title, True, C_TEXT)
    surface.blit(s1, ((WIN_W - s1.get_width()) // 2, y_title))
    if subtitle:
        s2 = fs.render(subtitle, True, C_DIM)
        surface.blit(s2, ((WIN_W - s2.get_width()) // 2, y_title + 38))


def draw_label(surface, text, cx, cy, font, color=C_DIM):
    s = font.render(text, True, color)
    surface.blit(s, (cx - s.get_width() // 2, cy - s.get_height() // 2))


# ============================================================
# КНОПКИ
# ============================================================

class Button:
    W = 280
    H = 48

    def __init__(self, cx, cy, label, action, active=False, w=None, h=None):
        w = w or self.W
        h = h or self.H
        self.rect   = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        self.label  = label
        self.action = action
        self.active = active

    def hit(self, pos):
        return self.rect.collidepoint(pos)

    def draw(self, surface, font, mouse_pos):
        hover = self.rect.collidepoint(mouse_pos)
        if self.active:
            base, hov = C_BTN_ACT, C_BTN_ACTH
        else:
            base, hov = C_BTN, C_BTN_HOV
        pygame.draw.rect(surface, hov if hover else base,
                         self.rect, border_radius=8)
        pygame.draw.rect(surface, C_BTN_BRD, self.rect,
                         width=2, border_radius=8)
        txt = font.render(self.label, True, C_TEXT)
        surface.blit(txt, (self.rect.centerx - txt.get_width() // 2,
                           self.rect.centery - txt.get_height() // 2))


# ============================================================
# ВЫПАДАЮЩИЙ СПИСОК (DROPDOWN)
# ============================================================

class Dropdown:
    """
    Кнопка-дропдаун: показывает текущее значение, по клику открывается
    список опций ВНИЗ. Активность («открыт/закрыт») управляется снаружи —
    в главном цикле, через Settings/Menu state. Это нужно потому, что
    при открытом дропдауне остальной UI должен быть неактивен.
    """
    W = 280
    H = 48

    def __init__(self, cx, cy, options, label_for, current_key, key_id):
        self.rect = pygame.Rect(cx - self.W // 2, cy - self.H // 2,
                                self.W, self.H)
        self.options     = options          # список ключей
        self.label_for   = label_for        # callable: ключ -> строка
        self.current_key = current_key
        self.id          = key_id           # строковый идентификатор для main loop

    def set_current(self, key):
        self.current_key = key

    def hit_button(self, pos):
        return self.rect.collidepoint(pos)

    def option_rects(self):
        # Если списку не хватает места снизу — открываем вверх.
        list_h  = len(self.options) * self.H
        open_up = self.rect.y + self.H + list_h > WIN_H
        rects = []
        for i, key in enumerate(self.options):
            y_off = -((i + 1) * self.H) if open_up else (i + 1) * self.H
            r = pygame.Rect(self.rect.x,
                            self.rect.y + y_off,
                            self.W, self.H)
            rects.append((key, r))
        return rects

    def hit_option(self, pos):
        for key, r in self.option_rects():
            if r.collidepoint(pos):
                return key
        return None

    def draw_button(self, surface, font, mouse_pos, expanded=False):
        hover = self.rect.collidepoint(mouse_pos)
        if expanded:
            base, hov = C_BTN_ACT, C_BTN_ACTH
        else:
            base, hov = C_BTN, C_BTN_HOV
        pygame.draw.rect(surface, hov if hover else base,
                         self.rect, border_radius=8)
        pygame.draw.rect(surface, C_BTN_BRD, self.rect,
                         width=2, border_radius=8)
        # Подпись по центру.
        txt = font.render(self.label_for(self.current_key), True, C_TEXT)
        surface.blit(txt, (self.rect.centerx - txt.get_width() // 2,
                           self.rect.centery - txt.get_height() // 2))
        # Треугольник-индикатор справа — рисуем сами, чтобы не зависеть
        # от наличия глифа в системном шрифте.
        cx = self.rect.right - 18
        cy = self.rect.centery
        s  = 6
        if expanded:
            pts = [(cx - s, cy + s // 2),
                   (cx + s, cy + s // 2),
                   (cx,     cy - s // 2 - 1)]
        else:
            pts = [(cx - s, cy - s // 2),
                   (cx + s, cy - s // 2),
                   (cx,     cy + s // 2 + 1)]
        pygame.draw.polygon(surface, C_TEXT, pts)

    def draw_options(self, surface, font, mouse_pos):
        for key, r in self.option_rects():
            hover = r.collidepoint(mouse_pos)
            is_current = (key == self.current_key)
            if is_current:
                base, hov = C_BTN_ACT, C_BTN_ACTH
            else:
                base, hov = C_BTN, C_BTN_HOV
            pygame.draw.rect(surface, hov if hover else base,
                             r, border_radius=8)
            pygame.draw.rect(surface, C_BTN_BRD, r,
                             width=2, border_radius=8)
            txt = font.render(self.label_for(key), True, C_TEXT)
            surface.blit(txt, (r.centerx - txt.get_width() // 2,
                               r.centery - txt.get_height() // 2))


# ============================================================
# ПОСТРОИТЕЛИ ЭКРАНОВ
# ============================================================

def build_main_menu_buttons():
    cx = WIN_W // 2
    y0 = WIN_H // 2 - 60
    return [
        Button(cx, y0,           "Играть",    ("play",     None)),
        Button(cx, y0 + 60,      "Настройки", ("settings", None)),
        Button(cx, y0 + 120,     "Выход",     ("quit",     None)),
    ]


def build_settings(difficulty, board_size):
    """
    Возвращает (diff_dropdown, walls_pos, bonuses_pos, revivals_pos,
                size_dropdown, back_button).
    *_pos — это (cx, cy) для построения кнопок-тумблеров снаружи
    (их подписи зависят от текущего состояния).
    """
    cx = WIN_W // 2
    diff_dd = Dropdown(
        cx, 170,
        DIFFICULTY_ORDER,
        lambda k: DIFFICULTIES[k]["name"],
        difficulty,
        "difficulty",
    )
    walls_pos    = (cx, 270)
    bonuses_pos  = (cx, 370)
    revivals_pos = (cx, 470)
    size_dd = Dropdown(
        cx, 570,
        SIZES,
        lambda s: f"{s} × {s}",
        board_size,
        "board_size",
    )
    back_btn = Button(cx, 670, "Назад", ("back", None))
    return diff_dd, walls_pos, bonuses_pos, revivals_pos, size_dd, back_btn


def build_walls_button(walls_pos, obstacles_on):
    cx, cy = walls_pos
    label = f"Препятствия: {'ВКЛ' if obstacles_on else 'ВЫКЛ'}"
    return Button(cx, cy, label, ("toggle_obstacles", None),
                  active=obstacles_on)


def build_bonuses_button(bonuses_pos, bonuses_on):
    cx, cy = bonuses_pos
    label = f"Бонусные яблоки: {'ВКЛ' if bonuses_on else 'ВЫКЛ'}"
    return Button(cx, cy, label, ("toggle_bonuses", None),
                  active=bonuses_on)


def build_revivals_button(revivals_pos, revivals_on):
    cx, cy = revivals_pos
    label = f"Возрождение: {'ВКЛ' if revivals_on else 'ВЫКЛ'}"
    return Button(cx, cy, label, ("toggle_revivals", None),
                  active=revivals_on)


def build_gameover_buttons():
    cx = WIN_W // 2
    y  = WIN_H // 2 + 80
    return [
        Button(cx - 150, y, "Заново", ("restart", None), w=240),
        Button(cx + 150, y, "В меню", ("menu",    None), w=240),
    ]


def build_pause_buttons():
    cx = WIN_W // 2
    y  = WIN_H // 2 + 40
    return [
        Button(cx - 150, y, "Продолжить", ("resume", None), w=240),
        Button(cx + 150, y, "В меню",     ("menu",   None), w=240),
    ]


def build_revival_offer_buttons():
    cx = WIN_W // 2
    y  = WIN_H // 2 + 60
    return [
        Button(cx - 150, y, "Возродиться", ("accept_revive", None), w=240),
        Button(cx + 150, y, "Отказаться",  ("decline_revive", None), w=240),
    ]


def build_math_answer_buttons(options):
    """Четыре кнопки с вариантами в сетке 2×2 по центру."""
    cx = WIN_W // 2
    cy = WIN_H // 2 + 80
    dx = 130
    dy = 32
    coords = [
        (cx - dx, cy - dy),  # TL
        (cx + dx, cy - dy),  # TR
        (cx - dx, cy + dy),  # BL
        (cx + dx, cy + dy),  # BR
    ]
    btns = []
    for (bx, by), opt in zip(coords, options):
        btns.append(Button(bx, by, str(opt),
                           ("answer", opt), w=240))
    return btns


def draw_time_bar(surface, fraction_left):
    """Полоса оставшегося времени по верху игровой зоны под панелью."""
    bar_h = 8
    full_w = WIN_W
    w = int(full_w * max(0.0, min(1.0, fraction_left)))
    # Цвет от зелёного к красному по мере уменьшения времени.
    if fraction_left > 0.5:
        color = (110, 200, 80)
    elif fraction_left > 0.25:
        color = (220, 195, 60)
    else:
        color = (220, 80, 60)
    pygame.draw.rect(surface, (40, 40, 40),
                     pygame.Rect(0, PANEL_H, full_w, bar_h))
    pygame.draw.rect(surface, color,
                     pygame.Rect(0, PANEL_H, w, bar_h))


def draw_countdown_number(surface, value, font_huge):
    """Огромная цифра отсчёта (3, 2, 1) по центру с лёгкой пульсацией."""
    cx = WIN_W // 2
    cy = WIN_H // 2
    # Pop-in: оп-у-у-у пульсация по фракции в секунде.
    txt_surf = font_huge.render(str(value), True, C_GOLDEN)
    # Анимация масштаба по фракции в текущей секунде.
    surface.blit(txt_surf, (cx - txt_surf.get_width() // 2,
                            cy - txt_surf.get_height() // 2))


def draw_math_problem(surface, question_text, fb_big):
    """Большой текст вопроса по центру верха игровой зоны."""
    cx = WIN_W // 2
    cy = WIN_H // 2 - 60
    s = fb_big.render(question_text, True, C_TEXT)
    surface.blit(s, (cx - s.get_width() // 2, cy - s.get_height() // 2))
