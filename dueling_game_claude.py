import pygame
import sys
import math
import random

# Initialize pygame
pygame.init()

# Constants
WINDOW_WIDTH, WINDOW_HEIGHT = 800, 600
FPS = 60
YELLOW = (255, 255, 0)
GREY = (150, 150, 150)
DARK_GREY = (80, 80, 80)
BROWN = (139, 69, 19)
GREEN = (34, 139, 34)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BLOOD_RED = (200, 0, 0)

# Game window
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Top-Down Battle Game")
clock = pygame.time.Clock()

# Game state
game_state = "menu"  # Can be "menu", "equipment_select", "game", "game_over"
highscore = 0
kills = 0
game_time = 0

# Fonts
font_small = pygame.font.SysFont("Arial", 16)
font_medium = pygame.font.SysFont("Arial", 24)
font_large = pygame.font.SysFont("Arial", 36)

# Equipment options
EQUIPMENT_TYPES = ["sword", "shield", "dagger", "bare_hand"]

# Layer groups for rendering order
ground_layer = pygame.sprite.Group()
splatter_layer = pygame.sprite.Group()
object_layer = pygame.sprite.Group()
effect_layer = pygame.sprite.Group()  # For visual effects
roof_layer = pygame.sprite.Group()

# Collision groups
characters = pygame.sprite.Group()
obstacles = pygame.sprite.Group()
weapons = pygame.sprite.Group()

class BlockEffect(pygame.sprite.Sprite):
    def __init__(self, position):
        super().__init__()
        self.position = position
        self.radius = 15
        self.lifetime = 0.3  # in seconds
        self.timer = self.lifetime
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=position)
        effect_layer.add(self)
        
    def update(self):
        self.timer -= 1/FPS
        if self.timer <= 0:
            self.kill()
            
    def draw(self, surface):
        # Draw block effect (circular flash)
        progress = self.timer / self.lifetime
        radius = self.radius * (2 - progress)
        alpha = int(255 * progress)
        color = (255, 255, 255, alpha)
        
        effect_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(effect_surface, color, (radius, radius), radius)
        
        surface.blit(effect_surface, 
                    (self.position[0] - radius, 
                     self.position[1] - radius))

class Entity(pygame.sprite.Sprite):
    def __init__(self, x, y, radius):
        super().__init__()
        self.x = x
        self.y = y
        self.radius = radius
        self.image = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.velocity = pygame.math.Vector2(0, 0)
        self.body_rotation = 0
        self.body_rotation_speed = 3
        self.knockback_force = pygame.math.Vector2(0, 0)
        
    def update(self):
        # Apply knockback
        if self.knockback_force.length() > 0:
            self.velocity += self.knockback_force
            self.knockback_force *= 0.9
            if self.knockback_force.length() < 0.1:
                self.knockback_force = pygame.math.Vector2(0, 0)
                
        # Apply velocity
        self.x += self.velocity.x
        self.y += self.velocity.y
        
        # Update rect position
        self.rect.center = (self.x, self.y)
        
        # Friction
        self.velocity *= 0.9
        
    def apply_knockback(self, force):
        self.knockback_force += force
        
    def draw(self, surface):
        pass  # Override in subclasses

class Arm:
    def __init__(self, character, side):
        self.character = character
        self.side = side  # "left" or "right"
        self.shoulder_size = 10
        self.arm_length = 0
        self.max_arm_length = 30
        self.extension_speed = 3
        self.is_extending = False
        self.is_retracting = False
        self.angle = 0
        self.min_angle = -45
        self.max_angle = 135
        self.rotation_speed = 5
        self.equipment = None
        self.hand_position = pygame.math.Vector2(0, 0)
        self.should_extend = False  # Flag to track if arm should be extending
        
        # Shield block animation
        self.is_blocked = False
        self.block_rotation_target = 0
        self.block_rotation_speed = 3
        
    def update(self, target_angle=None):
        # Handle shield block animation
        if self.is_blocked:
            # Smoothly rotate toward blocked position
            angle_diff = self.block_rotation_target - self.angle
            if abs(angle_diff) > self.block_rotation_speed:
                self.angle += self.block_rotation_speed * (1 if angle_diff > 0 else -1)
            else:
                self.angle = self.block_rotation_target
                self.is_blocked = False
        # Normal arm targeting when not blocked
        elif target_angle is not None:
            # Calculate target angle within limits
            relative_angle = (target_angle - self.character.body_rotation) % 360
            if relative_angle > 180:
                relative_angle -= 360
                
            target_rel_angle = max(self.min_angle, min(self.max_angle, relative_angle))
            
            # Smoothly rotate arm
            angle_diff = target_rel_angle - self.angle
            if abs(angle_diff) > self.rotation_speed:
                self.angle += self.rotation_speed * (1 if angle_diff > 0 else -1)
            else:
                self.angle = target_rel_angle
        
        # Update arm extension
        if self.should_extend and not self.is_extending and not self.is_retracting and not self.is_blocked:
            # Start extending if arm should be extended
            self.is_extending = True
        elif not self.should_extend and not self.is_retracting and self.arm_length > 0:
            # Start retracting if arm should not be extended
            self.is_retracting = True
            
        if self.is_extending:
            self.arm_length += self.extension_speed
            if self.arm_length >= self.max_arm_length:
                self.arm_length = self.max_arm_length
                self.is_extending = False
                # Only retract if not supposed to be extended
                if not self.should_extend:
                    self.is_retracting = True
        elif self.is_retracting:
            self.arm_length -= self.extension_speed
            if self.arm_length <= 0:
                self.arm_length = 0
                self.is_retracting = False
                
        # Calculate hand position
        shoulder_pos = self.get_shoulder_position()
        angle_rad = math.radians(self.character.body_rotation + self.angle)
        
        arm_vector = pygame.math.Vector2(
            math.cos(angle_rad),
            math.sin(angle_rad)
        ) * self.arm_length
        
        self.hand_position = shoulder_pos + arm_vector
        
        # Update equipment if present
        if self.equipment:
            self.equipment.update(self.hand_position, self.character.body_rotation + self.angle)
        
    def get_shoulder_position(self):
        side_factor = 1 if self.side == "right" else -1
        
        # Calculate the position based on body rotation
        angle_rad = math.radians(self.character.body_rotation + 90 * side_factor)
        
        offset = pygame.math.Vector2(
            math.cos(angle_rad),
            math.sin(angle_rad)
        ) * self.character.radius
        
        return pygame.math.Vector2(self.character.x, self.character.y) + offset
    
    def extend(self, target_angle=None, should_extend=True):
        self.should_extend = should_extend
        
        if should_extend and not self.is_extending and not self.is_retracting:
            self.is_extending = True
            if target_angle is not None:
                # Set arm angle towards target
                relative_angle = (target_angle - self.character.body_rotation) % 360
                if relative_angle > 180:
                    relative_angle -= 360
                
                self.angle = max(self.min_angle, min(self.max_angle, relative_angle))
    
    def draw(self, surface):
        shoulder_pos = self.get_shoulder_position()
        
        # Draw shoulder - same color as character (YELLOW)
        pygame.draw.rect(surface, YELLOW, 
                         pygame.Rect(shoulder_pos.x - self.shoulder_size/2, 
                                    shoulder_pos.y - self.shoulder_size/2, 
                                    self.shoulder_size, self.shoulder_size))
        
        # Draw arm if extended
        if self.arm_length > 0:
            angle_rad = math.radians(self.character.body_rotation + self.angle)
            end_pos = (
                shoulder_pos.x + math.cos(angle_rad) * self.arm_length,
                shoulder_pos.y + math.sin(angle_rad) * self.arm_length
            )
            
            # Calculate perpendicular points for rectangle
            perp_angle_rad = angle_rad + math.pi/2
            perp_vector = pygame.math.Vector2(
                math.cos(perp_angle_rad),
                math.sin(perp_angle_rad)
            ) * (self.shoulder_size/2)
            
            # Rectangle corners
            p1 = shoulder_pos + perp_vector
            p2 = shoulder_pos - perp_vector
            p3 = pygame.math.Vector2(end_pos) - perp_vector
            p4 = pygame.math.Vector2(end_pos) + perp_vector
            
            pygame.draw.polygon(surface, YELLOW, [p1, p2, p3, p4])
            
            # Draw hand at the end of arm
            pygame.draw.circle(surface, YELLOW, end_pos, 4)
            
            # Draw equipment if present
            if self.equipment:
                self.equipment.draw(surface)

class Equipment(pygame.sprite.Sprite):
    def __init__(self, owner, equipment_type):
        super().__init__()
        self.owner = owner
        self.type = equipment_type
        self.position = pygame.math.Vector2(0, 0)
        self.angle = 0
        self.width = 6
        self.length = 0
        self.knockback_strength = 0
        self.damage = 0
        self.extension_speed = 0
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.collision_points = []
        
        # Set properties based on type
        if equipment_type == "sword":
            self.length = 30
            self.knockback_strength = 5
            self.damage = 1
            self.extension_speed = 2
        elif equipment_type == "shield":
            self.length = 20
            self.width = 15
            self.knockback_strength = 0
            self.damage = 0
            self.extension_speed = 1
        elif equipment_type == "dagger":
            self.length = 15
            self.knockback_strength = 3
            self.damage = 1
            self.extension_speed = 4
        elif equipment_type == "bare_hand":
            self.length = 5
            self.knockback_strength = 4
            self.damage = 1
            self.extension_speed = 5
            
        weapons.add(self)
    
    def update(self, position, angle):
        self.position = position
        self.angle = angle
        
        # Update collision rectangle
        angle_rad = math.radians(self.angle)
        direction = pygame.math.Vector2(math.cos(angle_rad), math.sin(angle_rad))
        
        # For shield, make it tangent to the body (perpendicular to direction from body to hand)
        if self.type == "shield":
            # Calculate direction from body to hand (arm direction)
            body_to_hand = self.position - pygame.math.Vector2(self.owner.x, self.owner.y)
            if body_to_hand.length() > 0:
                body_to_hand.normalize_ip()
                # Tangent is perpendicular to this direction
                direction = pygame.math.Vector2(-body_to_hand.y, body_to_hand.x)
        
        # Calculate corners of the rectangle
        perp = pygame.math.Vector2(-direction.y, direction.x)
        
        # For all but shield, offset from hand to hold handle
        offset = 0
        if self.type in ["sword", "dagger"]:
            offset = self.width
            
        # Rectangle corners
        p1 = self.position + perp * (self.width/2) - direction * offset
        p2 = self.position - perp * (self.width/2) - direction * offset
        p3 = p2 + direction * self.length
        p4 = p1 + direction * self.length
        
        self.collision_points = [p1, p2, p3, p4]
        
        # Approximate rect
        min_x = min(p.x for p in self.collision_points)
        min_y = min(p.y for p in self.collision_points)
        max_x = max(p.x for p in self.collision_points)
        max_y = max(p.y for p in self.collision_points)
        
        self.rect = pygame.Rect(min_x, min_y, max_x - min_x, max_y - min_y)
    
    def draw(self, surface):
        if len(self.collision_points) == 4:
            pygame.draw.polygon(surface, GREY, self.collision_points)
            
    def check_collision(self, other_equipment):
        # Simple check for shield-sword interaction
        if self.type == "shield" and other_equipment.type in ["sword", "dagger"]:
            return self.rect.colliderect(other_equipment.rect)
        return False

class Character(Entity):
    def __init__(self, x, y, radius=15, health=9):
        super().__init__(x, y, radius)
        self.health = health
        self.max_health = health
        self.move_speed = 2
        self.target_rotation = 0
        self.left_arm = Arm(self, "left")
        self.right_arm = Arm(self, "right")
        self.left_equipped = None
        self.right_equipped = None
        self.fixed_rotation = False
        characters.add(self)
        object_layer.add(self)
        
    def equip(self, equipment_type, side):
        if side == "left":
            self.left_equipped = Equipment(self, equipment_type)
            self.left_arm.equipment = self.left_equipped
            self.left_arm.extension_speed = self.left_equipped.extension_speed
        else:
            self.right_equipped = Equipment(self, equipment_type)
            self.right_arm.equipment = self.right_equipped
            self.right_arm.extension_speed = self.right_equipped.extension_speed
    
    def update(self):
        super().update()
        
        # Rotate body towards target rotation if not fixed
        if not self.fixed_rotation:
            angle_diff = (self.target_rotation - self.body_rotation) % 360
            if angle_diff > 180:
                angle_diff -= 360
                
            if abs(angle_diff) > self.body_rotation_speed:
                self.body_rotation += self.body_rotation_speed * (1 if angle_diff > 0 else -1)
            else:
                self.body_rotation = self.target_rotation
                
        # Keep rotation in [0, 360]
        self.body_rotation %= 360
        
        # Update arms
        self.left_arm.update()
        self.right_arm.update()
        
        # Check collisions with other characters
        for character in characters:
            if character != self:
                dx = character.x - self.x
                dy = character.y - self.y
                distance = math.sqrt(dx**2 + dy**2)
                
                if distance < self.radius + character.radius:
                    # Apply knockback to both
                    knockback_dir = pygame.math.Vector2(dx, dy).normalize()
                    self.apply_knockback(-knockback_dir * 1)
                    character.apply_knockback(knockback_dir * 1)
        
        # Check weapon collisions
        self.check_weapon_collisions()
        
        # Ensure character stays in bounds
        self.x = max(self.radius, min(WINDOW_WIDTH - self.radius, self.x))
        self.y = max(self.radius, min(WINDOW_HEIGHT - self.radius, self.y))
    
    def check_weapon_collisions(self):
        # Check if character's weapons hit other characters
        for character in characters:
            if character != self:
                # Only check for collision when arm is extending
                if self.left_arm.is_extending and self.left_equipped:
                    if character.rect.colliderect(self.left_equipped.rect):
                        self.handle_hit(character, self.left_equipped)
                
                if self.right_arm.is_extending and self.right_equipped:
                    if character.rect.colliderect(self.right_equipped.rect):
                        self.handle_hit(character, self.right_equipped)
                        
                # Shield-weapon interaction
                if self.left_equipped and self.left_equipped.type == "shield":
                    if character.right_equipped and character.right_equipped.type in ["sword", "dagger"]:
                        if self.left_equipped.check_collision(character.right_equipped):
                            self.handle_shield_block(character, "right")
                
                if self.right_equipped and self.right_equipped.type == "shield":
                    if character.left_equipped and character.left_equipped.type in ["sword", "dagger"]:
                        if self.right_equipped.check_collision(character.left_equipped):
                            self.handle_shield_block(character, "left")
    
    def handle_hit(self, target, weapon):
        # Apply damage and knockback
        target.take_damage(weapon.damage)
        
        # Direction from attacker to target
        direction = pygame.math.Vector2(
            target.x - self.x,
            target.y - self.y
        ).normalize()
        
        target.apply_knockback(direction * weapon.knockback_strength)
    
    def handle_shield_block(self, attacker, blocked_arm):
        # Force the attacking arm to rotate backward gradually
        # We'll start a rotation animation rather than snapping immediately
        if blocked_arm == "left":
            attacker.left_arm.block_rotation_target = attacker.left_arm.angle - 90
            attacker.left_arm.is_blocked = True
        else:
            attacker.right_arm.block_rotation_target = attacker.right_arm.angle - 90
            attacker.right_arm.is_blocked = True
            
        # Create a visual block effect
        block_effect = BlockEffect(
            attacker.left_arm.hand_position if blocked_arm == "left" else attacker.right_arm.hand_position
        )
        object_layer.add(block_effect)
    
    def take_damage(self, amount):
        self.health -= amount
        
        # Create blood splatter
        for _ in range(amount * 5):
            splatter = BloodSplatter(self.x, self.y)
            splatter_layer.add(splatter)
            
        # Apply knockback from damage
        knockback_dir = pygame.math.Vector2(
            random.uniform(-1, 1),
            random.uniform(-1, 1)
        ).normalize()
        
        self.apply_knockback(knockback_dir * 3)
        
        if self.health <= 0:
            self.die()
    
    def die(self):
        # Create death effect
        for _ in range(20):
            splatter = BloodSplatter(self.x, self.y)
            splatter_layer.add(splatter)
            
        # Remove from all groups
        self.kill()
    
    def attack(self, side, target_angle=None, should_extend=True):
        if side == "left":
            self.left_arm.extend(target_angle, should_extend)
        else:
            self.right_arm.extend(target_angle, should_extend)
    
    def draw(self, surface):
        # Draw body
        pygame.draw.circle(surface, YELLOW, (self.x, self.y), self.radius)
        
        # Draw direction indicator
        direction_x = self.x + math.cos(math.radians(self.body_rotation)) * (self.radius - 2)
        direction_y = self.y + math.sin(math.radians(self.body_rotation)) * (self.radius - 2)
        pygame.draw.circle(surface, BLACK, (direction_x, direction_y), 3)
        
        # Draw arms
        self.left_arm.draw(surface)
        self.right_arm.draw(surface)
        
        # Draw health if enemy
        if not isinstance(self, Player):
            health_text = font_small.render(str(self.health), True, WHITE)
            text_rect = health_text.get_rect(center=(self.x, self.y))
            surface.blit(health_text, text_rect)

class Player(Character):
    def __init__(self, x, y):
        super().__init__(x, y, radius=15, health=9)
        self.move_speed = 3
        
    def update(self):
        # Get keys pressed
        keys = pygame.key.get_pressed()
        
        # Movement
        self.velocity = pygame.math.Vector2(0, 0)
        if keys[pygame.K_w]:
            self.velocity.y -= self.move_speed
        if keys[pygame.K_s]:
            self.velocity.y += self.move_speed
        if keys[pygame.K_a]:
            self.velocity.x -= self.move_speed
        if keys[pygame.K_d]:
            self.velocity.x += self.move_speed
            
        # Normalize diagonal movement
        if self.velocity.length() > 0:
            self.velocity.normalize_ip()
            self.velocity *= self.move_speed
        
        # Update mouse position for aiming
        mouse_pos = pygame.mouse.get_pos()
        dx = mouse_pos[0] - self.x
        dy = mouse_pos[1] - self.y
        self.target_rotation = math.degrees(math.atan2(dy, dx)) % 360
        
        # Check mouse buttons for arm extension/retraction
        mouse_buttons = pygame.mouse.get_pressed()
        
        # Right arm follows left mouse button
        if mouse_buttons[0]:  # Left click
            self.fixed_rotation = True
            self.right_arm.extend(self.target_rotation, True)
        else:
            self.right_arm.extend(None, False)
            
        # Left arm follows right mouse button
        if mouse_buttons[2]:  # Right click
            self.fixed_rotation = True
            self.left_arm.extend(self.target_rotation, True)
        else:
            self.left_arm.extend(None, False)
            
        # If no mouse buttons are pressed, allow body rotation
        if not mouse_buttons[0] and not mouse_buttons[2]:
            self.fixed_rotation = False
        
        super().update()
    
    def die(self):
        global game_state, highscore
        super().die()
        
        # Update highscore
        if kills > highscore:
            highscore = kills
            
        game_state = "game_over"

class Enemy(Character):
    def __init__(self, x, y, target=None):
        super().__init__(x, y, radius=15, health=random.randint(1, 5))
        self.target = target
        self.move_speed = random.uniform(1, 2)
        self.state = "idle"
        self.state_timer = random.uniform(1, 3)
        self.direction = pygame.math.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
        
        # Randomize behavior profile
        self.behavior_profile = random.choice([
            "aggressive",    # Always approach and attack
            "cautious",      # Circle and attack occasionally
            "defensive",     # Keep distance, attack when safe
            "erratic"        # Unpredictable movement and attacks
        ])
        
    def update(self):
        if self.target:
            # Update state timer
            self.state_timer -= 1/FPS
            if self.state_timer <= 0:
                self.change_state()
            
            # Calculate distance to target
            dx = self.target.x - self.x
            dy = self.target.y - self.y
            distance = math.sqrt(dx**2 + dy**2)
            direction_to_target = pygame.math.Vector2(dx, dy)
            if direction_to_target.length() > 0:
                direction_to_target.normalize_ip()
            
            # Point towards target
            self.target_rotation = math.degrees(math.atan2(dy, dx)) % 360
            
            # Behavior based on state and profile
            if self.state == "idle":
                self.velocity = pygame.math.Vector2(0, 0)
            
            elif self.state == "approach":
                self.velocity = direction_to_target * self.move_speed
                
                # Attack if close enough
                if distance < 50 and random.random() < 0.05:
                    self.attack(random.choice(["left", "right"]), self.target_rotation)
            
            elif self.state == "retreat":
                self.velocity = -direction_to_target * self.move_speed
            
            elif self.state == "circle":
                # Move perpendicular to direction to target
                perpendicular = pygame.math.Vector2(-direction_to_target.y, direction_to_target.x)
                self.velocity = perpendicular * self.move_speed
                
                # Occasionally attack while circling
                if distance < 60 and random.random() < 0.02:
                    self.attack(random.choice(["left", "right"]), self.target_rotation)
            
            elif self.state == "attack":
                if distance < 70:
                    # Stop moving and attack
                    self.velocity *= 0.5
                    
                    # Choose which arm to attack with
                    attack_arm = random.choice(["left", "right"])
                    self.attack(attack_arm, self.target_rotation)
                else:
                    # Too far to attack, change state
                    self.change_state()
            
            # Avoid campfire and other dangers
            for obj in object_layer:
                if isinstance(obj, Campfire) and obj != self:
                    obj_dx = obj.x - self.x
                    obj_dy = obj.y - self.y
                    obj_dist = math.sqrt(obj_dx**2 + obj_dy**2)
                    
                    if obj_dist < 50:  # Detect danger nearby
                        obj_dir = pygame.math.Vector2(obj_dx, obj_dy)
                        if obj_dir.length() > 0:
                            obj_dir.normalize_ip()
                        
                        # Add avoidance vector
                        avoid_strength = max(0, (50 - obj_dist) / 50) * 2
                        self.velocity -= obj_dir * avoid_strength
            
            # Avoid player's weapons
            if self.target.left_equipped and self.target.left_arm.is_extending:
                self.avoid_weapon(self.target.left_equipped)
                
            if self.target.right_equipped and self.target.right_arm.is_extending:
                self.avoid_weapon(self.target.right_equipped)
        
        super().update()
    
    def avoid_weapon(self, weapon):
        # Calculate distance to weapon
        weapon_center = weapon.position + pygame.math.Vector2(
            math.cos(math.radians(weapon.angle)),
            math.sin(math.radians(weapon.angle))
        ) * (weapon.length / 2)
        
        dx = weapon_center.x - self.x
        dy = weapon_center.y - self.y
        distance = math.sqrt(dx**2 + dy**2)
        
        if distance < 50:
            # Add avoidance vector
            avoid_dir = pygame.math.Vector2(dx, dy)
            if avoid_dir.length() > 0:
                avoid_dir.normalize_ip()
            
            avoid_strength = max(0, (50 - distance) / 50) * 3
            self.velocity -= avoid_dir * avoid_strength
    
    def change_state(self):
        # Choose new state based on behavior profile
        if self.behavior_profile == "aggressive":
            self.state = random.choices(
                ["approach", "attack", "circle", "idle"],
                weights=[0.5, 0.3, 0.15, 0.05],
                k=1
            )[0]
            
        elif self.behavior_profile == "cautious":
            self.state = random.choices(
                ["circle", "retreat", "approach", "attack", "idle"],
                weights=[0.4, 0.2, 0.2, 0.1, 0.1],
                k=1
            )[0]
            
        elif self.behavior_profile == "defensive":
            self.state = random.choices(
                ["retreat", "circle", "idle", "attack", "approach"],
                weights=[0.3, 0.3, 0.2, 0.1, 0.1],
                k=1
            )[0]
            
        elif self.behavior_profile == "erratic":
            self.state = random.choice(["approach", "retreat", "circle", "attack", "idle"])
        
        # Set timer for next state change
        self.state_timer = random.uniform(1, 4)
        
        # For attack state, use shorter duration
        if self.state == "attack":
            self.state_timer = random.uniform(0.5, 1.5)

    def die(self):
        global kills
        super().die()
        kills += 1

class BloodSplatter(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x + random.uniform(-20, 20)
        self.y = y + random.uniform(-20, 20)
        self.radius = random.uniform(2, 5)
        self.color = (BLOOD_RED[0], BLOOD_RED[1], BLOOD_RED[2], random.randint(100, 200))
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, self.color, (self.radius, self.radius), self.radius)
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.lifetime = random.uniform(5, 15)
        
    def update(self):
        self.lifetime -= 1/FPS
        if self.lifetime <= 0:
            self.kill()
        
    def draw(self, surface):
        surface.blit(self.image, self.rect)

class Campfire(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.base_size = 20
        self.flame_height = 30
        self.flame_tip_offset = 0
        self.flame_direction = 1
        self.animation_speed = 0.3
        self.flame_flicker = 0
        self.image = pygame.Surface((self.base_size + 20, self.base_size + self.flame_height + 10), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.damage_radius = self.base_size
        self.damage_timer = 0
        ground_layer.add(self)
        
        # Create fire embers
        self.embers = []
        for _ in range(10):
            self.embers.append({
                'x': self.x + random.uniform(-self.base_size/2, self.base_size/2),
                'y': self.y - random.uniform(0, self.flame_height),
                'size': random.uniform(1, 3),
                'speed': random.uniform(0.5, 1.5),
                'alpha': random.randint(150, 255)
            })
        
    def update(self):
        # Animate flame
        self.flame_tip_offset += self.animation_speed * self.flame_direction
        if abs(self.flame_tip_offset) > 5:
            self.flame_direction *= -1
            
        # Random flicker effect
        self.flame_flicker = random.uniform(-2, 2)
            
        # Update embers
        for ember in self.embers:
            ember['y'] -= ember['speed']
            ember['alpha'] -= random.uniform(1, 3)
            
            # Reset ember when it fades or rises too high
            if ember['alpha'] <= 0 or ember['y'] < self.y - self.flame_height - 20:
                ember['x'] = self.x + random.uniform(-self.base_size/2, self.base_size/2)
                ember['y'] = self.y - random.uniform(0, 5)
                ember['size'] = random.uniform(1, 3)
                ember['alpha'] = random.randint(150, 255)
                
        # Check for characters in fire
        self.damage_timer -= 1/60
        if self.damage_timer <= 0:
            self.damage_timer = 0.5  # Damage every half second
            for character in characters:
                dx = character.x - self.x
                dy = character.y - self.y
                distance = math.sqrt(dx**2 + dy**2)
                
                if distance < self.damage_radius:
                    character.take_damage(1)
        
    def draw(self, surface):
        # Draw base (brown square)
        pygame.draw.rect(surface, BROWN, 
                        pygame.Rect(self.x - self.base_size/2, self.y - self.base_size/2, 
                                   self.base_size, self.base_size))
        
        # Draw logs crossing the fire
        log_color = (100, 50, 20)
        pygame.draw.rect(surface, log_color, 
                        pygame.Rect(self.x - self.base_size*0.7, 
                                   self.y - self.base_size*0.2, 
                                   self.base_size*1.4, 
                                   self.base_size*0.4))
        pygame.draw.rect(surface, log_color, 
                        pygame.Rect(self.x - self.base_size*0.2, 
                                   self.y - self.base_size*0.7, 
                                   self.base_size*0.4, 
                                   self.base_size*1.4))
        
        # Draw flames (red triangle with yellow inside)
        flame_points = [
            (self.x, self.y - self.flame_height - self.flame_tip_offset + self.flame_flicker),  # Top
            (self.x - self.base_size/2, self.y),  # Bottom left
            (self.x + self.base_size/2, self.y)   # Bottom right
        ]
        
        # Inner flame (yellow)
        inner_flame_points = [
            (self.x, self.y - (self.flame_height/1.5) - self.flame_tip_offset/1.5 + self.flame_flicker/1.5),  # Top
            (self.x - self.base_size/4, self.y),  # Bottom left
            (self.x + self.base_size/4, self.y)   # Bottom right
        ]
        
        # Draw fire glow
        for i in range(3):
            glow_size = self.base_size + i * 10
            glow_color = (255, 100, 0, 50 - i * 15)
            glow_surf = pygame.Surface((glow_size*2, glow_size*2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, glow_color, (glow_size, glow_size), glow_size)
            surface.blit(glow_surf, (self.x - glow_size, self.y - glow_size))
        
        pygame.draw.polygon(surface, RED, flame_points)
        pygame.draw.polygon(surface, YELLOW, inner_flame_points)
        
        # Draw embers
        for ember in self.embers:
            ember_color = (255, 200, 50, int(ember['alpha']))
            ember_surf = pygame.Surface((ember['size']*2, ember['size']*2), pygame.SRCALPHA)
            pygame.draw.circle(ember_surf, ember_color, (ember['size'], ember['size']), ember['size'])
            surface.blit(ember_surf, (ember['x'] - ember['size'], ember['y'] - ember['size']))

class Tree(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.trunk_width = 15
        self.trunk_height = 30
        self.foliage_radius = 25
        self.sway_offset = 0
        self.sway_direction = 1
        self.sway_speed = random.uniform(0.05, 0.1)
        self.image = pygame.Surface((self.foliage_radius * 2 + 10, self.trunk_height + self.foliage_radius + 10), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.alpha = 255
        self.target_alpha = 255
        
        # Add to layers
        roof_layer.add(self)
        obstacles.add(self)
        
    def update(self):
        # Gentle swaying of the tree
        self.sway_offset += self.sway_speed * self.sway_direction
        if abs(self.sway_offset) > 2:
            self.sway_direction *= -1
        
        # Check for characters under the tree
        is_character_under = False
        for character in characters:
            if self.rect.colliderect(character.rect):
                is_character_under = True
                break
                
        # Update transparency based on character position
        self.target_alpha = 128 if is_character_under else 255
        
        # Smooth transition for transparency
        if self.alpha < self.target_alpha:
            self.alpha = min(self.alpha + 10, self.target_alpha)
        elif self.alpha > self.target_alpha:
            self.alpha = max(self.alpha - 10, self.target_alpha)
        
    def draw(self, surface):
        # Create a new surface for drawing with transparency
        tree_surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        
        # Draw trunk (brown rectangle with some detail)
        trunk_rect = pygame.Rect(
            self.rect.width/2 - self.trunk_width/2 + self.sway_offset,
            self.rect.height - self.trunk_height - 5,
            self.trunk_width,
            self.trunk_height
        )
        pygame.draw.rect(tree_surface, BROWN, trunk_rect)
        
        # Add trunk details
        dark_brown = (BROWN[0] - 20, BROWN[1] - 20, BROWN[2] - 20)
        for i in range(3):
            y_pos = trunk_rect.y + (i+1) * trunk_rect.height/4
            pygame.draw.line(
                tree_surface, 
                dark_brown,
                (trunk_rect.left, y_pos),
                (trunk_rect.right, y_pos + self.sway_offset),
                2
            )
        
        # Draw multiple overlapping foliage circles for more natural look
        foliage_center_x = self.rect.width/2 + self.sway_offset * 1.2
        foliage_center_y = self.rect.height - self.trunk_height - 5 - self.foliage_radius/2
        
        # Draw several overlapping circles with slightly different shades
        foliage_colors = [
            (GREEN[0] - 15, GREEN[1] - 15, GREEN[2] - 15),
            GREEN,
            (GREEN[0] + 15, GREEN[1] + 15, GREEN[2] + 15)
        ]
        
        for i, color in enumerate(foliage_colors):
            offset = i - 1
            pygame.draw.circle(
                tree_surface, 
                color,
                (foliage_center_x + offset * 5, foliage_center_y + offset * 3),
                self.foliage_radius - abs(offset) * 3
            )
        
        # Apply transparency
        tree_surface.set_alpha(self.alpha)
        
        # Blit to the main surface
        surface.blit(tree_surface, self.rect.topleft)

class Rock(pygame.sprite.Sprite):
    def __init__(self, x, y, size=None):
        super().__init__()
        self.x = x
        self.y = y
        self.size = size if size else random.randint(10, 25)
        self.image = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.color = DARK_GREY
        self.shape_points = []
        
        # Generate a more natural rocky shape
        self.generate_rock_shape()
        
        # Add to layers
        object_layer.add(self)
        obstacles.add(self)
    
    def generate_rock_shape(self):
        # Create an irregular polygon for a more natural rock
        num_points = random.randint(6, 10)
        self.shape_points = []
        
        for i in range(num_points):
            angle = math.radians((360 / num_points) * i)
            # Vary the radius to create irregular shape
            radius_variation = random.uniform(0.8, 1.2)
            x = self.x + math.cos(angle) * self.size * radius_variation
            y = self.y + math.sin(angle) * self.size * radius_variation
            self.shape_points.append((x, y))
        
    def draw(self, surface):
        if self.shape_points:
            # Draw main rock shape
            pygame.draw.polygon(surface, self.color, self.shape_points)
            
            # Add highlights and shadows for depth
            highlight_color = (min(255, self.color[0] + 30), 
                              min(255, self.color[1] + 30), 
                              min(255, self.color[2] + 30))
            
            shadow_color = (max(0, self.color[0] - 30), 
                           max(0, self.color[1] - 30), 
                           max(0, self.color[2] - 30))
            
            # Draw a smaller version for highlight (top-left)
            highlight_points = []
            for x, y in self.shape_points[:len(self.shape_points)//2]:
                highlight_points.append((
                    x - (x - self.x) * 0.3,
                    y - (y - self.y) * 0.3
                ))
            
            if len(highlight_points) > 2:
                pygame.draw.polygon(surface, highlight_color, highlight_points)
            
            # Draw some detail lines/cracks
            for _ in range(2):
                start_idx = random.randint(0, len(self.shape_points) - 1)
                end_idx = (start_idx + random.randint(1, len(self.shape_points) // 2)) % len(self.shape_points)
                
                pygame.draw.line(
                    surface,
                    shadow_color,
                    self.shape_points[start_idx],
                    self.shape_points[end_idx],
                    2
                )

def create_cobblestone_background():
    background = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
    background.fill((50, 50, 50))  # Dark grey base
    
    # Create detailed cobblestones
    for x in range(0, WINDOW_WIDTH, 15):
        for y in range(0, WINDOW_HEIGHT, 15):
            offset_x = random.randint(-3, 3)
            offset_y = random.randint(-3, 3)
            size = random.randint(5, 8)
            
            # Create more natural looking stones with varied shades of grey
            main_color = random.randint(100, 170)
            variation = random.randint(-15, 15)
            color = (main_color + variation, main_color + variation, main_color + variation)
            
            # Draw the cobblestone
            pygame.draw.circle(background, color, (x + offset_x, y + offset_y), size)
            
            # Add a subtle highlight or shadow to give dimension
            highlight = (min(255, main_color + 30), min(255, main_color + 30), min(255, main_color + 30))
            shadow = (max(0, main_color - 30), max(0, main_color - 30), max(0, main_color - 30))
            
            # Small highlight on top-left
            pygame.draw.circle(background, highlight, 
                              (x + offset_x - size//3, y + offset_y - size//3), 
                              size//3)
            
            # Small shadow on bottom-right
            pygame.draw.circle(background, shadow, 
                              (x + offset_x + size//3, y + offset_y + size//3), 
                              size//3)
    
    return background

def spawn_environment():
    # Create campfire in the center
    campfire = Campfire(WINDOW_WIDTH/2, WINDOW_HEIGHT/2)
    
    # Create stone circle around campfire
    num_stones = 8
    stone_distance = 60
    for i in range(num_stones):
        angle = math.radians((360 / num_stones) * i)
        x = WINDOW_WIDTH/2 + math.cos(angle) * stone_distance
        y = WINDOW_HEIGHT/2 + math.sin(angle) * stone_distance
        Rock(x, y, size=random.randint(8, 12))
    
    # Create larger rocks scattered around
    for _ in range(8):
        x = random.randint(50, WINDOW_WIDTH - 50)
        y = random.randint(50, WINDOW_HEIGHT - 50)
        
        # Ensure rocks aren't too close to campfire
        while math.sqrt((x - WINDOW_WIDTH/2)**2 + (y - WINDOW_HEIGHT/2)**2) < 100:
            x = random.randint(50, WINDOW_WIDTH - 50)
            y = random.randint(50, WINDOW_HEIGHT - 50)
            
        Rock(x, y, size=random.randint(15, 25))
    
    # Create tree clusters
    tree_clusters = 3
    for _ in range(tree_clusters):
        # Choose a central point for this cluster
        cluster_x = random.randint(100, WINDOW_WIDTH - 100)
        cluster_y = random.randint(100, WINDOW_HEIGHT - 100)
        
        # Ensure cluster isn't too close to campfire
        while math.sqrt((cluster_x - WINDOW_WIDTH/2)**2 + (cluster_y - WINDOW_HEIGHT/2)**2) < 150:
            cluster_x = random.randint(100, WINDOW_WIDTH - 100)
            cluster_y = random.randint(100, WINDOW_HEIGHT - 100)
        
        # Create 2-4 trees in this cluster
        for _ in range(random.randint(2, 4)):
            # Position within cluster
            x = cluster_x + random.randint(-50, 50)
            y = cluster_y + random.randint(-50, 50)
            
            # Keep trees within screen bounds
            x = max(50, min(WINDOW_WIDTH - 50, x))
            y = max(50, min(WINDOW_HEIGHT - 50, y))
            
            Tree(x, y)
            
    # Add some ground detail - fallen logs, small stones
    for _ in range(15):
        x = random.randint(50, WINDOW_WIDTH - 50)
        y = random.randint(50, WINDOW_HEIGHT - 50)
        
        # Skip if too close to campfire
        if math.sqrt((x - WINDOW_WIDTH/2)**2 + (y - WINDOW_HEIGHT/2)**2) < 80:
            continue
        
        # 50% chance for small rock, 50% for fallen log
        if random.random() < 0.5:
            Rock(x, y, size=random.randint(5, 8))
        else:
            # Create fallen log effect (small brown rectangle)
            log = pygame.sprite.Sprite()
            log.x = x
            log.y = y
            log.image = pygame.Surface((random.randint(15, 30), random.randint(5, 10)), pygame.SRCALPHA)
            log.rect = log.image.get_rect(center=(x, y))
            
            # Random rotation for log
            log.angle = random.randint(0, 360)
            log.draw = lambda surface: pygame.draw.rect(
                surface, BROWN, 
                pygame.Rect(log.x - log.image.get_width()/2, 
                           log.y - log.image.get_height()/2, 
                           log.image.get_width(), log.image.get_height()))
            
            ground_layer.add(log)

def spawn_enemy(player):
    # Determine spawn position outside screen
    side = random.choice(["top", "bottom", "left", "right"])
    
    if side == "top":
        x = random.randint(0, WINDOW_WIDTH)
        y = -30
    elif side == "bottom":
        x = random.randint(0, WINDOW_WIDTH)
        y = WINDOW_HEIGHT + 30
    elif side == "left":
        x = -30
        y = random.randint(0, WINDOW_HEIGHT)
    else:  # right
        x = WINDOW_WIDTH + 30
        y = random.randint(0, WINDOW_HEIGHT)
    
    # Create enemy
    enemy = Enemy(x, y, player)
    
    # Random equipment
    # Ensure at least one weapon
    left_type = random.choice(["sword", "dagger", "shield", "bare_hand"])
    if left_type == "shield":
        right_type = random.choice(["sword", "dagger"])
    else:
        right_type = random.choice(["sword", "dagger", "shield", "bare_hand"])
    
    enemy.equip(left_type, "left")
    enemy.equip(right_type, "right")
    
    return enemy

def draw_menu():
    screen.fill((30, 30, 30))
    
    # Title
    title = font_large.render("Top-Down Battle Game", True, WHITE)
    screen.blit(title, (WINDOW_WIDTH/2 - title.get_width()/2, 100))
    
    # Instructions
    instructions = [
        "Controls:",
        "WASD - Move",
        "Mouse - Aim",
        "Left Mouse Button - Right Arm Attack",
        "Right Mouse Button - Left Arm Attack",
        "Survive as long as possible and defeat enemies!",
        "",
        "Press SPACE to play"
    ]
    
    for i, line in enumerate(instructions):
        text = font_medium.render(line, True, WHITE)
        screen.blit(text, (WINDOW_WIDTH/2 - text.get_width()/2, 200 + i * 30))
    
    # Highscore
    score_text = font_medium.render(f"Highscore: {highscore}", True, WHITE)
    screen.blit(score_text, (WINDOW_WIDTH/2 - score_text.get_width()/2, 500))

def draw_equipment_select():
    screen.fill((30, 30, 30))
    
    # Title
    title = font_large.render("Select Equipment", True, WHITE)
    screen.blit(title, (WINDOW_WIDTH/2 - title.get_width()/2, 50))
    
    # Left hand
    left_title = font_medium.render("Left Hand", True, WHITE)
    screen.blit(left_title, (WINDOW_WIDTH/4 - left_title.get_width()/2, 100))
    
    # Right hand
    right_title = font_medium.render("Right Hand", True, WHITE)
    screen.blit(right_title, (3*WINDOW_WIDTH/4 - right_title.get_width()/2, 100))
    
    # Equipment options
    for i, equipment in enumerate(EQUIPMENT_TYPES):
        # Left side button
        left_rect = pygame.Rect(WINDOW_WIDTH/4 - 100, 150 + i * 60, 200, 40)
        pygame.draw.rect(screen, GREY, left_rect)
        left_text = font_medium.render(equipment.capitalize(), True, BLACK)
        screen.blit(left_text, (left_rect.centerx - left_text.get_width()/2, left_rect.centery - left_text.get_height()/2))
        
        # Right side button
        right_rect = pygame.Rect(3*WINDOW_WIDTH/4 - 100, 150 + i * 60, 200, 40)
        pygame.draw.rect(screen, GREY, right_rect)
        right_text = font_medium.render(equipment.capitalize(), True, BLACK)
        screen.blit(right_text, (right_rect.centerx - right_text.get_width()/2, right_rect.centery - right_text.get_height()/2))
    
    # Instructions
    instructions = font_medium.render("Click to select equipment for each hand", True, WHITE)
    screen.blit(instructions, (WINDOW_WIDTH/2 - instructions.get_width()/2, 400))
    
    return EQUIPMENT_TYPES

def draw_game_over():
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    screen.blit(overlay, (0, 0))
    
    # Game over message
    game_over = font_large.render("Game Over", True, RED)
    screen.blit(game_over, (WINDOW_WIDTH/2 - game_over.get_width()/2, WINDOW_HEIGHT/2 - 50))
    
    # Score
    score_text = font_medium.render(f"Score: {kills}", True, WHITE)
    screen.blit(score_text, (WINDOW_WIDTH/2 - score_text.get_width()/2, WINDOW_HEIGHT/2))
    
    # Highscore
    highscore_text = font_medium.render(f"Highscore: {highscore}", True, WHITE)
    screen.blit(highscore_text, (WINDOW_WIDTH/2 - highscore_text.get_width()/2, WINDOW_HEIGHT/2 + 30))
    
    # Continue message
    continue_text = font_medium.render("Press any key to continue", True, WHITE)
    screen.blit(continue_text, (WINDOW_WIDTH/2 - continue_text.get_width()/2, WINDOW_HEIGHT/2 + 80))

def draw_game_ui(player):
    # Draw health bar
    bar_width = 200
    bar_height = 20
    bar_x = 20
    bar_y = WINDOW_HEIGHT - 40
    
    # Background
    pygame.draw.rect(screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
    
    # Health
    health_width = max(0, (player.health / player.max_health) * bar_width)
    pygame.draw.rect(screen, (0, 200, 0), (bar_x, bar_y, health_width, bar_height))
    
    # Border
    pygame.draw.rect(screen, WHITE, (bar_x, bar_y, bar_width, bar_height), 2)
    
    # Health text
    health_text = font_small.render(f"Health: {player.health}/{player.max_health}", True, WHITE)
    screen.blit(health_text, (bar_x + 10, bar_y + 2))
    
    # Score
    score_text = font_medium.render(f"Kills: {kills}", True, WHITE)
    screen.blit(score_text, (WINDOW_WIDTH - score_text.get_width() - 20, 20))
    
    # Time
    time_text = font_medium.render(f"Time: {int(game_time)}", True, WHITE)
    screen.blit(time_text, (WINDOW_WIDTH - time_text.get_width() - 20, 50))

def reset_game():
    global kills, game_time
    
    # Clear all sprites
    ground_layer.empty()
    splatter_layer.empty()
    object_layer.empty()
    roof_layer.empty()
    characters.empty()
    obstacles.empty()
    weapons.empty()
    
    # Reset counters
    kills = 0
    game_time = 0

def main():
    global game_state, game_time
    
    background = create_cobblestone_background()
    spawn_environment()
    
    player = None
    left_equipment = None
    right_equipment = None
    spawn_timer = 0
    enemy_spawn_rate = 5
    
    running = True
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            if event.type == pygame.KEYDOWN:
                if game_state == "menu" and event.key == pygame.K_SPACE:
                    game_state = "equipment_select"
                elif game_state == "game_over":
                    game_state = "menu"
                    
            if event.type == pygame.MOUSEBUTTONDOWN and game_state == "equipment_select":
                mouse_pos = pygame.mouse.get_pos()
                
                # Check left equipment buttons
                for i, equipment in enumerate(EQUIPMENT_TYPES):
                    left_rect = pygame.Rect(WINDOW_WIDTH/4 - 100, 150 + i * 60, 200, 40)
                    if left_rect.collidepoint(mouse_pos):
                        left_equipment = equipment
                
                # Check right equipment buttons
                for i, equipment in enumerate(EQUIPMENT_TYPES):
                    right_rect = pygame.Rect(3*WINDOW_WIDTH/4 - 100, 150 + i * 60, 200, 40)
                    if right_rect.collidepoint(mouse_pos):
                        right_equipment = equipment
                
                # If both equipment selected, start game
                if left_equipment and right_equipment:
                    reset_game()
                    
                    # Create player in center of screen
                    player = Player(WINDOW_WIDTH/2, WINDOW_HEIGHT/2)
                    player.equip(left_equipment, "left")
                    player.equip(right_equipment, "right")
                    
                    # Spawn initial enemy
                    spawn_enemy(player)
                    
                    game_state = "game"
        
        # Update game state
        if game_state == "game":
            # Update time
            game_time += 1/FPS
            
            # Update sprites
            ground_layer.update()
            splatter_layer.update()
            object_layer.update()
            roof_layer.update()
            
            # Spawn enemies
            spawn_timer -= 1/FPS
            if spawn_timer <= 0:
                # Spawn rate increases with time and decreases with more enemies
                enemy_count = sum(1 for sprite in characters if isinstance(sprite, Enemy))
                time_factor = min(1, game_time / 60)  # Maxes out after 1 minute
                spawn_rate = max(1, enemy_spawn_rate - time_factor - (3 - enemy_count))
                
                spawn_timer = spawn_rate
                if enemy_count < 3:  # Cap at 3 enemies max
                    spawn_enemy(player)
        
        # Render
        screen.fill((0, 0, 0))
        
        if game_state == "menu":
            draw_menu()
            
        elif game_state == "equipment_select":
            draw_equipment_select()
            
        elif game_state == "game":
            # Draw background
            screen.blit(background, (0, 0))
            
            # Draw all layers in order
            for sprite in ground_layer:
                sprite.draw(screen)
                
            for sprite in splatter_layer:
                sprite.draw(screen)
                
            for sprite in object_layer:
                sprite.draw(screen)
                
            for sprite in effect_layer:
                sprite.draw(screen)
                
            for sprite in roof_layer:
                sprite.draw(screen)
            
            # Draw UI
            draw_game_ui(player)
            
        elif game_state == "game_over":
            # Draw background
            screen.blit(background, (0, 0))
            
            # Draw all layers in order
            for sprite in ground_layer:
                sprite.draw(screen)
                
            for sprite in splatter_layer:
                sprite.draw(screen)
                
            for sprite in object_layer:
                sprite.draw(screen)
                
            for sprite in effect_layer:
                sprite.draw(screen)
                
            for sprite in roof_layer:
                sprite.draw(screen)
            
            # Draw game over screen
            draw_game_over()
        
        # Update display
        pygame.display.flip()
        
        # Cap framerate
        clock.tick(FPS)
    
    pygame.quit()
    sys.exit()

# Run the game
if __name__ == "__main__":
    main()