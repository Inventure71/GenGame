from GameFolder.abilities.primary.milk_splash import ABILITY as milk_splash
from GameFolder.abilities.primary.horn_charge import ABILITY as horn_charge
from GameFolder.abilities.primary.stomp import ABILITY as stomp
from GameFolder.abilities.primary.moo_of_doom import ABILITY as moo_of_doom
from GameFolder.abilities.primary.tail_whip import ABILITY as tail_whip
from GameFolder.abilities.primary.final_moo_ment import ABILITY as final_moo_ment
from GameFolder.abilities.passive.adaptive_digestion import ABILITY as adaptive_digestion
from GameFolder.abilities.passive.angry_moo import ABILITY as angry_moo
from GameFolder.abilities.passive.grass_efficiency import ABILITY as grass_efficiency
from GameFolder.abilities.passive.ruminant_regen import ABILITY as ruminant_regen
from GameFolder.abilities.passive.poop_mines import ABILITY as poop_mines
from GameFolder.abilities.passive.quick_digestion import ABILITY as quick_digestion
from GameFolder.abilities.passive.barricowde import ABILITY as barricowde

PRIMARY_ABILITIES = [
    milk_splash,
    horn_charge,
    stomp,
    moo_of_doom,
    tail_whip,
    final_moo_ment,
]

PASSIVE_ABILITIES = [
    adaptive_digestion,
    angry_moo,
    grass_efficiency,
    ruminant_regen,
    poop_mines,
    quick_digestion,
    barricowde,
]

PRIMARY_BY_NAME = {ability["name"]: ability for ability in PRIMARY_ABILITIES}
PASSIVE_BY_NAME = {ability["name"]: ability for ability in PASSIVE_ABILITIES}
