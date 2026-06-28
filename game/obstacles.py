from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
import pygame
import config

class ObstacleType(Enum):
    LOW = auto()
    HIGH = auto()
    FULL = auto()

@dataclass
class Obstacle:
    rect: pygame.Rect
    kind: ObstacleType
    lane: int

    @property
    def hitbox(self) -> pygame.Rect:
        return self.rect.inflate(-6, -6)

@dataclass
class Collectible:
    x: float
    y: float
    lane: int
    collected: bool = False
    _spawn_time: float = field(default_factory=lambda: 0.0)

    @property
    def rect(self) -> pygame.Rect:
        r = config.COLLECTIBLE_RADIUS
        return pygame.Rect(int(self.x) - r, int(self.y) - r, r * 2, r * 2)

    @property
    def hitbox(self) -> pygame.Rect:
        r = config.COLLECTIBLE_RADIUS + 4
        return pygame.Rect(int(self.x) - r, int(self.y) - r, r * 2, r * 2)

@dataclass
class ParallaxLayer:
    scroll_factor: float
    color: tuple
    highlight: tuple
    elements: list[pygame.Rect] = field(default_factory=list)
    _offset: float = 0.0

    def update(self, dt: float, game_speed: float):
        self._offset += game_speed * self.scroll_factor * dt
        if self._offset >= config.GAME_WIDTH:
            self._offset -= config.GAME_WIDTH

    def draw(self, surface: pygame.Surface):
        for rect in self.elements:
            sx = (rect.x - self._offset) % config.GAME_WIDTH
            r = pygame.Rect(sx, rect.y, rect.width, rect.height)
            pygame.draw.rect(surface, self.color, r)
            pygame.draw.line(surface, self.highlight, r.topleft, r.topright)
            if sx + rect.width > config.GAME_WIDTH:
                r2 = pygame.Rect(sx - config.GAME_WIDTH, rect.y, rect.width, rect.height)
                pygame.draw.rect(surface, self.color, r2)
                pygame.draw.line(surface, self.highlight, r2.topleft, r2.topright)

class ObstacleManager:

    def __init__(self):
        self.obstacles: list[Obstacle] = []
        self.collectibles: list[Collectible] = []
        self._spawn_timer = 0.0
        self._spawn_interval = config.SPAWN_INTERVAL_MAX
        self._world_time = 0.0
        self.coins_collected = 0
        self._bg_layers = self._build_background()
        self._ground_offset = 0.0

    def reset(self):
        self.obstacles.clear()
        self.collectibles.clear()
        self._spawn_timer = 0.0
        self._spawn_interval = config.SPAWN_INTERVAL_MAX
        self._world_time = 0.0
        self.coins_collected = 0
        self._ground_offset = 0.0

    def update(self, dt: float, game_speed: float):
        self._world_time += dt
        self._update_parallax(dt, game_speed)
        self._scroll_objects(dt, game_speed)
        self._remove_offscreen()
        speed_ratio = (game_speed - config.SPEED_INITIAL) / max(config.SPEED_MAX - config.SPEED_INITIAL, 1)
        self._spawn_interval = config.SPAWN_INTERVAL_MAX - speed_ratio * (config.SPAWN_INTERVAL_MAX - config.SPAWN_INTERVAL_MIN)
        self._spawn_timer += dt
        if self._spawn_timer >= self._spawn_interval:
            self._spawn_timer = 0.0
            self._spawn_group()

    def check_obstacle_hit(self, player) -> bool:
        if player.is_invincible:
            return False
        phb = player.hitbox
        return any((obs.hitbox.colliderect(phb) for obs in self.obstacles))

    def collect_coins(self, player) -> int:
        phb = player.hitbox
        count = 0
        for coin in self.collectibles:
            if not coin.collected and coin.hitbox.colliderect(phb):
                coin.collected = True
                self.coins_collected += 1
                count += 1
        return count

    def draw_background(self, surface: pygame.Surface):
        self._draw_parallax(surface)

    def draw_objects(self, surface: pygame.Surface):
        self._draw_obstacles(surface)
        self._draw_collectibles(surface)

    def _build_background(self) -> list[ParallaxLayer]:
        far = ParallaxLayer(scroll_factor=config.PARALLAX_FAR_FACTOR, color=config.COLORS['bg_far'], highlight=config.COLORS['surface_edge'])
        for i in range(14):
            x = i * (config.GAME_WIDTH // 11) + random.randint(-10, 50)
            h = random.randint(90, 220)
            w = random.randint(35, 80)
            far.elements.append(pygame.Rect(x, config.GAME_HEIGHT - h - 90, w, h))
        mid = ParallaxLayer(scroll_factor=config.PARALLAX_MID_FACTOR, color=config.COLORS['bg_mid'], highlight=config.COLORS['surface'])
        for i in range(20):
            x = i * (config.GAME_WIDTH // 15) + random.randint(-5, 30)
            h = random.randint(30, 110)
            w = random.randint(20, 55)
            mid.elements.append(pygame.Rect(x, config.GAME_HEIGHT - h - 75, w, h))
        return [far, mid]

    def _update_parallax(self, dt: float, game_speed: float):
        for layer in self._bg_layers:
            layer.update(dt, game_speed)
        self._ground_offset += game_speed * config.PARALLAX_NEAR_FACTOR * dt
        if self._ground_offset >= config.GAME_WIDTH:
            self._ground_offset -= config.GAME_WIDTH

    def _draw_parallax(self, surface: pygame.Surface):
        surface.fill(config.COLORS['bg'])
        for layer in self._bg_layers:
            layer.draw(surface)
        self._draw_ground(surface)

    def _draw_ground(self, surface: pygame.Surface):
        ground_y = config.GAME_HEIGHT - 60
        ground_rect = pygame.Rect(0, ground_y, config.GAME_WIDTH, config.GAME_HEIGHT - ground_y)
        pygame.draw.rect(surface, config.COLORS['ground'], ground_rect)
        pygame.draw.line(surface, config.COLORS['ground_edge'], (0, ground_y), (config.GAME_WIDTH, ground_y))
        dash_w, gap = (36, 28)
        total = dash_w + gap
        offset = int(self._ground_offset) % total
        for lane_y in config.LANE_Y:
            marker_y = lane_y + config.PLAYER_H // 2 + 5
            x = -offset
            while x < config.GAME_WIDTH:
                pygame.draw.rect(surface, config.COLORS['ground_line'], pygame.Rect(x, marker_y, dash_w, 2))
                x += total

    def _spawn_group(self):
        max_obs = config.NUM_LANES - 1
        num_obs = random.choices(range(1, max_obs + 1), weights=[50, 35][:max_obs])[0]
        lanes_this_group: set[int] = set()
        spawn_x = config.GAME_WIDTH + 60
        for _ in range(num_obs):
            available = [l for l in range(config.NUM_LANES) if l not in lanes_this_group]
            if not available:
                break
            lane = random.choice(available)
            lanes_this_group.add(lane)
            kind = random.choice([ObstacleType.LOW, ObstacleType.HIGH, ObstacleType.FULL])
            self.obstacles.append(self._make_obstacle(kind, lane, spawn_x))
            spawn_x += random.randint(0, 60)
        clear_lanes = [l for l in range(config.NUM_LANES) if l not in lanes_this_group]
        if clear_lanes and random.random() < 0.6:
            lane = random.choice(clear_lanes)
            c = Collectible(x=float(config.GAME_WIDTH + 100), y=float(config.LANE_Y[lane]) - config.PLAYER_H * 0.3, lane=lane, _spawn_time=self._world_time)
            self.collectibles.append(c)

    def _make_obstacle(self, kind: ObstacleType, lane: int, x: int) -> Obstacle:
        lane_y = config.LANE_Y[lane]
        if kind == ObstacleType.LOW:
            w, h = (config.OBS_LOW_W, config.OBS_LOW_H)
            rect = pygame.Rect(x, lane_y + config.PLAYER_H // 2 - h, w, h)
        elif kind == ObstacleType.HIGH:
            w, h = (config.OBS_HIGH_W, config.OBS_HIGH_H)
            rect = pygame.Rect(x, lane_y - config.PLAYER_H // 2 - h + 10, w, h)
        else:
            w, h = (config.OBS_FULL_W, config.OBS_FULL_H)
            rect = pygame.Rect(x, lane_y - h // 2, w, h)
        return Obstacle(rect=rect, kind=kind, lane=lane)

    def _scroll_objects(self, dt: float, game_speed: float):
        dx = game_speed * dt
        for obs in self.obstacles:
            obs.rect.x -= int(dx)
        for coin in self.collectibles:
            coin.x -= dx

    def _remove_offscreen(self):
        self.obstacles = [o for o in self.obstacles if o.rect.right > -50]
        self.collectibles = [c for c in self.collectibles if c.x + config.COLLECTIBLE_RADIUS > -50]
    _OBS_COLORS = {ObstacleType.LOW: ('coral', 'coral_dim', 'coral_dark'), ObstacleType.HIGH: ('violet', 'violet_dim', 'cyan_dark'), ObstacleType.FULL: ('coral', 'coral_dim', 'coral_dark')}

    def _draw_obstacles(self, surface: pygame.Surface):
        for obs in self.obstacles:
            face, shadow, depth = self._OBS_COLORS[obs.kind]
            r = obs.rect
            if obs.kind == ObstacleType.HIGH:
                pygame.draw.rect(surface, config.COLORS[shadow], r, border_radius=3)
                pygame.draw.line(surface, config.COLORS[face], r.topleft, r.topright)
                pygame.draw.line(surface, config.COLORS[face], r.bottomleft, r.bottomright)
                mid_y = r.centery
                pygame.draw.circle(surface, config.COLORS[face], (r.left + 4, mid_y), 5)
                pygame.draw.circle(surface, config.COLORS[face], (r.right - 4, mid_y), 5)
            else:
                pygame.draw.rect(surface, config.COLORS[shadow], r, border_radius=2)
                pygame.draw.line(surface, config.COLORS[face], r.topleft, r.topright)
                stripe = pygame.Rect(r.left, r.top, 3, r.height)
                pygame.draw.rect(surface, config.COLORS[face], stripe)

    def _draw_collectibles(self, surface: pygame.Surface):
        for coin in self.collectibles:
            if coin.collected:
                continue
            age = self._world_time - coin._spawn_time
            pulse = 1 + 0.14 * math.sin(age * 6.28)
            r = int(config.COLLECTIBLE_RADIUS * pulse)
            cx, cy = (int(coin.x), int(coin.y))
            pygame.draw.circle(surface, config.COLORS['amber'], (cx, cy), r)
            if r > 4:
                pygame.draw.circle(surface, config.COLORS['amber_dim'], (cx, cy), r - 3, 2)
