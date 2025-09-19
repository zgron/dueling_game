import pygame
import pymunk
import random
import math
from enum import Enum

# Initialize Pygame and Pymunk
pygame.init()
WIDTH, HEIGHT = 1280, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dueling Game")
clock = pygame.time.Clock()

# Pymunk space
space = pymunk.Space()
space.gravity = (0, 0)

# Colors
YELLOW = (255, 255, 0)
GREY = (100, 100, 100)
DARK_GREY = (50, 50, 50)
BROWN = (139, 69, 19)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Equipment Enum
class Equipment(Enum):
    SWORD = 1
    SHIELD = 2
    DAGGER = 3
    BARE_HAND = 4

# Game states
class GameState(Enum):
    MENU = 1
    EQUIPMENT = 2
    PLAYING = 3
    GAME_OVER = 4

# Base Character class
class Character:
    def __init__(self, x, y, is_player=False):
        self.body = pymunk.Body(1, 100)
        self.body.position = (x, y)  # Pymunk tuple
        self.shape = pymunk.Circle(self.body, 20)
        self.shape.elasticity = 0.5
        self.shape.friction = 0.9
        self.shape.collision_type = 1
        self.shape.data = self
        space.add(self.body, self.shape)
        
        self.is_player = is_player
        self.health = 5 if is_player else random.randint(1, 9)
        self.facing_angle = 0
        self.max_rotation_speed = math.radians(180)
        self.speed = 200
        
        self.left_arm = Arm(self, False)
        self.right_arm = Arm(self, True)
        self.left_equipment = Equipment.BARE_HAND
        self.right_equipment = Equipment.BARE_HAND
        
    def update(self, dt):
        if self.is_player:
            self.handle_player_input(dt)
        self.left_arm.update(dt)
        self.right_arm.update(dt)
        self.apply_rotation(dt)
        if self.health <= 0 and not self.is_player:
            game.splatters.append((int(self.body.position.x), int(self.body.position.y)))
        
    def handle_player_input(self, dt):
        keys = pygame.key.get_pressed()
        vel = pygame.math.Vector2(0, 0)
        if keys[pygame.K_w]: vel.y -= self.speed
        if keys[pygame.K_s]: vel.y += self.speed
        if keys[pygame.K_a]: vel.x -= self.speed
        if keys[pygame.K_d]: vel.x += self.speed
        if vel.length() > 0:
            vel = vel.normalize() * self.speed
        self.body.velocity = (vel.x, vel.y)  # Convert to tuple for Pymunk
        
        mouse_pos = pygame.mouse.get_pos()
        mouse_vec = pygame.math.Vector2(mouse_pos) - pygame.math.Vector2(self.body.position)
        target_angle = math.atan2(-mouse_vec.y, mouse_vec.x)
        
        mouse_buttons = pygame.mouse.get_pressed()
        if not (mouse_buttons[0] or mouse_buttons[2]):
            self.facing_angle = target_angle
        else:
            if mouse_buttons[0]:
                self.right_arm.target_angle = target_angle
                self.right_arm.is_extending = True
            if mouse_buttons[2]:
                self.left_arm.target_angle = target_angle
                self.left_arm.is_extending = True
                
    def apply_rotation(self, dt):
        angle_diff = (self.facing_angle - self.body.angle) % (2 * math.pi)
        if angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        rotation = max(-self.max_rotation_speed * dt, min(self.max_rotation_speed * dt, angle_diff))
        self.body.angle += rotation
        
    def draw(self, screen):
        pos = self.body.position
        pygame.draw.circle(screen, YELLOW, (int(pos.x), int(pos.y)), 20)
        self.left_arm.draw(screen)
        self.right_arm.draw(screen)
        font = pygame.font.SysFont(None, 24)
        text = font.render(str(self.health), True, WHITE)
        screen.blit(text, (int(pos.x) - 5, int(pos.y) - 5))

# Arm class
class Arm:
    def __init__(self, character, is_right):
        self.character = character
        self.is_right = is_right
        self.length = 20
        self.max_length = 60
        self.extension_speed = 300
        self.is_extending = False
        self.target_angle = 0
        self.angle = 0
        self.max_rotation_speed = math.radians(360)
        self.last_hit = None
        
    def update(self, dt):
        equipment = self.character.right_equipment if self.is_right else self.character.left_equipment
        if equipment == Equipment.DAGGER:
            self.extension_speed = 400
            self.max_length = 40
        elif equipment == Equipment.SWORD:
            self.extension_speed = 300
            self.max_length = 60
        elif equipment == Equipment.SHIELD:
            self.extension_speed = 250
            self.max_length = 50
        else:
            self.extension_speed = 500
            self.max_length = 30
            
        if self.is_extending:
            self.length = min(self.length + self.extension_speed * dt, self.max_length)
            self.check_collision()
        else:
            self.length = max(self.length - self.extension_speed * dt, 20)
            self.last_hit = None
            
        base_angle = self.character.body.angle
        rel_angle = (self.target_angle - base_angle) % (2 * math.pi)
        if rel_angle > math.pi:
            rel_angle -= 2 * math.pi
        rel_angle = max(math.radians(-45), min(math.radians(135), rel_angle))
        target = base_angle + rel_angle
        angle_diff = (target - self.angle) % (2 * math.pi)
        if angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        rotation = max(-self.max_rotation_speed * dt, min(self.max_rotation_speed * dt, angle_diff))
        self.angle += rotation
        
    def check_collision(self):
        pos = self.character.body.position
        shoulder_offset = 20 * math.cos(self.character.body.angle + (math.pi/2 if self.is_right else -math.pi/2)), \
                         -20 * math.sin(self.character.body.angle + (math.pi/2 if self.is_right else -math.pi/2))
        end_x = pos.x + shoulder_offset[0] + self.length * math.cos(self.angle)
        end_y = pos.y + shoulder_offset[1] - self.length * math.sin(self.angle)
        equipment = self.character.right_equipment if self.is_right else self.character.left_equipment
        
        for enemy in game.enemies + ([game.player] if not self.character.is_player else []):
            if enemy == self.character or enemy == self.last_hit:
                continue
            dist = pygame.math.Vector2(end_x, end_y).distance_to(enemy.body.position)
            if dist < 20:
                if equipment in (Equipment.SWORD, Equipment.DAGGER):
                    enemy.health -= 1
                    knockback = (pymunk.Vec2d(*enemy.body.position) - pymunk.Vec2d(*self.character.body.position)).normalized() * 300
                    enemy.body.apply_impulse_at_local_point((knockback.x, knockback.y))
                    self.last_hit = enemy
                elif equipment == Equipment.BARE_HAND:
                    enemy.health -= 1
                    knockback = (pymunk.Vec2d(*enemy.body.position) - pymunk.Vec2d(*self.character.body.position)).normalized() * 200
                    enemy.body.apply_impulse_at_local_point((knockback.x, knockback.y))
                    self.last_hit = enemy
                    
    def draw(self, screen):
        pos = self.character.body.position
        shoulder_x = pos.x + 20 * math.cos(self.character.body.angle + (math.pi/2 if self.is_right else -math.pi/2))
        shoulder_y = pos.y - 20 * math.sin(self.character.body.angle + (math.pi/2 if self.is_right else -math.pi/2))
        end_x = shoulder_x + self.length * math.cos(self.angle)
        end_y = shoulder_y - self.length * math.sin(self.angle)
        
        pygame.draw.rect(screen, GREY, (shoulder_x - 10, shoulder_y - 10, 20, self.length), 0)
        equipment = self.character.right_equipment if self.is_right else self.character.left_equipment
        if equipment == Equipment.SWORD:
            pygame.draw.rect(screen, GREY, (end_x, end_y - 5, 40, 10))
        elif equipment == Equipment.SHIELD:
            shield_angle = self.character.body.angle + math.pi/2
            pygame.draw.rect(screen, GREY, (end_x - 20 * math.cos(shield_angle), end_y + 20 * math.sin(shield_angle), 40, 10))
        elif equipment == Equipment.DAGGER:
            pygame.draw.rect(screen, GREY, (end_x, end_y - 5, 20, 10))

# Enemy class
class Enemy(Character):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.state = "circle"
        self.state_timer = random.uniform(1, 3)
        
    def update(self, dt):
        self.state_timer -= dt
        if self.state_timer <= 0:
            self.state = random.choice(["circle", "approach", "swing", "retreat"])
            self.state_timer = random.uniform(1, 3)
            
        player_pos = game.player.body.position
        vec_to_player = pymunk.Vec2d(*player_pos) - pymunk.Vec2d(*self.body.position)
        dist = vec_to_player.length
        
        if self.state == "circle":
            perp = pymunk.Vec2d(-vec_to_player.y, vec_to_player.x).normalized() * 150
            target_pos = pymunk.Vec2d(*player_pos) + perp
            move_vec = (target_pos - pymunk.Vec2d(*self.body.position)).normalized() * self.speed
            self.body.velocity = (move_vec.x, move_vec.y)
            self.facing_angle = math.atan2(-vec_to_player.y, vec_to_player.x)
        elif self.state == "approach":
            move_vec = vec_to_player.normalized() * self.speed
            self.body.velocity = (move_vec.x, move_vec.y)
            self.facing_angle = math.atan2(-vec_to_player.y, vec_to_player.x)
            if dist < 100:
                self.right_arm.is_extending = True
        elif self.state == "swing":
            self.body.velocity = (0, 0)
            self.facing_angle = math.atan2(-vec_to_player.y, vec_to_player.x)
            self.right_arm.target_angle = self.facing_angle
            self.right_arm.is_extending = True
        elif self.state == "retreat":
            move_vec = -vec_to_player.normalized() * self.speed
            self.body.velocity = (move_vec.x, move_vec.y)
            self.facing_angle = math.atan2(-vec_to_player.y, vec_to_player.x)
            
        super().update(dt)

# Game class
class Game:
    def __init__(self):
        self.state = GameState.MENU
        self.player = Character(WIDTH // 2, HEIGHT // 2, True)
        self.enemies = []
        self.objects = []
        self.splatters = []
        self.spawn_timer = 0
        self.score = 0
        
        for _ in range(10):
            rock = pymunk.Body(body_type=pymunk.Body.STATIC)
            rock.position = (random.randint(0, WIDTH), random.randint(0, HEIGHT))
            shape = pymunk.Circle(rock, 30)
            shape.collision_type = 2
            space.add(rock, shape)
            self.objects.append((rock, "rock"))
            
        for _ in range(5):
            tree = pymunk.Body(body_type=pymunk.Body.STATIC)
            tree.position = (random.randint(0, WIDTH), random.randint(0, HEIGHT))
            shape = pymunk.Circle(tree, 20)
            shape.collision_type = 2
            space.add(tree, shape)
            self.objects.append((tree, "tree"))
            
        campfire = pymunk.Body(body_type=pymunk.Body.STATIC)
        campfire.position = (WIDTH // 2, HEIGHT // 2 - 100)
        shape = pymunk.Circle(campfire, 30)
        shape.collision_type = 3
        space.add(campfire, shape)
        self.objects.append((campfire, "campfire"))
        
    def update(self, dt):
        if self.state == GameState.PLAYING:
            space.step(dt)
            self.player.update(dt)
            if self.player.health <= 0:
                self.state = GameState.GAME_OVER
                
            for enemy in self.enemies[:]:
                enemy.update(dt)
                if enemy.health <= 0:
                    self.enemies.remove(enemy)
                    space.remove(enemy.body, enemy.shape)
                    self.score += 1
                    
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self.spawn_enemy()
                self.spawn_timer = max(0.5, 2 - self.score * 0.05)
                
            handler = space.add_collision_handler(1, 1)
            handler.separate = self.character_collision
            handler = space.add_collision_handler(1, 3)
            handler.begin = self.campfire_collision
            
    def character_collision(self, arbiter, space, data):
        char1 = arbiter.shapes[0].data
        char2 = arbiter.shapes[1].data
        if char1 and char2:
            vec = pymunk.Vec2d(*char2.body.position) - pymunk.Vec2d(*char1.body.position)
            if vec.length > 0:
                force = vec.normalized() * 100
                char1.body.apply_impulse_at_local_point((-force.x, -force.y))
                char2.body.apply_impulse_at_local_point((force.x, force.y))
        return True
    
    def campfire_collision(self, arbiter, space, data):
        char = arbiter.shapes[0].data
        if char:
            char.health -= 1
            knockback = (pymunk.Vec2d(*char.body.position) - pymunk.Vec2d(*arbiter.shapes[1].body.position)).normalized() * 300
            char.body.apply_impulse_at_local_point((knockback.x, knockback.y))
        return True
    
    def spawn_enemy(self):
        side = random.choice(["left", "right", "top", "bottom"])
        if side == "left": x, y = 0, random.randint(0, HEIGHT)
        elif side == "right": x, y = WIDTH, random.randint(0, HEIGHT)
        elif side == "top": x, y = random.randint(0, WIDTH), 0
        else: x, y = random.randint(0, WIDTH), HEIGHT
        enemy = Enemy(x, y)
        eq = random.choice([Equipment.SWORD, Equipment.DAGGER])
        enemy.right_equipment = eq
        enemy.left_equipment = random.choice([Equipment.SHIELD, Equipment.BARE_HAND])
        self.enemies.append(enemy)
        
    def draw(self, screen):
        screen.fill((50, 50, 50))
        for x in range(0, WIDTH, 40):
            for y in range(0, HEIGHT, 40):
                pygame.draw.circle(screen, (random.randint(80, 120),) * 3, (x + 20, y + 20), 20)
                
        for splatter in self.splatters:
            pygame.draw.circle(screen, RED, splatter, 5)
            
        for obj, obj_type in self.objects:
            pos = obj.position
            if obj_type == "rock":
                pygame.draw.circle(screen, DARK_GREY, (int(pos.x), int(pos.y)), 30)
            elif obj_type == "campfire":
                pygame.draw.rect(screen, BROWN, (pos.x - 20, pos.y - 20, 40, 40))
                t = pygame.time.get_ticks() % 1000 / 1000
                pygame.draw.polygon(screen, RED, [(pos.x, pos.y - 20 - t * 10), (pos.x - 20, pos.y + 20), (pos.x + 20, pos.y + 20)])
                pygame.draw.polygon(screen, YELLOW, [(pos.x, pos.y - 10 - t * 5), (pos.x - 10, pos.y + 10), (pos.x + 10, pos.y + 10)])
                
        self.player.draw(screen)
        for enemy in self.enemies:
            enemy.draw(screen)
            
        for obj, obj_type in self.objects:
            if obj_type == "tree":
                pos = obj.position
                surf = pygame.Surface((60, 60), pygame.SRCALPHA)
                alpha = 255
                for char in [self.player] + self.enemies:
                    if (pymunk.Vec2d(*char.body.position) - pymunk.Vec2d(*pos)).length < 40:
                        alpha = 100
                        break
                pygame.draw.circle(surf, (*GREEN, alpha), (30, 30), 30)
                screen.blit(surf, (pos.x - 30, pos.y - 30))
                
        if self.state == GameState.MENU:
            font = pygame.font.SysFont(None, 48)
            text = font.render("Press SPACE to Play", True, WHITE)
            screen.blit(text, (WIDTH // 2 - 150, HEIGHT // 2))
            text = font.render("WASD to move, Mouse to aim, L/R click to attack", True, WHITE)
            screen.blit(text, (WIDTH // 2 - 300, HEIGHT // 2 + 50))
            
        elif self.state == GameState.EQUIPMENT:
            font = pygame.font.SysFont(None, 36)
            text = font.render("Choose Equipment (1-4): 1=Sword, 2=Shield, 3=Dagger, 4=Bare", True, WHITE)
            screen.blit(text, (WIDTH // 2 - 300, HEIGHT // 2 - 50))
            
        elif self.state == GameState.PLAYING:
            pygame.draw.rect(screen, RED, (10, HEIGHT - 30, 100, 20))
            pygame.draw.rect(screen, GREEN, (10, HEIGHT - 30, self.player.health * 20, 20))
            
        elif self.state == GameState.GAME_OVER:
            font = pygame.font.SysFont(None, 48)
            text = font.render(f"Score: {self.score} - Press any key to restart", True, WHITE)
            screen.blit(text, (WIDTH // 2 - 200, HEIGHT // 2))

# Main loop
game = Game()
running = True
dt = 1 / 60

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if game.state == GameState.MENU and event.key == pygame.K_SPACE:
                game.state = GameState.EQUIPMENT
            elif game.state == GameState.EQUIPMENT:
                if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    eq = {pygame.K_1: Equipment.SWORD, pygame.K_2: Equipment.SHIELD,
                          pygame.K_3: Equipment.DAGGER, pygame.K_4: Equipment.BARE_HAND}
                    if game.player.right_equipment == Equipment.BARE_HAND:
                        game.player.right_equipment = eq[event.key]
                    else:
                        game.player.left_equipment = eq[event.key]
                        game.state = GameState.PLAYING
            elif game.state == GameState.GAME_OVER:
                game = Game()
                
    game.update(dt)
    game.draw(screen)
    pygame.display.flip()
    dt = clock.tick(60) / 1000

pygame.quit()