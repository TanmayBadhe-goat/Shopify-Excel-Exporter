import re

def hex_to_rgb(hex_str):
    """Convert hex to RGB tuple."""
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c*2 for c in hex_str])
    if len(hex_str) != 6:
        return None
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return None

# Simplified base color palette for business-friendly naming
BASE_COLORS = {
    "Black": (0, 0, 0),
    "White": (255, 255, 255),
    "Gray": (128, 128, 128),
    "Red": (255, 0, 0),
    "Maroon": (128, 0, 0),
    "Yellow": (255, 255, 0),
    "Olive": (128, 128, 0),
    "Lime": (0, 255, 0),
    "Green": (0, 128, 0),
    "Aqua": (0, 255, 255),
    "Teal": (0, 128, 128),
    "Blue": (0, 0, 255),
    "Navy": (0, 0, 128),
    "Fuchsia": (255, 0, 255),
    "Purple": (128, 0, 128),
    "Silver": (192, 192, 192),
    "Orange": (255, 165, 0),
    "Brown": (165, 42, 42),
    "Beige": (245, 245, 220),
    "Pink": (255, 192, 203),
    "Gold": (255, 215, 0),
    "Sky Blue": (135, 206, 235),
    "Khaki": (240, 230, 140),
}

def get_closest_color(hex_str):
    """
    Find the closest standard color name for a given hex code.
    """
    target_rgb = hex_to_rgb(hex_str)
    if not target_rgb:
        return hex_str

    closest_name = "Unknown"
    min_distance = float('inf')

    for name, rgb in BASE_COLORS.items():
        # Euclidean distance in RGB space
        distance = sum((a - b) ** 2 for a, b in zip(target_rgb, rgb))
        if distance < min_distance:
            min_distance = distance
            closest_name = name
            
    return closest_name

def resolve_color(color_input):
    """
    Main entry point to resolve any color input (hex or name) to a simplified name.
    """
    if not color_input:
        return ""
    
    color_input = str(color_input).strip()
    
    # 1. If it's a hex code, find the closest standard color
    hex_match = re.search(r'#(?:[0-9a-fA-F]{3}){1,2}', color_input)
    if hex_match:
        return get_closest_color(hex_match.group(0))
    
    # 2. If it's already a name, simplify it
    # First, handle the title casing
    name = color_input.title()
    
    # Remove common complex modifiers that make names too specific
    modifiers = [
        "Very Dark", "Very Light", "Darkish", "Lightish", "Dark", "Light", 
        "Bright", "Pale", "Deep", "Dull", "Vivid", "Grayish", "Greyish"
    ]
    for mod in modifiers:
        # Case-insensitive replacement of whole words
        name = re.sub(rf'\b{mod}\b', '', name, flags=re.IGNORECASE).strip()
    
    # 3. Final mapping: if the simplified name contains a base color, just use that
    # e.g., "Navy Blue" -> "Navy" or "Blue" (priority to the base color match)
    for base in BASE_COLORS.keys():
        if base.lower() in name.lower():
            return base
            
    return name or color_input
