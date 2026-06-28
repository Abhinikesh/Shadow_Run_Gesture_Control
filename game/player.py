from __future__ import annotations
import math
from collections import deque
from enum import Enum, auto
import pygame
import config

class PlayerState(Enum):
    RUNNING = auto()
    JUMPING = auto()
    SLIDING = auto()
    SHIELDING = auto()

class Player:

    def __init__(self):
        self.lane = config.PLAYER_START_LANE
        self._target_lane = self.lane
        self.rect = pygame.Rect(0, 0, config.PLAYER_W, config.PLAYER_H)
        self.rect.centerx = config.PLAYER_X
        self.rect.centery = config.LANE_Y[self.lane]
        self._y_float = float(self.rect.centery)
        self._lane_y_start = float(self.rect.centery)
        self._lane_y_target = float(self.rect.centery)
        self._lane_t = 1.0
        self.velocity_y = 0.0
        self._ground_y = float(config.LANE_Y[self.lane])
        self.state = PlayerState.RUNNING
        self._state_timer = 0.0
        self._shield_cooldown = 0.0
        self._invincible_timer = 0.0
        self.lives = config.PLAYER_LIVES
        self._anim_t = 0.0
        self.is_dead = False
        self._trail: deque[tuple[int, int]] = deque(maxlen=config.TRAIL_LENGTH)
        self._was_transitioning = False

    def action_jump(self):
        if self.state in (PlayerState.RUNNING, PlayerState.SHIELDING):
            self.state = PlayerState.JUMPING
            self.velocity_y = config.JUMP_VELOCITY
            self._state_timer = 0.0

    def action_slide(self):
        if self.state == PlayerState.RUNNING:
            self.state = PlayerState.SLIDING
            self._state_timer = 0.0

    def action_shield(self):
        if self._shield_cooldown <= 0 and self.state == PlayerState.RUNNING:
            self.state = PlayerState.SHIELDING
            self._state_timer = 0.0
            self._shield_cooldown = config.SHIELD_DURATION + config.SHIELD_COOLDOWN

    def action_lean(self, direction: int):
        new_lane = self.lane + direction
        if 0 <= new_lane <= config.NUM_LANES - 1 and new_lane != self._target_lane:
            self._target_lane = new_lane
            self._lane_y_start = self._y_float
            self._lane_y_target = float(config.LANE_Y[new_lane])
            self._lane_t = 0.0

    def update(self, dt: float):
        self._anim_t += dt
        self._state_timer += dt
        if self._invincible_timer > 0:
            self._invincible_timer -= dt
        if self._shield_cooldown > 0:
            self._shield_cooldown -= dt
        transitioning = self._lane_t < 1.0
        if transitioning:
            self._lane_t = min(1.0, self._lane_t + dt / config.LANE_TRANSITION_DURATION)
            t = 1.0 - (1.0 - self._lane_t) ** 2
            self._y_float = self._lane_y_start + (self._lane_y_target - self._lane_y_start) * t
            if self._lane_t >= 1.0:
                self.lane = self._target_lane
                self._ground_y = float(config.LANE_Y[self.lane])
        if transitioning:
            self._trail.appendleft((int(config.PLAYER_X), int(self._y_float)))
        elif self._was_transitioning:
            self._trail.clear()
        self._was_transitioning = transitioning
        if self.state == PlayerState.JUMPING:
            self._update_jump(dt)
        elif self.state == PlayerState.SLIDING:
            if self._state_timer >= config.SLIDE_DURATION:
                self.state = PlayerState.RUNNING
        elif self.state == PlayerState.SHIELDING:
            if self._state_timer >= config.SHIELD_DURATION:
                self.state = PlayerState.RUNNING
        h = config.PLAYER_SLIDE_H if self.state == PlayerState.SLIDING else config.PLAYER_H
        self.rect.width = config.PLAYER_W
        self.rect.height = h
        self.rect.centerx = config.PLAYER_X
        self.rect.centery = int(self._y_float)

    def _update_jump(self, dt: float):
        self.velocity_y += config.GRAVITY * dt
        self._y_float += self.velocity_y * dt
        if self._y_float >= self._ground_y:
            self._y_float = self._ground_y
            self.velocity_y = 0.0
            self.state = PlayerState.RUNNING

    @property
    def hitbox(self) -> pygame.Rect:
        return self.rect.inflate(-config.HITBOX_INSET_X * 2, -config.HITBOX_INSET_Y * 2)

    @property
    def is_invincible(self) -> bool:
        return self._invincible_timer > 0 or self.state == PlayerState.SHIELDING

    def take_hit(self):
        if self.is_invincible:
            return
        self.lives -= 1
        self._invincible_timer = config.HIT_INVINCIBILITY
        if self.state in (PlayerState.SLIDING, PlayerState.SHIELDING):
            self.state = PlayerState.RUNNING
        if self.lives <= 0:
            self.is_dead = True

    def draw(self, surface: pygame.Surface):
        if self._invincible_timer > 0:
            if int(self._invincible_timer * 10) % 2 == 0:
                return
        self._draw_trail(surface)
        cx, cy = (self.rect.centerx, self.rect.centery)
        if self.state == PlayerState.SLIDING:
            self._draw_slide(surface, cx, cy)
        elif self.state == PlayerState.SHIELDING:
            self._draw_shield(surface, cx, cy)
        elif self.state == PlayerState.JUMPING:
            self._draw_jump(surface, cx, cy)
        else:
            self._draw_run(surface, cx, cy)

    def _draw_trail(self, surface: pygame.Surface):
        if not self._trail:
            return
        col = config.COLORS['cyan']
        for i, (tx, ty) in enumerate(self._trail):
            frac = 1.0 - i / config.TRAIL_LENGTH
            alpha = int(config.TRAIL_ALPHA_MAX * frac)
            ghost = pygame.Surface((config.PLAYER_W, config.PLAYER_H), pygame.SRCALPHA)
            pygame.draw.rect(ghost, (*col, alpha), ghost.get_rect().inflate(-8, -8), border_radius=6)
            surface.blit(ghost, (tx - config.PLAYER_W // 2, ty - config.PLAYER_H // 2))

    def _primary_color(self) -> tuple:
        if self.state == PlayerState.SHIELDING:
            return config.COLORS['player_shield']
        if self.state == PlayerState.SLIDING:
            return config.COLORS['player_slide']
        return config.COLORS['player']

    def _draw_run(self, surface: pygame.Surface, cx: int, cy: int):
        col = self._primary_color()
        phase = math.sin(self._anim_t * 8.0)
        pygame.draw.circle(surface, col, (cx, cy - 28), 11)
        pygame.draw.circle(surface, config.COLORS['cyan_dark'], (cx, cy - 28), 11, 1)
        torso = pygame.Rect(cx - 8, cy - 17, 16, 26)
        pygame.draw.rect(surface, col, torso, border_radius=3)
        leg_off = int(phase * 10)
        pygame.draw.rect(surface, col, pygame.Rect(cx - 9, cy + 9, 7, 20 + leg_off), border_radius=2)
        pygame.draw.rect(surface, col, pygame.Rect(cx + 2, cy + 9, 7, 20 - leg_off), border_radius=2)
        arm_off = int(phase * 7)
        pygame.draw.rect(surface, col, pygame.Rect(cx - 17, cy - 11 + arm_off, 7, 16), border_radius=2)
        pygame.draw.rect(surface, col, pygame.Rect(cx + 10, cy - 11 - arm_off, 7, 16), border_radius=2)

    def _draw_jump(self, surface: pygame.Surface, cx: int, cy: int):
        col = self._primary_color()
        pygame.draw.circle(surface, col, (cx, cy - 28), 11)
        pygame.draw.circle(surface, config.COLORS['cyan_dark'], (cx, cy - 28), 11, 1)
        pygame.draw.rect(surface, col, pygame.Rect(cx - 8, cy - 17, 16, 22), border_radius=3)
        pygame.draw.rect(surface, col, pygame.Rect(cx - 13, cy + 6, 10, 12), border_radius=2)
        pygame.draw.rect(surface, col, pygame.Rect(cx + 3, cy + 6, 10, 12), border_radius=2)
        pygame.draw.rect(surface, col, pygame.Rect(cx - 22, cy - 18, 7, 16), border_radius=2)
        pygame.draw.rect(surface, col, pygame.Rect(cx + 15, cy - 18, 7, 16), border_radius=2)

    def _draw_slide(self, surface: pygame.Surface, cx: int, cy: int):
        col = self._primary_color()
        pygame.draw.ellipse(surface, col, pygame.Rect(cx - 22, cy - 9, 44, 18))
        pygame.draw.circle(surface, col, (cx + 20, cy - 5), 10)
        pygame.draw.circle(surface, config.COLORS['cyan_dark'], (cx + 20, cy - 5), 10, 1)

    def _draw_shield(self, surface: pygame.Surface, cx: int, cy: int):
        self._draw_run(surface, cx, cy)
        elapsed = min(self._state_timer / config.SHIELD_DURATION, 1.0)
        ring_alpha = int(200 * (1.0 - elapsed * 0.6))
        radius = 36
        ring_surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(ring_surf, (*config.COLORS['amber'], ring_alpha), (radius + 2, radius + 2), radius, 3)
        surface.blit(ring_surf, (cx - radius - 2, cy - radius - 14))
