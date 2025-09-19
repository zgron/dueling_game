import pygame
import pymunk
import math
import random

# Initialize Pygame and Pymunk
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Top-Down Combat Game")
clock = pygame.time.Clock()
space = pymunk.Space()
space.gravity = (0, 0)  # No gravity for top-down

# Colors
YELLOW = (255, 255, 0)
GREY = (150, 150, 150)
DARK_GREY = (100, 100, 100)
BROWN = (139, 69, 19)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
YELLOW_FIRE = (255, 255, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Game states
STATE_MENU = 0
STATE_EQUIP = 1
STATE_PLAYING = 2
STATE_GAME_OVER = 3

# Equipment types
EQUIP_SWORD = "sword"
EQUIP_DAGGER = "dagger"
EQUIP_SHIELD = "shield"
EQUIP_NONE = "none"

# Equipment properties
EQUIPMENT_DATA = {
    EQUIP_SWORD: {"speed": 200, "max_length": 40, "damage": 1, "size": (30, 10)},
    EQUIP_DAGGER: {"speed": 300, "max_length": 20, "damage": 1, "size": (20, 8)},
    EQUIP_SHIELD: {"speed": 100, "max_length": 30, "damage": 0, "size": (20, 15)},
    EQUIP_NONE: {"speed": 400, "max_length": 10, "damage": 1, "size": (0, 0)}
}

class Arm:
    def __init__(self, side, equipment):
        self.side = side  # "left" or "right"
        self.equipment = equipment
        self.length = 10  # Starts as shoulder size
        self.max_length = EQUIPMENT_DATA[equipment]["max_length"]
        self.extension_speed = EQUIPMENT_DATA[equipment]["speed"]
        self.angle = 0  # Relative to straight out (0 degrees)
        self.state = "retracted"  # "retracted", "extending", "extended", "retracting"
        self.target_angle = 0

    def update(self, dt, target_pos, body_pos, body_angle, fixed_rotation):
        dx = target_pos[0] - body_pos[0]
        dy = target_pos[1] - body_pos[1]
        desired_angle = math.degrees(math.atan2(-dy, dx)) - math.degrees(body_angle)
        if self.side == "left":
            desired_angle += 90
        else:
            desired_angle -= 90
        self.target_angle = max(-45, min(135, desired_angle))
        angle_diff = self.target_angle - self.angle
        max_rotate = 360 * dt
        self.angle += max(min(angle_diff, max_rotate), -max_rotate)
        if self.state == "extending":
            self.length += self.extension_speed * dt
            if self.length >= self.max_length:
                self.length = self.max_length
                self.state = "extended"
        elif self.state == "retracting":
            self.length -= self.extension_speed * dt
            if self.length <= 10:
                self.length = 10
                self.state = "retracted"

class Character:
    def __init__(self, x, y, is_player=False):
        self.pos = [x, y]
        self.angle = 0
        self.radius = 20
        self.health = 10 if is_player else random.randint(1, 9)
        self.speed = 200
        self.group = id(self)
        self.left_arm = Arm("left", EQUIP_NONE)
        self.right_arm = Arm("right", EQUIP_NONE)
        self.body = pymunk.Body(body_type=pymunk.Body.DYNAMIC)
        self.body.position = x, y
        self.body_shape = pymunk.Circle(self.body, self.radius)
        self.body_shape.friction = 0.5
        self.body_shape.collision_type = 1
        self.body_shape.group = self.group
        space.add(self.body, self.body_shape)
        self.arm_shapes = {"left": None, "right": None}
        self.equip_shapes = {"left": None, "right": None}
        self.is_player = is_player
        self.last_damage_time = 0  # Track last campfire damage time

    def update(self, dt):
        self.pos = list(self.body.position)
        self.angle = self.body.angle
        mouse_pos = pygame.mouse.get_pos()
        self.left_arm.update(dt, mouse_pos, self.pos, self.angle, pygame.mouse.get_pressed()[0])
        self.right_arm.update(dt, mouse_pos, self.pos, self.angle, pygame.mouse.get_pressed()[2])
        for side in ["left", "right"]:
            arm = self.left_arm if side == "left" else self.right_arm
            angle_offset = math.radians(90 if side == "left" else -90)
            shoulder_pos = (
                self.pos[0] + math.cos(self.angle + angle_offset) * self.radius,
                self.pos[1] + math.sin(self.angle + angle_offset) * self.radius
            )
            hand_pos = (
                shoulder_pos[0] + math.cos(self.angle + angle_offset + math.radians(arm.angle)) * arm.length,
                shoulder_pos[1] + math.sin(self.angle + angle_offset + math.radians(arm.angle)) * arm.length
            )
            if self.arm_shapes[side]:
                space.remove(self.arm_shapes[side])
            self.arm_shapes[side] = pymunk.Segment(space.static_body, shoulder_pos, hand_pos, 5)
            self.arm_shapes[side].collision_type = 2
            self.arm_shapes[side].group = self.group
            space.add(self.arm_shapes[side])
            if self.equip_shapes[side]:
                space.remove(self.equip_shapes[side])
            if arm.equipment != EQUIP_NONE:
                w, h = EQUIPMENT_DATA[arm.equipment]["size"]
                if arm.equipment == EQUIP_SHIELD:
                    equip_angle = self.angle + (math.pi / 2 if side == "left" else -math.pi / 2)
                else:
                    equip_angle = self.angle + angle_offset + math.radians(arm.angle)
                self.equip_shapes[side] = pymunk.Poly.create_box(None, (w, h))
                self.equip_shapes[side].body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
                self.equip_shapes[side].body.position = hand_pos
                self.equip_shapes[side].body.angle = equip_angle
                self.equip_shapes[side].collision_type = 3
                self.equip_shapes[side].group = self.group
                space.add(self.equip_shapes[side].body, self.equip_shapes[side])

    def draw(self, surface):
        pygame.draw.circle(surface, YELLOW, self.pos, self.radius)
        for side in ["left", "right"]:
            arm = self.left_arm if side == "left" else self.right_arm
            angle_offset = math.radians(90 if side == "left" else -90)
            shoulder_pos = (
                self.pos[0] + math.cos(self.angle + angle_offset) * self.radius,
                self.pos[1] + math.sin(self.angle + angle_offset) * self.radius
            )
            hand_pos = (
                shoulder_pos[0] + math.cos(self.angle + angle_offset + math.radians(arm.angle)) * arm.length,
                shoulder_pos[1] + math.sin(self.angle + angle_offset + math.radians(arm.angle)) * arm.length
            )
            points = self._get_rectangle_points(shoulder_pos, hand_pos, 10)
            pygame.draw.polygon(surface, GREY, points)
            if arm.equipment != EQUIP_NONE:
                w, h = EQUIPMENT_DATA[arm.equipment]["size"]
                if arm.equipment == EQUIP_SHIELD:
                    equip_angle = self.angle + (math.pi / 2 if side == "left" else -math.pi / 2)
                else:
                    equip_angle = self.angle + angle_offset + math.radians(arm.angle)
                equip_points = self._get_rectangle_points(hand_pos, (
                    hand_pos[0] + math.cos(equip_angle) * w,
                    hand_pos[1] + math.sin(equip_angle) * w
                ), h)
                pygame.draw.polygon(surface, GREY, equip_points)
        if not self.is_player:
            font = pygame.font.SysFont(None, 24)
            text = font.render(str(self.health), True, WHITE)
            surface.blit(text, (self.pos[0] - 5, self.pos[1] - 5))

    def _get_rectangle_points(self, start, end, width):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length == 0:
            return [start] * 4
        perp = (-dy / length * width / 2, dx / length * width / 2)
        return [
            (start[0] - perp[0], start[1] - perp[1]),
            (start[0] + perp[0], start[1] + perp[1]),
            (end[0] + perp[0], end[1] + perp[1]),
            (end[0] - perp[0], end[1] - perp[1])
        ]

    def take_damage(self, amount, source_pos):
        self.health -= amount
        dx = self.pos[0] - source_pos[0]
        dy = self.pos[1] - source_pos[1]
        dist = max(math.hypot(dx, dy), 1)
        impulse = (dx / dist * 200, dy / dist * 200)
        self.body.apply_impulse_at_local_point(impulse)
        splatters.append(Splatter(self.pos, amount))

class Player(Character):
    def __init__(self, x, y):
        super().__init__(x, y, is_player=True)

    def update(self, dt):
        keys = pygame.key.get_pressed()
        vel = [0, 0]
        if keys[pygame.K_w]: vel[1] -= self.speed
        if keys[pygame.K_s]: vel[1] += self.speed
        if keys[pygame.K_a]: vel[0] -= self.speed
        if keys[pygame.K_d]: vel[0] += self.speed
        self.body.velocity = vel
        mouse_pos = pygame.mouse.get_pos()
        if not any(pygame.mouse.get_pressed()):
            dx = mouse_pos[0] - self.pos[0]
            dy = mouse_pos[1] - self.pos[1]
            self.body.angle = math.atan2(-dy, dx)
        buttons = pygame.mouse.get_pressed()
        if buttons[0]:
            self.left_arm.state = "extending"
        elif self.left_arm.state == "extended":
            self.left_arm.state = "retracting"
        if buttons[2]:
            self.right_arm.state = "extending"
        elif self.right_arm.state == "extended":
            self.right_arm.state = "retracting"
        super().update(dt)

class Enemy(Character):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.state = "idle"
        self.timer = 0
        self.profile = random.choice(["aggressive", "cautious", "defensive"])
        self.target_pos = [x, y]
        self.attack_mode = False

    def update(self, dt):
        self.timer += dt
        player_pos = player.pos if "player" in globals() else [WIDTH / 2, HEIGHT / 2]
        if self.profile == "aggressive":
            self._move_toward(player_pos, dt)
            if math.hypot(player_pos[0] - self.pos[0], player_pos[1] - self.pos[1]) < 100:
                self.attack_mode = True
                self._attack(player_pos)
            else:
                self.attack_mode = False
        elif self.profile == "cautious":
            if self.timer > 2:
                self.state = random.choice(["circle", "approach"])
                self.timer = 0
            if self.state == "circle":
                self._circle(player_pos, dt)
            else:
                self._move_toward(player_pos, dt)
                if math.hypot(player_pos[0] - self.pos[0], player_pos[1] - self.pos[1]) < 150:
                    self.attack_mode = True
                    self._attack(player_pos)
                else:
                    self.attack_mode = False
        elif self.profile == "defensive":
            dist = math.hypot(player_pos[0] - self.pos[0], player_pos[1] - self.pos[1])
            if dist < 200:
                self._move_away(player_pos, dt)
                if dist < 100 and self.timer > 1:
                    self.attack_mode = True
                    self._attack(player_pos)
                    self.timer = 0
                else:
                    self.attack_mode = False
        super().update(dt)

    def _move_toward(self, target, dt):
        dx = target[0] - self.pos[0]
        dy = target[1] - self.pos[1]
        dist = max(math.hypot(dx, dy), 1)
        self.body.velocity = (dx / dist * self.speed, dy / dist * self.speed)
        self.body.angle = math.atan2(-dy, dx)

    def _move_away(self, target, dt):
        dx = self.pos[0] - target[0]
        dy = self.pos[1] - target[1]
        dist = max(math.hypot(dx, dy), 1)
        self.body.velocity = (dx / dist * self.speed, dy / dist * self.speed)

    def _circle(self, target, dt):
        angle = self.timer * 2
        self.target_pos = [
            target[0] + math.cos(angle) * 200,
            target[1] + math.sin(angle) * 200
        ]
        self._move_toward(self.target_pos, dt)

    def _attack(self, target):
        for arm in [self.left_arm, self.right_arm]:
            if arm.state == "retracted" and random.random() < 0.5:
                arm.state = "extending"
            elif arm.state == "extended":
                arm.state = "retracting"

class Splatter:
    def __init__(self, pos, amount):
        self.pos = list(pos)
        self.radius = 5 + amount * 2
        self.lifetime = 2

    def update(self, dt):
        self.lifetime -= dt
        return self.lifetime > 0

    def draw(self, surface):
        pygame.draw.circle(surface, RED, self.pos, self.radius)

class Campfire:
    def __init__(self, x, y):
        self.pos = [x, y]
        self.size = 30
        self.anim_time = 0
        self.shape = pymunk.Poly.create_box(space.static_body, (self.size, self.size))
        self.shape.position = x, y
        self.shape.collision_type = 4
        space.add(self.shape)

    def update(self, dt):
        self.anim_time += dt

    def draw(self, surface):
        pygame.draw.rect(surface, BROWN, (self.pos[0] - self.size / 2, self.pos[1] - self.size / 2, self.size, self.size))
        scale = 1 + math.sin(self.anim_time * 5) * 0.2
        red_points = [(self.pos[0], self.pos[1] - 15 * scale), (self.pos[0] - 10, self.pos[1] + 10), (self.pos[0] + 10, self.pos[1] + 10)]
        yellow_points = [(self.pos[0], self.pos[1] - 10 * scale), (self.pos[0] - 5, self.pos[1] + 5), (self.pos[0] + 5, self.pos[1] + 5)]
        pygame.draw.polygon(surface, RED, red_points)
        pygame.draw.polygon(surface, YELLOW_FIRE, yellow_points)

class Tree:
    def __init__(self, x, y):
        self.pos = [x, y]
        self.trunk_radius = 10
        self.foliage_radius = 30
        self.trunk_shape = pymunk.Circle(space.static_body, self.trunk_radius)
        self.trunk_shape.position = x, y
        self.trunk_shape.collision_type = 5
        space.add(self.trunk_shape)

    def draw(self, surface):
        alpha = 255
        if game_state == STATE_PLAYING:
            for char in [player] + enemies:
                if math.hypot(char.pos[0] - self.pos[0], char.pos[1] - self.pos[1]) < self.foliage_radius:
                    alpha = 100
                    break
        foliage_surface = pygame.Surface((self.foliage_radius * 2, self.foliage_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(foliage_surface, (0, 255, 0, alpha), (self.foliage_radius, self.foliage_radius), self.foliage_radius)
        surface.blit(foliage_surface, (self.pos[0] - self.foliage_radius, self.pos[1] - self.foliage_radius))
        pygame.draw.circle(surface, BROWN, self.pos, self.trunk_radius)

class Rock:
    def __init__(self, x, y):
        self.pos = [x, y]
        self.radius = 15
        self.shape = pymunk.Circle(space.static_body, self.radius)
        self.shape.position = x, y
        self.shape.collision_type = 5
        space.add(self.shape)

    def draw(self, surface):
        pygame.draw.circle(surface, DARK_GREY, self.pos, self.radius)

# Collision handlers
def character_collision(arbiter, space, data):
    char1 = next(c for c in [player] + enemies if c.body_shape == arbiter.shapes[0])
    char2 = next(c for c in [player] + enemies if c.body_shape == arbiter.shapes[1])
    dx = char1.pos[0] - char2.pos[0]
    dy = char1.pos[1] - char2.pos[1]
    dist = max(math.hypot(dx, dy), 1)
    impulse = (dx / dist * 50, dy / dist * 50)
    char1.body.apply_impulse_at_local_point(impulse)
    char2.body.apply_impulse_at_local_point((-impulse[0], -impulse[1]))
    return True

handler = space.add_collision_handler(1, 1)
handler.separate = character_collision

def equip_collision(arbiter, space, data):
    equip_shape = arbiter.shapes[0] if arbiter.shapes[0].collision_type == 3 else arbiter.shapes[1]
    body_shape = arbiter.shapes[0] if arbiter.shapes[0].collision_type == 1 else arbiter.shapes[1]
    owner = next(c for c in [player] + enemies if equip_shape in c.equip_shapes.values())
    target = next(c for c in [player] + enemies if c.body_shape == body_shape)
    if owner == target:
        return False
    equip = owner.left_arm.equipment if equip_shape == owner.equip_shapes["left"] else owner.right_arm.equipment
    arm = owner.left_arm if equip_shape == owner.equip_shapes["left"] else owner.right_arm
    if equip in [EQUIP_SWORD, EQUIP_DAGGER]:
        target.take_damage(EQUIPMENT_DATA[equip]["damage"], owner.pos)
    elif equip == EQUIP_NONE and (arm.state == "extending" or arm.state == "extended"):
        target.take_damage(1, owner.pos)
    return True

space.add_collision_handler(3, 1).pre_solve = equip_collision

def shield_sword_collision(arbiter, space, data):
    shield_shape = arbiter.shapes[0] if arbiter.shapes[0].group != arbiter.shapes[1].group else arbiter.shapes[1]
    sword_shape = arbiter.shapes[1] if shield_shape == arbiter.shapes[0] else arbiter.shapes[0]
    shield_owner = next(c for c in [player] + enemies if shield_shape in c.equip_shapes.values())
    sword_owner = next(c for c in [player] + enemies if sword_shape in c.equip_shapes.values())
    if shield_owner == sword_owner:
        return False
    arm = sword_owner.left_arm if sword_shape == sword_owner.equip_shapes["left"] else sword_owner.right_arm
    arm.angle -= 90
    return True

space.add_collision_handler(3, 3).pre_solve = shield_sword_collision

def campfire_collision(arbiter, space, data):
    char = next(c for c in [player] + enemies if c.body_shape == arbiter.shapes[0])
    current_time = pygame.time.get_ticks() / 1000.0  # Current time in seconds
    if current_time - char.last_damage_time >= 1:  # 1-second cooldown
        char.take_damage(1, char.pos)
        char.last_damage_time = current_time
    return True

space.add_collision_handler(1, 4).pre_solve = campfire_collision

# Game variables
game_state = STATE_MENU
player = None
enemies = []
splatters = []
environment = []
spawn_timer = 0
game_time = 0
highscore = 0
equip_choices = {"left": EQUIP_NONE, "right": EQUIP_NONE}

# Initialize environment
for _ in range(50):
    environment.append({"type": "cobblestone", "pos": [random.randint(0, WIDTH), random.randint(0, HEIGHT)], "radius": random.randint(5, 15), "color": (random.randint(100, 200),) * 3})
environment.append(Campfire(WIDTH / 2, HEIGHT / 2))
for _ in range(5):
    environment.append(Rock(random.randint(0, WIDTH), random.randint(0, HEIGHT)))
for _ in range(3):
    environment.append(Tree(random.randint(0, WIDTH), random.randint(0, HEIGHT)))

# Main game loop
running = True
font = pygame.font.SysFont(None, 36)
while running:
    dt = clock.tick(60) / 1000.0
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and game_state == STATE_GAME_OVER:
            game_state = STATE_MENU
        elif event.type == pygame.MOUSEBUTTONDOWN and game_state == STATE_EQUIP:
            mx, my = event.pos
            left_x = WIDTH / 4
            right_x = 3 * WIDTH / 4
            if left_x < mx < left_x + 100:
                if 100 < my < 150:
                    equip_choices["left"] = EQUIP_SWORD
                elif 150 < my < 200:
                    equip_choices["left"] = EQUIP_DAGGER
                elif 200 < my < 250:
                    equip_choices["left"] = EQUIP_SHIELD
                elif 250 < my < 300:
                    equip_choices["left"] = EQUIP_NONE
            elif right_x < mx < right_x + 100:
                if 100 < my < 150:
                    equip_choices["right"] = EQUIP_SWORD
                elif 150 < my < 200:
                    equip_choices["right"] = EQUIP_DAGGER
                elif 200 < my < 250:
                    equip_choices["right"] = EQUIP_SHIELD
                elif 250 < my < 300:
                    equip_choices["right"] = EQUIP_NONE
            elif WIDTH / 2 - 50 < mx < WIDTH / 2 + 50 and HEIGHT - 100 < my < HEIGHT - 50:
                game_state = STATE_PLAYING
                player = Player(WIDTH / 2 - 100, HEIGHT / 2)  # Spawn away from campfire
                player.left_arm.equipment = equip_choices["left"]
                player.right_arm.equipment = equip_choices["right"]
                enemies.clear()
                splatters.clear()
                game_time = 0

    # Update
    if game_state == STATE_PLAYING:
        space.step(dt)
        player.update(dt)
        for enemy in enemies[:]:
            enemy.update(dt)
            if enemy.health <= 0:
                enemies.remove(enemy)
                for shape in [enemy.body_shape] + list(enemy.arm_shapes.values()) + list(enemy.equip_shapes.values()):
                    if shape and shape in space.shapes:
                        space.remove(shape)
                if shape.body in space.bodies:
                    space.remove(shape.body)
        for splatter in splatters[:]:
            if not splatter.update(dt):
                splatters.remove(splatter)
        for obj in environment:
            if isinstance(obj, Campfire):
                obj.update(dt)

        # Spawning
        spawn_timer -= dt
        if spawn_timer <= 0:
            spawn_rate = max(0.5, 2 - len(enemies) * 0.2 - game_time * 0.01)
            spawn_timer = spawn_rate
            side = random.choice(["left", "right", "top", "bottom"])
            if side == "left":
                x, y = -50, random.randint(0, HEIGHT)
            elif side == "right":
                x, y = WIDTH + 50, random.randint(0, HEIGHT)
            elif side == "top":
                x, y = random.randint(0, WIDTH), -50
            else:
                x, y = random.randint(0, WIDTH), HEIGHT + 50
            enemy = Enemy(x, y)
            valid_combos = [
                (EQUIP_SWORD, EQUIP_SWORD), (EQUIP_SWORD, EQUIP_DAGGER), (EQUIP_SWORD, EQUIP_SHIELD), (EQUIP_SWORD, EQUIP_NONE),
                (EQUIP_DAGGER, EQUIP_SWORD), (EQUIP_DAGGER, EQUIP_DAGGER), (EQUIP_DAGGER, EQUIP_SHIELD), (EQUIP_DAGGER, EQUIP_NONE),
                (EQUIP_SHIELD, EQUIP_SWORD), (EQUIP_SHIELD, EQUIP_DAGGER),
                (EQUIP_NONE, EQUIP_SWORD), (EQUIP_NONE, EQUIP_DAGGER)
            ]
            left, right = random.choice(valid_combos)
            enemy.left_arm.equipment = left
            enemy.right_arm.equipment = right
            enemies.append(enemy)

        game_time += dt
        if player.health <= 0:
            highscore = max(highscore, int(game_time * 10))
            game_state = STATE_GAME_OVER

    # Draw
    screen.fill(BLACK)

    # Ground layer
    for obj in environment:
        if isinstance(obj, dict) and obj.get("type") == "cobblestone":
            pygame.draw.circle(screen, obj["color"], obj["pos"], obj["radius"])
        elif isinstance(obj, Campfire):
            obj.draw(screen)

    # Splatter layer
    for splatter in splatters:
        splatter.draw(screen)

    # Object layer
    if game_state == STATE_PLAYING:
        player.draw(screen)
        for enemy in enemies:
            enemy.draw(screen)
    for obj in environment:
        if isinstance(obj, Rock):
            obj.draw(screen)
        elif isinstance(obj, Tree):
            pygame.draw.circle(screen, BROWN, obj.pos, obj.trunk_radius)

    # Roof layer
    for obj in environment:
        if isinstance(obj, Tree):
            obj.draw(screen)

    # UI
    if game_state == STATE_MENU:
        text = font.render("WASD to move, Mouse to aim/attack. Click to start.", True, WHITE)
        screen.blit(text, (WIDTH / 2 - text.get_width() / 2, HEIGHT / 2 - 20))
        if pygame.mouse.get_pressed()[0]:
            game_state = STATE_EQUIP
    elif game_state == STATE_EQUIP:
        screen.blit(font.render("Choose Equipment:", True, WHITE), (WIDTH / 2 - 100, 50))
        options = [
            ("Left Sword", WIDTH / 4, 100), ("Left Dagger", WIDTH / 4, 150), ("Left Shield", WIDTH / 4, 200), ("Left None", WIDTH / 4, 250),
            ("Right Sword", 3 * WIDTH / 4, 100), ("Right Dagger", 3 * WIDTH / 4, 150), ("Right Shield", 3 * WIDTH / 4, 200), ("Right None", 3 * WIDTH / 4, 250),
            ("Play", WIDTH / 2 - 20, HEIGHT - 100)
        ]
        for text, x, y in options:
            color = GREEN if (text.startswith("Left") and equip_choices["left"] == text.split()[1].lower()) or \
                            (text.startswith("Right") and equip_choices["right"] == text.split()[1].lower()) else WHITE
            screen.blit(font.render(text, True, color), (x, y))
    elif game_state == STATE_PLAYING:
        pygame.draw.rect(screen, RED, (10, HEIGHT - 30, 100, 20))
        pygame.draw.rect(screen, GREEN, (10, HEIGHT - 30, player.health * 10, 20))
    elif game_state == STATE_GAME_OVER:
        screen.blit(font.render(f"Game Over! Highscore: {highscore}", True, WHITE), (WIDTH / 2 - 100, HEIGHT / 2 - 20))
        screen.blit(font.render("Press any key to restart", True, WHITE), (WIDTH / 2 - 100, HEIGHT / 2 + 20))

    pygame.display.flip()

pygame.quit()