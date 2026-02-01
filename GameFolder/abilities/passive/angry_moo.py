
def apply(cow):
    cow.can_get_angry = True


ABILITY = {
    "name": "Angry Moo",
    "description": "Gain a damage boost when your health is critically low.",
    "apply": apply,
}
