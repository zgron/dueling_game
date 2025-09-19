import pygame
import math
import random
from enum import Enum

# --- Constants ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 0, 0)
DARK_RED = (100, 0, 0)
YELLOW = (200, 200, 0)
GREEN = (0, 150, 0)
DARK_GREEN = (0, 80, 0)
GREY = (128, 128, 128)
DARK_GREY = (64, 64, 64)
LIGHT_GREY = (192, 192, 192)
BROWN = (139, 69, 19)
BLOOD_COLOR = (139, 0, 0)

# Game Settings
PLAYER_SPEED = 150 # pixels per second
PLAYER_ROT_SPEED = 360 # degrees per second
ENEMY_SPEED = 100
ENEMY_ROT_SPEED = 270
BODY_RADIUS = 20
SHOULDER_SIZE = 12
DEFAULT_ARM_LENGTH = 40
DEFAULT_ARM_EXTEND_SPEED = 300
DEFAULT_ARM_RETRACT_SPEED = 400
ARM_ROT_SPEED = 540 # degrees per second
KNOCKBACK_SELF_COLLIDE = 50
KNOCKBACK_DAMAGE = 200
MAX_HP = 9

# Equipment Specs
SWORD_LENGTH = 50
SWORD_WIDTH = 8
SWORD_EXTEND_SPEED = 250
DAGGER_LENGTH = 30
DAGGER_WIDTH = 6
DAGGER_EXTEND_SPEED = 400
BARE_HAND_EXTEND_SPEED = 500
BARE_HAND_KNOCKBACK = 300
SHIELD_WIDTH = 35
SHIELD_HEIGHT = 10

# Spawning
INITIAL_SPAWN_DELAY = 5.0 # seconds
BASE_SPAWN_INTERVAL = 15.0
MIN_SPAWN_INTERVAL = 3.0
SPAWN_TIME_FACTOR = 0.1 # Reduces interval by this much per second elapsed
SPAWN_COUNT_FACTOR = 1.5 # Reduces interval by this much per missing enemy (vs max)
MAX_ACTIVE_ENEMIES = 3

# --- Utility Functions ---
def normalize_vector(vector):
    if vector.length() == 0:
        return pygame.Vector2(0, 0)
    return vector.normalize()

def angle_lerp(current_angle, target_angle, factor, dt):
    """Linearly interpolates between two angles, handling wraparound."""
    diff = (target_angle - current_angle + 180) % 360 - 180
    step = diff * factor * dt * 50 # Adjusted factor for smoother lerp with dt
    # Prevent overshooting for small steps
    if abs(step) > abs(diff):
       return target_angle
    return (current_angle + step + 360) % 360

def rotate_point(point, angle, pivot):
    """Rotates a point around a pivot."""
    translated = point - pivot
    rotated = translated.rotate(-angle) # Pygame rotation is counter-clockwise
    return rotated + pivot

def draw_text(surface, text, size, x, y, color=WHITE, center=False):
    font = pygame.font.Font(None, size)
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect()
    if center:
        text_rect.center = (x, y)
    else:
        text_rect.topleft = (x, y)
    surface.blit(text_surface, text_rect)

def get_polygon_rect(points):
    """Gets the bounding Rect for a list of points."""
    if not points:
        return pygame.Rect(0,0,0,0)
    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)
    return pygame.Rect(min_x, min_y, max_x - min_x, max_y - min_y)

# --- Enums ---
class GameState(Enum):
    START_MENU = 1
    EQUIPMENT_SELECT = 2
    PLAYING = 3
    GAME_OVER = 4

class Hand(Enum):
    LEFT = 0
    RIGHT = 1

class EquipmentType(Enum):
    NONE = 0
    SWORD = 1
    DAGGER = 2
    SHIELD = 3

class AIState(Enum):
    IDLE = 1
    CIRCLING = 2
    APPROACHING = 3
    ATTACKING = 4
    FLEEING = 5
    REPOSITIONING = 6
    AVOIDING = 7 # Specific state for avoiding immediate danger

# --- Base Classes ---
class GameObject(pygame.sprite.Sprite):
    def __init__(self, pos, groups=None):
        super().__init__(groups or [])
        self.pos = pygame.Vector2(pos)
        self.image = None # Must be set by subclass
        self.rect = None  # Must be set by subclass

    def update(self, dt):
        pass # Overridden by subclasses

    def draw(self, surface, camera_offset):
        if self.image and self.rect:
            surface.blit(self.image, self.rect.move(camera_offset))

# --- Environment Objects ---
class Cobblestone:
    def __init__(self, pos, radius):
        self.pos = pos
        self.radius = radius
        self.color = random.choice([GREY, DARK_GREY, LIGHT_GREY])

class Obstacle(GameObject):
    def __init__(self, pos, radius, groups):
        super().__init__(pos, groups)
        self.radius = radius
        self.color = DARK_GREY
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, self.color, (self.radius, self.radius), self.radius)
        self.rect = self.image.get_rect(center=self.pos)
        self.is_locked = True # Obstacles don't move

    def draw(self, surface, camera_offset):
         # Adjust position for drawing based on camera
        draw_pos = self.pos + camera_offset
        pygame.draw.circle(surface, self.color, draw_pos, self.radius)
        # Update rect for potential interactions if needed (though locked objects usually don't need it)
        self.rect.center = draw_pos

class TreeTrunk(GameObject):
    def __init__(self, pos, radius, groups):
        super().__init__(pos, groups)
        self.radius = radius
        self.color = BROWN
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, self.color, (self.radius, self.radius), self.radius)
        self.rect = self.image.get_rect(center=self.pos)
        self.is_locked = True

    def draw(self, surface, camera_offset):
        draw_pos = self.pos + camera_offset
        pygame.draw.circle(surface, self.color, draw_pos, self.radius)
        self.rect.center = draw_pos


class TreeFoliage(GameObject):
    def __init__(self, pos, radius, groups):
        super().__init__(pos, groups)
        self.radius = radius
        self.color = GREEN
        self.dark_color = DARK_GREEN
        # Create base image
        self.base_image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.base_image, self.dark_color, (self.radius, self.radius), self.radius)
        pygame.draw.circle(self.base_image, self.color, (self.radius, self.radius), self.radius-3)
        self.image = self.base_image.copy() # Image used for drawing (can change alpha)
        self.rect = self.image.get_rect(center=self.pos)
        self.alpha = 255

    def update_transparency(self, character_rects):
        is_overlapping = False
        for char_rect in character_rects:
             # Use inflated rect for slightly earlier fade
            if self.rect.colliderect(char_rect.inflate(20, 20)):
                is_overlapping = True
                break

        target_alpha = 100 if is_overlapping else 255
        if self.alpha != target_alpha:
            # Simple immediate alpha change, could be smoothed
            self.alpha = target_alpha
            self.image = self.base_image.copy()
            self.image.set_alpha(self.alpha)

    def draw(self, surface, camera_offset):
        draw_pos = self.pos + camera_offset
        self.rect.center = draw_pos # Update rect based on draw pos
        surface.blit(self.image, self.rect.topleft)

class Campfire(GameObject):
    def __init__(self, pos, size, groups):
        super().__init__(pos, groups)
        self.size = size
        self.color_base = BROWN
        self.color_outer = RED
        self.color_inner = YELLOW
        self.bob_time = 0
        self.bob_speed = 3.0
        self.bob_amount = 0.2 # Percentage of height
        self.damage = 0.5 # Damage per second
        self.rect = pygame.Rect(pos[0] - size / 2, pos[1] - size / 2, size, size)
        self.hazard_shape = self.rect # Used for damage collision checks

    def update(self, dt):
        self.bob_time += dt * self.bob_speed

    def draw(self, surface, camera_offset):
        draw_rect = self.rect.move(camera_offset)
        pygame.draw.rect(surface, self.color_base, draw_rect)

        # Calculate triangle points with bobbing
        center_x = draw_rect.centerx
        bottom_y = draw_rect.bottom
        tip_y_base = draw_rect.top
        height = draw_rect.height
        bob_offset = math.sin(self.bob_time) * height * self.bob_amount

        tip_y_outer = tip_y_base - bob_offset
        tip_y_inner = tip_y_base - bob_offset * 0.6 # Inner bobs slightly less

        # Outer Triangle (Red)
        points_outer = [
            (center_x, tip_y_outer),
            (draw_rect.left, bottom_y),
            (draw_rect.right, bottom_y)
        ]
        pygame.draw.polygon(surface, self.color_outer, points_outer)

        # Inner Triangle (Yellow)
        points_inner = [
            (center_x, tip_y_inner),
            (draw_rect.left + self.size * 0.2, bottom_y - self.size*0.1),
            (draw_rect.right - self.size * 0.2, bottom_y - self.size*0.1)
        ]
        pygame.draw.polygon(surface, self.color_inner, points_inner)

class BloodSplatter(GameObject):
    def __init__(self, pos, size, duration=2.0):
        super().__init__(pos)
        self.size = int(size)
        self.duration = duration
        self.timer = 0
        self.color = BLOOD_COLOR
        # Create a simple splatter graphic (random circle)
        self.image = pygame.Surface((self.size*2, self.size*2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, self.color, (self.size, self.size), self.size)
        self.rect = self.image.get_rect(center=self.pos)
        self.initial_alpha = 180
        self.image.set_alpha(self.initial_alpha)


    def update(self, dt):
        self.timer += dt
        if self.timer >= self.duration:
            self.kill() # Remove from sprite group
        else:
            # Fade out
            alpha = int(self.initial_alpha * (1 - (self.timer / self.duration)))
            self.image.set_alpha(max(0, alpha))

    def draw(self, surface, camera_offset):
        surface.blit(self.image, self.rect.move(camera_offset))


# --- Character Related Classes ---
class Arm:
    def __init__(self, character, hand_side):
        self.character = character
        self.hand_side = hand_side # Hand.LEFT or Hand.RIGHT
        self.shoulder_size = SHOULDER_SIZE
        self.base_length = self.shoulder_size / 2 # Minimum length (is shoulder)
        self.max_length = self.base_length # Max potential length (set by equipment/bare hand)
        self.current_length = self.base_length
        self.extend_speed = DEFAULT_ARM_EXTEND_SPEED
        self.retract_speed = DEFAULT_ARM_RETRACT_SPEED
        self.is_extending = False
        self.is_retracting = False
        self.target_angle_offset = 0 # Relative to character angle
        self.current_angle_offset = 0 # Relative to character angle
        self.max_rot_speed = ARM_ROT_SPEED # degrees per second
        self.equipment = EquipmentType.NONE
        self.can_attack_this_swing = False # For bare hands

        # Angle limits relative to character forward direction (0 degrees)
        self.min_angle_offset = -45 # Backwards
        self.max_angle_offset = 135 # Forwards

        self.collision_poly = [] # Store points for collision detection
        self.hand_pos = pygame.Vector2(0, 0)
        self.shoulder_pos = pygame.Vector2(0, 0)

        # Shield specific animation
        self.shield_hit_timer = 0.0
        self.shield_hit_duration = 0.3 # How long the knockback effect lasts
        self.shield_hit_target_offset_delta = -90 # Degrees to rotate back


    def set_equipment(self, equipment_type):
        self.equipment = equipment_type
        if self.equipment == EquipmentType.SWORD:
            self.max_length = DEFAULT_ARM_LENGTH
            self.extend_speed = SWORD_EXTEND_SPEED
            self.retract_speed = DEFAULT_ARM_RETRACT_SPEED # Adjust if needed
        elif self.equipment == EquipmentType.DAGGER:
            self.max_length = DEFAULT_ARM_LENGTH * 0.6 # Daggers are shorter
            self.extend_speed = DAGGER_EXTEND_SPEED
            self.retract_speed = DEFAULT_ARM_RETRACT_SPEED
        elif self.equipment == EquipmentType.SHIELD:
            self.max_length = self.base_length # Shield doesn't really extend arm length itself
            self.extend_speed = 0 # Cannot extend 'arm' with shield
            self.retract_speed = 0
        else: # Bare hand
            self.max_length = DEFAULT_ARM_LENGTH * 0.7 # Punch reach
            self.extend_speed = BARE_HAND_EXTEND_SPEED
            self.retract_speed = DEFAULT_ARM_RETRACT_SPEED * 1.5 # Faster retraction


    def start_extend(self, target_world_angle):
        if self.equipment != EquipmentType.SHIELD: # Shields don't extend
            self.is_extending = True
            self.is_retracting = False
            # Set initial angle towards target, respecting limits
            target_offset = (target_world_angle - self.character.angle + 360) % 360
            # Normalize target_offset to be within -180 to 180 range for comparison
            if target_offset > 180: target_offset -= 360
            self.current_angle_offset = max(self.min_angle_offset, min(self.max_angle_offset, target_offset))
            self.target_angle_offset = self.current_angle_offset # Start aiming where it snaps
            if self.equipment == EquipmentType.NONE:
                self.can_attack_this_swing = True # Enable bare hand attack


    def start_retract(self):
        self.is_extending = False
        self.is_retracting = True
        self.can_attack_this_swing = False


    def update(self, dt, target_world_angle):
         # --- Shield Hit Animation ---
        if self.shield_hit_timer > 0:
            self.shield_hit_timer -= dt
            # Calculate the temporary forced angle offset
            progress = 1.0 - (self.shield_hit_timer / self.shield_hit_duration) # 0 to 1
            forced_offset = self.shield_hit_base_offset + self.shield_hit_target_offset_delta * math.sin(progress * math.pi) # Use sin wave for bounce back
            self.current_angle_offset = forced_offset # Override rotation
            # Keep length retracted during hit? Maybe not necessary.
        else:
            # --- Normal Rotation ---
            # Calculate target offset relative to character angle
            desired_offset = (target_world_angle - self.character.angle + 360) % 360
            # Normalize to -180 to 180 range for limit checking
            if desired_offset > 180: desired_offset -= 360
            # Clamp target offset within limits
            self.target_angle_offset = max(self.min_angle_offset, min(self.max_angle_offset, desired_offset))
            # Smoothly rotate current angle towards target angle
            self.current_angle_offset = angle_lerp(self.current_angle_offset, self.target_angle_offset, self.max_rot_speed / 360.0, dt) # Divide by 360 for normalization factor?


        # --- Extension / Retraction ---
        if self.is_extending:
            if self.current_length < self.max_length:
                self.current_length += self.extend_speed * dt
                if self.current_length >= self.max_length:
                    self.current_length = self.max_length
                    # If bare hand, attack frame is when it hits max length
                    if self.equipment == EquipmentType.NONE:
                        pass # Attack check happens in collision phase
            else: # Reached max length
                 if self.equipment == EquipmentType.NONE:
                      self.can_attack_this_swing = False # Can only hit on the way out/at the end frame

        elif self.is_retracting:
            if self.current_length > self.base_length:
                self.current_length -= self.retract_speed * dt
                if self.current_length <= self.base_length:
                    self.current_length = self.base_length
                    self.is_retracting = False # Finished retracting
            else:
                self.is_retracting = False

        # --- Calculate Geometry ---
        # Shoulder position: rotate offset vector from center
        shoulder_offset_dist = self.character.radius
        shoulder_angle = self.character.angle + (90 if self.hand_side == Hand.LEFT else -90)
        self.shoulder_pos = self.character.pos + pygame.Vector2(shoulder_offset_dist, 0).rotate(shoulder_angle)

        # Hand position: extend from shoulder along arm angle
        total_arm_angle = self.character.angle + self.current_angle_offset
        self.hand_pos = self.shoulder_pos + pygame.Vector2(self.current_length - self.base_length, 0).rotate(total_arm_angle) # Extend from shoulder joint

        # --- Calculate Collision Polygon ---
        arm_width = self.shoulder_size
        arm_vector = pygame.Vector2(1, 0).rotate(total_arm_angle)
        perp_vector = pygame.Vector2(0, 1).rotate(total_arm_angle) # Perpendicular to arm

        # Define corners relative to shoulder pos
        p1 = self.shoulder_pos - perp_vector * arm_width / 2
        p2 = self.shoulder_pos + perp_vector * arm_width / 2
        p3 = p2 + arm_vector * (self.current_length - self.base_length)
        p4 = p1 + arm_vector * (self.current_length - self.base_length)

        # Add weapon/shield geometry if equipped
        if self.equipment == EquipmentType.SWORD or self.equipment == EquipmentType.DAGGER:
            length = SWORD_LENGTH if self.equipment == EquipmentType.SWORD else DAGGER_LENGTH
            width = SWORD_WIDTH if self.equipment == EquipmentType.SWORD else DAGGER_WIDTH
            w_p1 = self.hand_pos - perp_vector * width / 2
            w_p2 = self.hand_pos + perp_vector * width / 2
            w_p3 = w_p2 + arm_vector * length
            w_p4 = w_p1 + arm_vector * length
            self.collision_poly = [p1, p2, w_p3, w_p4] # Combine arm base and weapon blade/handle area approx

        elif self.equipment == EquipmentType.SHIELD:
             # Shield sits tangent at hand position. Its angle is perp to arm angle.
            shield_angle = total_arm_angle + 90 # Angle of the shield's face
            shield_center = self.hand_pos # Place shield center at hand
            half_width_vec = pygame.Vector2(SHIELD_WIDTH / 2, 0).rotate(shield_angle)
            half_height_vec = pygame.Vector2(SHIELD_HEIGHT / 2, 0).rotate(shield_angle + 90) # Perpendicular to face

            s_p1 = shield_center - half_width_vec - half_height_vec
            s_p2 = shield_center + half_width_vec - half_height_vec
            s_p3 = shield_center + half_width_vec + half_height_vec
            s_p4 = shield_center - half_width_vec + half_height_vec
            self.collision_poly = [s_p1, s_p2, s_p3, s_p4]

        else: # Bare hand or just shoulder
            # If arm is extended beyond shoulder, use arm poly, else just shoulder square poly
            if self.current_length > self.base_length:
                 self.collision_poly = [p1, p2, p3, p4]
            else:
                 # Calculate shoulder square polygon based on character angle
                 shoulder_center_offset = pygame.Vector2(self.character.radius, 0).rotate(shoulder_angle)
                 shoulder_center = self.character.pos + shoulder_center_offset
                 half_size_vec_x = pygame.Vector2(self.shoulder_size / 2, 0).rotate(self.character.angle)
                 half_size_vec_y = pygame.Vector2(0, self.shoulder_size / 2).rotate(self.character.angle)

                 sh_p1 = shoulder_center - half_size_vec_x - half_size_vec_y
                 sh_p2 = shoulder_center + half_size_vec_x - half_size_vec_y
                 sh_p3 = shoulder_center + half_size_vec_x + half_size_vec_y
                 sh_p4 = shoulder_center - half_size_vec_x + half_size_vec_y
                 self.collision_poly = [sh_p1, sh_p2, sh_p3, sh_p4]

    def trigger_shield_hit(self):
        """Called when this arm's shield is hit by a weapon."""
        if self.equipment == EquipmentType.SHIELD and self.shield_hit_timer <= 0:
             # Need to store the angle *before* the hit starts
             self.shield_hit_base_offset = self.current_angle_offset
             self.shield_hit_timer = self.shield_hit_duration
             # Arm rotation will be handled in update based on timer

    def draw(self, surface, camera_offset):
        # --- Draw Shoulder ---
        # Calculate shoulder center based on current character pos and angle
        shoulder_offset_dist = self.character.radius
        shoulder_angle = self.character.angle + (90 if self.hand_side == Hand.LEFT else -90)
        shoulder_center = self.character.pos + pygame.Vector2(shoulder_offset_dist, 0).rotate(shoulder_angle)

        # Create a square surface for the shoulder
        shoulder_surf = pygame.Surface((self.shoulder_size, self.shoulder_size), pygame.SRCALPHA)
        shoulder_surf.fill(self.character.color)
        rotated_shoulder = pygame.transform.rotate(shoulder_surf, self.character.angle)
        shoulder_rect = rotated_shoulder.get_rect(center=shoulder_center + camera_offset)
        surface.blit(rotated_shoulder, shoulder_rect)

        # --- Draw Arm Extension ---
        if self.current_length > self.base_length:
            # Draw rectangle from shoulder joint along arm angle
            total_arm_angle = self.character.angle + self.current_angle_offset
            arm_vector = pygame.Vector2(1, 0).rotate(total_arm_angle)
            perp_vector = pygame.Vector2(0, 1).rotate(total_arm_angle)
            arm_width = self.shoulder_size # Arm width is same as shoulder
            arm_draw_length = self.current_length - self.base_length

            # Calculate the 4 points of the arm rectangle polygon
            p1 = self.shoulder_pos - perp_vector * arm_width / 2 + camera_offset
            p2 = self.shoulder_pos + perp_vector * arm_width / 2 + camera_offset
            p3 = p2 + arm_vector * arm_draw_length
            p4 = p1 + arm_vector * arm_draw_length
            pygame.draw.polygon(surface, self.character.color, [p1, p2, p3, p4])

        # --- Draw Equipment ---
        hand_draw_pos = self.hand_pos + camera_offset
        total_arm_angle = self.character.angle + self.current_angle_offset

        if self.equipment == EquipmentType.SWORD or self.equipment == EquipmentType.DAGGER:
            length = SWORD_LENGTH if self.equipment == EquipmentType.SWORD else DAGGER_LENGTH
            width = SWORD_WIDTH if self.equipment == EquipmentType.SWORD else DAGGER_WIDTH
            color = GREY

            # Polygon for the weapon rectangle pointing away from hand
            weapon_vector = pygame.Vector2(1, 0).rotate(total_arm_angle)
            perp_vector = pygame.Vector2(0, 1).rotate(total_arm_angle)

            wp1 = hand_draw_pos - perp_vector * width / 2
            wp2 = hand_draw_pos + perp_vector * width / 2
            wp3 = wp2 + weapon_vector * length
            wp4 = wp1 + weapon_vector * length
            pygame.draw.polygon(surface, color, [wp1, wp2, wp3, wp4])

        elif self.equipment == EquipmentType.SHIELD:
             # Polygon for the shield rectangle tangent at hand
            shield_angle = total_arm_angle + 90 # Angle of the shield's face
            shield_center = hand_draw_pos
            half_width_vec = pygame.Vector2(SHIELD_WIDTH / 2, 0).rotate(shield_angle)
            half_height_vec = pygame.Vector2(SHIELD_HEIGHT / 2, 0).rotate(shield_angle + 90)

            sp1 = shield_center - half_width_vec - half_height_vec
            sp2 = shield_center + half_width_vec - half_height_vec
            sp3 = shield_center + half_width_vec + half_height_vec
            sp4 = shield_center - half_width_vec + half_height_vec
            pygame.draw.polygon(surface, GREY, [sp1, sp2, sp3, sp4])


class Character(GameObject):
    def __init__(self, pos, groups=None):
        super().__init__(pos, groups)
        self.vel = pygame.Vector2(0, 0)
        self.angle = 0.0 # degrees, 0 is right
        self.target_angle = 0.0
        self.body_rot_speed = PLAYER_ROT_SPEED # Can be overridden by child classes
        self.radius = BODY_RADIUS
        self.color = YELLOW
        self.max_hp = MAX_HP
        self.current_hp = self.max_hp
        self.is_dead = False
        self.knockback_vel = pygame.Vector2(0, 0)
        self.knockback_decay = 0.85 # Multiplier per frame

        self.left_arm = Arm(self, Hand.LEFT)
        self.right_arm = Arm(self, Hand.RIGHT)
        self.arms = [self.left_arm, self.right_arm]

        # Simplified collision shape for body-body interaction
        self.collision_radius = self.radius

        # Used for roof transparency check
        self.body_rect_for_roof = pygame.Rect(0,0,0,0)


    def equip(self, left_eq, right_eq):
        self.left_arm.set_equipment(left_eq)
        self.right_arm.set_equipment(right_eq)

    def update(self, dt, all_collidables, hazards):
        if self.is_dead:
            return

        # Apply movement velocity
        self.pos += self.vel * dt

        # Apply and decay knockback
        self.pos += self.knockback_vel * dt
        self.knockback_vel *= self.knockback_decay
        if self.knockback_vel.length_squared() < 1:
            self.knockback_vel = pygame.Vector2(0, 0)

        # Rotate body towards target angle
        self.angle = angle_lerp(self.angle, self.target_angle, self.body_rot_speed / 360.0, dt)

        # Update arms
        mouse_pos = pygame.mouse.get_pos() # Player needs this, pass appropriately for AI
        # Convert mouse pos to world coords if camera is used
        world_mouse_pos = mouse_pos # Assuming no camera for now, adjust if added
        left_target_angle = (pygame.Vector2(world_mouse_pos) - self.left_arm.shoulder_pos).angle_to(pygame.Vector2(1, 0))
        right_target_angle = (pygame.Vector2(world_mouse_pos) - self.right_arm.shoulder_pos).angle_to(pygame.Vector2(1, 0))

        # --- Player specific arm targeting ---
        if isinstance(self, Player):
             mouse_pressed = pygame.mouse.get_pressed()
             if mouse_pressed[0]: # Left mouse
                 self.left_arm.update(dt, left_target_angle)
             else:
                 # Aim non-active arm forward-ish relative to body? or keep last target?
                 idle_target_angle = self.angle + self.left_arm.target_angle_offset # Maintain relative angle
                 self.left_arm.update(dt, idle_target_angle)

             if mouse_pressed[2]: # Right mouse
                  self.right_arm.update(dt, right_target_angle)
             else:
                  idle_target_angle = self.angle + self.right_arm.target_angle_offset
                  self.right_arm.update(dt, idle_target_angle)
        # --- AI specific arm targeting (handled in AI logic) ---
        elif isinstance(self, Enemy):
            # AI will set arm targets based on its state
            # Example: aim at player if attacking
            if self.ai_state == AIState.ATTACKING and self.target_entity:
                 left_target_pos = self.target_entity.pos
                 right_target_pos = self.target_entity.pos
                 # Could add slight offset/prediction based on target movement
                 left_target_angle = (left_target_pos - self.left_arm.shoulder_pos).angle_to(pygame.Vector2(1, 0))
                 right_target_angle = (right_target_pos - self.right_arm.shoulder_pos).angle_to(pygame.Vector2(1, 0))
                 self.left_arm.update(dt, left_target_angle)
                 self.right_arm.update(dt, right_target_angle)
            else: # Idle arm aiming (e.g., point forward relative to body)
                idle_angle = self.angle
                self.left_arm.update(dt, idle_angle)
                self.right_arm.update(dt, idle_angle)


        # Update rect used for roof check (approximates body)
        self.body_rect_for_roof = pygame.Rect(
            self.pos.x - self.radius, self.pos.y - self.radius,
            self.radius * 2, self.radius * 2
        )
        # Check for hazard damage (e.g., campfire)
        for hazard in hazards:
             if hazard.hazard_shape.collidepoint(self.pos):
                  self.take_damage(hazard.damage * dt, hazard.pos, apply_knockback=False) # Damage over time


    def apply_force(self, force_vector):
        # Simplified physics: directly add to knockback velocity
        self.knockback_vel += force_vector

    def apply_knockback(self, amount, source_pos):
        if self.pos == source_pos: # Avoid division by zero if source is self center
             direction = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
        else:
             direction = normalize_vector(self.pos - source_pos)
        self.apply_force(direction * amount)

    def take_damage(self, amount, damage_source_pos, apply_knockback=True):
        if self.is_dead:
            return
        self.current_hp -= amount
        print(f"{type(self).__name__} took {amount:.1f} damage, HP: {self.current_hp:.1f}/{self.max_hp}")

        # Add blood splatter effect
        splatter_size = 5 + amount * 5 # Scale size with damage
        if 'blood_splatters_group' in self.groups()[0].game.sprite_groups: # Access game instance safely
             splatter = BloodSplatter(self.pos + pygame.Vector2(random.uniform(-10, 10), random.uniform(-10, 10)), splatter_size)
             self.groups()[0].game.sprite_groups['blood_splatters_group'].add(splatter)


        if apply_knockback:
            self.apply_knockback(KNOCKBACK_DAMAGE, damage_source_pos)

        if self.current_hp <= 0:
            self.die()

    def die(self):
        print(f"{type(self).__name__} died.")
        self.is_dead = True
        self.current_hp = 0
        # Could add death animation/effect here
        # Player death handled in Game class
        if isinstance(self, Enemy):
            self.kill() # Remove enemy sprite from groups
            self.groups()[0].game.player_kills += 1 # Increment kill count


    def draw(self, surface, camera_offset):
        if self.is_dead: return

        draw_pos = self.pos + camera_offset

        # Draw Body Circle
        pygame.draw.circle(surface, self.color, draw_pos, self.radius)
        # Optional: Draw outline
        pygame.draw.circle(surface, BLACK, draw_pos, self.radius, 1)

        # Draw Arms (Shoulders + Extensions + Equipment)
        self.left_arm.draw(surface, camera_offset)
        self.right_arm.draw(surface, camera_offset)

        # Draw Health (for enemies)
        if isinstance(self, Enemy):
            draw_text(surface, str(int(self.current_hp)), 20, draw_pos.x, draw_pos.y, WHITE, center=True)

    # --- Collision Shapes for Physics ---
    def get_collision_shapes(self):
        """Returns a list of shapes for collision checking: [('type', geometry, owner_object)]"""
        shapes = []
        # Body: Use self.pos as geometry, self (the Character instance) as owner
        shapes.append(('circle', self.pos, self))

        # Arms: Use arm.collision_poly as geometry, the arm instance as owner
        if self.left_arm.collision_poly:
            shapes.append(('poly', self.left_arm.collision_poly, self.left_arm))
        if self.right_arm.collision_poly:
            shapes.append(('poly', self.right_arm.collision_poly, self.right_arm))
        return shapes



class Player(Character):
    def __init__(self, pos, groups=None):
        super().__init__(pos, groups)
        self.body_rot_speed = PLAYER_ROT_SPEED
        self.speed = PLAYER_SPEED
        self.is_aiming = False # Body rotation fixed when aiming/attacking

    def update(self, dt, all_collidables, hazards):
        # --- Movement Input ---
        keys = pygame.key.get_pressed()
        move_dir = pygame.Vector2(0, 0)
        if keys[pygame.K_w]:
            move_dir.y -= 1
        if keys[pygame.K_s]:
            move_dir.y += 1
        if keys[pygame.K_a]:
            move_dir.x -= 1
        if keys[pygame.K_d]:
            move_dir.x += 1

        move_dir = normalize_vector(move_dir)
        self.vel = move_dir * self.speed

        # --- Rotation and Arm Control Input ---
        mouse_buttons = pygame.mouse.get_pressed()
        mouse_pos_screen = pygame.mouse.get_pos()
        # Convert mouse screen coordinates to world coordinates if camera exists
        # world_mouse_pos = screen_to_world(mouse_pos_screen, camera_offset)
        world_mouse_pos = pygame.Vector2(mouse_pos_screen) # No camera yet

        self.is_aiming = mouse_buttons[0] or mouse_buttons[2]

        if not self.is_aiming:
            # Rotate body towards cursor when not attacking
            direction_to_mouse = world_mouse_pos - self.pos
            if direction_to_mouse.length() > 0:
                self.target_angle = direction_to_mouse.angle_to(pygame.Vector2(1, 0))
        # Else: Body angle remains fixed while aiming/attacking

        # --- Arm Actions ---
        left_target_angle = (world_mouse_pos - self.left_arm.shoulder_pos).angle_to(pygame.Vector2(1, 0))
        right_target_angle = (world_mouse_pos - self.right_arm.shoulder_pos).angle_to(pygame.Vector2(1, 0))

        if mouse_buttons[0]: # Left click - extend/aim left arm
            if not self.left_arm.is_extending:
                 self.left_arm.start_extend(left_target_angle)
        else:
            if self.left_arm.is_extending: # Button released
                 self.left_arm.start_retract()

        if mouse_buttons[2]: # Right click - extend/aim right arm
             if not self.right_arm.is_extending:
                 self.right_arm.start_extend(right_target_angle)
        else:
             if self.right_arm.is_extending: # Button released
                 self.right_arm.start_retract()

        # Call parent update AFTER handling input (sets vel, target_angle, arm states)
        super().update(dt, all_collidables, hazards) # Handles movement, rotation, arm updates

    def draw_ui(self, surface):
         # Health Bar Bottom Left
        bar_width = 200
        bar_height = 20
        hp_percent = self.current_hp / self.max_hp
        current_width = int(bar_width * hp_percent)

        pygame.draw.rect(surface, DARK_RED, (10, SCREEN_HEIGHT - bar_height - 10, bar_width, bar_height))
        if current_width > 0:
            pygame.draw.rect(surface, GREEN, (10, SCREEN_HEIGHT - bar_height - 10, current_width, bar_height))
        pygame.draw.rect(surface, WHITE, (10, SCREEN_HEIGHT - bar_height - 10, bar_width, bar_height), 2) # Outline
        draw_text(surface, f"HP: {int(self.current_hp)}/{self.max_hp}", 18, 15, SCREEN_HEIGHT - bar_height - 8)

    def die(self):
        super().die()
        # Player specific death logic handled in Game class (game over state)


class Enemy(Character):
    def __init__(self, pos, groups=None, ai_profile="standard"):
        super().__init__(pos, groups)
        self.body_rot_speed = ENEMY_ROT_SPEED
        self.speed = ENEMY_SPEED
        self.color = RED # Distinguish from player
        self.ai_state = AIState.IDLE
        self.ai_profile = ai_profile # e.g., "aggressive", "circler", "tester"
        self.state_timer = random.uniform(1.0, 3.0)
        self.target_entity = None # Usually the player
        self.aggro_radius = 400
        self.attack_radius = (BODY_RADIUS + DEFAULT_ARM_LENGTH + SWORD_LENGTH) * 0.8 # Approx attack range
        self.preferred_circling_distance = random.uniform(150, 250)
        self.avoid_radius = 80 # How close to check for avoidance

        # AI specific targets
        self.move_target_pos = None
        self.circling_angle_offset = random.uniform(0, 360) # For circling direction
        self.circling_direction = random.choice([-1, 1])

        # Attack timing
        self.attack_cooldown = 0.0
        self.min_attack_interval = 1.0
        self.max_attack_interval = 3.0


    def update(self, dt, all_collidables, hazards):
        if self.is_dead: return

        self.state_timer -= dt
        self.attack_cooldown -= dt

        # --- Find Target (Player) ---
        # This assumes the player is the only target. Could be expanded.
        if not self.target_entity or self.target_entity.is_dead:
            # Find the player instance (assuming one player)
            player = None
            for entity in all_collidables:
                if isinstance(entity, Player):
                    player = entity
                    break
            self.target_entity = player

        if not self.target_entity:
            self.vel = pygame.Vector2(0,0) # No target, stop moving
            # Stay idle or wander slightly maybe?
            if self.ai_state != AIState.IDLE:
                self.change_state(AIState.IDLE)
        else:
             # --- AI State Machine ---
             self.run_ai(dt, all_collidables, hazards)

        # Call parent update AFTER AI logic (sets vel, target_angle, arm states)
        super().update(dt, all_collidables, hazards)

    def run_ai(self, dt, all_collidables, hazards):
        player_dist = (self.target_entity.pos - self.pos).length()
        direction_to_player = normalize_vector(self.target_entity.pos - self.pos)

        # --- Hazard Avoidance (High Priority) ---
        avoid_vector = pygame.Vector2(0, 0)
        num_avoiding = 0
        for hazard in hazards:
            dist_sq = (hazard.pos - self.pos).length_squared()
            avoid_dist_sq = (self.avoid_radius + hazard.size/2)**2 # Approx check distance
            if dist_sq < avoid_dist_sq and dist_sq > 0:
                # Move directly away from hazard center
                avoid_vector += normalize_vector(self.pos - hazard.pos)
                num_avoiding += 1

        if num_avoiding > 0:
             avoid_vector = normalize_vector(avoid_vector)
             self.vel = avoid_vector * self.speed * 1.5 # Flee faster
             self.target_angle = avoid_vector.angle_to(pygame.Vector2(1,0)) # Face away
             if self.ai_state != AIState.AVOIDING:
                   self.change_state(AIState.AVOIDING)
             # Skip other behaviours while actively avoiding immediate danger
             return
        elif self.ai_state == AIState.AVOIDING:
            # Finished avoiding, transition back
            self.change_state(AIState.IDLE) # Or previous state?


        # --- State Transitions ---
        if self.ai_state == AIState.IDLE:
            self.vel = pygame.Vector2(0, 0)
            self.target_angle = (self.target_entity.pos - self.pos).angle_to(pygame.Vector2(1, 0)) # Look at player
            if player_dist < self.aggro_radius:
                 # Decide next action based on profile maybe
                 if self.ai_profile == "aggressive":
                     self.change_state(AIState.APPROACHING)
                 elif self.ai_profile == "circler":
                     self.change_state(AIState.CIRCLING)
                 else: # Standard/Tester mix
                     self.change_state(random.choice([AIState.CIRCLING, AIState.APPROACHING, AIState.REPOSITIONING]))
            # Reset arms
            if self.left_arm.is_extending: self.left_arm.start_retract()
            if self.right_arm.is_extending: self.right_arm.start_retract()


        elif self.ai_state == AIState.CIRCLING:
            # Maintain distance, move tangentially
            self.target_angle = direction_to_player.angle_to(pygame.Vector2(1, 0)) # Keep facing player

            # Vector perpendicular to player direction
            tangent_vector = direction_to_player.rotate(90 * self.circling_direction)

            # Adjust velocity to maintain distance
            dist_error = player_dist - self.preferred_circling_distance
            radial_vel = direction_to_player * dist_error * 0.5 # Move towards/away from player slowly
            tangential_vel = tangent_vector * self.speed

            self.vel = normalize_vector(tangential_vel + radial_vel) * self.speed

            if self.state_timer <= 0:
                # Change behaviour: approach, keep circling, reposition?
                next_state = random.choices(
                    [AIState.APPROACHING, AIState.CIRCLING, AIState.REPOSITIONING],
                    weights=[0.5, 0.3, 0.2], k=1)[0]
                self.change_state(next_state)
                if next_state == AIState.CIRCLING: # Change direction sometimes
                    if random.random() < 0.3: self.circling_direction *= -1
            # Consider attacking if player gets too close during circling
            elif player_dist < self.attack_radius * 1.2 and self.attack_cooldown <= 0:
                 if random.random() < 0.1: # Low chance to attack from circling
                     self.change_state(AIState.ATTACKING)


        elif self.ai_state == AIState.APPROACHING:
            # Move towards player
            self.target_angle = direction_to_player.angle_to(pygame.Vector2(1, 0))
            self.vel = direction_to_player * self.speed

            if player_dist <= self.attack_radius:
                self.change_state(AIState.ATTACKING)
            elif self.state_timer <= 0: # Took too long? Re-evaluate.
                self.change_state(AIState.IDLE) # Go back to idle/circling


        elif self.ai_state == AIState.ATTACKING:
            self.vel = pygame.Vector2(0, 0) # Stop to attack
            self.target_angle = direction_to_player.angle_to(pygame.Vector2(1, 0)) # Face player

            # Simple attack logic: swing one weapon if cooldown ready
            if self.attack_cooldown <= 0:
                # Choose which arm to swing (the one with a weapon preferably)
                can_attack_left = self.left_arm.equipment not in [EquipmentType.SHIELD, EquipmentType.NONE]
                can_attack_right = self.right_arm.equipment not in [EquipmentType.SHIELD, EquipmentType.NONE]
                chosen_arm = None
                if can_attack_left and can_attack_right:
                    chosen_arm = random.choice([self.left_arm, self.right_arm])
                elif can_attack_left:
                    chosen_arm = self.left_arm
                elif can_attack_right:
                    chosen_arm = self.right_arm
                # Else: Has no weapons? Should retreat or use bare hands if implemented for AI

                if chosen_arm:
                    target_pos = self.target_entity.pos # Aim at player center
                    arm_target_angle = (target_pos - chosen_arm.shoulder_pos).angle_to(pygame.Vector2(1, 0))
                    chosen_arm.start_extend(arm_target_angle)
                    self.attack_cooldown = random.uniform(self.min_attack_interval, self.max_attack_interval)
                    self.state_timer = 0.5 # Short timer in attack state after swing
                else:
                    # No weapon equipped? Maybe try bare hand or retreat
                    self.change_state(AIState.REPOSITIONING) # Step back


            # Retract arms automatically after extension finishes
            for arm in self.arms:
                 if arm.is_extending and arm.current_length >= arm.max_length:
                       arm.start_retract()
                 elif not arm.is_extending and not arm.is_retracting and arm.current_length > arm.base_length:
                       # If arm is just hanging out extended (e.g. interrupted), retract it
                       arm.start_retract()

            # Decide next action after attacking or timer runs out
            if self.state_timer <= 0:
                 # Should we reposition, circle, or keep attacking?
                 if player_dist > self.attack_radius * 1.5: # Player moved away
                      self.change_state(AIState.APPROACHING)
                 else:
                      next_state = random.choices(
                           [AIState.REPOSITIONING, AIState.CIRCLING, AIState.ATTACKING],
                           weights=[0.5, 0.3, 0.2], k=1)[0]
                      self.change_state(next_state)


        elif self.ai_state == AIState.REPOSITIONING:
            # "Testing distance" behaviour - step back or forward
            if self.move_target_pos is None: # Just entered state
                # Decide whether to step back or slightly adjust sideways/forward
                if random.random() < 0.7 or player_dist < self.attack_radius * 0.8: # Mostly step back
                    step_dir = -direction_to_player
                else: # Step sideways or slightly forward
                    step_dir = direction_to_player.rotate(random.uniform(-60, 60))
                self.move_target_pos = self.pos + step_dir * random.uniform(50, 100)

            # Move towards target position
            move_vec = self.move_target_pos - self.pos
            if move_vec.length() < 10 or self.state_timer <= 0:
                # Reached target or timer expired
                self.vel = pygame.Vector2(0,0)
                self.move_target_pos = None
                # Decide next state (often back to circling or approaching)
                self.change_state(random.choice([AIState.CIRCLING, AIState.IDLE, AIState.APPROACHING]))
            else:
                self.vel = normalize_vector(move_vec) * self.speed * 0.8 # Reposition slower
                self.target_angle = direction_to_player.angle_to(pygame.Vector2(1, 0)) # Keep looking at player


    def change_state(self, new_state):
        if self.ai_state != new_state:
            # print(f"Enemy changing from {self.ai_state.name} to {new_state.name}") # Debug
            self.ai_state = new_state
            # Reset timers/targets based on new state
            if new_state == AIState.IDLE:
                self.state_timer = random.uniform(0.5, 1.5)
            elif new_state == AIState.CIRCLING:
                self.state_timer = random.uniform(2.0, 5.0)
                self.preferred_circling_distance = random.uniform(150, 250) # Re-randomize?
            elif new_state == AIState.APPROACHING:
                self.state_timer = random.uniform(3.0, 6.0) # Time limit to reach player
            elif new_state == AIState.ATTACKING:
                self.state_timer = 0.5 # Duration of attack *attempt* before re-evaluating
                self.vel = pygame.Vector2(0,0)
            elif new_state == AIState.REPOSITIONING:
                self.state_timer = random.uniform(0.5, 1.5)
                self.move_target_pos = None # Will be set on first frame of state
            elif new_state == AIState.AVOIDING:
                 self.state_timer = 0.2 # Short timer, will exit once hazard is clear


# --- Collision Handling ---
def collide_circle_circle(pos1, r1, pos2, r2):
    return (pos1 - pos2).length_squared() <= (r1 + r2)**2

def collide_circle_poly(circle_pos, circle_r, poly_points):
    """Basic circle-polygon collision detection."""
    if not poly_points: return False

    # 1. Check if circle center is inside polygon (using point_in_poly check)
    # TODO: Implement point_in_poly if needed (more complex)

    # 2. Check if any polygon vertex is inside the circle
    for p in poly_points:
        if (pygame.Vector2(p) - circle_pos).length_squared() <= circle_r**2:
            return True

    # 3. Check if circle intersects any polygon edge
    for i in range(len(poly_points)):
        p1 = pygame.Vector2(poly_points[i])
        p2 = pygame.Vector2(poly_points[(i + 1) % len(poly_points)])
        # Find closest point on line segment (p1, p2) to circle_pos
        line_vec = p2 - p1
        len_sq = line_vec.length_squared()
        if len_sq == 0: continue # Skip zero-length segments

        t = ((circle_pos - p1).dot(line_vec)) / len_sq
        t = max(0, min(1, t)) # Clamp to segment

        closest_point = p1 + line_vec * t
        if (closest_point - circle_pos).length_squared() <= circle_r**2:
            return True

    return False


def collide_poly_poly(poly1_points, poly2_points):
    """Placeholder for SAT (Separating Axis Theorem) collision."""
    # SAT is complex. Using simple Rect overlap as a *very rough* approximation for now.
    # This will have many false positives and inaccuracies with rotated shapes.
    # For a real implementation, a proper SAT library or function is needed.
    if not poly1_points or not poly2_points: return False
    rect1 = get_polygon_rect(poly1_points)
    rect2 = get_polygon_rect(poly2_points)
    return rect1.colliderect(rect2)


def handle_collisions(entities, obstacles):
    # ... (broadphase setup) ...

    # --- Entity vs Entity Collisions ---
    entity_list = list(entities)
    for i in range(len(entity_list)):
        e1 = entity_list[i]
        if e1.is_dead: continue

        for j in range(i + 1, len(entity_list)):
            e2 = entity_list[j]
            if e2.is_dead: continue

            # ... (pair checking) ...

            shapes1 = e1.get_collision_shapes()
            shapes2 = e2.get_collision_shapes()

            collision_occurred = False
            collision_point = None
            collider1_obj = None # The object part (Character or Arm)
            collider2_obj = None
            collider1_geom = None # The geometry part (pos or poly)
            collider2_geom = None

            for s1_type, s1_geom, s1_obj in shapes1: # Correct unpacking
                for s2_type, s2_geom, s2_obj in shapes2: # Correct unpacking

                    collided = False
                    # --- Perform collision check based on types ---
                    if s1_type == 'circle' and s2_type == 'circle':
                        # Pass positions and radii from the objects
                        collided = collide_circle_circle(s1_geom, s1_obj.collision_radius, s2_geom, s2_obj.collision_radius)
                        if collided: collision_point = (s1_geom + s2_geom) / 2
                    elif s1_type == 'circle' and s2_type == 'poly':
                        collided = collide_circle_poly(s1_geom, s1_obj.collision_radius, s2_geom)
                        if collided: collision_point = s1_geom # Approx point
                    elif s1_type == 'poly' and s2_type == 'circle':
                        collided = collide_circle_poly(s2_geom, s2_obj.collision_radius, s1_geom)
                        if collided: collision_point = s2_geom # Approx point
                    elif s1_type == 'poly' and s2_type == 'poly':
                        collided = collide_poly_poly(s1_geom, s2_geom) # Uses basic rect overlap approx
                        if collided:
                            # Convert centers to vectors for midpoint calculation
                            center1 = pygame.Vector2(get_polygon_rect(s1_geom).center)
                            center2 = pygame.Vector2(get_polygon_rect(s2_geom).center)
                            collision_point = (center1 + center2) / 2
                    # --- Handle Collision Response ---
                    if collided:
                        collision_occurred = True
                        collider1_obj = s1_obj # Store the object
                        collider2_obj = s2_obj
                        collider1_geom = s1_geom # Store geometry if needed later
                        collider2_geom = s2_geom
                        break
                if collision_occurred:
                    break

            # --- Apply Effects based on Collision ---
            if collision_occurred and collision_point:
                # 1. General Knockback
                e1.apply_knockback(KNOCKBACK_SELF_COLLIDE / 2, collision_point)
                e2.apply_knockback(KNOCKBACK_SELF_COLLIDE / 2, collision_point)

                # 2. Damage and Weapon Effects (Use collider1_obj, collider2_obj)
                arm1 = collider1_obj if isinstance(collider1_obj, Arm) else None
                arm2 = collider2_obj if isinstance(collider2_obj, Arm) else None
                body1_hit = isinstance(collider1_obj, Character)
                body2_hit = isinstance(collider2_obj, Character)

                # ... (rest of the damage/shield logic using arm1, arm2, body1_hit, body2_hit) ...
                # Example:
                if arm1 and arm1.equipment in [EquipmentType.SWORD, EquipmentType.DAGGER]:
                     if arm2 and arm2.equipment == EquipmentType.SHIELD:
                         arm2.trigger_shield_hit()
                         e1.apply_knockback(KNOCKBACK_SELF_COLLIDE * 0.5, collision_point)
                     else: # Hit body or non-shield arm
                         damage = 1.0 # Damage per tick (frame)
                         e2.take_damage(damage, e1.pos)
                # ... etc ...


    # --- Entity vs Obstacle Collisions ---
    for entity in entities:
        if entity.is_dead: continue
        entity_shapes = entity.get_collision_shapes()

        for obstacle in obstacles:
             # Obstacle is assumed to be a circle here
             obstacle_pos = obstacle.pos
             obstacle_radius = obstacle.radius

             for e_type, e_geom, e_obj in entity_shapes: # Correct unpacking
                 collided = False
                 collision_normal = None
                 overlap = 0

                 if e_type == 'circle':
                     # e_geom is the position (Vector2), e_obj is the Character
                     # Pass the correct position and radius for the entity circle
                     collided = collide_circle_circle(e_geom, e_obj.collision_radius, obstacle_pos, obstacle_radius)
                     if collided:
                         collision_normal = normalize_vector(e_geom - obstacle_pos)
                         # Calculate overlap
                         dist = (e_geom - obstacle_pos).length()
                         overlap = (e_obj.collision_radius + obstacle_radius) - dist

                 elif e_type == 'poly':
                      # e_geom is the list of polygon points, e_obj is the Arm
                      poly_points = e_geom
                      if not poly_points: continue # Skip if poly is empty

                      # Use circle approx for entity arm vs obstacle circle for simplicity
                      poly_center = pygame.Vector2(sum(p[0] for p in poly_points)/len(poly_points), sum(p[1] for p in poly_points)/len(poly_points))
                      poly_radius = max((pygame.Vector2(p) - poly_center).length() for p in poly_points)

                      collided = collide_circle_circle(poly_center, poly_radius, obstacle_pos, obstacle_radius)
                      if collided:
                          collision_normal = normalize_vector(poly_center - obstacle_pos)
                          # Calculate overlap for the approximation
                          dist = (poly_center - obstacle_pos).length()
                          overlap = (poly_radius + obstacle_radius) - dist

                 # Resolve collision: Push entity out of obstacle
                 if collided and collision_normal and overlap > 0:
                      entity.pos += collision_normal * overlap
                      # Dampen velocity component into the obstacle
                      vel_proj = entity.vel.dot(collision_normal)
                      if vel_proj < 0: # Only dampen if moving towards obstacle
                           entity.vel -= collision_normal * vel_proj * 1.1 # Slight bounce effect

                      knockback_proj = entity.knockback_vel.dot(collision_normal)
                      if knockback_proj < 0:
                           entity.knockback_vel -= collision_normal * knockback_proj * 1.1

                      break # Only resolve one collision per entity-obstacle pair per frame


# --- Button Class for UI ---
class Button:
    def __init__(self, x, y, width, height, text, callback, color=GREY, hover_color=LIGHT_GREY):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.color = color
        self.hover_color = hover_color
        self.is_hovered = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.callback:
                    self.callback()
                return True # Event handled
        elif event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        return False

    def draw(self, surface):
        color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(surface, color, self.rect)
        pygame.draw.rect(surface, WHITE, self.rect, 2) # Outline
        draw_text(surface, self.text, 30, self.rect.centerx, self.rect.centery, BLACK, center=True)

# --- Game Class ---
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Top Down Circle Fighter")
        self.clock = pygame.time.Clock()
        self.running = True
        self.game_state = GameState.START_MENU
        self.player = None
        self.player_kills = 0
        self.game_time = 0.0
        self.campfire = None # <--- ADD THIS LINE

        # Sprite Groups (Layering)
        self.sprite_groups = {
            "ground_effects": pygame.sprite.Group(), # Campfire gfx, splatters
            "collidables": pygame.sprite.Group(),    # Player, Enemies, Obstacles
            "obstacles": pygame.sprite.Group(),      # Static obstacles only
            "characters": pygame.sprite.Group(),     # Player, Enemies
            "roof_objects": pygame.sprite.Group(),   # Tree foliage
            "hazards": pygame.sprite.Group(),        # Campfire (for damage check)
            "blood_splatters_group": pygame.sprite.Group(), # For drawing splatters
            "all_draw": pygame.sprite.Group()        # For potentially easier drawing? maybe remove
        }
        # Pass self to groups if needed for callbacks/access
        for group in self.sprite_groups.values():
            group.game = self # Give groups access back to the main game instance

        self.ground_cobblestones = []
        self.setup_start_menu()
        self.selected_equipment = {Hand.LEFT: EquipmentType.NONE, Hand.RIGHT: EquipmentType.NONE}
        self.spawn_timer = INITIAL_SPAWN_DELAY
        self.high_score = self.load_highscore()


    def load_highscore(self):
        try:
            with open("highscore.txt", "r") as f:
                return int(f.read())
        except (FileNotFoundError, ValueError):
            return 0

    def save_highscore(self):
         if self.player_kills > self.high_score:
              self.high_score = self.player_kills
              try:
                  with open("highscore.txt", "w") as f:
                      f.write(str(self.high_score))
              except IOError:
                   print("Error saving highscore.")


    def setup_start_menu(self):
        self.start_menu_buttons = []
        play_button = Button(SCREEN_WIDTH / 2 - 100, SCREEN_HEIGHT / 2 + 0, 200, 50, "Play", self.go_to_equipment_select)
        quit_button = Button(SCREEN_WIDTH / 2 - 100, SCREEN_HEIGHT / 2 + 70, 200, 50, "Quit", self.quit_game)
        self.start_menu_buttons.extend([play_button, quit_button])

    def setup_equipment_select(self):
        self.equip_buttons = []
        self.selected_equipment = {Hand.LEFT: EquipmentType.NONE, Hand.RIGHT: EquipmentType.NONE}
        spacing = 60
        button_width = 100
        button_height = 40
        start_y = SCREEN_HEIGHT / 2 - 100

        # Left Hand Options
        y = start_y
        x = SCREEN_WIDTH / 2 - 150 - button_width / 2
        self.equip_buttons.append(Button(x, y, button_width, button_height, "Bare Hand", lambda: self.select_equip(Hand.LEFT, EquipmentType.NONE)))
        y += spacing
        self.equip_buttons.append(Button(x, y, button_width, button_height, "Sword", lambda: self.select_equip(Hand.LEFT, EquipmentType.SWORD)))
        y += spacing
        self.equip_buttons.append(Button(x, y, button_width, button_height, "Dagger", lambda: self.select_equip(Hand.LEFT, EquipmentType.DAGGER)))
        y += spacing
        self.equip_buttons.append(Button(x, y, button_width, button_height, "Shield", lambda: self.select_equip(Hand.LEFT, EquipmentType.SHIELD)))

        # Right Hand Options
        y = start_y
        x = SCREEN_WIDTH / 2 + 150 - button_width / 2
        self.equip_buttons.append(Button(x, y, button_width, button_height, "Bare Hand", lambda: self.select_equip(Hand.RIGHT, EquipmentType.NONE)))
        y += spacing
        self.equip_buttons.append(Button(x, y, button_width, button_height, "Sword", lambda: self.select_equip(Hand.RIGHT, EquipmentType.SWORD)))
        y += spacing
        self.equip_buttons.append(Button(x, y, button_width, button_height, "Dagger", lambda: self.select_equip(Hand.RIGHT, EquipmentType.DAGGER)))
        y += spacing
        self.equip_buttons.append(Button(x, y, button_width, button_height, "Shield", lambda: self.select_equip(Hand.RIGHT, EquipmentType.SHIELD)))

        # Start Game Button
        self.start_game_button = Button(SCREEN_WIDTH / 2 - 100, SCREEN_HEIGHT - 100, 200, 50, "Start Game", self.start_playing_if_valid)
        self.equip_buttons.append(self.start_game_button)
        self.equip_error_message = ""


    def select_equip(self, hand, equip_type):
        self.selected_equipment[hand] = equip_type
        # Basic validation feedback: Cannot have two shields
        if self.selected_equipment[Hand.LEFT] == EquipmentType.SHIELD and self.selected_equipment[Hand.RIGHT] == EquipmentType.SHIELD:
             self.equip_error_message = "Cannot equip two shields!"
             # Maybe reset the selection or force user to change one
             # self.selected_equipment[hand] = EquipmentType.NONE # Revert last selection
        else:
            self.equip_error_message = ""


    def start_playing_if_valid(self):
        # Check validity (e.g., no two shields)
        if self.selected_equipment[Hand.LEFT] == EquipmentType.SHIELD and self.selected_equipment[Hand.RIGHT] == EquipmentType.SHIELD:
            self.equip_error_message = "Cannot start with two shields!"
            return
        # Could add check: must have at least one weapon? (User choice for now)

        self.equip_error_message = ""
        self.start_playing()

    def go_to_equipment_select(self):
        self.game_state = GameState.EQUIPMENT_SELECT
        self.setup_equipment_select()

    def start_playing(self):
        # --- Reset Game World ---
        self.game_time = 0.0
        self.player_kills = 0
        for group in self.sprite_groups.values():
            group.empty() # Clear all sprites
        self.ground_cobblestones = [] # Clear ground graphics

        # --- Create Player ---
        self.player = Player((SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2),
                             [self.sprite_groups["collidables"], self.sprite_groups["characters"]])
        self.player.equip(self.selected_equipment[Hand.LEFT], self.selected_equipment[Hand.RIGHT])

        # --- Create Environment ---
        # Cobblestone Ground
        for _ in range(300): # Adjust density as needed
            x = random.randint(-200, SCREEN_WIDTH + 200) # Extend beyond screen for camera movement
            y = random.randint(-200, SCREEN_HEIGHT + 200)
            r = random.randint(5, 25)
            self.ground_cobblestones.append(Cobblestone((x, y), r))

        # Obstacles (Rocks)
        for _ in range(10):
            x = random.randint(50, SCREEN_WIDTH - 50)
            y = random.randint(50, SCREEN_HEIGHT - 50)
            # Ensure not spawning on player start
            if abs(x - SCREEN_WIDTH/2) < 100 and abs(y - SCREEN_HEIGHT/2) < 100:
                 x += random.choice([-150, 150]) # Push away
            radius = random.randint(20, 40)
            obs = Obstacle((x, y), radius, [self.sprite_groups["collidables"], self.sprite_groups["obstacles"]])

         # Trees (Trunk in object layer, Foliage in roof layer)
        for _ in range(8):
             x = random.randint(50, SCREEN_WIDTH - 50)
             y = random.randint(50, SCREEN_HEIGHT - 50)
             if abs(x - SCREEN_WIDTH/2) < 100 and abs(y - SCREEN_HEIGHT/2) < 100:
                  x += random.choice([-200, 200])
             trunk_radius = random.randint(15, 25)
             foliage_radius = trunk_radius * 2.5
             # Trunk collides
             trunk = TreeTrunk((x, y), trunk_radius, [self.sprite_groups["collidables"], self.sprite_groups["obstacles"]])
             # Foliage drawn last, handles transparency
             foliage = TreeFoliage((x, y - trunk_radius * 0.5), foliage_radius, self.sprite_groups["roof_objects"]) # Foliage slightly higher

        # Campfire
        campfire_pos = (SCREEN_WIDTH * 0.8, SCREEN_HEIGHT * 0.2)
        self.campfire = Campfire(campfire_pos, 50, [self.sprite_groups["hazards"]])


        self.spawn_timer = INITIAL_SPAWN_DELAY
        self.game_state = GameState.PLAYING


    def go_to_game_over(self):
        self.save_highscore()
        self.game_state = GameState.GAME_OVER

    def go_to_start_menu(self):
        self.game_state = GameState.START_MENU
        self.setup_start_menu() # Recreate buttons

    def quit_game(self):
        self.running = False

    # --- Spawning Logic ---
    def update_spawning(self, dt):
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            num_enemies = len(self.sprite_groups["characters"]) -1 # Exclude player
            if num_enemies < MAX_ACTIVE_ENEMIES:
                self.spawn_enemy()

                # Calculate next spawn time dynamically
                time_reduction = self.game_time * SPAWN_TIME_FACTOR
                count_reduction = (MAX_ACTIVE_ENEMIES - num_enemies) * SPAWN_COUNT_FACTOR
                current_interval = BASE_SPAWN_INTERVAL - time_reduction - count_reduction
                self.spawn_timer = max(MIN_SPAWN_INTERVAL, current_interval)
                # Add some randomness
                self.spawn_timer += random.uniform(-0.5, 0.5)
            else:
                 # Max enemies reached, check again later
                 self.spawn_timer = 1.0 # Check every second if max capacity


    def spawn_enemy(self):
         # Spawn outside screen bounds
        side = random.choice(['top', 'bottom', 'left', 'right'])
        x, y = 0, 0
        margin = 50 # Distance outside screen
        if side == 'top':
            x = random.randint(-margin, SCREEN_WIDTH + margin)
            y = -margin
        elif side == 'bottom':
            x = random.randint(-margin, SCREEN_WIDTH + margin)
            y = SCREEN_HEIGHT + margin
        elif side == 'left':
            x = -margin
            y = random.randint(-margin, SCREEN_HEIGHT + margin)
        elif side == 'right':
            x = SCREEN_WIDTH + margin
            y = random.randint(-margin, SCREEN_HEIGHT + margin)

        # Choose random AI profile
        ai_profile = random.choice(["standard", "aggressive", "circler", "tester"])

        enemy = Enemy((x, y), [self.sprite_groups["collidables"], self.sprite_groups["characters"]], ai_profile=ai_profile)

        # Randomly equip enemy (no two shields, must have weapon)
        possible_weapons = [EquipmentType.SWORD, EquipmentType.DAGGER]
        possible_offhands = [EquipmentType.SHIELD, EquipmentType.NONE] # Could add dual wield later

        left = random.choice(possible_weapons)
        right = EquipmentType.NONE
        if random.random() < 0.6: # Chance to have something in offhand
            right = random.choice(possible_offhands)
            # If offhand is shield, ensure main hand is not shield (already guaranteed)
            # If offhand is another weapon (dual wield - not implemented yet)
        enemy.equip(left, right)

        print(f"Spawned Enemy at ({int(x)},{int(y)}) with {left.name}/{right.name} [{ai_profile}]")


    # --- Main Loop Stages ---
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if self.game_state == GameState.START_MENU:
                for button in self.start_menu_buttons:
                    button.handle_event(event)
            elif self.game_state == GameState.EQUIPMENT_SELECT:
                 for button in self.equip_buttons:
                      button.handle_event(event)
            elif self.game_state == GameState.GAME_OVER:
                if event.type == pygame.KEYDOWN:
                    self.go_to_start_menu()


    def update(self, dt):
        if self.game_state == GameState.PLAYING:
            self.game_time += dt

            # Update characters and other dynamic objects
            self.sprite_groups["characters"].update(dt, self.sprite_groups["collidables"], self.sprite_groups["hazards"])
            self.sprite_groups["ground_effects"].update(dt) # Campfire anim, blood fade
            self.sprite_groups["blood_splatters_group"].update(dt)

            # Update roof transparency based on character positions
            character_rects = [char.body_rect_for_roof for char in self.sprite_groups["characters"]]
            for roof in self.sprite_groups["roof_objects"]:
                roof.update_transparency(character_rects)

            # Collision Detection and Response
            handle_collisions(self.sprite_groups["characters"], self.sprite_groups["obstacles"])

            # Enemy Spawning
            self.update_spawning(dt)

            # Check for Player Death
            if self.player and self.player.is_dead:
                self.go_to_game_over()


    def draw(self):
        # Determine camera offset (simple centered on player for now)
        # cam_x = SCREEN_WIDTH / 2 - self.player.pos.x if self.player else 0
        # cam_y = SCREEN_HEIGHT / 2 - self.player.pos.y if self.player else 0
        # camera_offset = pygame.Vector2(cam_x, cam_y)
        camera_offset = pygame.Vector2(0, 0) # No camera movement yet

        # ---- DRAWING ORDER ----
        # 1. Ground Layer
        self.screen.fill(DARK_GREY) # Base background
        for stone in self.ground_cobblestones:
            pygame.draw.circle(self.screen, stone.color, stone.pos + camera_offset, stone.radius)

        # 2. Splatter Layer (Campfire GFX, Blood)
        # Manually draw the campfire using its own draw method
        if self.campfire: # Make sure it exists
            self.campfire.draw(self.screen, camera_offset)
        # Draw blood splatters using the group draw method (BloodSplatter sets self.image)
        self.sprite_groups["blood_splatters_group"].draw(self.screen, camera_offset)


        # 3. Object Layer (Characters, Obstacles)
        # Sort by Y for pseudo-depth? Optional.
        sprites_to_draw = sorted(self.sprite_groups["collidables"], key=lambda spr: spr.pos.y)
        for sprite in sprites_to_draw:
            sprite.draw(self.screen, camera_offset)

        # 4. Roof Layer (Tree Foliage)
        for roof in self.sprite_groups["roof_objects"]:
            roof.draw(self.screen, camera_offset) # Uses potentially adjusted alpha


        # --- UI / Game State Specific Drawing ---
        if self.game_state == GameState.START_MENU:
            draw_text(self.screen, "Circle Combat", 64, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 4, WHITE, center=True)
            draw_text(self.screen, "WASD to Move", 24, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 80, LIGHT_GREY, center=True)
            draw_text(self.screen, "Aim with Mouse", 24, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 50, LIGHT_GREY, center=True)
            draw_text(self.screen, "LMB/RMB to Attack/Use Arm", 24, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 20, LIGHT_GREY, center=True)
            for button in self.start_menu_buttons:
                button.draw(self.screen)

        elif self.game_state == GameState.EQUIPMENT_SELECT:
             draw_text(self.screen, "Choose Equipment", 48, SCREEN_WIDTH / 2, 50, WHITE, center=True)
             draw_text(self.screen, "Left Hand", 30, SCREEN_WIDTH / 2 - 150, SCREEN_HEIGHT / 2 - 140, WHITE, center=True)
             draw_text(self.screen, "Right Hand", 30, SCREEN_WIDTH / 2 + 150, SCREEN_HEIGHT / 2 - 140, WHITE, center=True)

             # Show currently selected
             sel_left_text = self.selected_equipment[Hand.LEFT].name
             sel_right_text = self.selected_equipment[Hand.RIGHT].name
             draw_text(self.screen, f"Selected: {sel_left_text}", 20, SCREEN_WIDTH / 2 - 150, SCREEN_HEIGHT - 150, WHITE, center=True)
             draw_text(self.screen, f"Selected: {sel_right_text}", 20, SCREEN_WIDTH / 2 + 150, SCREEN_HEIGHT - 150, WHITE, center=True)

             for button in self.equip_buttons:
                 button.draw(self.screen)

             if self.equip_error_message:
                  draw_text(self.screen, self.equip_error_message, 24, SCREEN_WIDTH / 2, SCREEN_HEIGHT - 40, RED, center=True)


        elif self.game_state == GameState.PLAYING:
            if self.player:
                self.player.draw_ui(self.screen)
            # Display Kills / Time?
            draw_text(self.screen, f"Kills: {self.player_kills}", 24, SCREEN_WIDTH - 100, 10, WHITE)
            draw_text(self.screen, f"Time: {int(self.game_time)}s", 24, SCREEN_WIDTH - 100, 40, WHITE)


        elif self.game_state == GameState.GAME_OVER:
            draw_text(self.screen, "Game Over", 64, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 3, RED, center=True)
            draw_text(self.screen, f"Final Kills: {self.player_kills}", 40, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, WHITE, center=True)
            draw_text(self.screen, f"High Score: {self.high_score}", 30, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 50, LIGHT_GREY, center=True)
            draw_text(self.screen, "Press any key to return to menu", 24, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.75, WHITE, center=True)


        pygame.display.flip()


    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0 # Delta time in seconds
            dt = min(dt, 0.1) # Prevent large dt spikes on lag

            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()

# --- Main Execution ---
if __name__ == '__main__':
    game = Game()
    game.run()