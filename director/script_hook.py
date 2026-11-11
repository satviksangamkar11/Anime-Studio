import math

HOOK_WINDOW_S = 3.0

MAX_FIRST_LINE_WORDS = {"en": 8, "hi": 6, "mr": 6}

OPENERS = {
    "en": (
        "once upon",
        "in ancient",
        "long ago",
        "in the beginning",
        "this is the story",
        "it was a time",
    ),
    "hi": (
        "एक समय की बात",
        "प्राचीन काल",
        "बहुत समय पहले",
        "एक बार की बात",
        "यह कहानी",
    ),
    "mr": (
        "एकेकाळी",
        "खूप वर्षांपूर्वी",
        "प्राचीन काळी",
        "ही गोष्ट",
        "एका काळी",
    ),
}

STAKES_WORDS = {
    "en": (
        "dies",
        "die",
        "curse",
        "cursed",
        "fails",
        "fail",
        "war",
        "lost",
        "burn",
        "burns",
        "destroy",
        "never",
        "kill",
        "trap",
        "fear",
        "danger",
        "secret",
        "only",
    ),
    "hi": (
        "श्राप",
        "मृत्यु",
        "युद्ध",
        "भय",
        "नाश",
        "केवल",
        "रहस्य",
        "कभी नहीं",
    ),
    "mr": (
        "शाप",
        "मृत्यू",
        "युद्ध",
        "भय",
        "नाश",
        "फक्त",
        "रहस्य",
        "कधीच नाही",
    ),
}

QUESTION_WORDS = {
    "en": ("what", "why", "how", "who", "can"),
    "hi": ("क्या", "क्यों", "कैसे", "कौन"),
    "mr": ("काय", "का", "कसे", "कोण"),
}

ENGLISH_NOUNS = (
    "god",
    "sage",
    "king",
    "queen",
    "demon",
    "warrior",
    "archer",
    "woman",
    "man",
    "boy",
    "girl",
    "child",
    "river",
    "mountain",
    "temple",
    "fire",
    "bow",
    "arrow",
    "lotus",
    "serpent",
    "throne",
    "spring",
    "flower",
)

DEVANAGARI_NOUNS = (
    "नदी",
    "राजा",
    "ऋषि",
    "देव",
    "धनुष",
    "बाण",
    "कमल",
    "पर्वत",
    "मंदिर",
    "अग्नि",
    "सिंहासन",
    "वसंत",
    "फूल",
)

STRIP_CHARS = ".,!?\"'-:;।"


def _strip_token(token):
    return token.strip(STRIP_CHARS)


def _tokens(line):
    return [_strip_token(token).lower() for token in line.split()]


def _phrase_matches(tokens, phrase):
    phrase_tokens = [_strip_token(token).lower() for token in phrase.split()]
    phrase_len = len(phrase_tokens)
    if phrase_len == 0:
        return False
    for start in range(0, len(tokens) - phrase_len + 1):
        if tokens[start:start + phrase_len] == phrase_tokens:
            return True
    return False


def _has_question(line, lang):
    if "?" in line or "？" in line:
        return True
    tokens = _tokens(line)
    for token in tokens:
        if token in QUESTION_WORDS.get(lang, ()):
            return True
    return False


def _has_stakes(line, lang):
    tokens = _tokens(line)
    for entry in STAKES_WORDS.get(lang, ()):
        if " " in entry:
            if _phrase_matches(tokens, entry):
                return True
        else:
            if entry.lower() in tokens:
                return True
    return False


def _is_opener(line, lang):
    tokens = _tokens(line)
    for opener in OPENERS.get(lang, ()):
        opener_len = len(_tokens(opener))
        if _phrase_matches(tokens[:opener_len], opener):
            return True
    return False


def _word_count(line):
    return len(line.split())


def _has_concrete_subject(action, lang):
    if not action or not action.strip():
        return False
    words = action.split()
    for index, word in enumerate(words):
        stripped = _strip_token(word)
        if index > 0 and stripped and stripped[0].isupper():
            return True
    lowered_tokens = [_strip_token(word).lower() for word in words]
    for noun in ENGLISH_NOUNS:
        if noun in lowered_tokens:
            return True
    for noun in DEVANAGARI_NOUNS:
        if noun in lowered_tokens:
            return True
    return False


def _validate_shots(shots):
    if not isinstance(shots, list) or len(shots) == 0:
        raise ValueError("shots must be a non-empty list")
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            raise ValueError("shot #" + str(index) + ": each shot must be a dict")
        shot_id = shot.get("id")
        if shot_id is None:
            prefix = "shot #" + str(index) + ": "
        else:
            prefix = "shot " + str(shot_id) + ": "
        for key in ("id", "seconds", "action", "events", "lines"):
            if key not in shot:
                raise ValueError(prefix + "missing key: " + key)


def _is_finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def validate_shots(shots):
    _validate_shots(shots)
    for shot in shots:
        shot_id = str(shot["id"])
        if not isinstance(shot["events"], list):
            raise ValueError("shot " + shot_id + ": events must be a list")
        for event in shot["events"]:
            if not isinstance(event, dict):
                raise ValueError("shot " + shot_id + ": each event must be a dict")
            if "t" not in event or not _is_finite_number(event["t"]) or event["t"] < 0:
                raise ValueError("shot " + shot_id + ": each event needs a finite numeric t >= 0")
        if not isinstance(shot["lines"], list):
            raise ValueError("shot " + shot_id + ": lines must be a list")
        for line in shot["lines"]:
            if not isinstance(line, dict):
                raise ValueError("shot " + shot_id + ": each line must be a dict")
            for key in ("start_s", "end_s"):
                if key not in line or not _is_finite_number(line[key]):
                    raise ValueError("shot " + shot_id + ": each line needs a finite numeric " + key)
            if line["start_s"] > line["end_s"]:
                raise ValueError("shot " + shot_id + ": line start_s is after end_s")
            if not isinstance(line.get("text"), str):
                raise ValueError("shot " + shot_id + ": each line needs a str text")


def inspect_hook(shots, lang):
    validate_shots(shots)
    if lang not in ("en", "hi", "mr"):
        raise ValueError("unsupported language: " + str(lang))

    first = shots[0]
    hard_fails = []
    reasons = []
    rewrites = []
    score = 100

    events = first["events"]
    lines = first["lines"]

    # H1: visible event with t <= 1.0
    h1_ok = False
    for event in events:
        if event["t"] <= 1.0:
            h1_ok = True
            break
    if not h1_ok:
        hard_fails.append("H1: no visible event within the first 1.0 s")
        reasons.append("H1: no visible event within the first 1.0 s")
        rewrites.append("Move the first visible event to within 1.0 s of frame 1")
        score -= 40

    # H2: first spoken line starts at <= 0.6 s; a first shot with no spoken line is a hard fail too
    if not lines:
        hard_fails.append("H2: no spoken line in the first shot")
        reasons.append("H2: no spoken line in the first shot")
        rewrites.append("Add a spoken line to the first shot")
        score -= 40
    elif lines[0]["start_s"] > 0.6:
        hard_fails.append("H2: first spoken line starts after 0.6 s")
        reasons.append("H2: first spoken line starts after 0.6 s")
        rewrites.append("Start the first spoken line at or before 0.6 s")
        score -= 40

    # H3: first line is stakes or a question
    h3_ok = True
    first_text = ""
    if lines:
        first_text = lines[0].get("text", "")
        if not (_has_stakes(first_text, lang) or _has_question(first_text, lang)):
            h3_ok = False
    if not h3_ok:
        reasons.append("H3: first spoken line is not stakes or a question")
        rewrites.append("Rewrite the first spoken line as a question or a consequence")
        score -= 15

    # H4: first line word count within limit
    h4_ok = True
    if lines:
        if _word_count(first_text) > MAX_FIRST_LINE_WORDS.get(lang, 8):
            h4_ok = False
    if not h4_ok:
        limit = MAX_FIRST_LINE_WORDS.get(lang, 8)
        reasons.append("H4: first spoken line is too long")
        rewrites.append(
            "Rewrite the first spoken line as a question or a consequence in at most "
            + str(limit)
            + " words"
        )
        score -= 15

    # H5: first line does not start with an opener
    h5_ok = True
    if lines:
        if _is_opener(first_text, lang):
            h5_ok = False
    if not h5_ok:
        hard_fails.append("H5: first spoken line starts with a scene-setting opener")
        reasons.append("H5: first spoken line starts with a scene-setting opener")
        rewrites.append("Rewrite the first spoken line without a scene-setting opener")
        score -= 40

    # H6: action names a concrete subject
    h6_ok = _has_concrete_subject(first.get("action", ""), lang)
    if not h6_ok:
        reasons.append("H6: first shot action does not name a concrete subject")
        rewrites.append("Name a concrete subject in the first shot action")
        score -= 15

    if score < 0:
        score = 0

    passed = (len(hard_fails) == 0 and score >= 70)

    return {
        "pass": passed,
        "score": score,
        "hard_fails": hard_fails,
        "reasons": reasons,
        "rewrites": rewrites,
    }
