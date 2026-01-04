import pygame

class BasePlatform:
    def __init__(self, x: float, y: float, width: float, height: float, color=(100, 100, 100), health: float = 100.0):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.health = health
        self.is_destroyed = False
    
    def take_damage(self, amount: float):
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.is_destroyed = True

    def draw(self, screen: pygame.Surface):
        if self.is_destroyed:
            return
        pygame.draw.rect(screen, self.color, self.rect)

