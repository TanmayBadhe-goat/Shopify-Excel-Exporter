from color_utils import resolve_color
from size_utils import get_next_size

def extract_color_robust(line_item, product=None):
    """
    Extract the human-readable color from line item and optional product data.
    """
    variant_title = line_item.get("variant_title") or ""
    
    # 1. Check variant options if product is provided
    if product:
        variant_id = line_item.get("variant_id")
        for variant in product.get("variants") or []:
            if variant.get("id") == variant_id:
                for opt in product.get("options") or []:
                    opt_name = (opt.get("name") or "").lower()
                    if opt_name in ("color", "colour"):
                        pos = opt.get("position", 1)
                        raw = variant.get(f"option{pos}", "")
                        if raw:
                            return resolve_color(raw)
                break

    # 2. Fallback: Variant title (e.g. "Pink / M")
    if variant_title:
        parts = variant_title.split("/")
        color_part = parts[0].strip()
        if color_part:
            return resolve_color(color_part)

    return ""

def extract_size_robust(line_item, product=None, upscale=True):
    """
    Extract the size and optionally upscale it.
    """
    variant_title = line_item.get("variant_title") or ""
    raw_size = ""

    # 1. Check variant options if product is provided
    if product:
        variant_id = line_item.get("variant_id")
        for variant in product.get("variants") or []:
            if variant.get("id") == variant_id:
                for opt in product.get("options") or []:
                    opt_name = (opt.get("name") or "").lower()
                    if opt_name == "size":
                        pos = opt.get("position", 1)
                        raw_size = variant.get(f"option{pos}", "")
                        break
                break

    # 2. Fallback: variant title last segment after '/'
    if not raw_size and "/" in variant_title:
        raw_size = variant_title.split("/")[-1].strip()
    elif not raw_size:
        raw_size = variant_title

    if not raw_size:
        return ""

    return get_next_size(raw_size) if upscale else raw_size
