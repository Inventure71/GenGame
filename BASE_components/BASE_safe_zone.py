import math
import random


class SafeZone:
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
        self.center = [width / 2, height / 2]
        self.radius = math.hypot(width, height) / 2
        self.min_radius = min(width, height) * 0.2
        self.shrink_rate = 4.0
        self.center_shift_timer = 0.0
        self.center_shift_interval = 12.0
        self.target_center = self.center[:]
        self.damage = 1.0
        self.elapsed = 0.0

    def update(self, delta_time: float):
        self.elapsed += delta_time
        self.radius = max(self.min_radius, self.radius - self.shrink_rate * delta_time)
        self.damage = 1.0 + min(5.0, self.elapsed / 30.0)

        self.center_shift_timer += delta_time
        if self.center_shift_timer >= self.center_shift_interval:
            self.center_shift_timer = 0.0
            shift = 40.0
            self.target_center = [
                random.uniform(shift, self.width - shift),
                random.uniform(shift, self.height - shift),
            ]

        self.center[0] += (self.target_center[0] - self.center[0]) * min(1.0, delta_time * 0.5)
        self.center[1] += (self.target_center[1] - self.center[1]) * min(1.0, delta_time * 0.5)

    def contains(self, x: float, y: float) -> bool:
        dx = x - self.center[0]
        dy = y - self.center[1]
        return dx * dx + dy * dy <= self.radius * self.radius
