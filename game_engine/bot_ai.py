import random
from typing import List, Dict, Optional

class BotPsychologyEngine:
    """
    Pure-Python Human-Psychology Hand Cricket Engine (zero external AI APIs, no fixed steps).
    Dynamically profiles the human opponent and computes soft-weighted probabilities across
    legal numbers (min_num..max_num) before sampling with a randomizer.
    """

    BOT_USER_ID: int = -999999
    BOT_USERNAME: str = "HandCricketAI"

    @staticmethod
    def profile_player(history: List[int]) -> Dict[str, float]:
        """
        Profiles the human player's live tendencies:
        - repeat_rate: Double-Tapper (>0.25) vs Switcher (<0.15)
        - greed_index: fraction of {4, 5, 6} moves
        - entropy_ratio: unique moves / window size (Level-1 vs Level-2 indicator)
        """
        if not history:
            return {"repeat_rate": 0.15, "greed_index": 0.45, "entropy_ratio": 0.5}

        repeats = sum(1 for i in range(1, len(history)) if history[i] == history[i - 1])
        repeat_rate = repeats / max(1, len(history) - 1) if len(history) > 1 else 0.15
        greed_index = sum(1 for x in history if x >= 4) / len(history)
        entropy_ratio = len(set(history[-6:])) / min(6, len(history))
        return {
            "repeat_rate": repeat_rate,
            "greed_index": greed_index,
            "entropy_ratio": entropy_ratio
        }

    @classmethod
    def choose_bowling_number(
        cls,
        human_bat_history: List[int],
        human_runs: int = 0,
        balls_played: int = 0,
        innings_num: int = 1,
        target: Optional[int] = None,
        max_balls: int = 36,
        min_num: int = 0,
        max_num: int = 6
    ) -> int:
        """
        Chooses a bowling delivery by predicting what the human batsman is psychologically
        likely to type next, using weighted randomized sampling.
        """
        candidates = list(range(min_num, max_num + 1))
        weights: Dict[int, float] = {n: 1.0 for n in candidates}
        recent = human_bat_history[-10:]
        persona = cls.profile_player(recent)

        # 1. Opening-ball caution: humans rarely risk 0, 1, or 6 on ball 1
        if balls_played == 0:
            for n in (2, 3, 4):
                if n in weights:
                    weights[n] += 1.4
            if 6 in weights:
                weights[6] *= 0.65

        # 2. Persona: Double-Tapper vs Switcher (Gambler's Fallacy)
        if recent:
            last_shot = recent[-1]
            if last_shot in weights:
                if persona["repeat_rate"] > 0.25:
                    weights[last_shot] += 1.6  # Double-Tapper likely to repeat
                elif len(recent) >= 2:
                    weights[last_shot] *= 0.45 # Switcher avoids repeating last ball

        # 3. Level-k Mind-Game Depth
        if len(recent) >= 4:
            freq = {n: recent.count(n) for n in candidates}
            if persona["entropy_ratio"] <= 0.65:
                # Level 1: Direct counter on human's favorite numbers
                for n, count in freq.items():
                    weights[n] += count * 0.65
            else:
                # Level 2: Reverse psychology — human is dodging; hunt neglected numbers
                last_three = set(recent[-3:])
                for n in candidates:
                    if n not in last_three:
                        weights[n] += 1.25

        # 4. Impatience after slow balls (2+ consecutive <= 2 runs -> human swings 4, 5, 6)
        if len(recent) >= 2 and all(x <= 2 for x in recent[-2:]):
            for n in (4, 5, 6):
                if n in weights:
                    weights[n] += 1.35

        # 5. Nervous 40s / 90s milestone pressure -> human plays safe 1, 2, 3
        if (44 <= human_runs <= 49) or (94 <= human_runs <= 99):
            for n in (1, 2, 3):
                if n in weights:
                    weights[n] += 1.8

        # 6. Chase / RRR pressure in 2nd innings
        if innings_num == 2 and target is not None:
            needed = max(0, target - human_runs)
            balls_left = max(1, max_balls - balls_played) if max_balls > 0 else 12
            rrr = (needed / balls_left) * 6
            if needed <= 3:
                for n in (1, 2, 3):
                    if n in weights:
                        weights[n] += 1.7
            elif rrr > 4.5 or balls_left <= 2:
                for n in (5, 6):
                    if n in weights:
                        weights[n] += 1.9

        # Soft floor + randomized sampling (no fixed steps)
        final_weights = [max(0.15, weights[n]) for n in candidates]
        return random.choices(candidates, weights=final_weights, k=1)[0]

    @classmethod
    def choose_batting_number(
        cls,
        human_bowl_history: List[int],
        bot_runs: int = 0,
        balls_played: int = 0,
        innings_num: int = 1,
        target: Optional[int] = None,
        max_balls: int = 36,
        last_bot_shot: Optional[int] = None,
        min_num: int = 0,
        max_num: int = 6
    ) -> int:
        """
        Chooses a batting shot by avoiding the human bowler's psychological traps
        and adapting to innings/chase momentum.
        """
        candidates = list(range(min_num, max_num + 1))
        # Base scoring preference (higher runs slightly favored, 0 low)
        weights: Dict[int, float] = {n: (0.4 + n * 0.35) for n in candidates}
        recent_bowl = human_bowl_history[-10:]
        persona = cls.profile_player(recent_bowl)

        # 1. Avoid human bowler's frequent trap numbers (Level 1) or neglected traps (Level 2)
        if recent_bowl:
            last_bowl = recent_bowl[-1]
            if last_bowl in weights:
                if persona["repeat_rate"] > 0.25:
                    weights[last_bowl] *= 0.35
                elif len(recent_bowl) >= 2:
                    # Switcher bowler likely avoids last_bowl -> safer for bot
                    weights[last_bowl] *= 1.35

            for n in candidates:
                count = recent_bowl.count(n)
                if count >= 2:
                    weights[n] *= max(0.3, 1.0 - count * 0.18)

        # 2. Bowler Tilt after getting hit for 4 or 6: human often revenge-bowls 6 next ball
        if last_bot_shot in (4, 6) and last_bot_shot in weights:
            weights[last_bot_shot] *= 0.4

        # 3. Chase awareness in 2nd innings
        if innings_num == 2 and target is not None:
            needed = max(0, target - bot_runs)
            balls_left = max(1, max_balls - balls_played) if max_balls > 0 else 12
            rrr = (needed / balls_left) * 6

            if needed <= 6 and balls_left >= 3:
                # Play smart, lower-risk runs to close out chase
                for n in (1, 2, 3):
                    if n in weights:
                        weights[n] += 1.6
                if needed in weights:
                    weights[needed] += 1.2
            elif rrr > 4.5 or balls_left <= 2:
                # Power-hitting needed
                for n in (5, 6):
                    if n in weights:
                        weights[n] += 2.2

        final_weights = [max(0.15, weights[n]) for n in candidates]
        return random.choices(candidates, weights=final_weights, k=1)[0]
