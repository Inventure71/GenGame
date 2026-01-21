
def apply(cow):
    cow.time_to_eat = max(0.2, cow.time_to_eat / 1.5)


ABILITY = {
    "name": "Adaptive Digestion",
    "description": "Eat faster to grow quicker and stay mobile.",
    "apply": apply,
}
