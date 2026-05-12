"""
Визуальные эффекты: разлетающиеся частицы и всплывающие "+N".
Чистая отрисовка, состояние храним в простых dict'ах.
"""

import math
import random
import pygame


class Effects:
    def __init__(self):
        self.particles  = []
        self.popups     = []
        self.big_popups = []   # крупный текст по центру (x2, x3, ...)

    def burst(self, x, y, color, count=12, speed=(80, 220), life=0.55, size=(2, 5)):
        for _ in range(count):
            ang = random.uniform(0, 2 * math.pi)
            v   = random.uniform(*speed)
            self.particles.append({
                "x": x, "y": y,
                "vx": math.cos(ang) * v,
                "vy": math.sin(ang) * v,
                "life": life, "max_life": life,
                "color": color,
                "r": random.randint(*size),
            })

    def popup(self, x, y, text, color):
        self.popups.append({
            "x": x, "y": y,
            "vy": -55,                 # пиксели/сек, отрицательное = вверх
            "life": 0.9, "max_life": 0.9,
            "text": text,
            "color": color,
        })

    def big_popup(self, x, y, text, color, font):
        """
        Крупный текст по центру с pop-in анимацией и затуханием.
        Шрифт пре-рендерится один раз, потом масштабируется при отрисовке.
        """
        surf = font.render(text, True, color)
        self.big_popups.append({
            "x": x, "y": y,
            "surf": surf,
            "life": 1.6, "max_life": 1.6,
        })

    def update(self, dt):
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 240 * dt        # лёгкая гравитация
            p["vx"] *= 0.96            # затухание
            p["vy"] *= 0.99
            p["life"] -= dt
        self.particles = [p for p in self.particles if p["life"] > 0]

        for p in self.popups:
            p["y"]    += p["vy"] * dt
            p["vy"]   *= 0.95
            p["life"] -= dt
        self.popups = [p for p in self.popups if p["life"] > 0]

        for p in self.big_popups:
            p["life"] -= dt
        self.big_popups = [p for p in self.big_popups if p["life"] > 0]

    def draw(self, surface, font):
        for p in self.particles:
            alpha = max(0, min(255, int(255 * p["life"] / p["max_life"])))
            r = max(1, int(p["r"] * (p["life"] / p["max_life"]) ** 0.5))
            buf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(buf, (*p["color"], alpha), (r, r), r)
            surface.blit(buf, (p["x"] - r, p["y"] - r))

        for p in self.popups:
            alpha = max(0, min(255, int(255 * p["life"] / p["max_life"])))
            txt = font.render(p["text"], True, p["color"])
            txt.set_alpha(alpha)
            surface.blit(txt, (int(p["x"] - txt.get_width() / 2),
                               int(p["y"] - txt.get_height() / 2)))

        # Большие центральные надписи (×2, ×3, ...).
        for p in self.big_popups:
            progress = 1.0 - p["life"] / p["max_life"]
            # Pop-in: 0..15% — увеличиваемся 0.5 → 1.3.
            # Settle:  15..30% — оседаем 1.3 → 1.0.
            # Hold:    30..60% — стоим на 1.0.
            # Fade:    60..100% — альфа уходит в 0.
            if progress < 0.15:
                scale = 0.5 + (1.3 - 0.5) * (progress / 0.15)
            elif progress < 0.30:
                scale = 1.3 - 0.3 * ((progress - 0.15) / 0.15)
            else:
                scale = 1.0
            if progress < 0.6:
                alpha = 255
            else:
                alpha = max(0, int(255 * (1.0 - (progress - 0.6) / 0.4)))

            base = p["surf"]
            new_w = max(1, int(base.get_width()  * scale))
            new_h = max(1, int(base.get_height() * scale))
            scaled = pygame.transform.smoothscale(base, (new_w, new_h))
            scaled.set_alpha(alpha)
            surface.blit(scaled, (int(p["x"] - new_w / 2),
                                  int(p["y"] - new_h / 2)))
