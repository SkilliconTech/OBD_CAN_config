def require(ok, message):
    if not ok:
        raise ValueError(message)

def check_keys(obj, expected, label):
    require(isinstance(obj, dict) and set(obj) == set(expected.split()),
            f"{label}: expected fields: {expected}")
    
def check_int(value, low, high, label):
    require(type(value) is int and low <= value <= high,
            f"{label}: enter an integer from {low} to {high}")

def check_bool(value, label):
    require(type(value) is bool, f"{label}: expected true or false")


def parse_can_id(value, extended):
    require(isinstance(value, str) and value.lower().startswith("0x")
            and len(value) > 2
            and all(c in "0123456789abcdefABCDEF" for c in value[2:]),
            "Use hexadecimal identifiers or masks, for example 0x123")
    result = int(value, 16)
    require(result <= (0x1FFFFFFF if extended else 0x7FF),
            "Identifier/mask exceeds selected ID width")
    return result


def validate_rule(rule):
    require(isinstance(rule, dict), "Filter must be an object")
    kind = rule.get("type")
    require(kind in ("id_list", "id_range", "id_mask"), "Invalid filter type")
    extra = {
        "id_list": "ids",
        "id_range": "id_start id_end",
        "id_mask": "match_id mask",
    }[kind]
    check_keys(rule, "filter_id type extended_id " + extra, "Filter")
    require(isinstance(rule["filter_id"], str)
            and 1 <= len(rule["filter_id"].strip()) <= 64,
            "Filter name must have 1-64 characters")
    check_bool(rule["extended_id"], "Extended ID")
    ext = rule["extended_id"]
    if kind == "id_list":
        require(isinstance(rule["ids"], list) and 1 <= len(rule["ids"]) <= 256,
                "Enter 1-256 IDs")
        values = [parse_can_id(v, ext) for v in rule["ids"]]
        require(len(set(values)) == len(values), "Duplicate IDs in list")
    elif kind == "id_range":
        require(parse_can_id(rule["id_start"], ext)
                <= parse_can_id(rule["id_end"], ext),
                "Range start exceeds end")
    else:
        parse_can_id(rule["match_id"], ext)
        parse_can_id(rule["mask"], ext)

# ---------------------------------------------------------------------------
# Two enabled filters must not match the same CAN identifier
# ---------------------------------------------------------------------------
def _rule_patterns(rule):
    """Turn a filter into ('m', match, mask) and ('r', start, end) pieces."""
    ext = rule["extended_id"]
    full = 0x1FFFFFFF if ext else 0x7FF
    kind = rule["type"]
    if kind == "id_list":
        return [("m", parse_can_id(v, ext), full) for v in rule["ids"]]
    if kind == "id_range":
        return [("r", parse_can_id(rule["id_start"], ext),
                      parse_can_id(rule["id_end"], ext))]
    return [("m", parse_can_id(rule["match_id"], ext),
                  parse_can_id(rule["mask"], ext))]


def _range_blocks(start, end):
    """Split [start, end] into aligned blocks (base, size)."""
    while start <= end:
        size = (start & -start) if start else 1 << 30
        while start + size - 1 > end:
            size >>= 1
        yield start, size
        start += size


def _patterns_overlap(p, q):
    if p[0] == "r" and q[0] == "r":
        return p[1] <= q[2] and q[1] <= p[2]
    if p[0] == "m" and q[0] == "m":
        return ((p[1] ^ q[1]) & p[2] & q[2]) == 0
    r, m = (p, q) if p[0] == "r" else (q, p)
    for base, size in _range_blocks(r[1], r[2]):
        if ((base ^ m[1]) & m[2] & ~(size - 1)) == 0:
            return True
    return False


def _rules_overlap(a, b):
    if a["extended_id"] != b["extended_id"]:
        return False
    pa, pb = _rule_patterns(a), _rule_patterns(b)
    if a["type"] == "id_list" and b["type"] == "id_list":
        return bool({p[1] for p in pa} & {q[1] for q in pb})
    return any(_patterns_overlap(p, q) for p in pa for q in pb)

def find_conflict_with(rule, others):
    """Name of a filter in 'others' that shares an identifier, or None."""
    for b in others:
        if _rules_overlap(rule, b):
            return b["filter_id"]
    return None


# ---------------------------------------------------------------------------
# CAN bus settings. These tables must match the dropdowns in the
# Classic CAN and CAN FD pages. If you change a dropdown, change it here too.
# Each bitrate maps to the sampling point(s) allowed with it.
# ---------------------------------------------------------------------------
CLASSIC_BITRATES = {
    "100.000 kbits/s": ("75%",),
    "125.000 kbits/s": ("75%",),
    "250.000 kbits/s": ("75%",),
    "500.000 kbits/s": ("75%",),
    "1.000 Mbits/s": ("75%",),
}

CLASSIC_SJW = ("1", "2", "3", "4")


def validate_filters(rules):
    require(isinstance(rules, list), "Filters must be a list")
    names = set()
    for rule in rules:
        validate_rule(rule)
        require(rule["filter_id"] not in names, "Duplicate filter name")
        names.add(rule["filter_id"])


def validate_classic_can(settings):
    check_keys(settings, "bitrate startup_delay_ms run_duration_ms",
               "Classic CAN")
    require(type(settings["bitrate"]) is int
            and settings["bitrate"] in CLASSIC_BITRATES,
            "Bitrate must be one of: "
            + ", ".join(str(b) for b in CLASSIC_BITRATES))
    check_int(settings["startup_delay_ms"], 0, 600000, "Startup delay")
    check_int(settings["run_duration_ms"], 0, 86400000, "Run duration")


def validate_complete_config(data):
    from can_tool.services.config_version import check_config_version

    check_config_version(data)      # also checks that data is an object
    check_keys(data, "version operating_mode bitrate startup_delay_ms "
                     "run_duration_ms filters", "Configuration")
    require(data["operating_mode"] == "can", 'operating_mode must be "can"')
    validate_classic_can({k: data[k] for k in
                          ("bitrate", "startup_delay_ms", "run_duration_ms")})
    check_keys(data["filters"], "classic_can", "Filters")
    validate_filters(data["filters"]["classic_can"])
    return True
