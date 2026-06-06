from typing import Dict

from artifactsmmo.extensions import CharacterSchemaExtension


class CharacterFightStats:
    def __init__(
        self,
        max_hp,
        haste,
        critical_strike,
        wisdom,
        prospecting,
        attack_fire,
        attack_earth,
        attack_water,
        attack_air,
        dmg_fire=0,
        dmg_earth=0,
        dmg_water=0,
        dmg_air=0,
        res_fire=0,
        res_earth=0,
        res_water=0,
        res_air=0,
        effects=None,
        healing_effect=None,
        burn_effect=None,
        lifesteal_effect=None,
        initiative: int = None,
        threat: int = None,
        level: int = None,
    ):
        self.level = level
        self.attack_elem = {}
        self.dmg_elem = {}
        self.res_elem = {}
        if effects:
            self.effect = effects
        else:
            self.effect = {}
            if healing_effect:
                self.effect['healing'] = healing_effect
            if burn_effect:
                self.effect['burn'] = burn_effect
            if lifesteal_effect:
                self.effect['lifesteal'] = lifesteal_effect

        self.hp = max_hp
        self.max_hp = max_hp
        self.initiative = initiative
        self.threat = threat

        self.haste = haste
        self.critical_strike = critical_strike
        self.wisdom = wisdom
        self.prospecting = prospecting

        # attack
        self.attack_elem['fire'] = attack_fire
        self.attack_elem['earth'] = attack_earth
        self.attack_elem['water'] = attack_water
        self.attack_elem['air'] = attack_air

        # dmg
        self.dmg_elem['fire'] = dmg_fire
        self.dmg_elem['earth'] = dmg_earth
        self.dmg_elem['water'] = dmg_water
        self.dmg_elem['air'] = dmg_air

        # res
        self.res_elem['fire'] = res_fire
        self.res_elem['earth'] = res_earth
        self.res_elem['water'] = res_water
        self.res_elem['air'] = res_air

        attack_sum: float = 0
        for element, attack in self.attack_elem.items():
            if attack > 0:
                damage = self.dmg_elem[element]
                total_attack = attack * (1 + damage * 0.01)
                attack_sum += total_attack
        self.base_attack_sum = attack_sum

    @classmethod
    def from_character(cls, character: CharacterSchemaExtension):
        return cls(
            max_hp=character.max_hp,
            haste=character.haste,
            critical_strike=character.critical_strike,
            wisdom=character.wisdom,
            prospecting=character.prospecting,
            attack_fire=character.attack_fire,
            attack_earth=character.attack_earth,
            attack_water=character.attack_water,
            attack_air=character.attack_air,
            dmg_fire=character.dmg_fire,
            dmg_earth=character.dmg_earth,
            dmg_water=character.dmg_water,
            dmg_air=character.dmg_air,
            res_fire=character.res_fire,
            res_earth=character.res_earth,
            res_water=character.res_water,
            res_air=character.res_air,
            effects={},
            initiative=character.initiative,
            threat=character.threat,
            level=character.level,
        )

    @classmethod
    def from_stats_dict(cls, stats_dict: Dict[str, int], character_level: int = None):
        stat_keys = (
            'max_hp',
            'haste',
            'critical_strike',
            'wisdom',
            'prospecting',
            'attack_fire',
            'attack_earth',
            'attack_water',
            'attack_air',
            'dmg_fire',
            'dmg_earth',
            'dmg_water',
            'dmg_air',
            'res_fire',
            'res_earth',
            'res_water',
            'res_air',
            'initiative',
            'threat',
        )

        extracted_stats = {key: stats_dict.get(key, 0) for key in stat_keys}
        stats_dict = {k: v for k, v in stats_dict.items() if k not in extracted_stats}

        return cls(**extracted_stats, effects=stats_dict, level=character_level)
