from __future__ import annotations
import math
import pygame
import config
from game.player import PlayerState

def _lerp_color(a: tuple, b: tuple, t: float) -> tuple:
    return tuple((int(a[i] + (b[i] - a[i]) * t) for i in range(3)))

class HUD:

    def __init__(self, fonts: dict[str, pygame.font.Font]):
        self._f = fonts

    def draw(self, surface: pygame.Surface, session, latest_gesture: str='none'):
        p = session.player
        self._draw_score_block(surface, session)
        self._draw_lives(surface, p)
        self._draw_shield_bar(surface, p)
        self._draw_gesture_readout(surface, latest_gesture)
        if config.SHOW_FPS:
            fps_val = getattr(session, 'fps', 0.0)
            fps_surf = self._f['label'].render(f'FPS: {fps_val:.1f}', True, config.COLORS['cyan'])
            surface.blit(fps_surf, (config.PAD_LG, config.PAD_MD + 80))

    def _draw_score_block(self, surface: pygame.Surface, session):
        score_str = f'{int(session.score):>7}'
        score_surf = self._f['body'].render(score_str, True, config.COLORS['text'])
        surface.blit(score_surf, (config.PAD_LG, config.PAD_MD))
        dist_str = f'{session.distance:>6.0f} m'
        dist_surf = self._f['label'].render(dist_str, True, config.COLORS['cyan'])
        surface.blit(dist_surf, (config.PAD_LG, config.PAD_MD + score_surf.get_height() + 4))
        coin_str = f'◆  {session.coins}'
        coin_surf = self._f['label'].render(coin_str, True, config.COLORS['amber'])
        surface.blit(coin_surf, (config.GAME_WIDTH - coin_surf.get_width() - config.PAD_LG, config.PAD_MD))

    def _draw_lives(self, surface: pygame.Surface, player):
        x = config.PAD_LG
        y = config.GAME_HEIGHT - config.PAD_LG - 14
        label = self._f['label'].render('LIVES', True, config.COLORS['text_dim'])
        surface.blit(label, (x, y - label.get_height() - 4))
        for i in range(config.PLAYER_LIVES):
            filled = i < player.lives
            col = config.COLORS['coral'] if filled else config.COLORS['surface_edge']
            cx_pip = x + i * 26 + 10
            pygame.draw.circle(surface, col, (cx_pip, y), 8)
            if filled:
                pygame.draw.circle(surface, config.COLORS['coral_dark'], (cx_pip, y), 4)

    def _draw_shield_bar(self, surface: pygame.Surface, player):
        bar_w = 150
        bar_h = 8
        x = config.GAME_WIDTH - bar_w - config.PAD_LG
        y = config.GAME_HEIGHT - config.PAD_LG - bar_h
        label = self._f['label'].render('SHIELD', True, config.COLORS['text_dim'])
        surface.blit(label, (x, y - label.get_height() - 4))
        pygame.draw.rect(surface, config.COLORS['surface'], pygame.Rect(x, y, bar_w, bar_h), border_radius=4)
        if player.state == PlayerState.SHIELDING:
            frac = max(0.0, 1.0 - player._state_timer / config.SHIELD_DURATION)
            fill_w = max(4, int(bar_w * frac))
            pygame.draw.rect(surface, config.COLORS['amber'], pygame.Rect(x, y, fill_w, bar_h), border_radius=4)
        else:
            total_cd = config.SHIELD_DURATION + config.SHIELD_COOLDOWN
            frac = max(0.0, 1.0 - player._shield_cooldown / total_cd)
            fill_w = max(0, int(bar_w * frac))
            col = config.COLORS['cyan'] if frac >= 1.0 else config.COLORS['cyan_dim']
            if fill_w:
                pygame.draw.rect(surface, col, pygame.Rect(x, y, fill_w, bar_h), border_radius=4)
        pygame.draw.rect(surface, config.COLORS['surface_edge'], pygame.Rect(x, y, bar_w, bar_h), 1, border_radius=4)

    def _draw_gesture_readout(self, surface: pygame.Surface, gesture: str):
        if gesture in ('none', 'calibrating', None):
            return
        label = gesture.replace('_', ' ').upper()
        surf = self._f['label'].render(label, True, config.COLORS['text_dim'])
        surface.blit(surf, (config.GAME_WIDTH // 2 - surf.get_width() // 2, config.GAME_HEIGHT - config.PAD_LG - surf.get_height()))

    def draw_calibrating(self, surface: pygame.Surface, progress: float):
        _draw_frosted_panel(surface, width=520, height=240)
        cx = config.GAME_WIDTH // 2
        cy = config.GAME_HEIGHT // 2
        title = self._f['body'].render('CALIBRATING', True, config.COLORS['cyan'])
        _blit_c(surface, title, cx, cy - 70)
        hint1 = self._f['label'].render('Stand in a neutral position, facing the camera.', True, config.COLORS['text'])
        hint2 = self._f['label'].render('Hold still for a moment.', True, config.COLORS['text_dim'])
        _blit_c(surface, hint1, cx, cy - 20)
        _blit_c(surface, hint2, cx, cy + 8)
        bar_w, bar_h = (360, 6)
        bx = cx - bar_w // 2
        by = cy + 40
        pygame.draw.rect(surface, config.COLORS['surface_edge'], pygame.Rect(bx, by, bar_w, bar_h), border_radius=3)
        if progress > 0:
            pygame.draw.rect(surface, config.COLORS['cyan'], pygame.Rect(bx, by, int(bar_w * progress), bar_h), border_radius=3)
        skip = self._f['label'].render('Or press any arrow key to skip', True, config.COLORS['text_muted'])
        _blit_c(surface, skip, cx, cy + 72)

    def draw_countdown(self, surface: pygame.Surface, timer: float):
        n = math.ceil(timer)
        txt = str(n) if n > 0 else 'GO!'
        col = config.COLORS['amber'] if n <= 1 else config.COLORS['text']
        surf = self._f['display'].render(txt, True, col)
        _blit_c(surface, surf, config.GAME_WIDTH // 2, config.GAME_HEIGHT // 2 - 20)
        sub = self._f['label'].render('Get ready', True, config.COLORS['text_dim'])
        _blit_c(surface, sub, config.GAME_WIDTH // 2, config.GAME_HEIGHT // 2 + 46)

    def draw_game_over(self, surface: pygame.Surface, score: int, high_score: int, coins: int, is_new_best: bool):
        _draw_frosted_panel(surface, width=480, height=320)
        cx = config.GAME_WIDTH // 2
        cy = config.GAME_HEIGHT // 2
        title = self._f['display'].render('GAME OVER', True, config.COLORS['coral'])
        _blit_c(surface, title, cx, cy - 110)
        rule_y = cy - 78
        pygame.draw.line(surface, config.COLORS['surface_edge'], (cx - 180, rule_y), (cx + 180, rule_y))
        lx, rx = (cx - 60, cx + 60)
        row1_y = cy - 48
        row2_y = cy + 4
        row3_y = cy + 56
        _label_value(surface, self._f, 'SCORE', f'{score:,}', lx, rx, row1_y)
        _label_value(surface, self._f, 'BEST', f'{high_score:,}', lx, rx, row2_y, val_col=config.COLORS['amber'] if is_new_best else config.COLORS['text'])
        _label_value(surface, self._f, 'COINS', str(coins), lx, rx, row3_y, val_col=config.COLORS['amber'])
        if is_new_best:
            new_best = self._f['label'].render('★  NEW BEST', True, config.COLORS['amber'])
            _blit_c(surface, new_best, cx, cy + 102)
        restart = self._f['label'].render('Press  R  to run again', True, config.COLORS['text_dim'])
        _blit_c(surface, restart, cx, cy + 132)

def _draw_frosted_panel(surface: pygame.Surface, width: int, height: int):
    cx = config.GAME_WIDTH // 2
    cy = config.GAME_HEIGHT // 2
    veil = pygame.Surface((config.GAME_WIDTH, config.GAME_HEIGHT), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 140))
    surface.blit(veil, (0, 0))
    panel_rect = pygame.Rect(cx - width // 2, cy - height // 2, width, height)
    panel = pygame.Surface((width, height), pygame.SRCALPHA)
    panel.fill((*config.COLORS['surface'], 220))
    surface.blit(panel, panel_rect.topleft)
    pygame.draw.rect(surface, config.COLORS['surface_edge'], panel_rect, 1, border_radius=4)

def _blit_c(surface: pygame.Surface, rendered: pygame.Surface, cx: int, cy: int):
    surface.blit(rendered, (cx - rendered.get_width() // 2, cy - rendered.get_height() // 2))

def _label_value(surface, fonts, label: str, value: str, lx: int, rx: int, y: int, val_col: tuple=None):
    if val_col is None:
        val_col = config.COLORS['text']
    lbl_surf = fonts['label'].render(label, True, config.COLORS['text_dim'])
    val_surf = fonts['body'].render(value, True, val_col)
    surface.blit(lbl_surf, (lx - lbl_surf.get_width(), y))
    surface.blit(val_surf, (rx, y - (val_surf.get_height() - lbl_surf.get_height()) // 2))
