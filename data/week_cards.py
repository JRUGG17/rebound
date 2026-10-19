"""The week card a coach walks onto court with.

Taken from the academy's own curriculum slides — the Tiger Curriculum deck,
one card per theme week. Each card carries the session shape, the shot
targets and the technique keys, which is what a coach needs in front of them
rather than what an agent needs to reason with.

These are illustrations of how a week is built, not the whole drill library.
No agent should tell a coach a drill is missing because it is not here.
"""

from __future__ import annotations

CARDS: dict[str, dict] = {
    "drive": {
        "title": "Drive Week",
        "sort": ["Above or behind", "Side vs. side", "Match play"],
        "work": [
            ("Block", ["Straight drive, two-man", "Cross-court drive, two-man"]),
            ("Routine", ["Straight / straight / cross", "Long ball / long ball / short ball"]),
            ("Pattern", ["Drive / drop, phasing", "All drives back to one wall"]),
        ],
        "targets": [
            "B drive: floor target halfway between the back of the service box and the back wall",
            "A drive: second bounce in the back wall nick — dying length",
            "Cross-court wide around the volley, side wall behind the back of the box",
        ],
        "keys": [
            "Racket before feet",
            "Open face, cut on the ball",
            "Follow through to a target",
            "Front-wall height varies — read the ball, do not chase a number",
        ],
    },
    "boast": {
        "title": "Boast Week",
        "sort": ["Above or behind / volley-boast option", "Side vs. side", "Match play"],
        "work": [
            ("Block", ["Cross-court and boast, 2 or 3 person",
                       "Stuart's cross and boast, three-person", "Front court driving"]),
            ("Routine", ["Drive / boast / cross — right, left, straight, random",
                         "Second boast option, or counter off the second boast",
                         "Front vs. back, rail option"]),
        ],
        "targets": [
            "Two wall, narrow angles",
            "Front wall on the same side as the side wall struck",
            "Avoid the two-and-a-half wall boast — it pops up and hangs",
        ],
        "keys": [
            "Mid-size swing, closer to a drive swing",
            "Use rotation",
            "Heavy slice, keep it down off the wall",
            "Shape it like a drive, then change the face — deception is the point",
        ],
    },
    "drop": {
        "title": "Drop Week",
        "sort": ["Two bounce / volley drop option", "Front wall first", "Match play"],
        "work": [
            ("Routine", ["Drive / drop", "Drive / drive / drop"]),
            ("Pattern", ["Drive / drop, strict — diagonals, straight, random",
                         "Counter drops in"]),
            ("Modified game", ["Long / long / short with dead quarters",
                               "Straight / straight / cross"]),
        ],
        "targets": [
            "Front wall first, then floor",
            "About a racket head above the tin — margin, not an inch",
            "Floor target a racket-and-a-half to two racket lengths out",
            "Three drops: straight · cross into the nick · cross at a narrow angle",
        ],
        "keys": [
            "Mid to small swing, shortened down",
            "Horizontal racket shaft, extend the volley drop",
            "Cut and slice, work on the ball",
            "Posture low, bend from the knees",
        ],
    },
    "lob": {
        "title": "Lob Week",
        "sort": ["Above or behind", "Side vs. side", "Match play"],
        "work": [
            ("Block", ["Cross-court lob and boast / nick, two-man", "As above, three-man"]),
            ("Routine", ["Drive / boast / cross-lob — diagonals then random",
                         "Counters as required"]),
        ],
        "targets": [
            "Almost touches the ceiling",
            "No side wall — under pressure that is how it goes out",
            "Back wall on the fly",
        ],
        "keys": [
            "Medium to small swing",
            "Hitting under the ball",
            "Extend the follow through upward",
            "Posture low, bending from the knees",
        ],
    },
}

# Weeks named for an idea rather than a shot.
THEMED = {
    "reset": {"title": "Reset Week",
              "note": "Height, lobs, recovering the T from under pressure."},
    "attacking": {"title": "Attacking Week",
                  "note": "Hitting down on the ball when in front of the opponent."},
    "positional": {"title": "Positional Driving Week",
                   "note": "Containing, length, keeping the opponent behind."},
}


def card_for(shot: str | None, theme_name: str = "") -> dict | None:
    if shot and shot in CARDS:
        return CARDS[shot]
    for key, meta in THEMED.items():
        if key in (theme_name or "").lower():
            return {"title": meta["title"], "sort": [], "work": [],
                    "targets": [meta["note"]], "keys": []}
    return None
