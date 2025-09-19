import pygame
import pymunk
import pymunk.pygame_util
import random
import math
import sys
import time

# -----------------------
# Configuration Constants
# -----------------------
WIDTH, HEIGHT = 800, 600
FPS = 60
SPAWN_RATE = 5  # seconds between enemy spawns (configurable)

# Colors
YELLOW = (255, 255, 0)
BLACK  = (0, 0, 0)
WHITE  = (255, 255, 255)
RED    = (255, 0, 0)
GREEN  = (0, 255, 0)
BROWN  = (139, 69, 19)

# -----------------------
# Utility Functions
# -----------------------
def clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))

def normalize_angle(angle):
    """Normalize angle to be between -pi and pi."""
    return (angle + math.pi) % (2 * math.pi) - math.pi

def world_to_local(world_point, body):
    """Convert world coordinates to local coordinates for the given body."""
    return pymunk.Vec2d(world_point) - body.position

# A simple pivot-based rotation blit.
def blit_rotate(surf, image, pos, pivot, angle):
    """
    Rotates an image around its pivot point and blits it so that the pivot stays at pos.
    pos: the pivot position on the destination surface.
    pivot: the pivot point inside the source image (offset from top-left).
    angle: angle in radians.
    """
    # Rotate image
    rotated_image = pygame.transform.rotate(image, -math.degrees(angle))
    # Rotate the pivot vector
    pivot_rotated = pygame.math.Vector2(pivot).rotate(math.degrees(angle))
    # Compute the new top-left such that pivot remains at pos.
    new_rect = rotated_image.get_rect(center=(pos[0] - pivot_rotated.x, pos[1] - pivot_rotated.y))
    surf.blit(rotated_image, new_rect)

# -----------------------
# Equipment Classes
# -----------------------
class Equipment:
    def __init__(self, name, extension_speed, length, damage):
        self.name = name
        self.extension_speed = extension_speed  # seconds for full extension (0 to 1)
        self.length = length  # maximum length (used for drawing/collision)
        self.damage = damage

    def render(self, surface, pos, angle):
        pass

class Sword(Equipment):
    def __init__(self):
        super().__init__("sword", extension_speed=0.5, length=40, damage=1)
        self.color = (128, 128, 128)  # grey

    def render(self, surface, pos, angle):
        width = 10
        length = self.length
        sword_surf = pygame.Surface((length, width), pygame.SRCALPHA)
        sword_surf.fill(self.color)
        # Pivot at left-center so the handle stays at the hand.
        pivot = (0, width/2)
        blit_rotate(surface, sword_surf, pos, pivot, angle)

class Dagger(Equipment):
    def __init__(self):
        super().__init__("dagger", extension_speed=0.3, length=30, damage=1)
        self.color = (100, 100, 100)

    def render(self, surface, pos, angle):
        width = 8
        length = self.length
        dagger_surf = pygame.Surface((length, width), pygame.SRCALPHA)
        dagger_surf.fill(self.color)
        pivot = (0, width/2)
        blit_rotate(surface, dagger_surf, pos, pivot, angle)

class Shield(Equipment):
    def __init__(self):
        # Shield does not gradually extend.
        super().__init__("shield", extension_speed=0, length=30, damage=0)
        self.color = (128, 128, 128)

    def render(self, surface, pos, arm_angle, body_angle):
        width = 20
        height = self.length
        shield_surf = pygame.Surface((height, width), pygame.SRCALPHA)
        shield_surf.fill(self.color)
        # For shields, the handle is at the left-center.
        pivot = (0, width/2)
        # Always perpendicular to the body.
        angle = body_angle + math.pi/2
        blit_rotate(surface, shield_surf, pos, pivot, angle)

class BareHand(Equipment):
    def __init__(self):
        super().__init__("bare_hand", extension_speed=0.2, length=20, damage=1)
        self.color = YELLOW

    def render(self, surface, pos, angle):
        pygame.draw.circle(surface, self.color, (int(pos[0]), int(pos[1])), 5)

# -----------------------
# Arm Class
# -----------------------
class Arm:
    def __init__(self, parent, side, equipment):
        self.parent = parent      # owning character
        self.side = side          # "left" or "right"
        self.equipment = equipment
        self.extension = 0.0      # 0.0 (retracted) to 1.0 (fully extended)
        # Baseline: arm sticks straight out (left: π, right: 0)
        self.baseline = math.pi if side == "left" else 0  
        # Allowed relative rotation: from -45° to +135° relative to baseline.
        self.min_offset = -math.radians(45)
        self.max_offset = math.radians(135)
        self.current_angle = self.baseline  
        self.target_angle = self.baseline
        # Extension speed in fraction/second.
        self.extension_speed = 1.0 / self.equipment.extension_speed if self.equipment.extension_speed > 0 else 0

    def update(self, dt, target_cursor_angle=None, extending=False):
        # For shields, always fully extended.
        if isinstance(self.equipment, Shield):
            self.extension = 1.0
        else:
            if extending:
                self.extension = min(1.0, self.extension + self.extension_speed * dt)
            else:
                self.extension = max(0.0, self.extension - self.extension_speed * dt)
        # Compute target angle (in world coordinates) if provided.
        if target_cursor_angle is not None:
            relative = normalize_angle(target_cursor_angle - self.parent.angle)
            desired = self.baseline + relative
            offset = desired - self.baseline
            clamped_offset = clamp(offset, self.min_offset, self.max_offset)
            self.target_angle = self.baseline + clamped_offset
        # Smoothly update current angle.
        diff = self.target_angle - self.current_angle
        max_rotation = 5 * dt  # max 5 radians/sec.
        if abs(diff) > max_rotation:
            self.current_angle += math.copysign(max_rotation, diff)
        else:
            self.current_angle = self.target_angle
        # If at angular limit, nudge parent's body.
        if self.current_angle <= self.baseline + self.min_offset + 0.01:
            self.parent.angle -= 0.5 * dt
        elif self.current_angle >= self.baseline + self.max_offset - 0.01:
            self.parent.angle += 0.5 * dt

    def get_hand_position(self):
        # Shoulder is at a fixed offset from the center.
        shoulder_offset = 20  
        shoulder_angle = self.parent.angle + (math.pi/2 if self.side == "left" else -math.pi/2)
        shoulder_pos = (self.parent.position[0] + shoulder_offset * math.cos(shoulder_angle),
                        self.parent.position[1] + shoulder_offset * math.sin(shoulder_angle))
        arm_angle = self.parent.angle + self.current_angle
        arm_length = self.equipment.length * self.extension
        hand_pos = (shoulder_pos[0] + arm_length * math.cos(arm_angle),
                    shoulder_pos[1] + arm_length * math.sin(arm_angle))
        return shoulder_pos, hand_pos, arm_angle

    def render(self, surface):
        shoulder_pos, hand_pos, arm_angle = self.get_hand_position()
        # Draw shoulder.
        shoulder_rect = pygame.Rect(0, 0, 10, 10)
        shoulder_rect.center = shoulder_pos
        pygame.draw.rect(surface, YELLOW, shoulder_rect)
        # Draw arm as a rectangle.
        if self.extension > 0:
            dx = hand_pos[0] - shoulder_pos[0]
            dy = hand_pos[1] - shoulder_pos[1]
            length = math.hypot(dx, dy)
            arm_surf = pygame.Surface((length, 6), pygame.SRCALPHA)
            arm_surf.fill(YELLOW)
            rotated = pygame.transform.rotate(arm_surf, -math.degrees(arm_angle))
            rect = rotated.get_rect(center=((shoulder_pos[0]+hand_pos[0])/2, (shoulder_pos[1]+hand_pos[1])/2))
            surface.blit(rotated, rect)
        # Render equipment.
        if isinstance(self.equipment, Shield):
            self.equipment.render(surface, hand_pos, arm_angle, self.parent.angle)
        else:
            self.equipment.render(surface, hand_pos, arm_angle)
        # Draw hand.
        pygame.draw.circle(surface, YELLOW, (int(hand_pos[0]), int(hand_pos[1])), 4)

# -----------------------
# Character Classes
# -----------------------
class Character:
    next_group_id = 1  # class variable to assign unique collision groups

    def __init__(self, space, position, angle=0):
        self.space = space
        self.position = list(position)
        self.angle = angle
        self.health = 10
        self.alive = True
        # Assign a unique collision group.
        self.group_id = Character.next_group_id
        Character.next_group_id += 1
        # Default arms (will be overridden in subclasses).
        self.left_arm = Arm(self, "left", Shield())
        self.right_arm = Arm(self, "right", Sword())
        self.body_radius = 20
        mass = 1
        moment = pymunk.moment_for_circle(mass, 0, self.body_radius)
        self.body = pymunk.Body(mass, moment)
        self.body.position = position
        self.body.angle = self.angle
        self.shape = pymunk.Circle(self.body, self.body_radius)
        self.shape.collision_type = 1  # main body collision type
        self.shape.owner = self
        # Set collision filter so that parts from the same character don't interact.
        self.shape.filter = pymunk.ShapeFilter(group=self.group_id)
        self.velocity = [0, 0]
        # Create containers for arm and equipment shapes.
        self.arm_shapes = {}   # keys: "left", "right"
        self.equip_shapes = {} # keys: "left", "right"
        # Add the main body shape to space.
        self.space.add(self.body, self.shape)

    def update_physics(self):
        # Sync body angle with our angle.
        self.body.angle = self.angle
        self.body.velocity = (self.velocity[0], self.velocity[1])
        self.position = list(self.body.position)
        if self.health <= 0:
            self.alive = False

    def update_collision_shapes(self):
        # Update arm and equipment collision shapes.
        for side, arm in (("left", self.left_arm), ("right", self.right_arm)):
            shoulder_pos, hand_pos, arm_angle = arm.get_hand_position()
            local_shoulder = pymunk.Vec2d(*shoulder_pos) - self.body.position
            local_hand = pymunk.Vec2d(*hand_pos) - self.body.position
            if side not in self.arm_shapes:
                seg = pymunk.Segment(self.body, local_shoulder, local_hand, 3)
                seg.filter = pymunk.ShapeFilter(group=self.group_id)
                seg.collision_type = 4
                seg.owner = self
                self.arm_shapes[side] = seg
                self.space.add(seg)
            else:
                self.arm_shapes[side].unsafe_set_endpoints(local_shoulder, local_hand)
            # Equipment shapes.
            equip = arm.equipment
            if equip:
                if side not in self.equip_shapes:
                    if isinstance(equip, (Sword, Dagger)):
                        weapon_end_world = (hand_pos[0] + equip.length * math.cos(arm_angle),
                                            hand_pos[1] + equip.length * math.sin(arm_angle))
                        local_hand = pymunk.Vec2d(*hand_pos) - self.body.position
                        local_weapon_end = pymunk.Vec2d(*weapon_end_world) - self.body.position
                        seg = pymunk.Segment(self.body, local_hand, local_weapon_end, 3)
                        seg.filter = pymunk.ShapeFilter(group=self.group_id)
                        seg.collision_type = 4
                        seg.owner = self
                        self.equip_shapes[side] = seg
                        self.space.add(seg)
                    elif isinstance(equip, Shield):
                        shield_angle = self.angle + math.pi/2
                        shield_end_world = (hand_pos[0] + equip.length * math.cos(shield_angle),
                                            hand_pos[1] + equip.length * math.sin(shield_angle))
                        local_hand = pymunk.Vec2d(*hand_pos) - self.body.position
                        local_shield_end = pymunk.Vec2d(*shield_end_world) - self.body.position
                        seg = pymunk.Segment(self.body, local_hand, local_shield_end, 3)
                        seg.filter = pymunk.ShapeFilter(group=self.group_id)
                        seg.collision_type = 4
                        seg.owner = self
                        self.equip_shapes[side] = seg
                        self.space.add(seg)
                else:
                    if isinstance(equip, (Sword, Dagger)):
                        weapon_end_world = (hand_pos[0] + equip.length * math.cos(arm_angle),
                                            hand_pos[1] + equip.length * math.sin(arm_angle))
                        local_hand = pymunk.Vec2d(*hand_pos) - self.body.position
                        local_weapon_end = pymunk.Vec2d(*weapon_end_world) - self.body.position
                        self.equip_shapes[side].unsafe_set_endpoints(local_hand, local_weapon_end)
                    elif isinstance(equip, Shield):
                        shield_angle = self.angle + math.pi/2
                        shield_end_world = (hand_pos[0] + equip.length * math.cos(shield_angle),
                                            hand_pos[1] + equip.length * math.sin(shield_angle))
                        local_hand = pymunk.Vec2d(*hand_pos) - self.body.position
                        local_shield_end = pymunk.Vec2d(*shield_end_world) - self.body.position
                        self.equip_shapes[side].unsafe_set_endpoints(local_hand, local_shield_end)

    def render(self, surface):
        pygame.draw.circle(surface, YELLOW, (int(self.position[0]), int(self.position[1])), self.body_radius)
        self.left_arm.render(surface)
        self.right_arm.render(surface)

    def apply_knockback(self, force):
        self.velocity[0] += force[0]
        self.velocity[1] += force[1]

    def take_damage(self, damage):
        self.health -= damage

# Player controlled by input.
class Player(Character):
    def __init__(self, space, position):
        super().__init__(space, position)
        self.left_arm = Arm(self, "left", Shield())
        self.right_arm = Arm(self, "right", Sword())
        self.speed = 200

    def handle_input(self, keys, mouse_buttons, mouse_pos, dt):
        dx, dy = 0, 0
        if keys[pygame.K_w]:
            dy -= 1
        if keys[pygame.K_s]:
            dy += 1
        if keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_d]:
            dx += 1
        norm = math.hypot(dx, dy)
        if norm:
            dx, dy = dx/norm, dy/norm
        self.velocity = [dx * self.speed, dy * self.speed]
        # Face cursor if no mouse button is pressed.
        if not any(mouse_buttons):
            rel_x = mouse_pos[0] - self.position[0]
            rel_y = mouse_pos[1] - self.position[1]
            self.angle = math.atan2(rel_y, rel_x)
        # Update arms based on mouse buttons.
        if mouse_buttons[0]:
            target = math.atan2(mouse_pos[1] - self.position[1], mouse_pos[0] - self.position[0])
            self.right_arm.update(dt, target_cursor_angle=target, extending=True)
        else:
            self.right_arm.update(dt, extending=False)
        if mouse_buttons[2]:
            target = math.atan2(mouse_pos[1] - self.position[1], mouse_pos[0] - self.position[0])
            self.left_arm.update(dt, target_cursor_angle=target, extending=True)
        else:
            self.left_arm.update(dt, extending=False)
        self.update_physics()
        self.update_collision_shapes()

# Enemy with a state machine.
class Enemy(Character):
    def __init__(self, space, position):
        super().__init__(space, position)
        # Randomly assign weapon to right arm.
        if random.random() < 0.5:
            self.right_arm = Arm(self, "right", Sword())
        else:
            self.right_arm = Arm(self, "right", Dagger())
        # Left arm: 50% chance shield; otherwise bare-hand.
        if random.random() < 0.5:
            self.left_arm = Arm(self, "left", Shield())
        else:
            self.left_arm = Arm(self, "left", BareHand())
        self.speed = 150
        # Initial AI state.
        self.ai_state = "circling"
        self.state_timer = 0
        # For circling, assign a target distance (e.g., 100 to 200 pixels) and a fixed direction.
        self.circling_distance = random.uniform(100, 200)
        self.circling_direction = random.choice([1, -1])

    def update(self, dt, player):
        self.state_timer -= dt
        if self.state_timer <= 0:
            r = random.random()
            if r < 0.2:
                self.ai_state = "attacking"
                self.state_timer = 1.0
            elif r < 0.4:
                self.ai_state = "fleeing"
                self.state_timer = 1.0
            else:
                self.ai_state = "circling"
                self.state_timer = 1.0

        if self.ai_state == "attacking":
            dx = player.position[0] - self.position[0]
            dy = player.position[1] - self.position[1]
            angle_to_player = math.atan2(dy, dx)
            self.angle = angle_to_player
            self.velocity = [math.cos(angle_to_player) * self.speed, math.sin(angle_to_player) * self.speed]
            if math.hypot(dx, dy) < 150:
                self.right_arm.update(dt, target_cursor_angle=angle_to_player, extending=True)
            else:
                self.right_arm.update(dt, extending=False)
        elif self.ai_state == "fleeing":
            dx = self.position[0] - player.position[0]
            dy = self.position[1] - player.position[1]
            angle = math.atan2(dy, dx)
            self.angle = angle
            self.velocity = [math.cos(angle) * self.speed, math.sin(angle) * self.speed]
            self.right_arm.update(dt, extending=False)
        elif self.ai_state == "circling":
            # Compute vector from player to enemy.
            vec = pymunk.Vec2d(*self.position) - pymunk.Vec2d(*player.position)
            if vec.length == 0:
                vec = pymunk.Vec2d(1, 0)
            current_distance = vec.length
            radial_direction = vec.normalized()
            radial_error = current_distance - self.circling_distance
            # Radial correction (tends to reduce error).
            v_radial = -2 * radial_error * radial_direction
            # Tangential velocity (perpendicular to radial direction).
            v_tangent = self.circling_direction * radial_direction.perpendicular() * self.speed
            velocity = v_radial + v_tangent
            self.velocity = (velocity.x, velocity.y)
            # Face tangentially.
            self.angle = math.atan2(v_tangent.y, v_tangent.x)
            self.right_arm.update(dt, extending=False)
        self.left_arm.update(dt)
        self.update_physics()
        self.update_collision_shapes()

    def render(self, surface):
        super().render(surface)
        # Draw enemy health (1 to 9) at the center.
        font = pygame.font.SysFont("Arial", 20)
        health_text = font.render(str(min(self.health, 9)), True, BLACK)
        rect = health_text.get_rect(center=(int(self.position[0]), int(self.position[1])))
        surface.blit(health_text, rect)

# -----------------------
# Environment Objects
# -----------------------
class Cobblestone:
    def __init__(self, pos, radius, color):
        self.pos = pos
        self.radius = radius
        self.color = color

    def render(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.pos[0]), int(self.pos[1])), self.radius)

class Rock:
    def __init__(self, pos, radius, space):
        self.pos = pos
        self.radius = radius
        self.color = (80, 80, 80)
        self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
        self.body.position = pos
        self.shape = pymunk.Circle(self.body, radius)
        self.shape.collision_type = 2  # obstacle
        space.add(self.body, self.shape)

    def render(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.pos[0]), int(self.pos[1])), self.radius)

class Tree:
    def __init__(self, pos, trunk_radius, foliage_radius):
        self.pos = pos
        self.trunk_radius = trunk_radius
        self.foliage_radius = foliage_radius
        self.trunk_color = BROWN
        self.foliage_color = (34, 139, 34)

    def render(self, surface):
        pygame.draw.circle(surface, self.trunk_color, (int(self.pos[0]), int(self.pos[1])), self.trunk_radius)
        pygame.draw.circle(surface, self.foliage_color,
                           (int(self.pos[0]), int(self.pos[1]) - self.trunk_radius), self.foliage_radius)

class Campfire:
    def __init__(self, pos, space):
        self.pos = pos
        self.size = 30
        self.base_color = BROWN
        self.fire_color = RED
        self.highlight_color = YELLOW
        self.bob_offset = 0
        self.bob_direction = 1
        self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
        self.body.position = pos
        self.shape = pymunk.Poly.create_box(self.body, (self.size, self.size))
        self.shape.collision_type = 3
        space.add(self.body, self.shape)

    def update(self, dt):
        self.bob_offset += self.bob_direction * 30 * dt
        if abs(self.bob_offset) > 5:
            self.bob_direction *= -1

    def render(self, surface):
        rect = pygame.Rect(0, 0, self.size, self.size)
        rect.center = self.pos
        pygame.draw.rect(surface, self.base_color, rect)
        tri = [
            (self.pos[0], self.pos[1] - self.size//2 + self.bob_offset),
            (self.pos[0] - self.size//4, self.pos[1] + self.size//4),
            (self.pos[0] + self.size//4, self.pos[1] + self.size//4)
        ]
        pygame.draw.polygon(surface, self.fire_color, tri)
        tri2 = [
            (self.pos[0], self.pos[1] - self.size//4 + self.bob_offset),
            (self.pos[0] - self.size//8, self.pos[1]),
            (self.pos[0] + self.size//8, self.pos[1])
        ]
        pygame.draw.polygon(surface, self.highlight_color, tri2)

# -----------------------
# Blood Splatter Effect
# -----------------------
class BloodSplatter:
    def __init__(self, pos, amount):
        self.pos = pos
        self.amount = amount
        self.life = 1.0

    def update(self, dt):
        self.life -= dt

    def render(self, surface):
        if self.life > 0:
            alpha = int(255 * self.life)
            splat = pygame.Surface((20, 20), pygame.SRCALPHA)
            splat.fill((255, 0, 0, alpha))
            surface.blit(splat, (self.pos[0] - 10, self.pos[1] - 10))

# -----------------------
# Main Game Class
# -----------------------
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Top Down Game")
        self.clock = pygame.time.Clock()
        self.space = pymunk.Space()
        self.space.gravity = (0, 0)
        self.setup_collision_handlers()
        self.state = "menu"  # "menu", "playing", "game_over"
        self.player = None
        self.enemies = []
        self.cobblestones = []
        self.rocks = []
        self.trees = []
        self.campfires = []
        self.blood_splatters = []
        self.spawn_timer = 0
        self.start_time = time.time()
        self.highscore = 0
        self.font = pygame.font.SysFont("Arial", 20)
        self.create_environment()

    def create_environment(self):
        for _ in range(50):
            pos = (random.randint(0, WIDTH), random.randint(0, HEIGHT))
            radius = random.randint(5, 15)
            shade = random.randint(100, 200)
            self.cobblestones.append(Cobblestone(pos, radius, (shade, shade, shade)))
        for _ in range(5):
            pos = (random.randint(50, WIDTH - 50), random.randint(50, HEIGHT - 50))
            radius = random.randint(20, 30)
            rock = Rock(pos, radius, self.space)
            self.rocks.append(rock)
        for _ in range(5):
            pos = (random.randint(50, WIDTH - 50), random.randint(50, HEIGHT - 50))
            tree = Tree(pos, trunk_radius=15, foliage_radius=30)
            self.trees.append(tree)
        campfire = Campfire((WIDTH // 2, HEIGHT // 2), self.space)
        self.campfires.append(campfire)

    def setup_collision_handlers(self):
        # Use pre_solve so damage is applied every physics step.
        handler = self.space.add_collision_handler(1, 3)
        handler.pre_solve = self.campfire_collision
        handler2 = self.space.add_collision_handler(1, 1)
        handler2.pre_solve = self.character_collision
        # Also handle collisions between arm/equipment shapes (collision_type 4).
        handler3 = self.space.add_collision_handler(4, 4)
        handler3.pre_solve = self.character_collision

    def campfire_collision(self, arbiter, space, data):
        # Damage and knockback per frame.
        shape_a, shape_b = arbiter.shapes
        character = getattr(shape_a, "owner", None) or getattr(shape_b, "owner", None)
        if character:
            character.take_damage(1)
            character.apply_knockback((random.uniform(-50, 50), random.uniform(-50, 50)))
            self.blood_splatters.append(BloodSplatter(character.position, 5))
        return True

    def character_collision(self, arbiter, space, data):
        shape_a, shape_b = arbiter.shapes
        char_a = getattr(shape_a, "owner", None)
        char_b = getattr(shape_b, "owner", None)
        if char_a and char_b and char_a != char_b:
            char_a.apply_knockback((random.uniform(-20, 20), random.uniform(-20, 20)))
            char_b.apply_knockback((random.uniform(-20, 20), random.uniform(-20, 20)))
            # Apply damage per frame if extended.
            if ((hasattr(char_a, "right_arm") and char_a.right_arm.extension > 0.8) or
                (hasattr(char_a, "left_arm") and char_a.left_arm.extension > 0.8)):
                char_b.take_damage(1)
                self.blood_splatters.append(BloodSplatter(char_b.position, 3))
            if ((hasattr(char_b, "right_arm") and char_b.right_arm.extension > 0.8) or
                (hasattr(char_b, "left_arm") and char_b.left_arm.extension > 0.8)):
                char_a.take_damage(1)
                self.blood_splatters.append(BloodSplatter(char_a.position, 3))
        return True

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            if self.state == "menu":
                self.update_menu(dt)
                self.render_menu()
            elif self.state == "playing":
                self.update_game(dt)
                self.render_game()
            elif self.state == "game_over":
                self.update_game_over(dt)
                self.render_game_over()
            pygame.display.flip()
        pygame.quit()
        sys.exit()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if self.state == "menu" and event.type == pygame.MOUSEBUTTONDOWN:
                self.start_game()
            if self.state == "game_over" and event.type == pygame.KEYDOWN:
                self.state = "menu"

    def update_menu(self, dt):
        pass

    def render_menu(self):
        self.screen.fill(BLACK)
        title = self.font.render("Top Down Game", True, WHITE)
        instruct = self.font.render("Click to Play. WASD to move. Aim with mouse. LMB/RMB to attack.", True, WHITE)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 3))
        self.screen.blit(instruct, (WIDTH // 2 - instruct.get_width() // 2, HEIGHT // 3 + 40))

    def start_game(self):
        self.state = "playing"
        self.player = Player(self.space, (WIDTH // 4, HEIGHT // 2))
        self.enemies = []
        self.spawn_timer = 0
        self.start_time = time.time()
        self.highscore = 0

    def update_game(self, dt):
        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()
        mouse_pos = pygame.mouse.get_pos()
        self.player.handle_input(keys, mouse_buttons, mouse_pos, dt)
        for enemy in self.enemies:
            enemy.update(dt, self.player)
        self.enemies = [e for e in self.enemies if e.alive]
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_enemy()
            self.spawn_timer = SPAWN_RATE
        for campfire in self.campfires:
            campfire.update(dt)
        for splatter in self.blood_splatters:
            splatter.update(dt)
        self.blood_splatters = [s for s in self.blood_splatters if s.life > 0]
        self.space.step(dt)
        if not self.player.alive:
            self.highscore = int(time.time() - self.start_time)
            self.state = "game_over"

    def spawn_enemy(self):
        pos = (random.randint(WIDTH // 2, WIDTH - 50), random.randint(50, HEIGHT - 50))
        enemy = Enemy(self.space, pos)
        self.enemies.append(enemy)

    def render_game(self):
        self.screen.fill((50, 50, 50))
        for cob in self.cobblestones:
            cob.render(self.screen)
        for campfire in self.campfires:
            campfire.render(self.screen)
        for splatter in self.blood_splatters:
            splatter.render(self.screen)
        for rock in self.rocks:
            rock.render(self.screen)
        self.player.render(self.screen)
        for enemy in self.enemies:
            enemy.render(self.screen)
        for tree in self.trees:
            tree.render(self.screen)
        pygame.draw.rect(self.screen, RED, (20, HEIGHT - 40, 100, 20))
        health_width = int(100 * (self.player.health / 10))
        pygame.draw.rect(self.screen, GREEN, (20, HEIGHT - 40, health_width, 20))
        score_text = self.font.render("Time: " + str(int(time.time() - self.start_time)), True, WHITE)
        self.screen.blit(score_text, (WIDTH - 150, 20))

    def update_game_over(self, dt):
        pass

    def render_game_over(self):
        self.screen.fill(BLACK)
        over_text = self.font.render("Game Over! Time Survived: " + str(self.highscore) + " sec", True, WHITE)
        prompt_text = self.font.render("Press any key to return to menu.", True, WHITE)
        self.screen.blit(over_text, (WIDTH // 2 - over_text.get_width() // 2, HEIGHT // 2 - 20))
        self.screen.blit(prompt_text, (WIDTH // 2 - prompt_text.get_width() // 2, HEIGHT // 2 + 20))

# -----------------------
# Entry Point
# -----------------------
if __name__ == "__main__":
    game = Game()
    game.run()
