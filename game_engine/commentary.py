import random
from typing import List, Optional, Dict

class CommentaryEngine:
    """
    Dynamic Cricket Commentary Engine using randomized word sets and phrase builders
    for scores 0-6, wickets, 50s, 100s, fastest milestones, and special achievements.
    """

    WORD_SETS: Dict[str, Dict[str, List[str]]] = {
        "0": {
            "openers": [
                "Tight line and length!",
                "Watchful defense!",
                "Sharp delivery from {bowler}!",
                "No room given!",
                "Solid block!"
            ],
            "middles": [
                "{batsman} taps it back down the pitch",
                "{bowler} beats the outside edge",
                "{batsman} plays it straight to the fielder",
                "Good bounce and carry forces {batsman} to leave it",
                "Accurate yorker length keeps {batsman} quiet"
            ],
            "closers": [
                "Dot ball.",
                "No run taken.",
                "Pressure building!",
                "Advantage bowler!",
                "Clean dot delivery."
            ]
        },
        "1": {
            "openers": [
                "Quick single!",
                "Smart cricket!",
                "Gentle tap!",
                "Soft hands!",
                "Alert running!"
            ],
            "middles": [
                "{batsman} nudges it into the gap",
                "{batsman} works it down to third man",
                "{batsman} pushes it past mid-on",
                "{batsman} glides it behind square",
                "{batsman} tucks it neatly off the pads"
            ],
            "closers": [
                "Strike rotated.",
                "Easy 1 run added.",
                "Keeps the scoreboard ticking.",
                "Good hustle between the wickets!",
                "+1 to the total."
            ]
        },
        "2": {
            "openers": [
                "Crisp placement!",
                "Good running!",
                "Nice wristwork!",
                "Clever shot!",
                "Well judged!"
            ],
            "middles": [
                "{batsman} threads it into the deep",
                "{batsman} flicks it through mid-wicket",
                "{batsman} punches it wide of cover",
                "{batsman} steers it past backward point",
                "{batsman} finds the vacant pocket"
            ],
            "closers": [
                "They sprint back for 2!",
                "Comfortable couple of runs.",
                "Great fitness on display!",
                "2 runs cleanly pocketed.",
                "Sharp calling for two!"
            ]
        },
        "3": {
            "openers": [
                "Brilliant running!",
                "Outfield slows it down!",
                "Superb placement!",
                "All-out sprint!",
                "Tireless running!"
            ],
            "middles": [
                "{batsman} drives it deep into the outfield",
                "{batsman} lofts it just short of the boundary",
                "{batsman} slices it past the diving fielder",
                "{batsman} times it well towards long-on",
                "{batsman} threads the needle through extra cover"
            ],
            "closers": [
                "They complete 3 hard-earned runs!",
                "Great effort brings 3 runs!",
                "Three runs added to the tally!",
                "Fielder slides to save the fourth!",
                "Exhausting three runs!"
            ]
        },
        "4": {
            "openers": [
                "CRACKING SHOT!",
                "PURE TIMING!",
                "SHOT OF THE DAY!",
                "PIERCED THE GAP!",
                "CLASSY STROKE!"
            ],
            "middles": [
                "{batsman} unleashes a glorious cover drive",
                "{batsman} hammers it past point",
                "{batsman} flicks it effortlessly off the toes",
                "{batsman} pulls it fiercely in front of square",
                "{batsman} leans in and caresses it through mid-off"
            ],
            "closers": [
                "Races away for FOUR! 🔥",
                "4 runs! The crowd loves it! ⚡",
                "One bounce and into the fence — FOUR!",
                "No chance for the fielder — 4 runs!",
                "Rocket to the boundary for FOUR!"
            ]
        },
        "5": {
            "openers": [
                "UNBELIEVABLE!",
                "RARE FIVE!",
                "CHAOS IN THE FIELD!",
                "BONUS RUNS!",
                "WHAT A TURN OF EVENTS!"
            ],
            "middles": [
                "{batsman} steals three and an overthrow adds two more",
                "{batsman} finds the gap and {bowler}'s fielders misfield",
                "{batsman} dashes through while the throw misses the stumps",
                "Wild throw from the deep gifts extra runs to {batsman}"
            ],
            "closers": [
                "5 huge runs added!",
                "A rare 5-run haul!",
                "Every run counts — +5!",
                "Pressure mounts on {bowler}!"
            ]
        },
        "6": {
            "openers": [
                "BOOM! MAXIMUM!",
                "OUT OF THE PARK!",
                "MONSTER HIT!",
                "INTO THE STANDS!",
                "PURE CARNAGE!"
            ],
            "middles": [
                "{batsman} launches {bowler} high over long-on",
                "{batsman} smokes a colossal slog-sweep",
                "{batsman} dances down and sends it into orbit",
                "{batsman} connects sweetly off the meat of the bat",
                "{batsman} deposits {bowler} into the top tier"
            ],
            "closers": [
                "SIX RUNS! 🚀",
                "Clean over the ropes for 6! 💥",
                "Fetch that from the stands — SIX!",
                "Massive 6! What a strike!",
                "6 runs! Absolute fireworks! 🎆"
            ]
        },
        "wicket": {
            "openers": [
                "TIMBER!!",
                "CLEAN BOWLED!",
                "HUGE BREAKTHROUGH!",
                "GONE! WHAT A BALL!",
                "STUMPS SHATTERED!"
            ],
            "middles": [
                "{bowler} outfoxes {batsman} completely",
                "{batsman} walks straight into {bowler}'s trap",
                "Deadly delivery from {bowler} crashes into the stumps",
                "{bowler} reads {batsman}'s mind and strikes gold",
                "{batsman} swings and misses — absolute perfection from {bowler}"
            ],
            "closers": [
                "{batsman} has to walk back! 💥",
                "Massive wicket for {bowler}! 🎯",
                "Celebrations erupt! OUT!",
                "Big blow to the batting side!",
                "Match-turning dismissal!"
            ]
        }
    }

    MILESTONE_SETS: Dict[str, Dict[str, List[str]]] = {
        "50": {
            "openers": ["🌟 HALF-CENTURY!", "👏 FIFTY UP!", "🔥 BRILLIANT 50!"],
            "middles": [
                "{batsman} raises the bat after a stellar knock",
                "{batsman} reaches 50 runs in commanding style",
                "What a composed innings from {batsman} to bring up 50"
            ],
            "closers": ["Standing ovation! 👏", "Pure class!", "Keep going!"]
        },
        "fastest_50": {
            "openers": ["⚡ LIGHTNING 50!", "🚀 BLISTERING HALF-CENTURY!", "🔥 RECORD PACE!"],
            "middles": [
                "{batsman} storms to 50 in just {balls} balls",
                "Unstoppable hitting! {batsman} smashes a rapid 50 in {balls} deliveries",
                "Pure mayhem — {batsman} races to a 50-run blitz in {balls} balls"
            ],
            "closers": ["Strike rate off the charts! 💥", "Sensational knock!", "Bowlers have nowhere to hide!"]
        },
        "100": {
            "openers": ["💯 CENTURY!!", "👑 MAGNIFICENT 100!", "🏆 TON UP!"],
            "middles": [
                "{batsman} reaches a glorious 100 runs",
                "Take a bow, {batsman}! A masterclass century",
                "{batsman} brings up triple figures with sheer dominance"
            ],
            "closers": ["Historic innings! 🎉", "Absolute legend!", "Unforgettable knock!"]
        },
        "fastest_100": {
            "openers": ["👑🔥 RECORD-SHATTERING 100!", "🚀⚡ SUPERSONIC CENTURY!"],
            "middles": [
                "{batsman} demolishes the attack for a 100 in just {balls} balls",
                "Blink and you missed it! {batsman} blasts 100 in {balls} balls"
            ],
            "closers": ["All-time great display! 🏆", "Pure destruction!"]
        },
        "golden_duck": {
            "openers": ["🦆 GOLDEN DUCK!", "😱 FIRST-BALL STUNNER!"],
            "middles": [
                "{batsman} departs on the very first delivery for 0",
                "Nightmare start for {batsman} — out first ball without scoring"
            ],
            "closers": ["{bowler} strikes immediately! 🎯", "Instant disaster!"]
        },
        "duck": {
            "openers": ["🦆 OUT FOR A DUCK!", "😬 ZERO ON THE BOARD!"],
            "middles": [
                "{batsman} heads back without troubling the scorers",
                "Tough break for {batsman}, dismissed for 0 runs"
            ],
            "closers": ["{bowler} wins the battle!", "Back to the pavilion!"]
        },
        "hat_trick_sixes": {
            "openers": ["🎆 HAT-TRICK OF SIXES!", "🚀 THREE IN A ROW!"],
            "middles": [
                "{batsman} has smashed 3 consecutive maximums",
                "6, 6, 6! {batsman} is teeing off at will"
            ],
            "closers": ["Absolute carnage! 🔥", "Bowler under serious fire!"]
        },
        "quickfire_30": {
            "openers": ["⚡ QUICKFIRE 30!", "🔥 BLAZING START!"],
            "middles": [
                "{batsman} races past 30 runs in just {balls} balls",
                "Explosive cameo from {batsman} — 30+ in {balls} deliveries"
            ],
            "closers": ["Momentum completely shifted!"]
        }
    }

    @classmethod
    def _build_sentence(cls, word_set: Dict[str, List[str]], **kwargs) -> str:
        opener = random.choice(word_set["openers"]).format(**kwargs)
        middle = random.choice(word_set["middles"]).format(**kwargs)
        closer = random.choice(word_set["closers"]).format(**kwargs)
        return f"{opener} {middle}. {closer}"

    @classmethod
    def generate_ball_commentary(
        cls,
        batsman_username: str,
        bowler_username: str,
        runs_scored: int,
        is_wicket: bool,
        prev_runs: int,
        new_runs: int,
        ball_number: int,
        recent_runs: Optional[List[int]] = None
    ) -> Dict[str, Optional[str]]:
        """
        Generates randomized ball commentary plus any milestone or achievement shoutouts.
        """
        batsman = f"@{batsman_username}"
        bowler = f"@{bowler_username}"
        ctx = {"batsman": batsman, "bowler": bowler, "balls": ball_number}

        key = "wicket" if is_wicket else str(runs_scored)
        word_set = cls.WORD_SETS.get(key, cls.WORD_SETS["0"])
        commentary = cls._build_sentence(word_set, **ctx)

        achievements: List[str] = []

        if is_wicket:
            if new_runs == 0 and ball_number == 1:
                achievements.append(cls._build_sentence(cls.MILESTONE_SETS["golden_duck"], **ctx))
            elif new_runs == 0:
                achievements.append(cls._build_sentence(cls.MILESTONE_SETS["duck"], **ctx))
        else:
            # 100 Milestone
            if prev_runs < 100 <= new_runs:
                m_key = "fastest_100" if ball_number <= 25 else "100"
                achievements.append(cls._build_sentence(cls.MILESTONE_SETS[m_key], **ctx))
            # 50 Milestone
            elif prev_runs < 50 <= new_runs:
                m_key = "fastest_50" if ball_number <= 15 else "50"
                achievements.append(cls._build_sentence(cls.MILESTONE_SETS[m_key], **ctx))
            # Quickfire 30
            elif prev_runs < 30 <= new_runs and ball_number <= 8:
                achievements.append(cls._build_sentence(cls.MILESTONE_SETS["quickfire_30"], **ctx))

            # Hat-trick of 6s
            if recent_runs and len(recent_runs) >= 3 and recent_runs[-3:] == [6, 6, 6]:
                achievements.append(cls._build_sentence(cls.MILESTONE_SETS["hat_trick_sixes"], **ctx))

        return {
            "commentary": commentary,
            "achievement": "\n".join(achievements) if achievements else None
        }
