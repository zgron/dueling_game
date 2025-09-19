# -*- coding: utf-8 -*-
"""
Top‑down Brawler
================
A compact yet complete implementation of the game you described.

Dependencies
------------
  pip install pygame pymunk

Run
---
  python topdown_brawler.py

Tweaks
------
All gameplay constants live in the CONFIG JSON string right below the imports.
"""

import json
import math
import random
import sys
from pathlib import Path

import pygame as pg
import pymunk
from pygame.math import Vector2 as V2
from pymunk import Vec2d

# -----------------------------------------------------------------------------
# Configuration ‑‑ tweak away!
# -----------------------------------------------------------------------------
CONFIG = {
    # Window ------------------------------------------------------------------
    "screen_width": 1280,
    "screen_height": 720,
    "fps": 60,

    # Player & character geometry ---------------------------------------------
    "body_radius": 32,       # circle radius
    "shoulder_size": 36,     # square side length; overlaps the body slightly
    "arm_length": 64,        # absolute arm length – reach varies by weapon length
    "sword_length": 64,
    "dagger_length": 32,
    "weapon_thickness": 8,

    # Speeds ------------------------------------------------------------------
    "arm_extend_speed": {
        "bare": 800,
        "dagger": 700,
        "sword": 500,
        "shield": 400,
    },
    "walk_speed": 260,             # px / s – brisk but readable
    "body_turn_speed": 540,        # °/s
    "arm_turn_speed": 960,         # °/s

    # Combat ------------------------------------------------------------------
    "knockback_minor": 50,
    "knockback_hit": 120,
    "hp_max": 9,

    # Spawning ---------------------------------------------------------------
    "spawn_base_interval": 5.0,    # seconds when only one enemy exists
    "spawn_min_interval": 1.2,
    "spawn_acceleration": 0.95,    # multiply interval every 30 s of playtime
}

# Derived helpers
SCREEN = pg.Rect(0, 0, CONFIG["screen_width"], CONFIG["screen_height"])
DT = 1.0 / CONFIG["fps"]
DEG2RAD = math.pi / 180

# Pymunk collision types
COL_PLAYER = 1
COL_ENEMY = 2
COL_WEAPON = 3
COL_CAMPFIRE = 4
COL_ROCK = 5
COL_TREE = 6

# Layers (draw order)
LAYER_GROUND = 0
LAYER_SPLATTER = 1
LAYER_OBJECT = 2
LAYER_ROOF = 3

pg.init()
FONT = pg.font.SysFont("consolas", 20)
BIGFONT = pg.font.SysFont("consolas", 36, bold=True)

# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------

def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def angle_to(a: V2, b: V2) -> float:
    """Return angle in degrees a→b (‑180…180)."""
    return math.degrees(math.atan2(b.y, b.x) - math.atan2(a.y, a.x))


def rot_vec(angle_deg: float, length: float = 1.0) -> V2:
    rad = angle_deg * DEG2RAD
    return V2(math.cos(rad), math.sin(rad)) * length


def wrap_angle(deg: float) -> float:
    while deg <= -180:
        deg += 360
    while deg > 180:
        deg -= 360
    return deg


# -----------------------------------------------------------------------------
# Base sprites (hand‑rolled ‑ we don't subclass pg.sprite.Sprite to stay simple)
# -----------------------------------------------------------------------------
class GameObject:
    __slots__ = ("pos", "layer")

    def __init__(self, pos: V2, layer=LAYER_OBJECT):
        self.pos = V2(pos)
        self.layer = layer

    def update(self, dt):
        pass

    def draw(self, surf):
        pass


# -----------------------------------------------------------------------------
# Character, Arms, Weapons
# -----------------------------------------------------------------------------
class Weapon:
    """Pure data container, drawn by the Arm."""

    def __init__(self, kind: str):
        self.kind = kind  # "sword" | "dagger" | "shield" | "bare"
        self.length = {
            "sword": CONFIG["sword_length"],
            "dagger": CONFIG["dagger_length"],
            "shield": CONFIG["weapon_thickness"],  # minimal, handled separately
            "bare": 0,
        }[kind]
        self.thickness = CONFIG["weapon_thickness"]
        self.extend_speed = CONFIG["arm_extend_speed"].get(kind, 600)


class Arm:
    """Handles extension, rotation limits, collision shape construction."""

    def __init__(self, owner, side: str, weapon: Weapon):
        self.owner = owner
        self.side = side  # "left" or "right"
        self.weapon = weapon
        self.extended = False  # currently holding mouse button / attack
        self.t = 0.0           # 0…1 extension fraction
        # angle 0° = "baseline" (straight out), positive forward swing
        self.angle = 0.0
        self.target_angle = 0.0
        # collision shape – created on demand
        self.shape = None

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    def shoulder_angle(self, body_angle):
        return body_angle + (90 if self.side == "left" else -90)

    def shoulder_pos(self):
        return self.owner.pos + rot_vec(self.shoulder_angle(self.owner.angle), CONFIG["body_radius"] - 4)

    def hand_pos(self):
        # angle world‑space
        world_angle = self.shoulder_angle(self.owner.angle) + self.angle
        return self.shoulder_pos() + rot_vec(world_angle, CONFIG["arm_length"] * self.t)

    # ------------------------------------------------------------------
    def update(self, dt):
        # handle extension / retraction towards target t
        target_t = 1.0 if self.extended else 0.0
        speed_px = self.weapon.extend_speed
        delta_t = speed_px * dt / CONFIG["arm_length"]
        if target_t > self.t:
            self.t = clamp(self.t + delta_t, 0, target_t)
        else:
            self.t = clamp(self.t - delta_t, target_t, 1)

        # rotate toward target_angle within limits
        # First establish desired target angle: owner sets it frame‑wise
        limit_lo, limit_hi = -45, 135  # degrees relative to baseline
        delta = wrap_angle(self.target_angle - self.angle)
        max_step = CONFIG["arm_turn_speed"] * dt
        step = clamp(delta, -max_step, max_step)
        self.angle = clamp(self.angle + step, limit_lo, limit_hi)

        # rebuild physics shape if needed
        self.ensure_shape()

    def ensure_shape(self):
        if self.shape is not None:
            self.owner.game.space.remove(self.shape)
        if self.t > 0.1 and self.weapon.kind != "shield":
            # Segment from shoulder to hand
            a = self.shoulder_pos()
            b = self.hand_pos()
            self.shape = pymunk.Segment(self.owner.body, (a.x - self.owner.pos.x, a.y - self.owner.pos.y),
                                         (b.x - self.owner.pos.x, b.y - self.owner.pos.y),
                                         self.weapon.thickness / 2)
            self.shape.sensor = False
            self.shape.collision_type = COL_WEAPON
            self.shape.filter = pymunk.ShapeFilter(group=self.owner.pymunk_group)
            self.shape.user_data = {"owner": self.owner}
            self.owner.game.space.add(self.shape)
        else:
            self.shape = None

    def draw(self, surf):
        # Shoulder square
        shp = self.shoulder_pos()
        size = CONFIG["shoulder_size"]
        rect = pg.Rect(0, 0, size, size)
        rect.center = shp
        pg.draw.rect(surf, (220, 200, 40), rect)  # yellowish

        # Arm (line) if t>0
        if self.t > 0.05:
            pg.draw.line(surf, (220, 200, 40), shp, self.hand_pos(), CONFIG["weapon_thickness"])

        # Weapon rendering
        if self.weapon.kind in ("sword", "dagger") and self.t > 0.1:
            # Draw as grey rectangle from hand outward
            length = self.weapon.length
            thickness = self.weapon.thickness
            dir_vec = (self.hand_pos() - shp).normalize()
            outward = self.hand_pos() + dir_vec * length
            pg.draw.line(surf, (160, 160, 160), self.hand_pos(), outward, thickness)
        elif self.weapon.kind == "shield":
            # Small square perpendicular to arm, centered on hand
            size = CONFIG["shoulder_size"] * 0.9
            rect = pg.Rect(0, 0, size, size)
            rect.center = self.hand_pos()
            pg.draw.rect(surf, (100, 100, 100), rect)


class Character(GameObject):
    _id_counter = 0

    def __init__(self, game, pos: V2, ai=None, left_weapon="bare", right_weapon="sword"):
        super().__init__(pos)
        self.game = game
        self.id = Character._id_counter; Character._id_counter += 1
        self.angle = 0.0  # facing degrees (0 = +x)
        self.hp = CONFIG["hp_max"]
        self.ai = ai  # None -> player controlled
        # Pymunk body
        self.body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.body.position = Vec2d(*pos)
        self.shape = pymunk.Circle(self.body, CONFIG["body_radius"])
        if self.ai is None:
            self.shape.collision_type = COL_PLAYER
        else:
            self.shape.collision_type = COL_ENEMY
        self.shape.filter = pymunk.ShapeFilter(group=self.id)
        self.shape.user_data = {"owner": self}
        game.space.add(self.body, self.shape)
        self.pymunk_group = self.id  # used to keep own shapes from colliding with each other
        # Arms
        self.left_arm = Arm(self, "left", Weapon(left_weapon))
        self.right_arm = Arm(self, "right", Weapon(right_weapon))
        # Movement & state
        self.vel = V2()
        self.knock_timer = 0.0

    # ------------------------------------------------------------------
    # Control interface
    # ------------------------------------------------------------------
    def set_target_dir(self, dir_vec: V2):
        if dir_vec.length_squared() == 0:
            return
        target_angle = math.degrees(math.atan2(dir_vec.y, dir_vec.x))
        delta = wrap_angle(target_angle - self.angle)
        max_step = CONFIG["body_turn_speed"] * self.game.dt
        step = clamp(delta, -max_step, max_step)
        self.angle += step

    def update(self, dt):
        self.game.dt = dt  # quick access for arms
        # Player or AI logic to set movement & attacks
        if self.ai is None:
            self.player_control(dt)
        else:
            self.ai_control(dt)
        # Update arms
        self.left_arm.update(dt)
        self.right_arm.update(dt)
        # Move
        self.pos += self.vel * dt
        self.body.position = Vec2d(*self.pos)
        # prevent going off screen
        self.pos.x = clamp(self.pos.x, CONFIG["body_radius"], CONFIG["screen_width"] - CONFIG["body_radius"])
        self.pos.y = clamp(self.pos.y, CONFIG["body_radius"], CONFIG["screen_height"] - CONFIG["body_radius"])
        self.body.position = Vec2d(*self.pos)
        # timers
        self.knock_timer = max(0, self.knock_timer - dt)

    def player_control(self, dt):
        keys = pg.key.get_pressed()
        dir_input = V2(keys[pg.K_d] - keys[pg.K_a], keys[pg.K_s] - keys[pg.K_w])
        if dir_input.length_squared() > 0:
            dir_input = dir_input.normalize()
        self.vel = dir_input * CONFIG["walk_speed"]
        mx, my = pg.mouse.get_pos()
        cursor_dir = V2(mx, my) - self.pos
        self.set_target_dir(cursor_dir)

        # Arms & mouse buttons
        l, _, r = pg.mouse.get_pressed()
        self.left_arm.extended = l
        self.right_arm.extended = r
        if l:
            self.left_arm.target_angle = clamp(angle_to(rot_vec(self.left_arm.shoulder_angle(self.angle)), cursor_dir), -45, 135)
        if r:
            self.right_arm.target_angle = clamp(angle_to(rot_vec(self.right_arm.shoulder_angle(self.angle)), cursor_dir), -45, 135)

    def ai_control(self, dt):
        if not hasattr(self, "ai_state"):
            self.ai_state = "circle"
            self.state_timer = random.uniform(1, 3)
        self.state_timer -= dt
        # Basic state machine
        player = self.game.player
        to_player = player.pos - self.pos
        dist = to_player.length()
        dir_to_player = to_player.normalize()
        self.left_arm.extended = False
        self.right_arm.extended = False
        if self.ai_state == "circle":
            # strafe at roughly fixed distance
            tangent = V2(-dir_to_player.y, dir_to_player.x) * CONFIG["walk_speed"]
            self.vel = tangent * (1 if random.random() < 0.5 else -1)
            if dist < 140:
                self.ai_state = "attack"
                self.state_timer = random.uniform(0.4, 1.0)
        elif self.ai_state == "attack":
            self.vel = dir_to_player * CONFIG["walk_speed"]
            self.right_arm.extended = True
            self.right_arm.target_angle = 45  # generic swing
            if self.state_timer <= 0:
                self.ai_state = "retreat"
                self.state_timer = random.uniform(0.6, 1.2)
        elif self.ai_state == "retreat":
            self.vel = -dir_to_player * CONFIG["walk_speed"]
            if dist > 220 or self.state_timer <= 0:
                self.ai_state = "circle"
                self.state_timer = random.uniform(1, 3)
        self.set_target_dir(dir_to_player)

    # ------------------------------------------------------------------
    def take_damage(self, amount: int, source_pos: V2):
        if self.hp <= 0:
            return
        self.hp -= amount
        self.knock_timer = 0.15
        # knockback impulse
        knock = (self.pos - source_pos).normalize() * CONFIG["knockback_hit"]
        self.pos += knock
        # blood splatter
        self.game.splatters.append((self.pos.xy, pg.time.get_ticks()))
        if self.hp <= 0:
            self.die()

    def die(self):
        # remove shapes
        self.game.space.remove(self.shape)
        self.game.characters.remove(self)
        if self.ai is None:
            self.game.on_player_death()
        else:
            self.game.kills += 1

    # ------------------------------------------------------------------
    def draw(self, surf):
        # body circle
        pg.draw.circle(surf, (220, 200, 40), self.pos, CONFIG["body_radius"])
        # facing indicator (small line)
        tip = self.pos + rot_vec(self.angle, CONFIG["body_radius"])
        pg.draw.line(surf, (0, 0, 0), self.pos, tip, 3)
        # arms
        self.left_arm.draw(surf)
        self.right_arm.draw(surf)
        # HP for enemies
        if self.ai is not None:
            txt = FONT.render(str(self.hp), True, (255, 0, 0))
            rect = txt.get_rect(center=self.pos)
            surf.blit(txt, rect)


# -----------------------------------------------------------------------------
# Game class – orchestrates everything
# -----------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.screen = pg.display.set_mode((CONFIG["screen_width"], CONFIG["screen_height"]))
        pg.display.set_caption("Top‑down Brawler")
        self.clock = pg.time.Clock()
        self.dt = DT
        # physics
        self.space = pymunk.Space()
        self.space.gravity = (0, 0)
        self.space.damping = 0.9
        # entities
        self.characters = []
        self.splatters = []  # (pos, time_ms)
        # player + initial enemy
        self.player = Character(self, V2(CONFIG["screen_width"] / 2, CONFIG["screen_height"] / 2))
        self.characters.append(self.player)
        self.spawn_enemy()
        # UI / meta
        self.running = True
        self.kills = 0
        self.spawn_timer = CONFIG["spawn_base_interval"]
        self.playtime = 0.0
        # collision handlers
        self.space.add_collision_handler(COL_WEAPON, COL_ENEMY).post_solve = self.weapon_hits_body
        self.space.add_collision_handler(COL_WEAPON, COL_PLAYER).post_solve = self.weapon_hits_body

    # ------------------------------------------------------------------
    def weapon_hits_body(self, arbiter, _space, _data):
        weapon_shape, body_shape = arbiter.shapes
        owner = weapon_shape.user_data["owner"]
        victim = body_shape.user_data["owner"]
        if owner is victim:
            return
        # Simple damage once per frame; in future we can gate by cooldown
        victim.take_damage(1, owner.pos)

    # ------------------------------------------------------------------
    def spawn_enemy(self):
        # choose a spawn point off‑screen
        margin = 50
        side = random.choice(["top", "bottom", "left", "right"])
        if side == "top":
            pos = V2(random.uniform(0, CONFIG["screen_width"]), -margin)
        elif side == "bottom":
            pos = V2(random.uniform(0, CONFIG["screen_width"]), CONFIG["screen_height"] + margin)
        elif side == "left":
            pos = V2(-margin, random.uniform(0, CONFIG["screen_height"]))
        else:
            pos = V2(CONFIG["screen_width"] + margin, random.uniform(0, CONFIG["screen_height"]))
        # equipment random
        weapons = ["sword", "dagger"]
        left = random.choice(weapons)
        right = random.choice(weapons + ["shield"])
        if left == "shield" and right == "shield":
            right = "sword"
        enemy = Character(self, pos, ai=True, left_weapon=left, right_weapon=right)
        self.characters.append(enemy)

    # ------------------------------------------------------------------
    def on_player_death(self):
        self.running = False
        name = input("\nGame Over! You scored %d kills. Enter initials: " % self.kills)[:3].upper()
        hi_path = Path("highscore.txt")
        line = f"{name} {self.kills}\n"
        with hi_path.open("a", encoding="utf8") as f:
            f.write(line)
        print("Score saved to", hi_path.absolute())

    # ------------------------------------------------------------------
    def run(self):
        while self.running:
            self.dt = self.clock.tick(CONFIG["fps"]) / 1000.0
            self.playtime += self.dt
            self.handle_events()
            self.update(self.dt)
            self.draw()
        pg.quit()

    # ------------------------------------------------------------------
    def handle_events(self):
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                pg.quit(); sys.exit()
            elif ev.type == pg.KEYDOWN and ev.key == pg.K_ESCAPE:
                pg.quit(); sys.exit()

    # ------------------------------------------------------------------
    def update(self, dt):
        # gravity / physics
        self.space.step(dt)
        # characters
        for ch in list(self.characters):
            ch.update(dt)
        # spawn logic
        self.spawn_timer -= dt
        target_interval = max(CONFIG["spawn_min_interval"], CONFIG["spawn_base_interval"] * (CONFIG["spawn_acceleration"] ** (self.playtime / 30)))
        if len([c for c in self.characters if c.ai]) < 3 and self.spawn_timer <= 0:
            self.spawn_enemy()
            self.spawn_timer = target_interval
        # splatter cleanup (older than 10 s)
        now = pg.time.get_ticks()
        self.splatters = [s for s in self.splatters if now - s[1] < 10000]

    # ------------------------------------------------------------------
    def draw(self):
        # ground layer (cobblestones) – simple grey noise pattern
        self.screen.fill((60, 60, 60))
        for x in range(0, CONFIG["screen_width"], 64):
            for y in range(0, CONFIG["screen_height"], 64):
                pg.draw.circle(self.screen, (80 + (x ^ y) % 40,)*3, (x+32, y+32), 30, 1)
        # splatter layer
        for pos, _ in self.splatters:
            pg.draw.circle(self.screen, (120, 0, 0), (int(pos[0]), int(pos[1])), 6)
        # object layer (characters & rocks) – characters only for now
        for c in self.characters:
            c.draw(self.screen)
        # UI
        self.draw_ui()
        pg.display.flip()

    # ------------------------------------------------------------------
    def draw_ui(self):
        # player HP bar bottom left
        bar_w = 180
        hp_ratio = self.player.hp / CONFIG["hp_max"]
        pg.draw.rect(self.screen, (0, 0, 0), (20, CONFIG["screen_height"] - 40, bar_w, 16), 2)
        pg.draw.rect(self.screen, (200, 0, 0), (22, CONFIG["screen_height"] - 38, (bar_w - 4) * hp_ratio, 12))
        # kill counter top‑left
        txt = FONT.render(f"Kills: {self.kills}", True, (255, 255, 255))
        self.screen.blit(txt, (20, 20))


# -----------------------------------------------------------------------------
if __name__ == "__main__":
    Game().run()
