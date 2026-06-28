from __future__ import annotations
import queue
import random
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
import pygame
import config
from game.player import Player
from game.obstacles import ObstacleManager
from game.ui_hud import HUD

class GameState(Enum):
    CALIBRATING = auto()
    COUNTDOWN = auto()
    PLAYING = auto()
    GAME_OVER = auto()
_GESTURE_ACTION = {'jump': 'jump', 'slide': 'slide', 'shield': 'shield', 'lean_left': 'lean_left', 'lean_right': 'lean_right'}
_KEY_MAP = {pygame.K_UP: 'jump', pygame.K_DOWN: 'slide', pygame.K_LEFT: 'lean_left', pygame.K_RIGHT: 'lean_right', pygame.K_SPACE: 'shield', pygame.K_w: 'jump', pygame.K_s: 'slide', pygame.K_a: 'lean_left', pygame.K_d: 'lean_right'}

class _ScreenShake:

    def __init__(self):
        self._frames = 0
        self._mag = 0

    def trigger(self):
        self._frames = config.SCREEN_SHAKE_FRAMES
        self._mag = config.SCREEN_SHAKE_MAGNITUDE

    def offset(self) -> tuple[int, int]:
        if self._frames <= 0:
            return (0, 0)
        self._frames -= 1
        return (random.randint(-self._mag, self._mag), random.randint(-self._mag, self._mag))

class GameSession:

    def __init__(self):
        self.player = Player()
        self.obstacles = ObstacleManager()
        self.game_speed = config.SPEED_INITIAL
        self.score = 0.0
        self.distance = 0.0
        self.coins = 0
        self._last_gesture = 'none'

    def reset(self):
        self.player = Player()
        self.obstacles.reset()
        self.game_speed = config.SPEED_INITIAL
        self.score = 0.0
        self.distance = 0.0
        self.coins = 0
        self._last_gesture = 'none'

@dataclass
class GameLoopState:
    screen: pygame.Surface
    canvas: pygame.Surface
    clock: pygame.time.Clock
    fonts: dict
    hud: HUD
    shake: _ScreenShake
    session: GameSession = field(default_factory=GameSession)
    state: GameState = GameState.CALIBRATING
    countdown_timer: float = 0.0
    high_score: int = 0
    flash_frames: int = 0
    calib_progress: float = 0.0
    latest_gesture: str = 'none'
    latest_confidence: int = 0
_FLASH_TOTAL = 8

def init_game() -> GameLoopState:
    pygame.init()
    pygame.display.set_caption(config.GAME_WINDOW_TITLE)
    screen = pygame.display.set_mode((config.GAME_WIDTH, config.GAME_HEIGHT))
    clock = pygame.time.Clock()
    fonts = {'display': pygame.font.SysFont('monospace', config.FONT_SIZE_DISPLAY, bold=True), 'body': pygame.font.SysFont('monospace', config.FONT_SIZE_BODY), 'label': pygame.font.SysFont('monospace', config.FONT_SIZE_LABEL)}
    return GameLoopState(screen=screen, canvas=pygame.Surface((config.GAME_WIDTH, config.GAME_HEIGHT)), clock=clock, fonts=fonts, hud=HUD(fonts), shake=_ScreenShake())

def step_game(gs: GameLoopState, gesture_queue: queue.Queue, stop_event: threading.Event) -> None:
    dt = min(gs.clock.tick(config.FPS) / 1000.0, 0.05)
    while True:
        try:
            result = gesture_queue.get_nowait()
            gs.latest_gesture = result.gesture
            gs.latest_confidence = result.confidence
        except (queue.Empty, AttributeError):
            break
    pending_actions: list[str] = []
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            stop_event.set()
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                stop_event.set()
                return
            action = _KEY_MAP.get(event.key)
            if action:
                pending_actions.append(action)
            if gs.state == GameState.CALIBRATING and action:
                gs.state = GameState.COUNTDOWN
                gs.countdown_timer = float(config.COUNTDOWN_SECONDS)
            if gs.state == GameState.GAME_OVER and event.key == pygame.K_r:
                gs.session.reset()
                gs.state = GameState.COUNTDOWN
                gs.countdown_timer = float(config.COUNTDOWN_SECONDS)
                gs.flash_frames = 0
    if gs.latest_gesture and gs.latest_gesture not in ('none', 'calibrating') and (gs.latest_gesture != gs.session._last_gesture) and (gs.latest_confidence >= config.GESTURE_CONFIDENCE_MIN) and (gs.state == GameState.PLAYING):
        act = _GESTURE_ACTION.get(gs.latest_gesture)
        if act:
            pending_actions.append(act)
    gs.session._last_gesture = gs.latest_gesture or 'none'
    if gs.state == GameState.CALIBRATING:
        if gs.latest_gesture not in (None, 'calibrating'):
            gs.state = GameState.COUNTDOWN
            gs.countdown_timer = float(config.COUNTDOWN_SECONDS)
    elif gs.state == GameState.COUNTDOWN:
        gs.countdown_timer -= dt
        if gs.countdown_timer <= 0:
            gs.state = GameState.PLAYING
    elif gs.state == GameState.PLAYING:
        hit = _tick_playing(gs.session, pending_actions, dt, gs.shake)
        if hit:
            gs.flash_frames = _FLASH_TOTAL
        if gs.session.player.is_dead:
            gs.high_score = max(gs.high_score, int(gs.session.score))
            gs.state = GameState.GAME_OVER
    obs = gs.session.obstacles
    p = gs.session.player
    obs.draw_background(gs.canvas)
    obs.draw_objects(gs.canvas)
    p.draw(gs.canvas)
    if gs.flash_frames > 0:
        frac = gs.flash_frames / _FLASH_TOTAL
        flash = pygame.Surface((config.GAME_WIDTH, config.GAME_HEIGHT), pygame.SRCALPHA)
        flash.fill((*config.COLORS['coral'], int(80 * frac)))
        gs.canvas.blit(flash, (0, 0))
        gs.flash_frames -= 1
    if gs.state in (GameState.PLAYING, GameState.GAME_OVER):
        gs.session.fps = gs.clock.get_fps()
        gs.hud.draw(gs.canvas, gs.session, gs.latest_gesture)
    if gs.state == GameState.CALIBRATING:
        gs.hud.draw_calibrating(gs.canvas, gs.calib_progress)
    elif gs.state == GameState.COUNTDOWN:
        gs.hud.draw_countdown(gs.canvas, gs.countdown_timer)
    elif gs.state == GameState.GAME_OVER:
        is_new_best = int(gs.session.score) >= gs.high_score and gs.high_score > 0
        gs.hud.draw_game_over(gs.canvas, int(gs.session.score), gs.high_score, gs.session.coins, is_new_best)
    ox, oy = gs.shake.offset()
    gs.screen.fill(config.COLORS['bg'])
    gs.screen.blit(gs.canvas, (ox, oy))
    pygame.display.flip()

def shutdown_game(gs: GameLoopState) -> None:
    pygame.quit()

def _tick_playing(session: GameSession, actions: list[str], dt: float, shake: _ScreenShake) -> bool:
    p = session.player
    obs = session.obstacles
    for action in actions:
        if action == 'jump':
            p.action_jump()
        elif action == 'slide':
            p.action_slide()
        elif action == 'shield':
            p.action_shield()
        elif action == 'lean_left':
            p.action_lean(-1)
        elif action == 'lean_right':
            p.action_lean(+1)
    session.game_speed = min(config.SPEED_MAX, session.game_speed + config.SPEED_INCREASE * dt)
    p.update(dt)
    obs.update(dt, session.game_speed)
    hit = obs.check_obstacle_hit(p)
    if hit:
        p.take_hit()
        shake.trigger()
    earned = obs.collect_coins(p)
    session.coins += earned
    session.score += earned * config.COLLECTIBLE_POINTS
    session.score += config.SCORE_PER_SECOND * dt
    session.distance += session.game_speed * dt / 100.0
    return hit
