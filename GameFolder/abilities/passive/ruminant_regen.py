
def apply(cow):
    cow.regeneration_rate = 2.0
    cow.regenation = True


ABILITY = {
    "name": "Ruminant Regen",
    "description": "Regenerate health over time while alive.",
    "apply": apply,
}
