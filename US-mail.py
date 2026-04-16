import random
import string
from collections import defaultdict
from pathlib import Path
from secrets import choice as sec_choice
from secrets import randbelow

# 仅标准库，兼容性强
# 输出格式：username----password

BIRTH_GROUPS = {
    "older": {
        "years": (1983, 1989),
        "male": {
            "james": 11.0, "john": 10.8, "robert": 10.5, "michael": 12.2, "william": 10.0,
            "david": 10.0, "richard": 10.2, "joseph": 9.6, "thomas": 9.4, "christopher": 8.2,
            "daniel": 8.2, "matthew": 7.2, "joshua": 5.0, "tyler": 2.0, "noah": 1.0,
            "ethan": 1.6, "logan": 0.8,
        },
        "female": {
            "mary": 12.0, "patricia": 10.0, "jennifer": 11.2, "linda": 9.5, "elizabeth": 9.2,
            "barbara": 9.0, "susan": 8.8, "sarah": 7.2, "karen": 8.2, "lisa": 7.6,
            "jessica": 6.2, "amanda": 5.6, "emily": 2.8, "olivia": 0.8, "emma": 1.0,
        },
    },
    "mid": {
        "years": (1990, 1997),
        "male": {
            "michael": 9.4, "christopher": 10.5, "daniel": 10.0, "matthew": 11.4, "anthony": 8.8,
            "mark": 6.5, "andrew": 9.8, "joshua": 10.8, "kevin": 7.2, "brian": 6.8,
            "jason": 8.6, "ryan": 9.8, "jacob": 9.0, "nicholas": 9.2, "jonathan": 8.4,
            "justin": 10.0, "brandon": 10.2, "benjamin": 7.2, "alexander": 6.4, "tyler": 10.4,
            "aaron": 7.2, "adam": 7.2, "nathan": 7.4, "kyle": 8.2, "ethan": 5.2,
            "noah": 3.0, "austin": 8.8,
        },
        "female": {
            "jennifer": 8.2, "jessica": 11.8, "sarah": 10.2, "ashley": 11.2, "kimberly": 7.4,
            "emily": 10.8, "michelle": 8.0, "amanda": 10.0, "melissa": 9.2, "stephanie": 8.8,
            "rebecca": 8.2, "nicole": 9.8, "samantha": 10.0, "katherine": 6.6, "emma": 3.0,
            "olivia": 2.2, "hannah": 7.6, "natalie": 6.0, "elizabeth": 7.4, "anna": 6.6,
        },
    },
    "younger": {
        "years": (1998, 2005),
        "male": {
            "joshua": 6.6, "jacob": 11.0, "nicholas": 7.2, "brandon": 5.0, "benjamin": 9.8,
            "alexander": 9.6, "tyler": 6.0, "nathan": 9.6, "ethan": 11.4, "noah": 11.8,
            "logan": 10.2, "elijah": 9.4, "mason": 10.8, "luke": 8.6, "isaac": 7.2,
            "caleb": 8.2, "owen": 7.8, "wyatt": 7.4, "julian": 6.2, "levi": 6.8,
            "ezra": 5.6, "hudson": 4.2, "connor": 7.2, "jordan": 5.6, "adrian": 5.0,
            "xavier": 5.4, "asher": 6.0, "landon": 7.0, "eli": 6.2,
        },
        "female": {
            "emily": 7.0, "emma": 12.0, "olivia": 12.6, "sophia": 10.8, "ava": 10.0,
            "chloe": 8.6, "grace": 8.2, "hannah": 8.0, "natalie": 7.0, "zoe": 7.6,
            "claire": 6.6, "audrey": 6.2, "lucy": 6.6, "maya": 6.0, "ella": 8.8,
            "lily": 8.6, "aria": 7.2, "scarlett": 6.6, "layla": 7.2, "nora": 6.6,
            "hazel": 5.6, "violet": 6.0, "aurora": 4.8, "bella": 6.2, "skylar": 4.4,
            "madelyn": 6.8, "leah": 6.0, "naomi": 5.0, "sadie": 4.6, "hailey": 6.2,
        },
    },
}

LAST_NAME_WEIGHTS = {
    "smith": 10.0, "johnson": 9.2, "williams": 8.8, "brown": 8.6, "jones": 8.1,
    "garcia": 7.3, "miller": 7.1, "davis": 6.9, "rodriguez": 6.2, "martinez": 6.0,
    "hernandez": 5.8, "lopez": 5.7, "gonzalez": 5.6, "wilson": 5.4, "anderson": 5.1,
    "thomas": 4.9, "taylor": 4.8, "moore": 4.7, "jackson": 4.5, "martin": 4.4,
    "lee": 4.3, "perez": 4.1, "thompson": 4.0, "white": 3.9, "harris": 3.8,
    "sanchez": 3.6, "clark": 3.5, "ramirez": 3.4, "lewis": 3.3, "robinson": 3.2,
    "walker": 3.1, "young": 3.0, "allen": 2.9, "king": 2.8, "wright": 2.8,
    "scott": 2.7, "torres": 2.7, "nguyen": 2.6, "hill": 2.6, "flores": 2.5,
    "green": 2.5, "adams": 2.4, "nelson": 2.4, "baker": 2.3, "hall": 2.3,
    "rivera": 2.2, "campbell": 2.2, "mitchell": 2.1, "carter": 2.1, "roberts": 2.1,
    "gomez": 2.0, "phillips": 2.0, "evans": 1.9, "turner": 1.9, "diaz": 1.9,
    "parker": 1.8, "cruz": 1.8, "edwards": 1.8, "collins": 1.7, "reyes": 1.7,
    "stewart": 1.7, "morris": 1.6, "morales": 1.6, "murphy": 1.6, "cook": 1.5,
    "rogers": 1.5, "morgan": 1.5, "peterson": 1.5, "cooper": 1.4, "reed": 1.4,
    "bailey": 1.4, "bell": 1.4, "kelly": 1.4, "howard": 1.3, "ward": 1.3,
    "cox": 1.3, "richardson": 1.2, "watson": 1.2, "brooks": 1.2, "bennett": 1.2,
    "gray": 1.2, "james": 1.1, "wood": 1.1, "barnes": 1.1, "ross": 1.1,
    "henderson": 1.0, "coleman": 1.0, "jenkins": 1.0, "perry": 1.0, "powell": 0.9,
    "long": 0.9, "patterson": 0.9, "hughes": 0.9, "price": 0.9, "butler": 0.8,
    "simmons": 0.8, "foster": 0.8, "gonzales": 0.8, "bryant": 0.8, "alexander": 0.7,
    "russell": 0.7, "griffin": 0.7, "hayes": 0.7, "myers": 0.7,
}

ETHNIC_LAST_NAME_GROUPS = {
    "hispanic": {"garcia", "rodriguez", "martinez", "hernandez", "lopez", "gonzalez", "perez", "sanchez", "ramirez", "rivera", "gomez", "diaz", "cruz", "reyes", "morales", "flores", "torres"},
    "asian": {"nguyen", "lee"},
}

ETHNIC_FIRST_NAME_BIAS = {
    "hispanic": {
        "male": {"joseph": 1.18, "anthony": 1.10, "daniel": 1.08, "adrian": 1.14, "xavier": 1.14, "alexander": 1.08, "christopher": 1.04},
        "female": {"jessica": 1.08, "samantha": 1.10, "anna": 1.08, "isabella": 1.20, "bella": 1.18, "olivia": 1.02},
    },
    "asian": {
        "male": {"kevin": 1.12, "daniel": 1.08, "andrew": 1.08, "ethan": 1.05, "christopher": 1.03},
        "female": {"michelle": 1.10, "emily": 1.08, "grace": 1.08, "anna": 1.06, "amy": 1.06},
    },
}

NICKNAME_MAP = {
    "michael": [("mike", 0.72), ("mikey", 0.28)],
    "william": [("will", 0.45), ("bill", 0.35), ("billy", 0.20)],
    "robert": [("rob", 0.60), ("bobby", 0.40)],
    "richard": [("rick", 0.58), ("ricky", 0.42)],
    "joseph": [("joe", 0.78), ("joey", 0.22)],
    "thomas": [("tom", 0.72), ("tommy", 0.28)],
    "daniel": [("dan", 0.64), ("danny", 0.36)],
    "matthew": [("matt", 1.0)],
    "anthony": [("tony", 1.0)],
    "andrew": [("andy", 0.65), ("drew", 0.35)],
    "nicholas": [("nick", 0.78), ("nicky", 0.22)],
    "jonathan": [("jon", 0.78), ("johnny", 0.22)],
    "benjamin": [("ben", 0.82), ("benny", 0.18)],
    "alexander": [("alex", 0.88), ("xander", 0.12)],
    "katherine": [("kate", 0.63), ("katie", 0.37)],
    "elizabeth": [("liz", 0.42), ("lizzy", 0.18), ("beth", 0.40)],
    "jennifer": [("jen", 0.58), ("jenny", 0.42)],
    "jessica": [("jess", 0.56), ("jessie", 0.44)],
    "kimberly": [("kim", 1.0)],
    "rebecca": [("becca", 0.54), ("becky", 0.46)],
    "samantha": [("sam", 0.66), ("sammie", 0.34)],
    "olivia": [("liv", 1.0)],
    "madelyn": [("maddy", 1.0)],
    "caroline": [("carrie", 1.0)],
    "anthony": [("tony", 1.0)],
    "christopher": [("chris", 0.88), ("topher", 0.12)],
    "james": [("jim", 0.46), ("jimmy", 0.54)],
    "charles": [("charlie", 0.64), ("chuck", 0.36)],
    "joseph": [("joe", 0.76), ("joey", 0.24)],
    "isabella": [("bella", 1.0)],
}

COMMON_MIDDLE_INITIALS = list("AJMKRTECLDBS")
COMMON_PASSWORD_WORDS = [
    "River", "Shadow", "Hunter", "Sky", "Stone", "Falcon", "Maple", "Ash",
    "Storm", "Tiger", "Eagle", "Silver", "Cedar", "Nova", "Echo", "Blaze",
    "Atlas", "Phoenix", "Jasper", "Harbor", "Forest", "Rocket", "Knight",
    "Willow", "Coral", "Autumn", "Summer", "Winter", "Sunny", "Ocean", "Brook",
    "Amber", "Olive", "Pearl", "Ruby", "Ivy", "Sage", "Aspen", "Raven",
    "Canyon", "Meadow", "Birch", "Copper", "Dawn", "Ember", "Frost", "Glacier",
]
COMMON_PASSWORD_TAILS = [
    "Lane", "Cloud", "Field", "Spark", "Trail", "Point", "Light", "Wave",
    "Brook", "Fox", "Wolf", "Star", "Dust", "Bloom", "Crest", "Peak",
    "Wood", "Hill", "Stone", "Gate", "Heart", "Flame", "Shore", "Vale",
    "Bridge", "Park", "Ridge", "Lake", "Harbor", "Creek", "Berry", "View",
]
CASUAL_PASSWORD_WORDS = [
    "Family", "Monkey", "Soccer", "Summer", "Winter", "Secret", "Princess", "Sunshine",
    "Coffee", "Baseball", "Welcome", "Freedom", "Mustang", "Jordan", "Taylor", "Buddy",
]
KEYBOARD_PASSWORDS = ["Qwer", "Asdf", "Zxcv", "Pass", "Login", "Admin"]
STATE_CODES = ["tx", "ca", "ny", "fl", "nj", "az", "ga", "nc", "va", "wa"]
EMAIL_DOMAINS = [
    ("gmail", 0.50), ("yahoo", 0.20), ("hotmail", 0.13), ("outlook", 0.09),
    ("aol", 0.03), ("icloud", 0.05),
]
SPECIALS = "!@#$%&*?"
SEPARATORS = ["", ".", "_"]
CLASSIC_SEPARATORS = ["", "", "."]
LUCKY_NUMBERS = [7, 8, 11, 13, 17, 21, 23, 24, 27, 32, 42]
MONTH_ABBR = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def weighted_choice_map(weight_map):
    keys = list(weight_map.keys())
    weights = list(weight_map.values())
    return random.choices(keys, weights=weights, k=1)[0]


def weighted_pick_pairs(pairs):
    values = [item[0] for item in pairs]
    weights = [item[1] for item in pairs]
    return random.choices(values, weights=weights, k=1)[0]


def pick_birth_profile():
    group_name = random.choices(
        ["older", "mid", "younger"],
        weights=[0.18, 0.45, 0.37],
        k=1,
    )[0]
    group = BIRTH_GROUPS[group_name]
    birth_year = random.randint(group["years"][0], group["years"][1])
    gender = "male" if random.random() < 0.51 else "female"
    return group_name, birth_year, group, gender


def weighted_last_name():
    return weighted_choice_map(LAST_NAME_WEIGHTS)


def detect_last_name_group(last):
    for group_name, names in ETHNIC_LAST_NAME_GROUPS.items():
        if last in names:
            return group_name
    return "general"


def weighted_first_name(group, gender, last_name_group):
    source = dict(group[gender])
    bias_map = ETHNIC_FIRST_NAME_BIAS.get(last_name_group, {}).get(gender, {})
    for name, factor in bias_map.items():
        if name in source:
            source[name] *= factor
    return weighted_choice_map(source)


def nickname_for(first, account_era):
    if first not in NICKNAME_MAP:
        return None
    chance = 0.08
    if first in {"michael", "william", "robert", "joseph", "jennifer", "jessica", "christopher"}:
        chance = 0.14
    if account_era == "legacy":
        chance += 0.03
    if random.random() >= chance:
        return None
    return weighted_pick_pairs(NICKNAME_MAP[first])


def compact_num():
    value = random.randint(1, 99)
    if value < 10:
        return f"0{value}" if random.random() < 0.55 else str(value)
    return str(value)


def random_month_day():
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{month:02d}{day:02d}"


def pick_month_token():
    return random.choice(MONTH_ABBR)


def realistic_middle_initial(account_era):
    if account_era == "legacy" and random.random() < 0.16:
        return random.choice(COMMON_MIDDLE_INITIALS).lower()
    if account_era == "transition" and random.random() < 0.07:
        return random.choice(COMMON_MIDDLE_INITIALS).lower()
    if random.random() < 0.03:
        return random.choice(COMMON_MIDDLE_INITIALS).lower()
    return ""


def cleanup_username(username):
    username = username.replace("..", ".").replace("__", "_").replace("._", ".").replace("_.", "_")
    username = username.strip("._")
    return username[:30]


HIGH_OCCUPANCY_LAST_NAMES = {
    "smith", "johnson", "williams", "brown", "jones", "miller", "davis", "wilson",
    "anderson", "taylor", "martin", "thompson", "moore", "jackson", "white", "harris",
}

HIGH_OCCUPANCY_FIRST_NAMES = {
    "michael", "james", "john", "david", "jennifer", "jessica", "sarah", "emily",
    "ashley", "matthew", "daniel", "joshua", "chris", "christopher", "amanda", "emma",
}

CURRENT_ERA_OCCUPANCY = {
    "gmail": 1.10,
    "yahoo": 1.05,
    "hotmail": 1.08,
    "outlook": 1.00,
    "aol": 0.96,
    "icloud": 0.92,
}


def estimate_platform_taken_probability(profile, candidate, pair_count):
    probability = 0.0
    first = profile["first"]
    last = profile["last"]
    nick = profile["nickname"] or first
    lowered = candidate.lower()
    length = len(lowered)
    has_digit = any(ch.isdigit() for ch in lowered)
    digit_count = sum(ch.isdigit() for ch in lowered)
    domain_factor = CURRENT_ERA_OCCUPANCY.get(profile["preferred_domain"], 1.0)

    if lowered in {f"{first}{last}", f"{first}.{last}", f"{first}_{last}"}:
        probability += 0.70
    elif lowered in {f"{nick}{last}", f"{nick}.{last}", f"{nick}_{last}"}:
        probability += 0.57
    elif lowered in {f"{first}{last}{str(profile['birth_year'])[-2:]}", f"{first}.{last}{str(profile['birth_year'])[-2:]}", f"{first}_{last}{str(profile['birth_year'])[-2:]}", f"{nick}{str(profile['birth_year'])[-2:]}"}:
        probability += 0.42
    elif lowered in {f"{first}{last}{profile['birthday_md']}", f"{first}.{last}{profile['birthday_md']}", f"{first}_{last}{profile['birthday_md']}"}:
        probability += 0.26

    if length <= 8:
        return 0.998
    if length <= 10 and not has_digit:
        return 0.993
    if length <= 12 and not has_digit:
        probability += 0.40
    if length <= 12 and has_digit and digit_count <= 2:
        probability += 0.22
    if length <= 14 and has_digit and digit_count <= 2:
        probability += 0.10

    if first in HIGH_OCCUPANCY_FIRST_NAMES:
        probability += 0.10
    if last in HIGH_OCCUPANCY_LAST_NAMES:
        probability += 0.14
    if pair_count > 0:
        probability += min(0.08 * pair_count, 0.28)
    if not has_digit:
        probability += 0.12
    if "." in lowered or "_" in lowered:
        probability -= 0.03
    if digit_count >= 4:
        probability -= 0.14
    elif digit_count >= 3:
        probability -= 0.09
    elif has_digit:
        probability -= 0.03
    if length >= 15:
        probability -= 0.07
    if profile["account_era"] == "legacy":
        probability += 0.05

    probability *= domain_factor
    return max(0.0, min(probability, 0.998))


def is_platform_taken(profile, candidate, pair_count):
    probability = estimate_platform_taken_probability(profile, candidate, pair_count)
    return random.random() < probability


def choose_email_domain(account_era):
    pairs = EMAIL_DOMAINS
    if account_era == "legacy":
        pairs = [("gmail", 0.34), ("yahoo", 0.26), ("hotmail", 0.20), ("outlook", 0.06), ("aol", 0.08), ("icloud", 0.06)]
    elif account_era == "modern":
        pairs = [("gmail", 0.60), ("yahoo", 0.14), ("hotmail", 0.08), ("outlook", 0.10), ("aol", 0.01), ("icloud", 0.07)]
    return weighted_pick_pairs(pairs)


def choose_digit_token(profile, purpose="username"):
    year = str(profile["birth_year"])
    yy = year[-2:]
    style = profile["digit_style"]

    if style == "birth_year":
        base_choices = [(yy, 0.50), (year, 0.30), (compact_num(), 0.12), (str(profile["lucky_number"]), 0.08)]
    elif style == "birthday":
        base_choices = [(profile["birthday_md"], 0.42), (profile["birthday_m"], 0.22), (yy, 0.18), (compact_num(), 0.18)]
    elif style == "lucky":
        base_choices = [(str(profile["lucky_number"]), 0.42), (yy, 0.26), (compact_num(), 0.22), (str(random.randint(100, 999)), 0.10)]
    else:
        base_choices = [(compact_num(), 0.32), (yy, 0.26), (str(random.randint(100, 999)), 0.22), (year, 0.12), (profile["birthday_md"], 0.08)]

    if purpose == "password":
        base_choices.append((random_month_day(), 0.06))

    values = [item[0] for item in base_choices]
    weights = [item[1] for item in base_choices]
    return random.choices(values, weights=weights, k=1)[0]


def choose_user_habit(profile):
    if profile["account_era"] == "legacy":
        return random.choices(["full_name", "nickname", "initial_last", "name_year", "stateful"], weights=[0.28, 0.22, 0.18, 0.24, 0.08], k=1)[0]
    if profile["group_name"] == "younger":
        return random.choices(["full_name", "nickname", "name_year", "short_handle", "stateful"], weights=[0.24, 0.24, 0.24, 0.18, 0.10], k=1)[0]
    return random.choices(["full_name", "nickname", "initial_last", "name_year", "short_handle"], weights=[0.28, 0.18, 0.20, 0.24, 0.10], k=1)[0]


def choose_password_style(profile):
    if profile["account_era"] == "legacy":
        return random.choices(["legacy", "nickname", "casual", "nature", "keyboard"], weights=[0.34, 0.20, 0.20, 0.18, 0.08], k=1)[0]
    if profile["group_name"] == "younger":
        return random.choices(["nickname", "nature", "casual", "mixed_case", "keyboard"], weights=[0.26, 0.22, 0.24, 0.18, 0.10], k=1)[0]
    return random.choices(["nature", "nickname", "legacy", "mixed_case", "casual", "keyboard"], weights=[0.24, 0.22, 0.18, 0.16, 0.12, 0.08], k=1)[0]


def build_profile(used_name_pairs):
    best = None
    best_score = None

    for _ in range(14):
        group_name, birth_year, group, gender = pick_birth_profile()
        account_era = random.choices(["legacy", "transition", "modern"], weights=[0.24, 0.31, 0.45], k=1)[0]
        last = weighted_last_name()
        last_name_group = detect_last_name_group(last)
        first = weighted_first_name(group, gender, last_name_group)
        score = used_name_pairs[(first, last)]
        birth_month = random.randint(1, 12)
        birth_day = random.randint(1, 28)
        birthday_md = f"{birth_month:02d}{birth_day:02d}"
        birthday_m = f"{birth_month}{birth_day:02d}" if random.random() < 0.52 else birthday_md

        profile = {
            "group_name": group_name,
            "gender": gender,
            "birth_year": birth_year,
            "first": first,
            "last": last,
            "last_name_group": last_name_group,
            "account_era": account_era,
            "lucky_number": random.choice(LUCKY_NUMBERS),
            "state_code": random.choice(STATE_CODES),
            "birthday_md": birthday_md,
            "birthday_m": birthday_m,
        }
        profile["digit_style"] = random.choices(["birth_year", "birthday", "lucky", "random"], weights=[0.26, 0.24, 0.10, 0.40], k=1)[0]
        profile["nickname"] = nickname_for(first, account_era)
        profile["middle_initial"] = realistic_middle_initial(account_era)
        profile["user_habit"] = choose_user_habit(profile)
        profile["password_style"] = choose_password_style(profile)
        profile["preferred_domain"] = choose_email_domain(account_era)
        profile["separator_preference"] = random.choices(["none", "dot", "underscore"], weights=[0.58, 0.26, 0.16], k=1)[0]
        profile["uses_birth_hint"] = random.random() < 0.62
        profile["reuse_name_in_password"] = random.random() < 0.44
        profile["double_special"] = random.random() < 0.14
        profile["caps_style"] = random.choices(["title", "mixed", "lower_lead"], weights=[0.64, 0.16, 0.20], k=1)[0]

        if best is None or score < best_score:
            best = profile
            best_score = score
            if score == 0:
                break

    return best


def separator_for(profile, allow_empty=True):
    pref = profile["separator_preference"]
    if pref == "dot":
        return "."
    if pref == "underscore":
        return "_"
    return "" if allow_empty else random.choice([".", "_"])


def short_first(first):
    if len(first) <= 4:
        return first
    cut = random.choice([3, 4, 5])
    return first[:cut]


def short_last(last):
    if len(last) <= 5:
        return last
    cut = random.choice([4, 5, 6])
    return last[:cut]


def style_sequence(pair_count, profile):
    user_habit = profile["user_habit"]
    account_era = profile["account_era"]

    if user_habit == "full_name":
        desired = ["human_core"]
    elif user_habit == "nickname":
        desired = ["nickname_core"]
    elif user_habit == "initial_last":
        desired = ["initial_last"]
    elif user_habit == "stateful":
        desired = ["stateful"]
    elif user_habit == "short_handle":
        desired = ["short_handle"]
    else:
        desired = ["name_year"]

    compromise = ["name_year", "human_core", "nickname_core", "classic"]
    if account_era == "legacy":
        compromise.append("initial_last")
    if profile["group_name"] == "younger":
        compromise.append("short_handle")

    fallback = ["collision", "fallback"]
    ordered = []
    seen = set()
    for item in desired + compromise + fallback:
        if item not in seen:
            seen.add(item)
            ordered.append(item)

    shift = min(pair_count, max(0, len(ordered) - 2))
    if shift > 0:
        stable = ordered[:-2]
        stable = stable[shift:] + stable[:shift]
        ordered = stable + ordered[-2:]
    return ordered


def username_candidates(profile, style):
    first = profile["first"]
    last = profile["last"]
    nick = profile["nickname"] or first
    fi = first[0]
    li = last[0]
    mi = profile["middle_initial"]
    yy = str(profile["birth_year"])[-2:]
    year = str(profile["birth_year"])
    sep = separator_for(profile)
    alt_sep = separator_for(profile, allow_empty=False)
    digit = choose_digit_token(profile, purpose="username")
    alt_digit = choose_digit_token(profile, purpose="username")
    domain = profile["preferred_domain"]
    month_token = pick_month_token()

    style_map = {
        "human_core": [
            f"{first}{sep}{last}{digit}{compact_num()}",
            f"{first}{alt_sep}{last}{profile['birthday_md']}",
            f"{first}{sep}{li}{digit}{compact_num()}",
            f"{first}{alt_sep}{last}{yy}{compact_num()}",
            f"{first}{last}{digit}{compact_num()}",
        ],
        "nickname_core": [
            f"{nick}{alt_sep}{last}{digit}{compact_num()}",
            f"{nick}{profile['birthday_md']}{compact_num()}",
            f"{nick}{li}{digit}{compact_num()}",
            f"{nick}{month_token}{compact_num()}{compact_num()}",
            f"{nick}{alt_sep}{last}{yy}{compact_num()}",
        ],
        "initial_last": [
            f"{fi}{last}{yy}{compact_num()}",
            f"{fi}{alt_sep}{last}{digit}{compact_num()}",
            f"{first}{mi}{last}{profile['birthday_md']}" if mi else f"{fi}{last}{digit}{compact_num()}",
            f"{fi}{short_last(last)}{digit}{compact_num()}",
            f"{fi}{last}{profile['birthday_md']}",
        ],
        "name_year": [
            f"{first}{last}{year}",
            f"{first}.{last}{profile['birthday_md']}",
            f"{nick}{last}{digit}{compact_num()}",
            f"{first}{digit}{compact_num()}{compact_num()}",
            f"{last}{yy}{compact_num()}{compact_num()}",
        ],
        "short_handle": [
            f"{short_first(first)}{digit}{compact_num()}{compact_num()}",
            f"{short_first(first)}{alt_sep}{li}{digit}{compact_num()}",
            f"{nick}{short_last(last)}{digit}{compact_num()}",
            f"{short_first(first)}{month_token}{compact_num()}{compact_num()}",
            f"{short_first(first)}{short_last(last)}{yy}{compact_num()}",
        ],
        "stateful": [
            f"{nick}_{profile['state_code']}{yy}{compact_num()}",
            f"{first}{li}{profile['state_code']}{digit}{compact_num()}",
            f"{first}{last}{profile['state_code']}{profile['birthday_md']}",
            f"{nick}{domain}{compact_num()}{compact_num()}",
            f"{first}{alt_sep}{last}{profile['state_code']}{compact_num()}",
        ],
        "classic": [
            f"{first}{last}{digit}{compact_num()}",
            f"{fi}{last}{yy}{compact_num()}",
            f"{first}.{last}{digit}{compact_num()}",
            f"{nick}{last}{yy}{compact_num()}",
            f"{first}_{last}{profile['birthday_md']}",
        ],
        "collision": [
            f"{first}{last}{alt_digit}{compact_num()}",
            f"{nick}.{last}{random.randint(100, 999)}",
            f"{first}{random.choice(string.ascii_lowercase)}{last}{random.randint(100, 999)}",
            f"{last}{first}{random.randint(100, 999)}",
            f"{first}{alt_sep}{last}{random.randint(1000, 9999)}",
        ],
        "fallback": [
            f"{first}{last}{random.randint(1000, 9999)}",
            f"{nick}.{last}{random.randint(100, 999)}",
            f"{first}{random.choice(string.ascii_lowercase)}{last}{random.randint(100, 999)}",
            f"{last}{first}{random.randint(100, 999)}",
            f"{first}{last}{year}{compact_num()}",
        ],
    }

    min_length = 12
    if profile["preferred_domain"] in {"gmail", "hotmail", "yahoo"}:
        min_length = 13
    elif profile["preferred_domain"] in {"outlook", "icloud"}:
        min_length = 12
    else:
        min_length = 11

    cleaned = []
    seen = set()
    for item in style_map.get(style, []):
        value = cleanup_username(item)
        if value and value not in seen and len(value) >= min_length:
            seen.add(value)
            cleaned.append(value)
    return cleaned


def make_username(profile, used_usernames, used_name_pairs):
    first = profile["first"]
    last = profile["last"]
    pair_count = used_name_pairs[(first, last)]
    plan = style_sequence(pair_count, profile)

    for stage_index, style in enumerate(plan):
        candidates = username_candidates(profile, style)
        for candidate in candidates:
            if candidate in used_usernames:
                continue
            effective_pair_count = pair_count + stage_index
            if is_platform_taken(profile, candidate, effective_pair_count):
                continue
            used_name_pairs[(first, last)] += 1
            return candidate

    staged_suffixes = [
        profile["birthday_md"],
        str(profile["birth_year"]),
        f"{str(profile['birth_year'])[-2:]}{compact_num()}",
        str(random.randint(100, 999)),
        str(random.randint(1000, 9999)),
    ]

    base_handles = [
        f"{first}{last}",
        f"{profile['nickname'] or first}{last}",
        f"{first}.{last}",
        f"{first}_{last}",
        f"{first}{last}{profile['state_code']}",
    ]

    min_fallback_length = 12 if profile["preferred_domain"] in {"outlook", "icloud", "gmail", "hotmail", "yahoo"} else 11

    for stage_index, suffix in enumerate(staged_suffixes, start=len(plan)):
        for handle in base_handles:
            fallback = cleanup_username(f"{handle}{suffix}")
            if len(fallback) < min_fallback_length or fallback in used_usernames:
                continue
            if is_platform_taken(profile, fallback, pair_count + stage_index):
                continue
            used_name_pairs[(first, last)] += 1
            return fallback

    for stage_index in range(12):
        fallback = cleanup_username(f"{first}{last}{random.randint(1000, 99999)}")
        if fallback in used_usernames:
            continue
        if is_platform_taken(profile, fallback, pair_count + len(plan) + stage_index):
            continue
        used_name_pairs[(first, last)] += 1
        return fallback

    fallback = cleanup_username(f"{first}{last}{random.randint(100000, 999999)}")
    used_name_pairs[(first, last)] += 1
    return fallback


def natural_tail():
    pieces = [
        str(random.randint(10, 99)),
        random.choice(string.ascii_lowercase),
        sec_choice(SPECIALS),
    ]
    return random.choices(
        [pieces[0] + pieces[2], pieces[2] + pieces[0], pieces[0] + pieces[1]],
        weights=[0.48, 0.27, 0.25],
        k=1,
    )[0]


def name_fragment(profile):
    options = [profile["first"], profile["last"], profile["nickname"] or profile["first"]]
    value = random.choice(options)
    if profile["caps_style"] == "lower_lead":
        return value.lower()
    if profile["caps_style"] == "mixed":
        return value[:1].upper() + value[1:].lower()
    return value.capitalize()


def casual_word():
    return random.choice(CASUAL_PASSWORD_WORDS)


def finalize_special(special, profile):
    if profile["double_special"] and random.random() < 0.65:
        return special * 2
    return special


def build_password_seed(profile):
    style = profile["password_style"]
    number_part = choose_digit_token(profile, purpose="password")
    special = finalize_special(sec_choice(SPECIALS), profile)
    name_part = name_fragment(profile)
    word1 = random.choice(COMMON_PASSWORD_WORDS)
    word2 = random.choice(COMMON_PASSWORD_TAILS)
    casual = casual_word()
    reusable_name = name_part if profile["reuse_name_in_password"] else random.choice([word1, casual])

    if style == "nickname":
        patterns = [
            f"{reusable_name}{number_part}{special}",
            f"{reusable_name}{special}{number_part}",
            f"{reusable_name}{profile['birthday_md']}{special}",
            f"{reusable_name}{profile['lucky_number']}{special}{profile['last'][0].upper()}",
        ]
    elif style == "keyboard":
        key = random.choice(KEYBOARD_PASSWORDS)
        patterns = [
            f"{key}{number_part}{special}",
            f"{key}{special}{number_part}",
            f"{key}{profile['birth_year']}{special}",
            f"{key.capitalize()}{profile['lucky_number']}{special}{profile['first'][0]}",
        ]
    elif style == "legacy":
        patterns = [
            f"{word1}{number_part}{special}",
            f"{word1}{word2}{str(profile['birth_year'])[-2:]}{special}",
            f"{reusable_name}{str(profile['birth_year'])[-2:]}{special}",
            f"{word1}{profile['lucky_number']}{special}",
        ]
    elif style == "mixed_case":
        patterns = [
            f"{word1.lower()}{word2}{number_part}{special}",
            f"{reusable_name.lower()}{word2}{number_part}{special}",
            f"{word1}{number_part}{special}{word2.lower()}",
            f"{reusable_name}{special}{number_part}{word2.lower()}",
        ]
    elif style == "casual":
        patterns = [
            f"{casual}{number_part}{special}",
            f"{casual}{profile['birthday_md']}{special}",
            f"{casual}{profile['lucky_number']}{special}",
            f"{reusable_name}{casual[:3]}{number_part}{special}",
        ]
    else:
        patterns = [
            f"{word1}{word2}{number_part}{special}",
            f"{word1}{special}{word2}{number_part}",
            f"{word1}{number_part}{special}{word2}",
            f"{word1}{word2}{special}{number_part}",
            f"{reusable_name}{number_part}{word2}{special}",
        ]

    return random.choice(patterns)


def finalize_password(password, target_length):
    while len(password) < target_length:
        password += natural_tail()

    password = password[:target_length]

    if not any(c.islower() for c in password):
        password = "a" + password[1:]
    if not any(c.isupper() for c in password):
        password = password[0] + "A" + password[2:]
    if not any(c.isdigit() for c in password):
        password = password[:-1] + str(randbelow(10))
    if not any(c in SPECIALS for c in password):
        password = password[:-2] + sec_choice(SPECIALS) + password[-1]

    return password


def make_password(profile, length=None):
    password = build_password_seed(profile)
    if length is None:
        if profile["account_era"] == "legacy":
            length = random.randint(10, 14)
        else:
            length = random.randint(12, 16)
    return finalize_password(password, length)


def generate_pairs(count=200):
    used_usernames = set()
    used_name_pairs = defaultdict(int)
    rows = []
    max_attempts = count * 45
    attempts = 0

    while len(rows) < count and attempts < max_attempts:
        attempts += 1
        profile = build_profile(used_name_pairs)
        username = make_username(profile, used_usernames, used_name_pairs)

        if len(username) < 6 or username in used_usernames:
            continue

        used_usernames.add(username)
        rows.append(f"{username}----{make_password(profile)}")

    return rows


def save_to_file(rows, output_file="accounts.txt"):
    path = Path(output_file)
    path.write_text("\n".join(rows), encoding="utf-8")
    return path


def main():
    count = 300
    output_file = "accounts.txt"

    rows = generate_pairs(count=count)
    path = save_to_file(rows, output_file=output_file)
    print(f"Generated {len(rows)} pairs -> {path}")


if __name__ == "__main__":
    main()
