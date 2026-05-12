"""
Точка входа: pygame, главный цикл, обработка ввода, состояния.
Логика игры — в game.py, рисование — в render.py, константы — в config.py.
"""

import os
import sys
import random
import asyncio
import pygame

import config
from config import (
    WIN_W, WIN_H, PANEL_H, FPS, SCALE,
    UP, DOWN, LEFT, RIGHT,
    DIFFICULTIES, WALLS_COUNT,
    STATE_MAIN_MENU, STATE_SETTINGS, STATE_PLAYING,
    STATE_PAUSED, STATE_DYING, STATE_GAMEOVER,
    STATE_REVIVAL_OFFER, STATE_REVIVAL_COUNTDOWN, STATE_REVIVAL_MATH,
    DYING_DURATION, GLITCH_THRESHOLD, GLITCH_DURATION,
    REVIVAL_LENGTH_PENALTY, REVIVAL_SCORE_PENALTY,
    REVIVAL_INVINCIBLE_SEC, REVIVAL_TIMER_SEC, REVIVAL_COUNTDOWN_SEC,
    FOOD_GOLDEN, FOOD_SLOW, SLOW_DELTA,
    C_FOOD, C_GOLDEN, C_SLOW, C_TEXT, C_SNAKE, C_DIM,
)
from game import Game, load_data, save_data, _is_mobile_device
from render import (
    draw_grid, draw_walls, draw_food, draw_bonus, draw_snake, draw_panel,
    draw_overlay_bg, draw_title, draw_label,
    build_main_menu_buttons, build_settings,
    build_walls_button, build_bonuses_button, build_revivals_button,
    build_gameover_buttons, build_pause_buttons,
    build_revival_offer_buttons, build_math_answer_buttons,
    draw_time_bar, draw_countdown_number, draw_math_problem,
)
from effects import Effects


def generate_math_problem():
    """Простая арифметика. Возвращает (текст, верный ответ, [4 варианта])."""
    op = random.choice(["+", "+", "−", "−", "×"])
    if op == "+":
        a, b = random.randint(2, 15), random.randint(2, 15)
        answer = a + b
    elif op == "−":
        a, b = random.randint(5, 20), random.randint(1, 10)
        if b > a:
            a, b = b, a
        answer = a - b
    else:  # ×
        a, b = random.randint(2, 9), random.randint(2, 9)
        answer = a * b
    question = f"{a}  {op}  {b}  =  ?"

    wrongs = set()
    deltas = [-3, -2, -1, 1, 2, 3]
    random.shuffle(deltas)
    for d in deltas:
        c = answer + d
        if c >= 0 and c != answer:
            wrongs.add(c)
        if len(wrongs) >= 3:
            break
    options = list(wrongs) + [answer]
    random.shuffle(options)
    return question, answer, options


def cell_center_px(cell_pos):
    """Пиксельный центр клетки (с учётом смещения для центрования поля)."""
    cx, cy = cell_pos
    return (cx * config.CELL + config.OFFSET_X + config.CELL // 2,
            cy * config.CELL + config.OFFSET_Y + config.CELL // 2)


async def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Змейка")
    clock  = pygame.time.Clock()

    # Шрифт: предпочитаем приложенный DejaVu Sans (свободная гарнитура
    # с кириллицей) — он гарантирует одинаковый вид и на десктопе,
    # и в браузере на iOS. Если файла нет — падаем на системный шрифт.
    _DIR = os.path.dirname(os.path.abspath(__file__))
    _FONT_REG  = os.path.join(_DIR, "assets", "DejaVuSans.ttf")
    _FONT_BOLD = os.path.join(_DIR, "assets", "DejaVuSans-Bold.ttf")

    def load_font(size, bold=False):
        path = _FONT_BOLD if bold else _FONT_REG
        if os.path.isfile(path):
            return pygame.font.Font(path, size)
        try:
            return pygame.font.SysFont("segoeui,arial", size, bold=bold)
        except Exception:
            return pygame.font.Font(None, size)

    # На мобильных устройствах canvas сжимается браузером сильнее, чем на ПК,
    # поэтому шрифты дополнительно увеличиваем. Базовые кегли умножены на
    # SCALE — общий множитель внутреннего разрешения рендера.
    _is_mobile  = _is_mobile_device()
    _scale      = 1.45 if _is_mobile else 1.0
    fb           = load_font(int(24 * _scale * SCALE), bold=True)
    fs           = load_font(int(17 * _scale * SCALE))
    fx_font      = load_font(int(20 * _scale * SCALE), bold=True)
    fx_big_font  = load_font(int(86 * _scale * SCALE), bold=True)  # отсчёт 3-2-1, ×N
    fx_math_font = load_font(int(50 * _scale * SCALE), bold=True)  # текст примера
    START_LENGTH = 5  # совпадает с длиной змейки в Game.reset()

    # ---- Загрузка сохранения и применение размера поля ----
    data              = load_data()
    best              = data["best"]
    best_with_revival = data["best_with_revival"]
    best_milestone    = data["best_milestone"]
    difficulty        = data["difficulty"]
    obstacles_on      = data["obstacles"]
    bonuses_on        = data["bonuses"]
    revivals_on       = data["revivals"]
    board_size        = data["board_size"]
    touch_mode        = data["touch_mode"]
    config.apply_size(board_size)

    # Создаём пустую игру, чтобы было что рисовать на фоне меню.
    game       = Game()
    game.reset()
    prev_snake = list(game.snake)
    fx         = Effects()

    state      = STATE_MAIN_MENU
    # Какой дропдаун сейчас раскрыт на экране настроек: "difficulty" / "board_size" / None.
    open_dropdown = None

    def _sync_touch_mode_to_js():
        """Передаём текущий режим тач-управления в localStorage,
        чтобы JS-перехватчик свайпов знал, отключаться ему или нет.
        На десктопе platform.window отсутствует — просто игнорируем."""
        try:
            import platform as _pf
            if hasattr(_pf, "window"):
                _pf.window.localStorage.setItem("snake_touch_mode", touch_mode)
        except Exception:
            pass

    def persist():
        save_data({
            "best":              best,
            "best_with_revival": best_with_revival,
            "best_milestone":    best_milestone,
            "difficulty":        difficulty,
            "obstacles":         obstacles_on,
            "bonuses":           bonuses_on,
            "revivals":          revivals_on,
            "board_size":        board_size,
            "touch_mode":        touch_mode,
        })
        _sync_touch_mode_to_js()

    # Один раз на старте — выставляем JS-флаг.
    _sync_touch_mode_to_js()

    tick_rate     = DIFFICULTIES[difficulty]["start"]
    tick_interval = 1.0 / tick_rate
    tick_accum    = 0.0
    frame         = 0
    dying_t       = 0.0
    glitch_t      = 0.0  # активный остаток времени глитч-эффекта
    milestone     = 1    # последний достигнутый множитель длины (×1 = старт)

    # ---- Состояние возрождения ----
    used_revival       = False  # использовалось ли возрождение в текущей игре
    invincible_left    = 0.0    # сколько секунд неуязвимости осталось
    countdown_t        = 0.0    # обратный отсчёт 3-2-1 (секунды)
    math_timer         = 0.0    # сколько осталось на решение примера
    math_question      = ""
    math_answer        = 0
    math_options       = []
    math_buttons       = []
    revival_offer_btns = build_revival_offer_buttons()

    # Кнопки экранов, не зависящие от состояния тумблеров.
    main_menu_btns = build_main_menu_buttons()
    gameover_btns  = build_gameover_buttons()
    pause_btns     = build_pause_buttons()

    KEY_MAP = {
        pygame.K_UP:    UP,    pygame.K_w: UP,
        pygame.K_DOWN:  DOWN,  pygame.K_s: DOWN,
        pygame.K_LEFT:  LEFT,  pygame.K_a: LEFT,
        pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT,
    }
    PAUSE_KEYS = (pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_p)

    # ---- Тач-управление ----
    # Координаты пальца в нормированных значениях [0..1] относительно окна.
    # Детектим свайп НА ДВИЖЕНИИ (FINGERMOTION), как только палец сдвинулся
    # на достаточное расстояние — это намного отзывчивее, чем ждать FINGERUP.
    # После срабатывания "потребляем" жест (swipe_consumed=True), чтобы он
    # не сработал второй раз в том же касании.
    swipe_start     = None    # (x, y) при FINGERDOWN
    swipe_consumed  = False   # уже передали направление в этом касании?
    SWIPE_THRESHOLD = 0.03    # 3% стороны окна — около 20 px на айфоне

    def start_game():
        """Запускает новую игру с текущими настройками."""
        nonlocal tick_rate, tick_interval, tick_accum, prev_snake, state, milestone
        nonlocal glitch_t, used_revival, invincible_left
        config.apply_size(board_size)
        cfg = DIFFICULTIES[difficulty]
        walls = WALLS_COUNT if obstacles_on else 0
        game.reset(walls_count=walls, bonuses_enabled=bonuses_on)
        prev_snake      = list(game.snake)
        tick_rate       = cfg["start"]
        tick_interval   = 1.0 / tick_rate
        tick_accum      = 0.0
        state           = STATE_PLAYING
        milestone       = 1
        glitch_t        = 0.0
        used_revival    = False
        invincible_left = 0.0
        fx.particles.clear()
        fx.popups.clear()
        fx.big_popups.clear()

    def finalize_records():
        """Обновляет рекорды после окончательной смерти."""
        nonlocal best, best_with_revival
        if difficulty == "chill":
            return  # Чилл не идёт ни в один рекорд
        if used_revival:
            if game.score > best_with_revival:
                best_with_revival = game.score
                persist()
        else:
            if game.score > best:
                best = game.score
                persist()

    def revive():
        """Восстанавливает змейку из prev_snake со штрафами и неуязвимостью."""
        nonlocal state, tick_accum, milestone, used_revival, invincible_left, prev_snake
        new_len = max(1, len(prev_snake) - REVIVAL_LENGTH_PENALTY)
        game.snake = list(prev_snake[:new_len])
        game.over  = False
        game.death_pos = None
        # Направление — то, что было ДО рокового шага (от шеи к голове).
        if len(game.snake) >= 2:
            game.dir = (game.snake[0][0] - game.snake[1][0],
                        game.snake[0][1] - game.snake[1][1])
        game.queue.clear()
        game.score = max(0, game.score - REVIVAL_SCORE_PENALTY)
        # Пересчитываем текущий множитель — длина уменьшилась.
        milestone = max(1, len(game.snake) // START_LENGTH)
        game.invincible = True
        invincible_left = REVIVAL_INVINCIBLE_SEC
        used_revival    = True
        state           = STATE_PLAYING
        tick_accum      = 0.0
        prev_snake      = list(game.snake)
        fx.particles.clear()
        fx.popups.clear()
        fx.big_popups.clear()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()

        # ----------------------------------------------------------
        # UI экрана настроек строим один раз и переиспользуем в обработке
        # событий И в отрисовке этого же кадра. Если состояние сменится
        # внутри обработки (например, "Настройки" нажали из главного меню)
        # — UI будет всё равно нужен для отрисовки этого кадра.
        # ----------------------------------------------------------
        def build_settings_ui():
            d, wp, bp, rp, s, t, b = build_settings(difficulty, board_size, touch_mode)
            w  = build_walls_button(wp, obstacles_on)
            bn = build_bonuses_button(bp, bonuses_on)
            r  = build_revivals_button(rp, revivals_on)
            return d, w, bn, r, s, t, b

        diff_dd, walls_btn, bonuses_btn, revivals_btn, size_dd, touch_dd, back_btn = build_settings_ui()

        # ----------------------------------------------------------
        # ОБРАБОТКА ВВОДА
        # ----------------------------------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            # ===== Тач: свайпы во время игры (если выбран режим свайпов) =====
            # Меню/кнопки работают через MOUSEBUTTONDOWN (SDL автоматически
            # конвертирует тап в клик), сюда попадают только жесты в STATE_PLAYING.
            # В режиме крестовины свайпы игнорируем — управление только кнопками.
            if event.type == pygame.FINGERDOWN:
                swipe_start    = (event.x, event.y)
                swipe_consumed = False
            elif event.type == pygame.FINGERMOTION:
                if (swipe_start is not None
                        and not swipe_consumed
                        and state == STATE_PLAYING
                        and touch_mode == "swipes"):
                    dx = event.x - swipe_start[0]
                    dy = event.y - swipe_start[1]
                    if abs(dx) > SWIPE_THRESHOLD or abs(dy) > SWIPE_THRESHOLD:
                        if abs(dx) > abs(dy):
                            game.steer(RIGHT if dx > 0 else LEFT)
                        else:
                            game.steer(DOWN if dy > 0 else UP)
                        # Сдвигаем "начало" к текущей точке — серия свайпов
                        # в одном жесте (зигзаг) ловится без отрыва пальца.
                        swipe_start = (event.x, event.y)
            elif event.type == pygame.FINGERUP:
                swipe_start    = None
                swipe_consumed = False

            # ===== Мышь =====
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state == STATE_MAIN_MENU:
                    for b in main_menu_btns:
                        if b.hit(event.pos):
                            kind, _ = b.action
                            if   kind == "play":     start_game()
                            elif kind == "settings": state = STATE_SETTINGS; open_dropdown = None
                            elif kind == "quit":     running = False
                            break

                elif state == STATE_SETTINGS:
                    # Если открыт дропдаун — клик может попасть в одну из его опций
                    # ИЛИ в любое другое место (тогда дропдаун закроется).
                    if open_dropdown == "difficulty":
                        chosen = diff_dd.hit_option(event.pos)
                        if chosen is not None:
                            difficulty = chosen
                            persist()
                        open_dropdown = None
                    elif open_dropdown == "board_size":
                        chosen = size_dd.hit_option(event.pos)
                        if chosen is not None:
                            board_size = chosen
                            config.apply_size(board_size)
                            persist()
                        open_dropdown = None
                    elif open_dropdown == "touch_mode":
                        chosen = touch_dd.hit_option(event.pos)
                        if chosen is not None:
                            touch_mode = chosen
                            persist()
                        open_dropdown = None
                    else:
                        # Дропдаунов не открыто — обычные клики.
                        if diff_dd.hit_button(event.pos):
                            open_dropdown = "difficulty"
                        elif size_dd.hit_button(event.pos):
                            open_dropdown = "board_size"
                        elif touch_dd.hit_button(event.pos):
                            open_dropdown = "touch_mode"
                        elif walls_btn.hit(event.pos):
                            obstacles_on = not obstacles_on
                            persist()
                        elif bonuses_btn.hit(event.pos):
                            bonuses_on = not bonuses_on
                            persist()
                        elif revivals_btn.hit(event.pos):
                            revivals_on = not revivals_on
                            persist()
                        elif back_btn.hit(event.pos):
                            state = STATE_MAIN_MENU

                elif state == STATE_GAMEOVER:
                    for b in gameover_btns:
                        if b.hit(event.pos):
                            kind, _ = b.action
                            if   kind == "restart": start_game()
                            elif kind == "menu":    state = STATE_MAIN_MENU
                            break

                elif state == STATE_PAUSED:
                    for b in pause_btns:
                        if b.hit(event.pos):
                            kind, _ = b.action
                            if   kind == "resume":
                                state = STATE_PLAYING
                                tick_accum = 0.0
                            elif kind == "menu":
                                state = STATE_MAIN_MENU
                            break


                elif state == STATE_REVIVAL_OFFER:
                    for b in revival_offer_btns:
                        if b.hit(event.pos):
                            kind, _ = b.action
                            if kind == "accept_revive":
                                state = STATE_REVIVAL_COUNTDOWN
                                countdown_t = REVIVAL_COUNTDOWN_SEC
                            elif kind == "decline_revive":
                                state = STATE_GAMEOVER
                                finalize_records()
                            break

                elif state == STATE_REVIVAL_MATH:
                    for b in math_buttons:
                        if b.hit(event.pos):
                            _, payload = b.action
                            if payload == math_answer:
                                revive()
                            else:
                                state = STATE_GAMEOVER
                                finalize_records()
                            break

            # ===== Клавиатура =====
            if event.type == pygame.KEYDOWN:
                if state == STATE_PLAYING:
                    if event.key in PAUSE_KEYS:
                        state = STATE_PAUSED
                    elif event.key in KEY_MAP:
                        game.steer(KEY_MAP[event.key])
                elif state == STATE_PAUSED:
                    if event.key in PAUSE_KEYS:
                        state = STATE_PLAYING
                        tick_accum = 0.0
                elif state == STATE_GAMEOVER:
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        start_game()
                    elif event.key == pygame.K_ESCAPE:
                        state = STATE_MAIN_MENU
                elif state == STATE_MAIN_MENU:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        start_game()
                elif state == STATE_SETTINGS:
                    if event.key == pygame.K_ESCAPE:
                        if open_dropdown is not None:
                            open_dropdown = None
                        else:
                            state = STATE_MAIN_MENU
                elif state == STATE_REVIVAL_OFFER:
                    if event.key == pygame.K_ESCAPE:
                        state = STATE_GAMEOVER
                        finalize_records()

        # ----------------------------------------------------------
        # ИГРОВАЯ ЛОГИКА
        # ----------------------------------------------------------
        if state == STATE_PLAYING:
            tick_accum += dt
            cfg = DIFFICULTIES[difficulty]
            while tick_accum >= tick_interval:
                tick_accum -= tick_interval
                prev_snake  = list(game.snake)
                food_pos_before  = game.food
                bonus_pos_before = game.bonus["pos"] if game.bonus else None
                eaten            = game.tick()

                if game.over:
                    if game.death_pos:
                        px, py = cell_center_px(game.death_pos)
                        fx.burst(px, py, (220, 60, 50),
                                 count=24, speed=(120, 320), life=0.7, size=(3, 6))
                        fx.burst(px, py, C_SNAKE,
                                 count=14, speed=(60, 200), life=0.6, size=(2, 5))
                    state   = STATE_DYING
                    dying_t = 0.0
                    break

                if eaten is not None:
                    # Рекорды по счёту обновляются только в конце игры
                    # (через finalize_records) — мид-игре мы ещё не знаем,
                    # использует ли игрок возрождение.
                    if eaten == FOOD_GOLDEN:
                        ex, ey = cell_center_px(bonus_pos_before)
                        fx.burst(ex, ey, C_GOLDEN, count=14)
                        fx.popup(ex, ey - 6 * SCALE, "+3", C_GOLDEN)
                    elif eaten == FOOD_SLOW:
                        ex, ey = cell_center_px(bonus_pos_before)
                        fx.burst(ex, ey, C_SLOW, count=12)
                        fx.popup(ex, ey - 6 * SCALE, "+1", C_SLOW)
                        tick_rate     = max(tick_rate - SLOW_DELTA, cfg["start"])
                        tick_interval = 1.0 / tick_rate
                    else:
                        ex, ey = cell_center_px(food_pos_before)
                        fx.burst(ex, ey, C_FOOD, count=10)
                        fx.popup(ex, ey - 6 * SCALE, "+1", C_TEXT)
                    if game.apples_eaten % cfg["step"] == 0:
                        tick_rate     = min(tick_rate + 2, cfg["max"])
                        tick_interval = 1.0 / tick_rate

                    # Достижение нового множителя длины: ×2, ×3, ×4 ...
                    new_mult = len(game.snake) // START_LENGTH
                    if new_mult > milestone:
                        milestone = new_mult
                        fx.big_popup(WIN_W // 2,
                                     PANEL_H + (WIN_H - PANEL_H) // 2,
                                     f"×{milestone}",
                                     C_GOLDEN, fx_big_font)
                        # Обновляем рекорд множителя (как и счёт — не в Чилле).
                        if difficulty != "chill" and milestone > best_milestone:
                            best_milestone = milestone
                            persist()
                        if milestone >= GLITCH_THRESHOLD:
                            glitch_t = GLITCH_DURATION

        elif state == STATE_DYING:
            dying_t += dt
            if dying_t >= DYING_DURATION:
                # Можно ли возродиться?
                if (revivals_on
                        and not used_revival
                        and difficulty != "hardcore"):
                    state = STATE_REVIVAL_OFFER
                else:
                    state = STATE_GAMEOVER
                    finalize_records()

        elif state == STATE_REVIVAL_COUNTDOWN:
            countdown_t -= dt
            if countdown_t <= 0:
                # Отсчёт закончился — генерируем пример и переходим к решению.
                math_question, math_answer, math_options = generate_math_problem()
                math_buttons = build_math_answer_buttons(math_options)
                math_timer   = REVIVAL_TIMER_SEC
                state        = STATE_REVIVAL_MATH

        elif state == STATE_REVIVAL_MATH:
            math_timer -= dt
            if math_timer <= 0:
                state = STATE_GAMEOVER
                finalize_records()

        fx.update(dt)
        # Глитч-таймер тикает только во время игры — на паузе/смерти держим.
        if state == STATE_PLAYING:
            glitch_t = max(0.0, glitch_t - dt)
            # Тикаем неуязвимость.
            if game.invincible:
                invincible_left -= dt
                if invincible_left <= 0:
                    game.invincible = False
                    invincible_left = 0.0
        glitch_progress = glitch_t / GLITCH_DURATION if GLITCH_DURATION > 0 else 0.0

        # Мигание змейки во время неуязвимости (4 Гц).
        snake_visible = True
        if game.invincible:
            snake_visible = (pygame.time.get_ticks() // 125) % 2 == 0

        interp_t = (
            min(tick_accum / tick_interval, 1.0)
            if state == STATE_PLAYING else 1.0
        )
        # Анимация смерти: краснеет в STATE_DYING, остаётся красной
        # на экране Game Over до рестарта/выхода в меню.
        if state == STATE_DYING:
            dying_progress = min(1.0, dying_t / DYING_DURATION)
        elif state == STATE_GAMEOVER:
            dying_progress = 1.0
        else:
            dying_progress = 0.0

        # ----------------------------------------------------------
        # РИСОВАНИЕ
        # ----------------------------------------------------------
        draw_grid(screen)
        draw_walls(screen, game.walls)
        if state != STATE_DYING:
            draw_food(screen, game.food)
            if game.bonus is not None:
                draw_bonus(screen, game.bonus, frame)
        draw_snake(screen, game.snake, prev_snake, interp_t,
                   dying=dying_progress, glitch=glitch_progress,
                   visible=snake_visible)
        fx.draw(screen, fx_font)
        draw_panel(screen, game.score, best,
                   DIFFICULTIES[difficulty]["name"],
                   milestone, best_milestone, fb, fs)

        if state == STATE_MAIN_MENU:
            draw_overlay_bg(screen)
            draw_title(screen, "ЗМЕЙКА",
                       "Стрелки · WASD · Свайпы",
                       WIN_H // 2 - 180 * SCALE, fb, fs)
            for b in main_menu_btns:
                b.draw(screen, fs, mouse_pos)

        elif state == STATE_SETTINGS:
            diff_dd, walls_btn, bonuses_btn, revivals_btn, size_dd, touch_dd, back_btn = build_settings_ui()
            draw_overlay_bg(screen)
            draw_title(screen, "НАСТРОЙКИ", "", 75 * SCALE, fb, fs)
            Lx = WIN_W // 4
            Rx = WIN_W * 3 // 4
            # Ряд 1
            draw_label(screen, "Сложность",        Lx, 135 * SCALE, fs)
            draw_label(screen, "Препятствия",      Rx, 135 * SCALE, fs)
            # Ряд 2
            draw_label(screen, "Бонусные яблоки",  Lx, 295 * SCALE, fs)
            draw_label(screen, "Возрождение",      Rx, 295 * SCALE, fs)
            # Ряд 3
            draw_label(screen, "Размер поля",      Lx, 455 * SCALE, fs)
            draw_label(screen, "Управление",       Rx, 455 * SCALE, fs)
            diff_dd.draw_button(screen, fs, mouse_pos,
                                expanded=(open_dropdown == "difficulty"))
            walls_btn.draw(screen, fs, mouse_pos)
            bonuses_btn.draw(screen, fs, mouse_pos)
            revivals_btn.draw(screen, fs, mouse_pos)
            size_dd.draw_button(screen, fs, mouse_pos,
                                expanded=(open_dropdown == "board_size"))
            touch_dd.draw_button(screen, fs, mouse_pos,
                                 expanded=(open_dropdown == "touch_mode"))
            back_btn.draw(screen, fs, mouse_pos)
            if open_dropdown is not None:
                draw_overlay_bg(screen, alpha=110)
                if open_dropdown == "difficulty":
                    diff_dd.draw_button(screen, fs, mouse_pos, expanded=True)
                    diff_dd.draw_options(screen, fs, mouse_pos)
                elif open_dropdown == "board_size":
                    size_dd.draw_button(screen, fs, mouse_pos, expanded=True)
                    size_dd.draw_options(screen, fs, mouse_pos)
                elif open_dropdown == "touch_mode":
                    touch_dd.draw_button(screen, fs, mouse_pos, expanded=True)
                    touch_dd.draw_options(screen, fs, mouse_pos)

        elif state == STATE_GAMEOVER:
            draw_overlay_bg(screen)
            # Заголовок и счёт.
            draw_title(screen, "КОНЕЦ ИГРЫ",
                       f"Счёт: {game.score}",
                       WIN_H // 2 - 140 * SCALE, fb, fs)
            # Два рекорда — без возрождения и с ним.
            line1 = f"Рекорд без возрождения: {best}"
            line2 = f"Рекорд с возрождением:  {best_with_revival}"
            s1 = fs.render(line1, True, C_DIM)
            s2 = fs.render(line2, True, C_DIM)
            surface_y = WIN_H // 2 - 30 * SCALE
            screen.blit(s1, ((WIN_W - s1.get_width()) // 2, surface_y))
            screen.blit(s2, ((WIN_W - s2.get_width()) // 2, surface_y + 30 * SCALE))
            # Кнопки рисуем последними, чтобы они были поверх (но теперь
            # они и так не накладываются — текст выше).
            # Build_gameover_buttons возвращает их на WIN_H//2 + 40 = 404,
            # это ниже текста (текст заканчивается на 364 + 60 = ~394).
            for b in gameover_btns:
                b.draw(screen, fs, mouse_pos)

        elif state == STATE_PAUSED:
            draw_overlay_bg(screen)
            draw_title(screen, "ПАУЗА", "Space / Esc — продолжить",
                       WIN_H // 2 - 60 * SCALE, fb, fs)
            for b in pause_btns:
                b.draw(screen, fs, mouse_pos)

        elif state == STATE_REVIVAL_OFFER:
            draw_overlay_bg(screen)
            draw_title(screen, "ВТОРОЙ ШАНС",
                       "Решите пример, чтобы вернуться в игру",
                       WIN_H // 2 - 100 * SCALE, fb, fs)
            for b in revival_offer_btns:
                b.draw(screen, fs, mouse_pos)

        elif state == STATE_REVIVAL_COUNTDOWN:
            draw_overlay_bg(screen)
            # Показываем целое число (3, 2, 1) — округление вверх по убыванию.
            shown = max(1, int(countdown_t) + (1 if countdown_t > int(countdown_t) else 0))
            shown = min(int(REVIVAL_COUNTDOWN_SEC), shown)
            draw_countdown_number(screen, shown, fx_big_font)

        elif state == STATE_REVIVAL_MATH:
            draw_overlay_bg(screen)
            # Полоса оставшегося времени сверху.
            draw_time_bar(screen, math_timer / REVIVAL_TIMER_SEC)
            # Текст примера большим шрифтом.
            draw_math_problem(screen, math_question, fx_math_font)
            # Кнопки с вариантами.
            for b in math_buttons:
                b.draw(screen, fs, mouse_pos)

        pygame.display.flip()
        frame += 1
        await asyncio.sleep(0)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
