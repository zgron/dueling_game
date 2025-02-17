import pygame
import random
import math

pygame.init()

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Colors
WHITE      = (255, 255, 255)
GREY       = (128, 128, 128)
DARK_GREY  = (50, 50, 50)
BLOOD_RED  = (200, 0, 0)
GREEN      = (0, 200, 0)
BROWN      = (139, 69, 19)
BLACK      = (0, 0, 0)
ROCK_COLOR = (120, 120, 120)  # Lighter so they are visible

# --- Helper Functions ---

def rotate_vector(vec, angle):
    """Rotate a pygame.math.Vector2 by angle (radians)."""
    cos_theta = math.cos(angle)
    sin_theta = math.sin(angle)
    return pygame.math.Vector2(vec.x * cos_theta - vec.y * sin_theta,
                               vec.x * sin_theta + vec.y * cos_theta)

def lerp_angle(current, target, max_delta):
    """Interpolate angle 'current' toward 'target' by at most max_delta."""
    diff = (target - current + math.pi) % (2 * math.pi) - math.pi
    if diff > max_delta:
        diff = max_delta
    if diff < -max_delta:
        diff = -max_delta
    return current + diff

def clamp_arm_angle(target, base, is_left=False):
    """
    Clamp the target arm angle relative to the default (base) angle.
    For right arms (is_left False): allowed delta = [-45°, +135°]
    For left arms (is_left True): allowed delta = [-135°, +45°]
    """
    delta = (target - base + math.pi) % (2 * math.pi) - math.pi
    if is_left:
        lower_bound = -3 * math.pi / 4   # -135 degrees
        upper_bound = math.pi / 4          # +45 degrees
    else:
        lower_bound = -math.pi / 4         # -45 degrees
        upper_bound = 3 * math.pi / 4        # +135 degrees
    if delta < lower_bound:
        delta = lower_bound
    elif delta > upper_bound:
        delta = upper_bound
    return base + delta

def draw_rotated_rect(surface, color, center, width, height, angle):
    """Draw a rectangle rotated (radians) around center."""
    hw, hh = width / 2, height / 2
    corners = [
        pygame.math.Vector2(-hw, -hh),
        pygame.math.Vector2(hw, -hh),
        pygame.math.Vector2(hw, hh),
        pygame.math.Vector2(-hw, hh)
    ]
    rotated = [rotate_vector(c, angle) + center for c in corners]
    pygame.draw.polygon(surface, color, rotated)

# --- Blood Splatter ---

class BloodSplatter:
    def __init__(self, pos, damage):
        self.pos = pygame.math.Vector2(pos)
        self.radius = 5 + damage  # damage influences size
        self.life = 120  # frames

    def update(self):
        self.life -= 1

    def render(self, surface):
        if self.life > 0:
            pygame.draw.circle(surface, BLOOD_RED, (int(self.pos.x), int(self.pos.y)), int(self.radius))

# --- Equipment Base Class ---

class Equipment:
    def __init__(self):
        self.pos = pygame.math.Vector2(0, 0)
        self.angle = 0

    def update_position(self, arm, body_angle):
        pass

    def render(self, surface):
        pass

# --- Sword ---

class Sword(Equipment):
    def __init__(self):
        super().__init__()
        self.length = 30
        self.width = 6
        self.damage = 1  # divided by 10

    def update_position(self, arm, body_angle):
        self.pos = arm.hand_pos
        self.angle = arm.angle if arm.extended else body_angle

    def render(self, surface):
        draw_rotated_rect(surface, GREY, self.pos, self.length, self.width, self.angle)

# --- Dagger (Short Sword) ---

class Dagger(Equipment):
    def __init__(self):
        super().__init__()
        self.length = 20
        self.width = 4
        self.damage = 0.5  # divided by 10

    def update_position(self, arm, body_angle):
        self.pos = arm.hand_pos
        self.angle = arm.angle if arm.extended else body_angle

    def render(self, surface):
        draw_rotated_rect(surface, GREY, self.pos, self.length, self.width, self.angle)

# --- Shield ---

class Shield(Equipment):
    def __init__(self):
        super().__init__()
        self.size = (15, 20)  # slimmer shield

    def update_position(self, arm, body_angle):
        self.pos = arm.hand_pos
        if arm.extended:
            # Follow the arm's angle directly.
            self.angle = arm.angle
        else:
            # When retracted, stay tangent to the body.
            self.angle = body_angle + math.pi/2

    def render(self, surface):
        draw_rotated_rect(surface, GREY, self.pos, self.size[0], self.size[1], self.angle)

# --- Arm Class ---

class Arm:
    def __init__(self, shoulder_pos):
        self.shoulder_pos = shoulder_pos
        self.extended = False
        self.angle = 0  # in radians
        self.length = 25
        self.max_rotation_speed = 0.1
        self.hand_pos = self.shoulder_pos

    def update(self, target_angle):
        self.angle = lerp_angle(self.angle, target_angle, self.max_rotation_speed)
        if self.extended:
            self.hand_pos = self.shoulder_pos + pygame.math.Vector2(math.cos(self.angle), math.sin(self.angle)) * self.length
        else:
            self.hand_pos = self.shoulder_pos

    def render(self, surface):
        if self.extended:
            pygame.draw.line(surface, DARK_GREY, self.shoulder_pos, self.hand_pos, 4)
        pygame.draw.circle(surface, DARK_GREY, (int(self.hand_pos.x), int(self.hand_pos.y)), 4)

# --- Character Base Class ---

class Character:
    def __init__(self, pos, is_player=False):
        self.pos = pygame.math.Vector2(pos)
        self.body_radius = 20
        self.body_angle = 0  # radians (facing)
        self.max_rotation_speed = 0.1
        self.health = 10  # divided by 10
        self.is_player = is_player
        self.shoulder_offset = self.body_radius

        self.left_arm = Arm(self.get_shoulder_pos('left'))
        self.right_arm = Arm(self.get_shoulder_pos('right'))

        # Player gets shield on left and sword on right.
        self.equipment = {}
        if self.is_player:
            self.equipment['left'] = Shield()
            self.equipment['right'] = Sword()
        else:
            self.equipment['right'] = random.choice([Sword(), Dagger()])
            if random.random() < 0.5:
                self.equipment['left'] = Shield()

        self.knockback = pygame.math.Vector2(0, 0)

    def get_shoulder_pos(self, side):
        offset_angle = math.pi/2 if side == 'left' else -math.pi/2
        shoulder_angle = self.body_angle + offset_angle
        return self.pos + pygame.math.Vector2(math.cos(shoulder_angle), math.sin(shoulder_angle)) * self.shoulder_offset

    def update_shoulders_and_arms(self, left_target_angle, right_target_angle):
        left_default = self.body_angle + math.pi/2
        right_default = self.body_angle - math.pi/2
        left_target_angle = clamp_arm_angle(left_target_angle, left_default, is_left=True)
        right_target_angle = clamp_arm_angle(right_target_angle, right_default, is_left=False)

        left_shoulder = self.get_shoulder_pos('left')
        right_shoulder = self.get_shoulder_pos('right')
        self.left_arm.shoulder_pos = left_shoulder
        self.right_arm.shoulder_pos = right_shoulder

        self.left_arm.update(left_target_angle)
        self.right_arm.update(right_target_angle)

        if 'left' in self.equipment:
            self.equipment['left'].update_position(self.left_arm, self.body_angle)
        if 'right' in self.equipment:
            self.equipment['right'].update_position(self.right_arm, self.body_angle)

    def update(self):
        self.pos += self.knockback
        self.knockback *= 0.9

    def render(self, surface):
        pygame.draw.circle(surface, WHITE, (int(self.pos.x), int(self.pos.y)), self.body_radius)
        left_shoulder = self.get_shoulder_pos('left')
        right_shoulder = self.get_shoulder_pos('right')
        shoulder_size = 6
        pygame.draw.rect(surface, DARK_GREY, (left_shoulder.x - shoulder_size/2, left_shoulder.y - shoulder_size/2, shoulder_size, shoulder_size))
        pygame.draw.rect(surface, DARK_GREY, (right_shoulder.x - shoulder_size/2, right_shoulder.y - shoulder_size/2, shoulder_size, shoulder_size))
        self.left_arm.render(surface)
        self.right_arm.render(surface)
        if 'left' in self.equipment:
            self.equipment['left'].render(surface)
        if 'right' in self.equipment:
            self.equipment['right'].render(surface)
        if not self.is_player:
            font = pygame.font.SysFont(None, 20)
            text = font.render(str(self.health), True, BLACK)
            surface.blit(text, (self.pos.x - text.get_width()/2, self.pos.y - text.get_height()/2))

# --- Player Subclass ---

class Player(Character):
    def __init__(self, pos):
        super().__init__(pos, is_player=True)
        self.speed = 3

    def handle_input(self, keys, mouse_pos, mouse_buttons):
        move = pygame.math.Vector2(0, 0)
        if keys[pygame.K_w]:
            move.y -= 1
        if keys[pygame.K_s]:
            move.y += 1
        if keys[pygame.K_a]:
            move.x -= 1
        if keys[pygame.K_d]:
            move.x += 1
        if move.length() > 0:
            move = move.normalize() * self.speed
        self.pos += move

        if not mouse_buttons[0] and not mouse_buttons[2]:
            target_angle = math.atan2(mouse_pos[1] - self.pos.y, mouse_pos[0] - self.pos.x)
            self.body_angle = lerp_angle(self.body_angle, target_angle, self.max_rotation_speed)
            left_target = self.body_angle + math.pi/2
            right_target = self.body_angle - math.pi/2
            self.left_arm.extended = False
            self.right_arm.extended = False
        else:
            left_target = self.body_angle + math.pi/2
            right_target = self.body_angle - math.pi/2
            if mouse_buttons[0]:
                target_angle = math.atan2(mouse_pos[1] - self.right_arm.shoulder_pos.y, mouse_pos[0] - self.right_arm.shoulder_pos.x)
                right_target = target_angle
                self.right_arm.extended = True
            else:
                self.right_arm.extended = False
            if mouse_buttons[2]:
                target_angle = math.atan2(mouse_pos[1] - self.left_arm.shoulder_pos.y, mouse_pos[0] - self.left_arm.shoulder_pos.x)
                left_target = target_angle
                self.left_arm.extended = True
            else:
                self.left_arm.extended = False

        self.update_shoulders_and_arms(left_target, right_target)
        self.update()

# --- Enemy Subclass with AI State Machine ---

class Enemy(Character):
    def __init__(self, pos):
        super().__init__(pos, is_player=False)
        self.speed = 2
        # Override health to 10 (divided by 10)
        self.health = 10
        # Initialize a basic state machine.
        self.state = random.choice(["always_point", "occasional_swing", "circling", "close_combat", "distance_test"])
        self.state_timer = random.randint(120, 300)

    def update_ai(self, player):
        self.state_timer -= 1
        if self.state_timer <= 0:
            self.state = random.choice(["always_point", "occasional_swing", "circling", "close_combat", "distance_test"])
            self.state_timer = random.randint(120, 300)
        vec_to_player = player.pos - self.pos
        distance = vec_to_player.length() if vec_to_player.length() != 0 else 1
        # Default target angles.
        left_target = self.body_angle + math.pi/2
        right_target = math.atan2(player.pos.y - self.right_arm.shoulder_pos.y,
                                  player.pos.x - self.right_arm.shoulder_pos.x)
        # Choose behavior based on state.
        if self.state == "always_point":
            # Always aim weapon at player when close.
            direction = vec_to_player.normalize()
            self.body_angle = lerp_angle(self.body_angle, math.atan2(direction.y, direction.x), self.max_rotation_speed)
            if distance > 50:
                self.pos += direction * self.speed
            if distance < 80:
                self.right_arm.extended = True
            else:
                self.right_arm.extended = False
            # Right arm always points toward player.
            right_target = math.atan2(player.pos.y - self.right_arm.shoulder_pos.y,
                                      player.pos.x - self.right_arm.shoulder_pos.x)
        elif self.state == "occasional_swing":
            direction = vec_to_player.normalize()
            self.body_angle = lerp_angle(self.body_angle, math.atan2(direction.y, direction.x), self.max_rotation_speed)
            self.pos += direction * (self.speed * 0.5)
            # Swing weapon on a periodic basis.
            if (self.state_timer % 60) < 30:
                self.right_arm.extended = True
            else:
                self.right_arm.extended = False
            right_target = math.atan2(player.pos.y - self.right_arm.shoulder_pos.y,
                                      player.pos.x - self.right_arm.shoulder_pos.x)
        elif self.state == "circling":
            # Move tangentially around the player with a slight approach.
            tangent = pygame.math.Vector2(-vec_to_player.y, vec_to_player.x).normalize()
            if random.random() < 0.5:
                tangent = -tangent
            move_vector = tangent * self.speed + vec_to_player.normalize() * (self.speed * 0.3)
            self.pos += move_vector
            target_angle = math.atan2(vec_to_player.y, vec_to_player.x)
            movement_angle = math.atan2(move_vector.y, move_vector.x)
            self.body_angle = lerp_angle(self.body_angle, (target_angle + movement_angle) / 2, self.max_rotation_speed)
            # Randomly decide to extend weapon.
            self.right_arm.extended = (random.random() < 0.5)
            right_target = math.atan2(player.pos.y - self.right_arm.shoulder_pos.y,
                                      player.pos.x - self.right_arm.shoulder_pos.x)
        elif self.state == "close_combat":
            direction = vec_to_player.normalize()
            self.pos += direction * self.speed
            self.body_angle = lerp_angle(self.body_angle, math.atan2(direction.y, direction.x), self.max_rotation_speed)
            self.right_arm.extended = True
            right_target = math.atan2(player.pos.y - self.right_arm.shoulder_pos.y,
                                      player.pos.x - self.right_arm.shoulder_pos.x)
        elif self.state == "distance_test":
            # Oscillate forward and backward.
            oscillation = math.sin(self.state_timer / 10)
            direction = vec_to_player.normalize()
            self.pos += direction * self.speed * (0.5 + 0.5 * oscillation)
            self.body_angle = lerp_angle(self.body_angle, math.atan2(direction.y, direction.x), self.max_rotation_speed)
            self.right_arm.extended = (oscillation > 0)
            right_target = math.atan2(player.pos.y - self.right_arm.shoulder_pos.y,
                                      player.pos.x - self.right_arm.shoulder_pos.x)
        self.update_shoulders_and_arms(left_target, right_target)
        super().update()

    def update(self, player):
        self.update_ai(player)

# --- Obstacle Classes ---

class Rock:
    def __init__(self, pos):
        self.pos = pygame.math.Vector2(pos)
        self.radius = random.randint(15, 30)
    def render(self, surface):
        pygame.draw.circle(surface, ROCK_COLOR, (int(self.pos.x), int(self.pos.y)), self.radius)

class Tree:
    def __init__(self, pos):
        self.pos = pygame.math.Vector2(pos)
        self.trunk_radius = 40  # solid obstacle
        self.foliage_radius = 30
    def render_trunk(self, surface):
        pygame.draw.circle(surface, BROWN, (int(self.pos.x), int(self.pos.y)), self.trunk_radius)
    def render_foliage(self, surface, player):
        distance = (player.pos - self.pos).length()
        alpha = 255 if distance > self.foliage_radius else 100
        foliage_surface = pygame.Surface((self.foliage_radius * 2, self.foliage_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(foliage_surface, (0, 200, 0, alpha), (self.foliage_radius, self.foliage_radius), self.foliage_radius)
        surface.blit(foliage_surface, (self.pos.x - self.foliage_radius, self.pos.y - self.foliage_radius))

# --- Main Game Class ---

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Top Down Game")
        self.clock = pygame.time.Clock()
        self.running = True
        self.game_over = False

        self.ground_layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.splatter_layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.object_layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.roof_layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        self.player = Player((SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2))
        self.enemies = []
        self.obstacles = []
        self.blood_splatters = []

        self.cobblestones = []
        for _ in range(100):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, SCREEN_HEIGHT)
            radius = random.randint(3, 6)
            shade = random.randint(100, 200)
            self.cobblestones.append((pygame.math.Vector2(x, y), radius, (shade, shade, shade)))
        
        for _ in range(10):
            pos = (random.randint(0, SCREEN_WIDTH), random.randint(0, SCREEN_HEIGHT))
            self.obstacles.append(Rock(pos))
        self.trees = []
        for _ in range(5):
            pos = (random.randint(50, SCREEN_WIDTH - 50), random.randint(50, SCREEN_HEIGHT - 50))
            self.trees.append(Tree(pos))

        self.enemy_spawn_timer = 0
        self.score = 0
        self.high_score = 0

    def spawn_enemy(self):
        pos = (random.randint(0, SCREEN_WIDTH), random.randint(0, SCREEN_HEIGHT))
        enemy = Enemy(pos)
        self.enemies.append(enemy)

    def handle_collisions(self):
        if 'right' in self.player.equipment:
            weapon = self.player.equipment['right']
            for enemy in self.enemies:
                dist = (weapon.pos - enemy.pos).length()
                if dist < enemy.body_radius + 10:
                    direction = (enemy.pos - self.player.pos).normalize()
                    enemy.knockback += direction * 2
                    enemy.health -= weapon.damage
                    self.blood_splatters.append(BloodSplatter(enemy.pos, weapon.damage))
        for enemy in self.enemies:
            if 'right' in enemy.equipment:
                weapon = enemy.equipment['right']
                dist = (weapon.pos - self.player.pos).length()
                if dist < self.player.body_radius + 10:
                    direction = (self.player.pos - enemy.pos).normalize()
                    self.player.knockback += direction * 2
                    self.player.health -= weapon.damage
                    self.blood_splatters.append(BloodSplatter(self.player.pos, weapon.damage))

    def resolve_all_collisions(self):
        collidables = []
        collidables.append({'pos': self.player.pos, 'radius': self.player.body_radius, 'type': 'character', 'ref': self.player})
        for enemy in self.enemies:
            collidables.append({'pos': enemy.pos, 'radius': enemy.body_radius, 'type': 'character', 'ref': enemy})
        for obstacle in self.obstacles:
            if isinstance(obstacle, Rock):
                collidables.append({'pos': obstacle.pos, 'radius': obstacle.radius, 'type': 'rock', 'ref': obstacle})
        for tree in self.trees:
            collidables.append({'pos': tree.pos, 'radius': tree.trunk_radius, 'type': 'tree', 'ref': tree})
        def add_equipment(coll_list, character):
            for side, equip in character.equipment.items():
                if isinstance(equip, (Sword, Dagger)):
                    r = equip.length / 2
                    coll_list.append({'pos': equip.pos, 'radius': r, 'type': 'weapon', 'subtype': 'sword' if isinstance(equip, Sword) else 'dagger', 'ref': equip, 'owner': character})
                elif isinstance(equip, Shield):
                    r = max(equip.size) / 2
                    coll_list.append({'pos': equip.pos, 'radius': r, 'type': 'weapon', 'subtype': 'shield', 'ref': equip, 'owner': character})
        add_equipment(collidables, self.player)
        for enemy in self.enemies:
            add_equipment(collidables, enemy)
        
        for i in range(len(collidables)):
            for j in range(i+1, len(collidables)):
                a = collidables[i]
                b = collidables[j]
                diff = b['pos'] - a['pos']
                dist = diff.length()
                if dist == 0:
                    continue
                overlap = a['radius'] + b['radius'] - dist
                if overlap > 0:
                    if a['type'] == 'weapon' and b['type'] == 'weapon':
                        if (a.get('subtype') == 'shield' and b.get('subtype') in ['sword', 'dagger']) or \
                           (b.get('subtype') == 'shield' and a.get('subtype') in ['sword', 'dagger']):
                            if a.get('subtype') == 'shield':
                                shield_obj = a
                                sword_obj = b
                            else:
                                shield_obj = b
                                sword_obj = a
                            angle_between = math.atan2(sword_obj['pos'].y - shield_obj['pos'].y,
                                                       sword_obj['pos'].x - shield_obj['pos'].x)
                            sword_obj['ref'].angle = angle_between
                            owner = sword_obj.get('owner')
                            if owner:
                                owner.knockback += pygame.math.Vector2(math.cos(angle_between), math.sin(angle_between)) * 1
                            continue

                    movable_a = (a['type'] == 'character')
                    movable_b = (b['type'] == 'character')
                    if a['type'] == 'weapon' or b['type'] == 'weapon':
                        continue
                    push = diff.normalize() * (overlap + 0.1)
                    if movable_a and movable_b:
                        a['ref'].pos -= push / 2
                        b['ref'].pos += push / 2
                    elif movable_a and not movable_b:
                        a['ref'].pos -= push
                    elif movable_b and not movable_a:
                        b['ref'].pos += push

    def update(self):
        self.clock.tick(FPS)
        if not self.game_over:
            mouse_pos = pygame.mouse.get_pos()
            mouse_buttons = pygame.mouse.get_pressed()
            keys = pygame.key.get_pressed()

            self.player.handle_input(keys, mouse_pos, mouse_buttons)

            new_enemies = []
            for enemy in self.enemies:
                enemy.update(self.player)
                if enemy.health > 0:
                    new_enemies.append(enemy)
                else:
                    self.score += 1
            self.enemies = new_enemies

            for splatter in self.blood_splatters:
                splatter.update()
            self.blood_splatters = [s for s in self.blood_splatters if s.life > 0]

            self.enemy_spawn_timer += 1
            if self.enemy_spawn_timer > 300:
                self.spawn_enemy()
                self.enemy_spawn_timer = 0

            self.handle_collisions()
            self.resolve_all_collisions()

            if self.player.health <= 0:
                self.game_over = True
                if self.score > self.high_score:
                    self.high_score = self.score

    def render_ground(self):
        self.ground_layer.fill((50, 50, 50))
        for pos, radius, color in self.cobblestones:
            pygame.draw.circle(self.ground_layer, color, (int(pos.x), int(pos.y)), radius)

    def render_splatter(self):
        self.splatter_layer.fill((0, 0, 0, 0))
        for splatter in self.blood_splatters:
            splatter.render(self.splatter_layer)

    def render_objects(self):
        self.object_layer.fill((0, 0, 0, 0))
        for obstacle in self.obstacles:
            obstacle.render(self.object_layer)
        for tree in self.trees:
            tree.render_trunk(self.object_layer)
        self.player.render(self.object_layer)
        for enemy in self.enemies:
            enemy.render(self.object_layer)

    def render_roof(self):
        self.roof_layer.fill((0, 0, 0, 0))
        for tree in self.trees:
            tree.render_foliage(self.roof_layer, self.player)

    def render_ui(self):
        health_bar_width = 100
        health_bar_height = 10
        x = 20
        y = SCREEN_HEIGHT - 40
        pygame.draw.rect(self.screen, DARK_GREY, (x, y, health_bar_width, health_bar_height))
        current_width = health_bar_width * (self.player.health / 10)
        pygame.draw.rect(self.screen, GREEN, (x, y, current_width, health_bar_height))
        score_text = pygame.font.SysFont(None, 24).render(f"Score: {self.score}", True, WHITE)
        self.screen.blit(score_text, (SCREEN_WIDTH - 120, 20))

    def render_death_screen(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        font_big = pygame.font.SysFont(None, 72)
        font_small = pygame.font.SysFont(None, 36)
        game_over_text = font_big.render("GAME OVER", True, BLOOD_RED)
        score_text = font_small.render(f"Score: {self.score}", True, WHITE)
        high_score_text = font_small.render(f"High Score: {self.high_score}", True, WHITE)
        restart_text = font_small.render("Press R to Restart", True, WHITE)
        self.screen.blit(game_over_text, ((SCREEN_WIDTH - game_over_text.get_width()) // 2, SCREEN_HEIGHT//3))
        self.screen.blit(score_text, ((SCREEN_WIDTH - score_text.get_width()) // 2, SCREEN_HEIGHT//3 + 80))
        self.screen.blit(high_score_text, ((SCREEN_WIDTH - high_score_text.get_width()) // 2, SCREEN_HEIGHT//3 + 120))
        self.screen.blit(restart_text, ((SCREEN_WIDTH - restart_text.get_width()) // 2, SCREEN_HEIGHT//3 + 180))

    def reset(self):
        self.player = Player((SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2))
        self.enemies.clear()
        self.blood_splatters.clear()
        self.score = 0
        self.enemy_spawn_timer = 0
        self.game_over = False

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if self.game_over and event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        self.reset()

            self.update()

            self.render_ground()
            self.render_splatter()
            self.render_objects()
            self.render_roof()

            self.screen.blit(self.ground_layer, (0, 0))
            self.screen.blit(self.splatter_layer, (0, 0))
            self.screen.blit(self.object_layer, (0, 0))
            self.screen.blit(self.roof_layer, (0, 0))
            self.render_ui()

            if self.game_over:
                self.render_death_screen()

            pygame.display.flip()

        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()
