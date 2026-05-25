import math

class Adjudicator:
    def resolve_engagement(self, attacker: dict, defender: dict, environment: dict) -> dict:
        """
        Resolves an engagement based on:
        Combat Power = (Numerical Strength * WLI) * Terrain Multiplier * Weather Penalty
        """
        # 1. Base Combat Power = Strength * WLI
        base_attacker_power = attacker['numerical_strength'] * attacker['wli']
        base_defender_power = defender['numerical_strength'] * defender['wli']

        # 2. Apply Environment Modifiers
        # Weather typically hampers the attacker's ability to coordinate/shoot accurately
        modified_attacker_power = base_attacker_power * environment['weather_penalty']
        
        # Terrain typically boosts the defender's survivability (e.g., dug in on a slope)
        modified_defender_power = base_defender_power * environment['terrain_multiplier']

        # Avoid div by zero
        if modified_defender_power <= 0:
            power_ratio = 999.0
        else:
            power_ratio = modified_attacker_power / modified_defender_power

        # 3. Calculate Casualties
        # Heuristic: 
        # If power_ratio == 1, both take moderate baseline casualties (e.g. 5% of their force)
        # If power_ratio > 1, defender takes more, attacker takes less.
        
        # Max casualties per engagement is capped at 50% for realism in a single bound
        defender_loss_pct = min(0.5, 0.05 * power_ratio)
        attacker_loss_pct = min(0.5, 0.05 * (1.0 / power_ratio if power_ratio > 0 else 1.0))

        defender_casualties = int(math.ceil(defender['numerical_strength'] * defender_loss_pct))
        attacker_casualties = int(math.ceil(attacker['numerical_strength'] * attacker_loss_pct))

        # Ensure we don't kill more than exist
        defender_casualties = min(defender_casualties, defender['numerical_strength'])
        attacker_casualties = min(attacker_casualties, attacker['numerical_strength'])

        # 4. Calculate Morale State
        def determine_morale(losses: int, initial_strength: int) -> str:
            if initial_strength == 0:
                return "Routed"
            loss_ratio = losses / initial_strength
            if loss_ratio >= 0.30:
                return "Retreating"
            elif loss_ratio >= 0.15:
                return "Pinned"
            return "Holding"

        defender_morale = determine_morale(defender_casualties, defender['numerical_strength'])
        attacker_morale = determine_morale(attacker_casualties, attacker['numerical_strength'])

        return {
            "attacker_casualties": attacker_casualties,
            "defender_casualties": defender_casualties,
            "attacker_morale_state": attacker_morale,
            "defender_morale_state": defender_morale,
            "ammo_depleted": True  # Simplified boolean flag for Phase 6
        }
