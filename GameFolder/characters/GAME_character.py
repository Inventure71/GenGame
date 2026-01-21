import math
import random
import pygame
from BASE_components.BASE_character import BaseCharacter
from GameFolder.abilities import PRIMARY_BY_NAME, PASSIVE_BY_NAME
from GameFolder.effects.GAME_effects import ObstacleEffect


class Character(BaseCharacter):
    """MS2 cow implementation built on the low-level BaseCharacter."""

    def __init__(self, name, description, image, location, width=30, height=30):
        super().__init__(name, description, image, location, width, height)
        self.base_size = float(width)
        self.size = float(width)
        self.width = self.size
        self.height = self.size

        self.speed = 3.0
        self.base_max_health = 50.0
        self.max_health = self.base_max_health + self.size // 3
        self.health = self.max_health

        self.damage_multiplier = 1.0
        self.primary_damage = 0.0
        self.primary_delay = 0.6
        self.primary_knockback = 0.0
        self.primary_use_cooldown = 0.2
        self.last_primary_use = 0.0

        self.primary_ability_name = None
        self.primary_ability = None
        self.primary_description = ""
        self.available_primary_abilities = 0
        self.max_primary_abilities = 1

        self.passive_ability_name = None
        self.passive_description = ""

        self.probability_of_gun = 0.1
        self.time_to_eat = 0.6
        self.eat_cooldown = 0.0
        self.eat_increase = 1.0
        self.is_eating = False

        self.poop_cooldown = 0.8
        self.poop_timer = 0.0
        self.poop_percentage = 10
        self.mine_poop = False
        self.mine_wall = False

        self.dashes_left = 3
        self.max_dashes = 3
        self.dash_recharge_timer = 0.0
        self.time_to_recharge_dash = 1.0
        self.dash_multiplier = 5.0
        self.is_slowed = False
        self._dash_held = False

        self.is_attacking = False
        self.horn_charge_duration = 2.0
        self.horn_charge_end_time = 0.0
        self.attack_speed_multiplier = 1.9

        self.regeneration_rate = 0.0
        self.regenation = False
        self.can_get_angry = False
        self.angry = False

        self.color = (240, 240, 255)

        self.update_damage_multiplier()

    def __setstate__(self, state):
        super().__setstate__(state)
        if not hasattr(self, "size"):
            self.size = float(self.width)
        if not hasattr(self, "base_size"):
            self.base_size = float(self.width)
        if not hasattr(self, "dashes_left"):
            self.dashes_left = 3
        if not hasattr(self, "max_dashes"):
            self.max_dashes = 3
        if not hasattr(self, "dash_recharge_timer"):
            self.dash_recharge_timer = 0.0
        if not hasattr(self, "time_to_recharge_dash"):
            self.time_to_recharge_dash = 1.0
        if not hasattr(self, "primary_use_cooldown"):
            self.primary_use_cooldown = 0.2
        if not hasattr(self, "last_primary_use"):
            self.last_primary_use = 0.0
        if not hasattr(self, "is_slowed"):
            self.is_slowed = False
        if not hasattr(self, "is_eating"):
            self.is_eating = False
        if not hasattr(self, "primary_ability_name"):
            self.primary_ability_name = None
        if not hasattr(self, "primary_description"):
            self.primary_description = ""
        if not hasattr(self, "passive_ability_name"):
            self.passive_ability_name = None
        if not hasattr(self, "passive_description"):
            self.passive_description = ""
        if not hasattr(self, "available_primary_abilities"):
            self.available_primary_abilities = 0
        if not hasattr(self, "max_primary_abilities"):
            self.max_primary_abilities = 1
        if not hasattr(self, "mine_poop"):
            self.mine_poop = False
        if not hasattr(self, "mine_wall"):
            self.mine_wall = False
        if not hasattr(self, "can_get_angry"):
            self.can_get_angry = False
        if not hasattr(self, "angry"):
            self.angry = False
        if not hasattr(self, "primary_damage"):
            self.primary_damage = 0.0
        if not hasattr(self, "primary_delay"):
            self.primary_delay = 0.6

    @staticmethod
    def get_input_data(held_keys, mouse_buttons, mouse_pos):
        input_data = BaseCharacter.get_input_data(held_keys, mouse_buttons, mouse_pos)

        if pygame.K_SPACE in held_keys:
            input_data["eat"] = True
        if pygame.K_LSHIFT in held_keys or pygame.K_RSHIFT in held_keys:
            input_data["dash"] = True
        if pygame.K_p in held_keys:
            input_data["poop"] = True
        if mouse_buttons[0]:
            input_data["primary"] = mouse_pos
        return input_data

    def process_input(self, input_data: dict, arena):
        if not self.is_alive:
            return
        if input_data.get("eat"):
            self.try_eat(arena)
        if input_data.get("poop"):
            self.try_poop(arena)
        if "primary" in input_data:
            self.use_primary_ability(arena, input_data.get("primary"))

        move_dir = input_data.get("movement", [0, 0])
        dash_pressed = input_data.get("dash", False)
        dash = dash_pressed and not self._dash_held
        self._dash_held = dash_pressed
        self.move(move_dir, arena, input_data.get("mouse_pos"), dash)

    def update(self, delta_time: float, arena):
        self.last_arena_height = arena.height

        if self.is_attacking and arena.current_time >= self.horn_charge_end_time:
            self.is_attacking = False

        if self.eat_cooldown > 0:
            self.eat_cooldown = max(0.0, self.eat_cooldown - delta_time)
            self.is_eating = True
        else:
            self.is_eating = False

        if self.poop_timer > 0:
            self.poop_timer = max(0.0, self.poop_timer - delta_time)

        if self.dashes_left < self.max_dashes:
            self.dash_recharge_timer += delta_time
            if self.dash_recharge_timer >= self.time_to_recharge_dash:
                self.dashes_left += 1
                self.dash_recharge_timer = 0.0

        if self.regenation and self.health < self.max_health:
            self.health = min(self.max_health, self.health + self.regeneration_rate * delta_time)

        if self.can_get_angry:
            if self.health <= self.max_health * 0.25:
                if not self.angry:
                    self.damage_multiplier += self.damage_multiplier / 2
                    self.angry = True
            else:
                if self.angry:
                    self.angry = False
                    self.update_damage_multiplier()

    def move(self, direction, arena, mouse_pos=None, dash=False):
        if not self.is_alive:
            return
        if self.is_eating:
            return

        dx, dy = direction
        speed = self.speed
        if self.is_slowed:
            speed *= 0.6

        if dash and self.dashes_left > 0 and self.dash_recharge_timer <= 0.0:
            speed *= self.dash_multiplier
            self.dashes_left -= 1
            self.dash_recharge_timer = 0.0

        if self.is_attacking and mouse_pos is not None:
            target_x, target_y = mouse_pos
            vec_x = target_x - self.location[0]
            vec_y = target_y - self.location[1]
            dist = math.hypot(vec_x, vec_y)
            if dist > 0:
                dx = vec_x / dist
                dy = vec_y / dist
                speed *= self.attack_speed_multiplier

        if dx != 0 and dy != 0:
            speed /= math.sqrt(2)

        self.location[0] += dx * speed
        self.location[1] += dy * speed

        margin = self.size / 2
        self.location[0] = max(margin, min(arena.width - margin, self.location[0]))
        self.location[1] = max(margin, min(arena.height - margin, self.location[1]))

    def try_eat(self, arena):
        if self.eat_cooldown > 0:
            return
        for field in arena.grass_fields:
            if field.can_eat(self.location[0], self.location[1], self.size / 2):
                if field.eat():
                    self.size += self.eat_increase
                    self.heal(0.5)

                    if random.random() < self.probability_of_gun:
                        if self.available_primary_abilities < self.max_primary_abilities:
                            self.available_primary_abilities += 1

                    self.changed_size()
                    self.eat_cooldown = self.time_to_eat
                    self.is_eating = True
                    return

    def try_poop(self, arena):
        if self.poop_timer > 0:
            return
        poop_size = max(4.0, self.size * (self.poop_percentage / 100.0))
        self.size = max(9.0, self.size - poop_size)
        self.changed_size()

        poop = ObstacleEffect(
            location=[self.location[0], self.location[1]],
            size=poop_size * 2,
            owner_id=self.id,
            mine=self.mine_poop,
            wall=self.mine_wall,
        )
        arena.add_effect(poop)
        self.poop_timer = self.poop_cooldown

    def use_primary_ability(self, arena, mouse_pos):
        if not self.primary_ability or self.available_primary_abilities <= 0:
            return
        if arena.current_time - self.last_primary_use < self.primary_use_cooldown:
            return
        self.last_primary_use = arena.current_time
        self.available_primary_abilities -= 1
        self.primary_ability(arena, mouse_pos)

    def set_primary_ability(self, ability_name: str):
        if ability_name is None:
            self.primary_ability_name = None
            self.primary_ability = None
            self.primary_description = ""
            self.available_primary_abilities = 0
            return

        ability_def = PRIMARY_BY_NAME.get(ability_name)
        if not ability_def:
            return
        self.primary_ability = ability_def.activate
        self.primary_ability_name = ability_def.name
        self.primary_description = ability_def.description
        self.max_primary_abilities = ability_def.max_charges
        self.available_primary_abilities = self.max_primary_abilities

    def set_passive_ability(self, ability_name: str):
        self.passive_ability_name = ability_name
        self.passive_description = ""
        self.regenation = False
        self.regeneration_rate = 0.0
        self.mine_poop = False
        self.mine_wall = False
        self.can_get_angry = False

        if not ability_name:
            return

        ability_def = PASSIVE_BY_NAME.get(ability_name)
        if not ability_def:
            return
        self.passive_ability_name = ability_def.name
        self.passive_description = ability_def.description
        ability_def.apply(self)

    def changed_size(self):
        self.max_health = self.base_max_health + self.size // 3
        self.health = min(self.health, self.max_health)
        self.width = self.size
        self.height = self.size
        self.update_damage_multiplier()

    def update_damage_multiplier(self):
        min_size = 9.0
        max_size = 80.0
        min_multiplier = 0.7
        max_multiplier = 1.5

        size_ratio = (self.size - min_size) / max(1.0, (max_size - min_size))
        self.damage_multiplier = max(min_multiplier, min(max_multiplier, min_multiplier + (max_multiplier - min_multiplier) * size_ratio))

        speed_min = 1.5
        speed_max = 5.5
        speed_ratio = (self.size - 10.0) / 190.0
        self.speed = max(speed_min, min(speed_max, speed_max - (speed_max - speed_min) * speed_ratio))

    def _angle_to_mouse(self, mouse_pos):
        if mouse_pos is None:
            return 0.0
        dx = mouse_pos[0] - self.location[0]
        dy = mouse_pos[1] - self.location[1]
        return math.atan2(dy, dx)

    def draw(self, screen: pygame.Surface, arena_height: float = None, camera=None):
        if not self._graphics_initialized:
            return
        rect = self.get_draw_rect(arena_height, camera)
        draw_color = (200, 200, 255) if self.is_attacking else self.color
        if not self.is_alive:
            draw_color = (120, 120, 120)
        pygame.draw.rect(screen, draw_color, rect)
        pygame.draw.rect(screen, (30, 30, 30), rect, 2)

        health_ratio = self.health / max(1.0, self.max_health)
        bar_width = self.size
        bar_height = 6
        bar_x = rect.x
        bar_y = rect.y - 10
        pygame.draw.rect(screen, (60, 60, 60), (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(screen, (80, 220, 80), (bar_x, bar_y, bar_width * health_ratio, bar_height))
