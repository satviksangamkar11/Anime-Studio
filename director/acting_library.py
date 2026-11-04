"""Bhava -> acting progression library for believable anime acting.

Each bhava is an ordered list of nine steps, each (action, typical seconds).
Order is always eyes -> brows -> mouth -> head -> breath -> hands -> torso -> full_body -> cloth_hair,
so the expression lands before the full-body action. Classical mudras are notes only:
use them when the scene is worship or a named gesture; otherwise use the everyday gesture.
"""

STEPS = ("eyes", "brows", "mouth", "head", "breath", "hands", "torso", "full_body", "cloth_hair")

BHAVAS = {
    "affection": {
        "gesture": {"everyday": "open hands, a hand on the arm", "mudra": "none; no mudra for affection"},
        "steps": [
            ("eyes soften and rest on the loved one", 0.6),
            ("brows lift slightly, relaxed", 0.4),
            ("lips part into a small smile", 0.5),
            ("head tilts a few degrees toward them", 0.6),
            ("slow exhale, shoulders drop", 0.5),
            ("hands open, loosen from whatever they held", 0.7),
            ("torso leans in", 0.6),
            ("steps closer or reaches to touch", 1.0),
            ("cloth and curls settle after the lean", 0.8),
        ],
    },
    "mischief": {
        "gesture": {"everyday": "hands behind the back, a sideways step", "mudra": "none"},
        "example": "Krishna's affectionate mischief toward Balarama (Dau): looks at him, remembers, suppresses a smile, tilts head, reaches for his arm, brightens when eyes meet.",
        "steps": [
            ("looks at Dau, then a remembered plan flicks the eyes up and aside and back", 0.8),
            ("one brow lifts a hair, brows pull toward the nose", 0.4),
            ("suppresses a smile: lips press in, one cheek twitches", 0.6),
            ("tilts head ten degrees, eyes stay on Dau", 0.6),
            ("a held breath, then a small nose-breath", 0.4),
            ("hands hidden behind the back, fingers curl", 0.5),
            ("weight shifts forward onto the toes", 0.5),
            ("steps in and reaches toward Dau's forearm; on contact the eyes meet Dau's and brighten, the held smile breaks", 1.0),
            ("sash swings after the step, curls bounce", 0.6),
        ],
    },
    "maternal_anxiety": {
        "gesture": {"everyday": "hand to the cheek, hand gripping the pallu", "mudra": "none"},
        "steps": [
            ("eyes search the child, fixed on the danger", 0.6),
            ("brows draw together and up in worry", 0.5),
            ("lips press, a breath catches", 0.5),
            ("head snaps toward the child, then holds", 0.5),
            ("sharp inhale, held", 0.6),
            ("hands rise to the cheeks or grip the pallu", 0.7),
            ("torso leans forward, one foot steps", 0.6),
            ("takes a step or two toward the child, stopped by a raised hand", 1.0),
            ("pallu flies off the shoulder", 0.7),
        ],
    },
    "anger": {
        "gesture": {"everyday": "fists at the sides, a pointed finger", "mudra": "none"},
        "steps": [
            ("eyes narrow and fix on the target", 0.5),
            ("brows drop hard, a vertical line between them", 0.5),
            ("jaw sets, lips tighten", 0.5),
            ("head lowers, chin forward", 0.5),
            ("nostrils flare on one long breath", 0.6),
            ("fists close at the sides", 0.5),
            ("chest lifts and stays squared", 0.6),
            ("one step forward, weight held", 0.8),
            ("cloth snaps once, then held tight", 0.5),
        ],
    },
    "courage": {
        "gesture": {"everyday": "a grip on a branch or rope, chin up", "mudra": "none"},
        "steps": [
            ("eyes lift and lock on the danger", 0.5),
            ("brows level, steady", 0.4),
            ("mouth closes, a small firm line", 0.4),
            ("head lifts, chin level", 0.5),
            ("breath drawn in and held", 0.5),
            ("hands take a grip", 0.6),
            ("chest opens, spine straightens", 0.5),
            ("drops into a crouch, then launches", 1.2),
            ("sash and curls trail the launch", 0.7),
        ],
    },
    "surrender": {
        "gesture": {"everyday": "open palms lowered, head bowed", "mudra": "none; a folded-hand mudra only in a worship frame"},
        "steps": [
            ("eyes lower, lids half closed", 0.7),
            ("brows soften, inner corners lift", 0.5),
            ("lips part, a slow exhale", 0.5),
            ("head bows forward, slowly", 0.8),
            ("a long trembling exhale", 0.7),
            ("palms open, lowered, offered", 0.7),
            ("upper body folds forward", 0.8),
            ("knees bend, body lowers to the ground", 1.0),
            ("hood or pallu falls and rests", 0.6),
        ],
    },
    "compassion": {
        "gesture": {"everyday": "palm up toward the hurt one, a kneel", "mudra": "none"},
        "steps": [
            ("eyes soften and fill with attention", 0.7),
            ("brows lift at the inner corners", 0.5),
            ("mouth relaxes, lips close gently", 0.5),
            ("head tilts down toward the suffering one", 0.7),
            ("slow breath in, long out", 0.7),
            ("hands extend palm up", 0.6),
            ("torso lowers to the level of the other", 0.7),
            ("kneels or sits beside, hands reaching", 1.0),
            ("cloth settles around the knees", 0.6),
        ],
    },
    "devotion": {
        "gesture": {"everyday": "bowed head, hand on the heart", "mudra": "anjali (folded palms) only in a worship frame"},
        "steps": [
            ("eyes half closed, gaze turned up or inward", 0.8),
            ("brows smooth, calm", 0.5),
            ("lips move slightly, a whispered name", 0.6),
            ("head lowers in reverence", 0.7),
            ("breath slows to a rhythm", 0.8),
            ("palms join at the chest", 0.7),
            ("spine lengthens in stillness", 0.7),
            ("folds into a bow or sits in stillness", 1.0),
            ("pleats still, no wind motion", 0.8),
        ],
    },
    "fear": {
        "gesture": {"everyday": "hands fly up, a clutch at a companion", "mudra": "none"},
        "steps": [
            ("eyes go wide, pupils small, whites show", 0.4),
            ("brows lift and pull together", 0.4),
            ("mouth opens or lips tremble", 0.5),
            ("head jerks back half an inch", 0.4),
            ("a gasp, breath held", 0.5),
            ("hands fly up or clutch a companion", 0.6),
            ("body pulls back, weight to the rear foot", 0.6),
            ("steps back or turns to run", 0.9),
            ("cloth and hair whip after the turn", 0.6),
        ],
    },
    "wonder": {
        "gesture": {"everyday": "hands drift up, lips parted", "mudra": "none"},
        "steps": [
            ("eyes widen and fix on the sight", 0.6),
            ("brows lift high, forehead creases", 0.5),
            ("lips part, slowly", 0.5),
            ("head rises, tilts up toward the sight", 0.6),
            ("breath held, then released in a sigh", 0.7),
            ("hands drift up without intent", 0.6),
            ("body rises onto the toes", 0.5),
            ("holds, then steps forward once", 1.0),
            ("pleats and curls settle after the step", 0.6),
        ],
    },
    "grief": {
        "gesture": {"everyday": "hands fall to the lap, a hand over the face", "mudra": "none"},
        "steps": [
            ("eyes lose focus, lids heavy, tears held back", 0.9),
            ("brows draw in, inner corners rise", 0.6),
            ("lower lip trembles, mouth drags down", 0.6),
            ("head drops, eyes to the ground", 0.8),
            ("a broken inhale, a long shaking exhale", 0.8),
            ("hands fall to the lap or cover the face", 0.8),
            ("shoulders curl forward", 0.8),
            ("sinks to sit or kneels", 1.0),
            ("pallu drapes over the head, hair falls forward", 0.7),
        ],
    },
    "relief": {
        "gesture": {"everyday": "hands drop from the chest, open", "mudra": "none"},
        "steps": [
            ("eyes close for a beat, then reopen softened", 0.7),
            ("brows release, unclench", 0.5),
            ("mouth opens into a breath of a smile", 0.6),
            ("head lifts slowly", 0.6),
            ("a long, audible exhale", 0.8),
            ("hands drop from the chest, open", 0.6),
            ("shoulders drop and the spine lengthens", 0.7),
            ("weight settles, one step toward the others", 0.9),
            ("cloth and hair drop back into place", 0.6),
        ],
    },
    "playful_defeat": {
        "gesture": {"everyday": "hands fling up, then slap the thighs", "mudra": "none"},
        "steps": [
            ("eyes roll up and sideways, then squeeze shut", 0.6),
            ("brows flick up, a pout", 0.5),
            ("pout, then a lopsided grin", 0.6),
            ("head tips back, then drops", 0.6),
            ("a theatrical sigh", 0.5),
            ("hands fling up, then slap the thighs", 0.7),
            ("body folds in half, then flops", 0.7),
            ("falls back onto the seat or into the water", 1.0),
            ("wet or loose cloth flops over, curls bounce", 0.8),
        ],
    },
}

OVERRIDES = {
    "CHAR-KRISHNA": {
        "tempo": 0.8,
        "note": "child (about 7-8): quicker, smaller gestures; the body moves from head and hands, hips stay high; expression lands before the body.",
        "steps": {"torso": "shoulders and belly lead, hips stay high (child proportion)"},
    },
    "CHAR-YASHODA": {
        "tempo": 1.2,
        "note": "restrained maternal: hands and face do most of the work; slow grounded full body; the pallu is the main secondary motion.",
        "steps": {"full_body": "moves slowly, pallu held in one hand"},
    },
    "CHAR-BALARAMA": {
        "tempo": 1.3,
        "note": "elder brother: square stance and held restraint; anger shows in the jaw, never in shouting or flailing.",
        "steps": {"hands": "arm held out flat to stop the crowd, no fist"},
    },
    "CHAR-KALIYA": {
        "tempo": 1.5,
        "note": "serpent: no hands or face gestures beyond eyes and tongue; the body acts through coils and the hood fan; the hood lift leads, a tongue flick marks each beat.",
        "steps": {
            "mouth": "jaw opens, tongue flicks once, fangs visible",
            "hands": "no hands: the coils and hood fan carry the action",
            "full_body": "hood fan rises and drops as one, coils tighten",
        },
    },
}


def progression(bhava, character=None, seconds=None):
    """Ordered beats for a bhava, optionally tuned to a character and scaled to `seconds`."""
    if bhava not in BHAVAS:
        raise KeyError(f"unknown bhava: {bhava}")
    spec = BHAVAS[bhava]
    ov = OVERRIDES.get(character, {})
    tempo = ov.get("tempo", 1.0)
    rows = []
    for name, (text, sec) in zip(STEPS, spec["steps"]):
        text = ov.get("steps", {}).get(name, text)
        rows.append((name, text, sec * tempo))
    total = sum(r[2] for r in rows)
    target = total if seconds is None else float(seconds)
    scale = target / total
    beats, t = [], 0.0
    for i, (name, text, sec) in enumerate(rows):
        dur = round(target - t, 2) if i == len(rows) - 1 else round(sec * scale, 2)
        beats.append({"step": name, "action": text, "t": [round(t, 2), round(t + dur, 2)]})
        t += dur
    return beats
