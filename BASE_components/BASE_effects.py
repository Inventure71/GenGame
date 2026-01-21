import pygame
from BASE_files.BASE_network import NetworkObject


class BaseEffect(NetworkObject):
    def __init__(self, location):
        super().__init__()
        self.location = location

    def update(self, delta_time: float) -> bool:
        return False

    def draw(self, screen: pygame.Surface, arena_height: float, camera=None):
        pass


class TimedEffect(BaseEffect):
    def __init__(self, location, lifetime: float):
        super().__init__(location)
        self.lifetime = float(lifetime)
        self.age = 0.0

    def update(self, delta_time: float) -> bool:
        self.age += delta_time
        return self.age >= self.lifetime

    def remaining(self) -> float:
        return max(0.0, self.lifetime - self.age)
