import pygame
import math
import random
import time
from enum import Enum
from typing import List, Tuple, Optional, Dict, Any

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60

# Colors
YELLOW = (255, 255, 0)
GREY = (128, 128, 128)
DARK_GREY = (64, 64, 64)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BROWN = (139, 69, 19)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLOOD_RED = (139, 0, 0)

# Game settings
CHARACTER_RADIUS = 20
SHOULDER_SIZE = 8
ARM_WIDTH = 6
MAX_ARM_LENGTH = 40
MOVEMENT_SPEED = 2
BODY_ROTATION_SPEED = 0.05
ARM_ROTATION_SPEED = 0.08
MAX_HP = 9

class GameState(Enum):
    MENU = 1
    EQUIPMENT_SELECT = 2
    PLAYING = 3
    GAME_OVER = 4

class EquipmentType(Enum):
    NONE = 0
    SWORD = 1
    SHIELD = 2
    DAGGER = 3

class AIState(Enum):
    CIRCLING = 1
    APPROACHING = 2
    ATTACKING = 3
    RETREATING = 4
    TESTING_DISTANCE = 5

class Equipment:
    def __init__(self, eq_type: EquipmentType):
        self.type = eq_type
        self.extension_speed = self._get_extension_speed()
        
    def _get_extension_speed(self):
        speeds = {
            EquipmentType.NONE: 0.8,
            EquipmentType.SWORD: 0.3,
            EquipmentType.SHIELD: 0.4,
            EquipmentType.DAGGER: 0.6
        }
        return speeds.get(self.type, 0.3)

class Character:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.radius = CHARACTER_RADIUS
        self.angle = 0
        self.hp = MAX_HP
        self.max_hp = MAX_HP
        
        # Arms
        self.left_arm_extended = False
        self.right_arm_extended = False
        self.left_arm_length = SHOULDER_SIZE
        self.right_arm_length = SHOULDER_SIZE
        self.left_arm_angle = math.pi
        self.right_arm_angle = 0
        self.target_left_length = SHOULDER_SIZE
        self.target_right_length = SHOULDER_SIZE
        
        # Equipment
        self.left_equipment = Equipment(EquipmentType.NONE)
        self.right_equipment = Equipment(EquipmentType.NONE)
        
        # Physics
        self.velocity_x = 0
        self.velocity_y = 0
        self.knockback_factor = 0.8
        
        # Combat
        self.damage_cooldown = 0
        self.last_damage_time = 0
        
    def update(self, dt: float):
        # Update arm extensions
        self._update_arm_extension(dt)
        
        # Apply velocity
        self.x += self.velocity_x
        self.y += self.velocity_y
        
        # Apply friction
        self.velocity_x *= 0.9
        self.velocity_y *= 0.9
        
        # Update damage cooldown
        if self.damage_cooldown > 0:
            self.damage_cooldown -= dt
            
    def _update_arm_extension(self, dt: float):
        # Left arm
        if self.left_arm_extended:
            if self.left_arm_length < self.target_left_length:
                self.left_arm_length += self.left_equipment.extension_speed * dt * 60
                self.left_arm_length = min(self.left_arm_length, self.target_left_length)
        else:
            if self.left_arm_length > SHOULDER_SIZE:
                self.left_arm_length -= self.left_equipment.extension_speed * dt * 60
                self.left_arm_length = max(self.left_arm_length, SHOULDER_SIZE)
                
        # Right arm
        if self.right_arm_extended:
            if self.right_arm_length < self.target_right_length:
                self.right_arm_length += self.right_equipment.extension_speed * dt * 60
                self.right_arm_length = min(self.right_arm_length, self.target_right_length)
        else:
            if self.right_arm_length > SHOULDER_SIZE:
                self.right_arm_length -= self.right_equipment.extension_speed * dt * 60
                self.right_arm_length = max(self.right_arm_length, SHOULDER_SIZE)
    
    def extend_arm(self, left: bool, target_angle: float):
        if left:
            self.left_arm_extended = True
            self.target_left_length = MAX_ARM_LENGTH
            # Set initial angle toward target within limits
            relative_angle = target_angle - self.angle
            relative_angle = max(-math.pi/4, min(relative_angle, 3*math.pi/4))
            self.left_arm_angle = self.angle + relative_angle
        else:
            self.right_arm_extended = True
            self.target_right_length = MAX_ARM_LENGTH
            # Set initial angle toward target within limits
            relative_angle = target_angle - self.angle
            relative_angle = max(-3*math.pi/4, min(relative_angle, math.pi/4))
            self.right_arm_angle = self.angle + relative_angle
    
    def retract_arm(self, left: bool):
        if left:
            self.left_arm_extended = False
            self.target_left_length = SHOULDER_SIZE
        else:
            self.right_arm_extended = False
            self.target_right_length = SHOULDER_SIZE
    
    def update_arm_angle(self, left: bool, target_angle: float, dt: float):
        if left and self.left_arm_extended:
            # Apply rotation limits
            relative_angle = target_angle - self.angle
            relative_angle = max(-math.pi/4, min(relative_angle, 3*math.pi/4))
            target = self.angle + relative_angle
            
            angle_diff = target - self.left_arm_angle
            if abs(angle_diff) > math.pi:
                angle_diff = angle_diff - 2*math.pi if angle_diff > 0 else angle_diff + 2*math.pi
            
            self.left_arm_angle += max(-ARM_ROTATION_SPEED, min(ARM_ROTATION_SPEED, angle_diff))
            
        elif not left and self.right_arm_extended:
            # Apply rotation limits
            relative_angle = target_angle - self.angle
            relative_angle = max(-3*math.pi/4, min(relative_angle, math.pi/4))
            target = self.angle + relative_angle
            
            angle_diff = target - self.right_arm_angle
            if abs(angle_diff) > math.pi:
                angle_diff = angle_diff - 2*math.pi if angle_diff > 0 else angle_diff + 2*math.pi
            
            self.right_arm_angle += max(-ARM_ROTATION_SPEED, min(ARM_ROTATION_SPEED, angle_diff))
    
    def get_hand_position(self, left: bool) -> Tuple[float, float]:
        if left:
            hand_x = self.x + math.cos(self.left_arm_angle) * self.left_arm_length
            hand_y = self.y + math.sin(self.left_arm_angle) * self.left_arm_length
        else:
            hand_x = self.x + math.cos(self.right_arm_angle) * self.right_arm_length
            hand_y = self.y + math.sin(self.right_arm_angle) * self.right_arm_length
        return hand_x, hand_y
    
    def apply_knockback(self, angle: float, force: float):
        self.velocity_x += math.cos(angle) * force
        self.velocity_y += math.sin(angle) * force
    
    def take_damage(self, amount: int, attacker_pos: Tuple[float, float]):
        if self.damage_cooldown <= 0:
            self.hp -= amount
            self.damage_cooldown = 0.5  # Damage immunity frames
            
            # Apply knockback away from attacker
            dx = self.x - attacker_pos[0]
            dy = self.y - attacker_pos[1]
            distance = math.sqrt(dx*dx + dy*dy)
            if distance > 0:
                knockback_angle = math.atan2(dy, dx)
                self.apply_knockback(knockback_angle, 5.0)
    
    def get_collision_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x - self.radius, self.y - self.radius, 
                          self.radius * 2, self.radius * 2)

class Player(Character):
    def __init__(self, x: float, y: float):
        super().__init__(x, y)
        self.kills = 0
        
    def update(self, dt: float, mouse_pos: Tuple[int, int], mouse_buttons: Tuple[bool, bool, bool]):
        super().update(dt)
        
        # Face cursor when not attacking
        if not (mouse_buttons[0] or mouse_buttons[2]):
            target_angle = math.atan2(mouse_pos[1] - self.y, mouse_pos[0] - self.x)
            angle_diff = target_angle - self.angle
            if abs(angle_diff) > math.pi:
                angle_diff = angle_diff - 2*math.pi if angle_diff > 0 else angle_diff + 2*math.pi
            self.angle += max(-BODY_ROTATION_SPEED, min(BODY_ROTATION_SPEED, angle_diff))
        
        # Handle arm extensions
        cursor_angle = math.atan2(mouse_pos[1] - self.y, mouse_pos[0] - self.x)
        
        if mouse_buttons[0]:  # Left click - right arm
            if not self.right_arm_extended:
                self.extend_arm(False, cursor_angle)
            self.update_arm_angle(False, cursor_angle, dt)
        else:
            self.retract_arm(False)
            
        if mouse_buttons[2]:  # Right click - left arm
            if not self.left_arm_extended:
                self.extend_arm(True, cursor_angle)
            self.update_arm_angle(True, cursor_angle, dt)
        else:
            self.retract_arm(True)

class Enemy(Character):
    def __init__(self, x: float, y: float):
        super().__init__(x, y)
        self.ai_state = AIState.CIRCLING
        self.state_timer = 0
        self.circle_angle = random.uniform(0, 2*math.pi)
        self.circle_radius = random.uniform(80, 120)
        self.attack_cooldown = 0
        self.retreat_timer = 0
        
        # Random equipment
        self._equip_random()
        
    def _equip_random(self):
        weapons = [EquipmentType.SWORD, EquipmentType.DAGGER, EquipmentType.NONE]
        left_eq = random.choice(weapons)
        
        # Ensure at least one weapon and never two shields
        if left_eq == EquipmentType.NONE:
            right_eq = random.choice([EquipmentType.SWORD, EquipmentType.DAGGER])
        else:
            right_eq = random.choice([EquipmentType.SWORD, EquipmentType.DAGGER, EquipmentType.SHIELD, EquipmentType.NONE])
            
        self.left_equipment = Equipment(left_eq)
        self.right_equipment = Equipment(right_eq)
        
    def update(self, dt: float, player: Player, obstacles: List[Any]):
        super().update(dt)
        
        distance_to_player = math.sqrt((self.x - player.x)**2 + (self.y - player.y)**2)
        
        self.state_timer += dt
        self.attack_cooldown -= dt
        
        # State machine
        if self.ai_state == AIState.CIRCLING:
            self._circle_player(dt, player)
            if distance_to_player < 60 and random.random() < 0.01:
                self.ai_state = AIState.APPROACHING
                self.state_timer = 0
                
        elif self.ai_state == AIState.APPROACHING:
            self._approach_player(dt, player)
            if distance_to_player < 35:
                self.ai_state = AIState.ATTACKING
                self.state_timer = 0
            elif self.state_timer > 3:
                self.ai_state = AIState.CIRCLING
                self.state_timer = 0
                
        elif self.ai_state == AIState.ATTACKING:
            self._attack_player(dt, player)
            if distance_to_player > 80 or self.state_timer > 2:
                self.ai_state = AIState.CIRCLING if random.random() < 0.7 else AIState.RETREATING
                self.state_timer = 0
                
        elif self.ai_state == AIState.RETREATING:
            self._retreat_from_player(dt, player)
            if distance_to_player > 100 or self.state_timer > 1.5:
                self.ai_state = AIState.CIRCLING
                self.state_timer = 0
                
        # Face player
        target_angle = math.atan2(player.y - self.y, player.x - self.x)
        angle_diff = target_angle - self.angle
        if abs(angle_diff) > math.pi:
            angle_diff = angle_diff - 2*math.pi if angle_diff > 0 else angle_diff + 2*math.pi
        self.angle += max(-BODY_ROTATION_SPEED, min(BODY_ROTATION_SPEED, angle_diff))
        
    def _circle_player(self, dt: float, player: Player):
        self.circle_angle += 0.01
        target_x = player.x + math.cos(self.circle_angle) * self.circle_radius
        target_y = player.y + math.sin(self.circle_angle) * self.circle_radius
        
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance > 5:
            self.x += (dx / distance) * MOVEMENT_SPEED * 0.7
            self.y += (dy / distance) * MOVEMENT_SPEED * 0.7
            
    def _approach_player(self, dt: float, player: Player):
        dx = player.x - self.x
        dy = player.y - self.y
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance > 0:
            self.x += (dx / distance) * MOVEMENT_SPEED * 0.8
            self.y += (dy / distance) * MOVEMENT_SPEED * 0.8
            
    def _attack_player(self, dt: float, player: Player):
        if self.attack_cooldown <= 0:
            # Extend arms toward player
            player_angle = math.atan2(player.y - self.y, player.x - self.x)
            
            if not self.left_arm_extended and self.left_equipment.type != EquipmentType.SHIELD:
                self.extend_arm(True, player_angle)
                self.attack_cooldown = 1.0
                
            if not self.right_arm_extended and self.right_equipment.type != EquipmentType.SHIELD:
                self.extend_arm(False, player_angle)
                self.attack_cooldown = 1.0
        else:
            # Retract after attack
            if self.attack_cooldown < 0.5:
                self.retract_arm(True)
                self.retract_arm(False)
                
    def _retreat_from_player(self, dt: float, player: Player):
        dx = self.x - player.x
        dy = self.y - player.y
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance > 0:
            self.x += (dx / distance) * MOVEMENT_SPEED
            self.y += (dy / distance) * MOVEMENT_SPEED

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Top-Down Combat Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        self.state = GameState.MENU
        self.player = None
        self.enemies = []
        self.obstacles = []
        self.blood_splatters = []
        self.campfire = None
        
        # Equipment selection
        self.selected_left = EquipmentType.SWORD
        self.selected_right = EquipmentType.SHIELD
        
        # Game stats
        self.game_time = 0
        self.spawn_timer = 0
        self.highscore = 0
        
        self._generate_environment()
        
    def _generate_environment(self):
        # Generate obstacles (rocks)
        for _ in range(15):
            x = random.randint(50, SCREEN_WIDTH - 50)
            y = random.randint(50, SCREEN_HEIGHT - 50)
            size = random.randint(15, 25)
            self.obstacles.append({'x': x, 'y': y, 'size': size, 'type': 'rock'})
            
        # Generate trees
        for _ in range(10):
            x = random.randint(50, SCREEN_WIDTH - 50)
            y = random.randint(50, SCREEN_HEIGHT - 50)
            self.obstacles.append({'x': x, 'y': y, 'size': 30, 'type': 'tree'})
            
        # Place campfire
        self.campfire = {'x': SCREEN_WIDTH // 2, 'y': SCREEN_HEIGHT // 2, 'bob_offset': 0}
        
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if self.state == GameState.GAME_OVER:
                        self.state = GameState.MENU
                        
            if self.state == GameState.MENU:
                self._handle_menu(pygame.mouse.get_pressed(), pygame.mouse.get_pos())
            elif self.state == GameState.EQUIPMENT_SELECT:
                self._handle_equipment_select(pygame.mouse.get_pressed(), pygame.mouse.get_pos())
            elif self.state == GameState.PLAYING:
                self._update_game(dt)
            elif self.state == GameState.GAME_OVER:
                pass
                
            self._render()
            
        pygame.quit()
        
    def _handle_menu(self, mouse_buttons, mouse_pos):
        if mouse_buttons[0]:  # Left click
            # Check if clicked on play button area
            if SCREEN_WIDTH//2 - 100 < mouse_pos[0] < SCREEN_WIDTH//2 + 100 and \
               SCREEN_HEIGHT//2 < mouse_pos[1] < SCREEN_HEIGHT//2 + 50:
                self.state = GameState.EQUIPMENT_SELECT
                
    def _handle_equipment_select(self, mouse_buttons, mouse_pos):
        if mouse_buttons[0]:
            # Left hand equipment selection
            for i, eq_type in enumerate([EquipmentType.SWORD, EquipmentType.DAGGER, EquipmentType.NONE]):
                button_x = 200 + i * 120
                button_y = 300
                if button_x < mouse_pos[0] < button_x + 100 and button_y < mouse_pos[1] < button_y + 50:
                    self.selected_left = eq_type
                    
            # Right hand equipment selection
            for i, eq_type in enumerate([EquipmentType.SWORD, EquipmentType.DAGGER, EquipmentType.SHIELD, EquipmentType.NONE]):
                button_x = 200 + i * 120
                button_y = 450
                if button_x < mouse_pos[0] < button_x + 100 and button_y < mouse_pos[1] < button_y + 50:
                    self.selected_right = eq_type
                    
            # Start game button
            if SCREEN_WIDTH//2 - 100 < mouse_pos[0] < SCREEN_WIDTH//2 + 100 and \
               600 < mouse_pos[1] < 650:
                self._start_game()
                
    def _start_game(self):
        self.state = GameState.PLAYING
        self.player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.player.left_equipment = Equipment(self.selected_left)
        self.player.right_equipment = Equipment(self.selected_right)
        self.enemies = []
        self.blood_splatters = []
        self.game_time = 0
        self.spawn_timer = 0
        
    def _update_game(self, dt):
        self.game_time += dt
        self.spawn_timer += dt
        
        # Update player
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            self.player.y -= MOVEMENT_SPEED
        if keys[pygame.K_s]:
            self.player.y += MOVEMENT_SPEED
        if keys[pygame.K_a]:
            self.player.x -= MOVEMENT_SPEED
        if keys[pygame.K_d]:
            self.player.x += MOVEMENT_SPEED
            
        # Keep player in bounds
        self.player.x = max(self.player.radius, min(SCREEN_WIDTH - self.player.radius, self.player.x))
        self.player.y = max(self.player.radius, min(SCREEN_HEIGHT - self.player.radius, self.player.y))
        
        mouse_pos = pygame.mouse.get_pos()
        mouse_buttons = pygame.mouse.get_pressed()
        self.player.update(dt, mouse_pos, mouse_buttons)
        
        # Update enemies
        for enemy in self.enemies[:]:
            enemy.update(dt, self.player, self.obstacles)
            if enemy.hp <= 0:
                self.enemies.remove(enemy)
                self.player.kills += 1
                # Add blood splatter
                self.blood_splatters.append({
                    'x': enemy.x, 'y': enemy.y, 'time': 0, 'max_time': 10
                })
                
        # Spawn enemies
        spawn_rate = max(0.5, 3 - self.game_time * 0.1)
        if self.spawn_timer > spawn_rate and len(self.enemies) < 3:
            self._spawn_enemy()
            self.spawn_timer = 0
            
        # Check collisions
        self._handle_collisions()
        
        # Update campfire
        self.campfire['bob_offset'] = math.sin(self.game_time * 3) * 5
        
        # Check campfire damage
        campfire_dist = math.sqrt((self.player.x - self.campfire['x'])**2 + 
                                 (self.player.y - self.campfire['y'])**2)
        if campfire_dist < 25:
            self.player.take_damage(1, (self.campfire['x'], self.campfire['y']))
            
        # Update blood splatters
        for splatter in self.blood_splatters[:]:
            splatter['time'] += dt
            if splatter['time'] > splatter['max_time']:
                self.blood_splatters.remove(splatter)
                
        # Check game over
        if self.player.hp <= 0:
            self.highscore = max(self.highscore, self.player.kills)
            self.state = GameState.GAME_OVER
            
    def _spawn_enemy(self):
        # Spawn from edge of screen
        side = random.randint(0, 3)
        if side == 0:  # Top
            x = random.randint(0, SCREEN_WIDTH)
            y = -50
        elif side == 1:  # Right
            x = SCREEN_WIDTH + 50
            y = random.randint(0, SCREEN_HEIGHT)
        elif side == 2:  # Bottom
            x = random.randint(0, SCREEN_WIDTH)
            y = SCREEN_HEIGHT + 50
        else:  # Left
            x = -50
            y = random.randint(0, SCREEN_HEIGHT)
            
        enemy = Enemy(x, y)
        self.enemies.append(enemy)
        
    def _handle_collisions(self):
        # Character vs character collisions
        all_chars = [self.player] + self.enemies
        
        for i, char1 in enumerate(all_chars):
            for char2 in all_chars[i+1:]:
                distance = math.sqrt((char1.x - char2.x)**2 + (char1.y - char2.y)**2)
                if distance < char1.radius + char2.radius:
                    # Apply separation
                    angle = math.atan2(char2.y - char1.y, char2.x - char1.x)
                    overlap = (char1.radius + char2.radius) - distance
                    
                    char1.x -= math.cos(angle) * overlap * 0.5
                    char1.y -= math.sin(angle) * overlap * 0.5
                    char2.x += math.cos(angle) * overlap * 0.5
                    char2.y += math.sin(angle) * overlap * 0.5
                    
        # Weapon vs character collisions
        for char in all_chars:
            for other in all_chars:
                if char == other:
                    continue
                    
                # Check weapon collisions
                self._check_weapon_collision(char, other, True)  # Left hand
                self._check_weapon_collision(char, other, False)  # Right hand
                
    def _check_weapon_collision(self, attacker, target, left_hand):
        equipment = attacker.left_equipment if left_hand else attacker.right_equipment
        arm_extended = attacker.left_arm_extended if left_hand else attacker.right_arm_extended
        
        if not arm_extended or equipment.type not in [EquipmentType.SWORD, EquipmentType.DAGGER, EquipmentType.NONE]:
            return
            
        hand_x, hand_y = attacker.get_hand_position(left_hand)
        distance = math.sqrt((hand_x - target.x)**2 + (hand_y - target.y)**2)
        
        weapon_reach = 30 if equipment.type == EquipmentType.SWORD else 20 if equipment.type == EquipmentType.DAGGER else 5
        
        if distance < target.radius + weapon_reach:
            damage = 1
            target.take_damage(damage, (attacker.x, attacker.y))
            
            # Add blood splatter
            self.blood_splatters.append({
                'x': target.x + random.uniform(-10, 10),
                'y': target.y + random.uniform(-10, 10),
                'time': 0, 'max_time': 5
            })
    
    def _render(self):
        self.screen.fill(BLACK)
        
        if self.state == GameState.MENU:
            self._render_menu()
        elif self.state == GameState.EQUIPMENT_SELECT:
            self._render_equipment_select()
        elif self.state == GameState.PLAYING:
            self._render_game()
        elif self.state == GameState.GAME_OVER:
            self._render_game_over()
            
        pygame.display.flip()
        
    def _render_menu(self):
        title = self.font.render("Top-Down Combat Game", True, WHITE)
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 200))
        
        instructions = [
            "WASD to move",
            "Left/Right mouse to attack with respective hands",
            "Face cursor when not attacking",
            "Avoid campfire and enemy weapons",
            "Survive as long as possible!"
        ]
        
        for i, instruction in enumerate(instructions):
            text = self.small_font.render(instruction, True, WHITE)
            self.screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, 300 + i * 30))
            
        play_button = pygame.Rect(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2, 200, 50)
        pygame.draw.rect(self.screen, GREY, play_button)
        play_text = self.font.render("PLAY", True, BLACK)
        self.screen.blit(play_text, (play_button.centerx - play_text.get_width()//2,
                                   play_button.centery - play_text.get_height()//2))
        
    def _render_equipment_select(self):
        title = self.font.render("Select Equipment", True, WHITE)
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 100))
        
        # Left hand selection
        left_text = self.font.render("Left Hand:", True, WHITE)
        self.screen.blit(left_text, (50, 250))
        
        left_options = [EquipmentType.SWORD, EquipmentType.DAGGER, EquipmentType.NONE]
        left_names = ["Sword", "Dagger", "Bare Hand"]
        
        for i, (eq_type, name) in enumerate(zip(left_options, left_names)):
            button_x = 200 + i * 120
            button_y = 300
            color = GREEN if eq_type == self.selected_left else GREY
            button = pygame.Rect(button_x, button_y, 100, 50)
            pygame.draw.rect(self.screen, color, button)
            text = self.small_font.render(name, True, BLACK)
            self.screen.blit(text, (button.centerx - text.get_width()//2,
                                  button.centery - text.get_height()//2))
        
        # Right hand selection
        right_text = self.font.render("Right Hand:", True, WHITE)
        self.screen.blit(right_text, (50, 400))
        
        right_options = [EquipmentType.SWORD, EquipmentType.DAGGER, EquipmentType.SHIELD, EquipmentType.NONE]
        right_names = ["Sword", "Dagger", "Shield", "Bare Hand"]
        
        for i, (eq_type, name) in enumerate(zip(right_options, right_names)):
            button_x = 200 + i * 120
            button_y = 450
            color = GREEN if eq_type == self.selected_right else GREY
            button = pygame.Rect(button_x, button_y, 100, 50)
            pygame.draw.rect(self.screen, color, button)
            text = self.small_font.render(name, True, BLACK)
            self.screen.blit(text, (button.centerx - text.get_width()//2,
                                  button.centery - text.get_height()//2))
        
        # Start button
        start_button = pygame.Rect(SCREEN_WIDTH//2 - 100, 600, 200, 50)
        pygame.draw.rect(self.screen, GREY, start_button)
        start_text = self.font.render("START GAME", True, BLACK)
        self.screen.blit(start_text, (start_button.centerx - start_text.get_width()//2,
                                    start_button.centery - start_text.get_height()//2))
        
    def _render_game(self):
        # Ground layer - cobblestone
        for x in range(0, SCREEN_WIDTH, 40):
            for y in range(0, SCREEN_HEIGHT, 40):
                shade = random.randint(100, 140)
                color = (shade, shade, shade)
                pygame.draw.circle(self.screen, color, (x + 20, y + 20), 15)
        
        # Splatter layer - blood
        for splatter in self.blood_splatters:
            alpha = max(0, 255 - int(splatter['time'] * 50))
            color = (*BLOOD_RED, alpha)
            size = max(1, 8 - int(splatter['time']))
            pygame.draw.circle(self.screen, BLOOD_RED, 
                             (int(splatter['x']), int(splatter['y'])), size)
        
        # Campfire
        campfire_x = int(self.campfire['x'])
        campfire_y = int(self.campfire['y'])
        
        # Base
        pygame.draw.rect(self.screen, BROWN, 
                        (campfire_x - 15, campfire_y - 10, 30, 20))
        
        # Fire triangles with bobbing
        bob = self.campfire['bob_offset']
        fire_points_red = [
            (campfire_x, campfire_y - 20 + bob),
            (campfire_x - 10, campfire_y),
            (campfire_x + 10, campfire_y)
        ]
        fire_points_yellow = [
            (campfire_x, campfire_y - 15 + bob),
            (campfire_x - 5, campfire_y),
            (campfire_x + 5, campfire_y)
        ]
        
        pygame.draw.polygon(self.screen, RED, fire_points_red)
        pygame.draw.polygon(self.screen, YELLOW, fire_points_yellow)
        
        # Object layer
        # Rocks
        for obstacle in self.obstacles:
            if obstacle['type'] == 'rock':
                pygame.draw.circle(self.screen, DARK_GREY, 
                                 (int(obstacle['x']), int(obstacle['y'])), 
                                 obstacle['size'])
        
        # Characters
        all_chars = [self.player] + self.enemies
        for char in all_chars:
            self._render_character(char)
        
        # Roof layer - trees with transparency
        for obstacle in self.obstacles:
            if obstacle['type'] == 'tree':
                # Check if any character is under this tree
                transparency = 255
                for char in all_chars:
                    distance = math.sqrt((char.x - obstacle['x'])**2 + (char.y - obstacle['y'])**2)
                    if distance < obstacle['size']:
                        transparency = 100
                        break
                
                # Tree trunk
                trunk_color = (*BROWN, min(255, transparency))
                pygame.draw.circle(self.screen, BROWN, 
                                 (int(obstacle['x']), int(obstacle['y'])), 8)
                
                # Foliage
                foliage_color = (*GREEN, min(255, transparency))
                pygame.draw.circle(self.screen, GREEN, 
                                 (int(obstacle['x']), int(obstacle['y']) - 5), 
                                 obstacle['size'])
        
        # UI
        self._render_ui()
    
    def _render_character(self, char):
        # Main body circle
        pygame.draw.circle(self.screen, YELLOW, (int(char.x), int(char.y)), char.radius)
        
        # Direction indicator (small line)
        end_x = char.x + math.cos(char.angle) * (char.radius + 5)
        end_y = char.y + math.sin(char.angle) * (char.radius + 5)
        pygame.draw.line(self.screen, BLACK, (char.x, char.y), (end_x, end_y), 2)
        
        # Arms/shoulders
        self._render_arm(char, True)  # Left arm
        self._render_arm(char, False)  # Right arm
        
        # Health display for enemies
        if isinstance(char, Enemy):
            health_text = self.small_font.render(str(char.hp), True, RED)
            self.screen.blit(health_text, (char.x - health_text.get_width()//2, 
                                         char.y - health_text.get_height()//2))
    
    def _render_arm(self, char, left):
        if left:
            arm_angle = char.left_arm_angle
            arm_length = char.left_arm_length
            equipment = char.left_equipment
        else:
            arm_angle = char.right_arm_angle
            arm_length = char.right_arm_length
            equipment = char.right_equipment
        
        # Arm rectangle
        arm_end_x = char.x + math.cos(arm_angle) * arm_length
        arm_end_y = char.y + math.sin(arm_angle) * arm_length
        
        # Draw arm as thick line
        pygame.draw.line(self.screen, YELLOW, (char.x, char.y), 
                        (arm_end_x, arm_end_y), ARM_WIDTH)
        
        # Hand position
        hand_x, hand_y = char.get_hand_position(left)
        
        # Equipment rendering
        if equipment.type == EquipmentType.SWORD:
            # Sword extends from hand
            sword_length = 25
            sword_end_x = hand_x + math.cos(arm_angle) * sword_length
            sword_end_y = hand_y + math.sin(arm_angle) * sword_length
            pygame.draw.line(self.screen, GREY, (hand_x, hand_y), 
                           (sword_end_x, sword_end_y), 4)
            
        elif equipment.type == EquipmentType.DAGGER:
            # Shorter dagger
            dagger_length = 15
            dagger_end_x = hand_x + math.cos(arm_angle) * dagger_length
            dagger_end_y = hand_y + math.sin(arm_angle) * dagger_length
            pygame.draw.line(self.screen, GREY, (hand_x, hand_y), 
                           (dagger_end_x, dagger_end_y), 3)
            
        elif equipment.type == EquipmentType.SHIELD:
            # Shield tangent to body
            shield_angle = math.atan2(hand_y - char.y, hand_x - char.x) + math.pi/2
            shield_size = 15
            
            shield_points = []
            for i in range(4):
                angle = shield_angle + (i * math.pi/2)
                px = hand_x + math.cos(angle) * shield_size
                py = hand_y + math.sin(angle) * shield_size
                shield_points.append((px, py))
            
            pygame.draw.polygon(self.screen, GREY, shield_points)
    
    def _render_ui(self):
        # Player health bar
        bar_width = 200
        bar_height = 20
        bar_x = 20
        bar_y = SCREEN_HEIGHT - 40
        
        # Background
        pygame.draw.rect(self.screen, DARK_GREY, (bar_x, bar_y, bar_width, bar_height))
        
        # Health bar
        health_ratio = self.player.hp / self.player.max_hp
        health_width = int(bar_width * health_ratio)
        color = GREEN if health_ratio > 0.5 else YELLOW if health_ratio > 0.25 else RED
        pygame.draw.rect(self.screen, color, (bar_x, bar_y, health_width, bar_height))
        
        # Health text
        health_text = self.small_font.render(f"HP: {self.player.hp}/{self.player.max_hp}", 
                                           True, WHITE)
        self.screen.blit(health_text, (bar_x, bar_y - 25))
        
        # Kills counter
        kills_text = self.small_font.render(f"Kills: {self.player.kills}", True, WHITE)
        self.screen.blit(kills_text, (SCREEN_WIDTH - kills_text.get_width() - 20, 20))
        
        # Game time
        time_text = self.small_font.render(f"Time: {int(self.game_time)}s", True, WHITE)
        self.screen.blit(time_text, (SCREEN_WIDTH - time_text.get_width() - 20, 50))
    
    def _render_game_over(self):
        # Darken screen
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))
        
        # Game over text
        game_over_text = self.font.render("GAME OVER", True, RED)
        self.screen.blit(game_over_text, (SCREEN_WIDTH//2 - game_over_text.get_width()//2, 200))
        
        # Final stats
        kills_text = self.font.render(f"Final Kills: {self.player.kills}", True, WHITE)
        self.screen.blit(kills_text, (SCREEN_WIDTH//2 - kills_text.get_width()//2, 300))
        
        survival_text = self.font.render(f"Survival Time: {int(self.game_time)}s", True, WHITE)
        self.screen.blit(survival_text, (SCREEN_WIDTH//2 - survival_text.get_width()//2, 350))
        
        highscore_text = self.font.render(f"High Score: {self.highscore}", True, YELLOW)
        self.screen.blit(highscore_text, (SCREEN_WIDTH//2 - highscore_text.get_width()//2, 400))
        
        # Continue instruction
        continue_text = self.small_font.render("Press any key to return to menu", True, WHITE)
        self.screen.blit(continue_text, (SCREEN_WIDTH//2 - continue_text.get_width()//2, 500))

if __name__ == "__main__":
    game = Game()
    game.run()