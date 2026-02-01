
def apply(cow):
    cow.probability_of_gun += cow.probability_of_gun * 0.4


ABILITY = {
    "name": "Grass Efficiency",
    "description": "Grass is more nourishing, increasing your chance to gain charges.",
    "apply": apply,
}
