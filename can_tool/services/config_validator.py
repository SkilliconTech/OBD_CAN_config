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
    check_keys(rule, "filter_id enabled type extended_id " + extra, "Filter")
    require(isinstance(rule["filter_id"], str)
            and 1 <= len(rule["filter_id"].strip()) <= 64,
            "Filter name must have 1-64 characters")
    check_bool(rule["enabled"], "Filter enabled")
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


def find_identifier_conflict(rules):
    """Names of the first two enabled filters sharing an identifier, or None."""
    active = [r for r in rules if r["enabled"]]
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            if _rules_overlap(a, b):
                return a["filter_id"], b["filter_id"]
    return None


def find_conflict_with(rule, others):
    """Name of an enabled filter in 'others' that shares an identifier."""
    if not rule["enabled"]:
        return None
    for b in others:
        if b["enabled"] and _rules_overlap(rule, b):
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

def validate_classic_can(settings):
    require(isinstance(settings, dict),
            "Classic CAN settings must be a JSON object.")
    _check_pair(settings, "bitrate", "sampling_point",
                CLASSIC_BITRATES, "Classic CAN")
    _check_choice(settings, "sjw", CLASSIC_SJW, "Classic CAN SJW")
    if "enabled" in settings:
        check_bool(settings["enabled"], "Classic CAN enabled")


def validate_complete_config(data):
    """
    Validate the overall configuration structure.
    """

    from can_tool.services.config_version import check_config_version

    if not isinstance(data, dict):
        raise ValueError(
            "Configuration must be a JSON object."
        )

    check_config_version(data)

    if not isinstance(data.get("classic_can"), dict):
        raise ValueError(
            "Classic CAN settings are missing or invalid."
        )

    if "canfd" in data and not isinstance(data["canfd"], dict):
        raise ValueError(
            "CAN FD settings must be a JSON object."
        )

    # Both flags may be true: they select frame types to record.
    for key in ("classic_can", "canfd"):
        if key in data and "enabled" in data[key]:
            check_bool(
                data[key]["enabled"],
                f"{key} enabled",
            )

    from can_tool.services.can_timing import normalize_shared_timing

    normalize_shared_timing(data)

    # NEW: reject incorrect CAN values
    validate_classic_can(data["classic_can"])
    if "canfd" in data:
        validate_canfd(data["canfd"])
    

    from can_tool.models.config_model import default_log_config

    log_data = default_log_config()

    for key in ("filters", "triggers", "logging"):
        if key in data:
            log_data[key] = data[key]

    validate_log_config(log_data)

    return True