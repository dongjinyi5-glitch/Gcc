"""Single source of truth for character -> faction.

Faction here is a **palette** grouping, not a game-logic grouping. What matters
for 重彩 is what a character is made of: a suit is not a corpse is not fur. That
is why ZombieRatBoss sits with the rats (fur) rather than with the human bosses
(suits), and why the 4 human bosses sit with the gangsters.

If a new character is added to the game, add it here and every script -- the
survey, the restyler and the acceptance gate -- picks it up at once. Keeping
this duplicated in three places is how the three copies drift apart.
"""

HUMAN = "人类"
ZOMBIE = "僵尸"
RAT = "鼠怪"
FACTIONS = (HUMAN, ZOMBIE, RAT)
DEFAULT = HUMAN

_NAMED = {}
for _n in ("Vinnie", "Scientist", "Frankie", "EvilFrankie",
           "EvilFrankieOnFloor", "BonninoBoss"):
    _NAMED[_n] = HUMAN
for _i in range(1, 7):
    _NAMED[f"Gangster{_i}"] = HUMAN
for _n in ("ZombieRat", "ZombieRatBoss", "ZombieRatJumper", "ZombieRatSpitter"):
    _NAMED[_n] = RAT


def faction_of(name):
    """Faction for a character name. Rats win over the 'Zombie' prefix."""
    if name in _NAMED:
        return _NAMED[name]
    if name.startswith("ZombieRat"):
        return RAT
    if name.startswith("Zombie"):
        return ZOMBIE
    return DEFAULT


def members(faction):
    """Known character names for a faction (from the explicit table only)."""
    return sorted(n for n, f in _NAMED.items() if f == faction)
