"""
size_utils.py — Shared size upsizing logic.

Used by both Export Orders and Update Existing Excel workflows.
Change the mapping here and both workflows update automatically.
"""

# ── Size upsizing map ─────────────────────────────────────────────────────
_SIZE_UP = {
    "XXS":   "XS",
    "XS":    "S",
    "S":     "M",
    "M":     "L",
    "L":     "XL",
    "XL":    "XXL",
    "XXL":   "XXXL",
    "XXXL":  "XXXXL",
    "2XL":   "3XL",
    "3XL":   "4XL",
    "4XL":   "5XL",
    "5XL":   "6XL",
}

# Numeric sizes: 20→21, 36→37, 40→41, etc.
for _n in range(20, 60):
    _SIZE_UP[str(_n)] = str(_n + 1)


def get_next_size(size_str: str) -> str:
    """Return the next size up, or the original if no mapping exists.

    Preserves the original casing style:
      'xl'  → 'xxl'
      'XL'  → 'XXL'
      'Xl'  → 'Xxl'
    """
    if not size_str or not size_str.strip():
        return size_str

    stripped = size_str.strip()
    key = stripped.upper()
    upped = _SIZE_UP.get(key)

    if not upped:
        return stripped

    # Preserve original casing style
    if stripped.islower():
        return upped.lower()
    if stripped[0].isupper() and len(stripped) > 1 and stripped[1:].islower():
        return upped.capitalize()
    return upped
