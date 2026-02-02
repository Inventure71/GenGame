
def apply(cow):
    cow.poop_cooldown = max(0.2, cow.poop_cooldown / 2)


ABILITY = {
    "name": "Quick Digestion",
    "description": "Poop more often to control space with obstacles.",
    "apply": apply,
}
