from fake_useragent import UserAgent
import requests
from bs4 import BeautifulSoup
import re
import time

def lookup_filament_code(code):
    """
    Search DuckDuckGo for '{code} filament' 
    and try to infer details from the results.
    """
    query = f"{code} filament code 3D printing"
    print(f"Searching DuckDuckGo for: {query}")
    
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    
    # DuckDuckGo HTML search
    url = f"https://html.duckduckgo.com/html/?q={query}"
    
    results = []
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Extract result titles (class 'result__a')
            links = soup.find_all('a', class_='result__a')
            for link in links[:5]: # Top 5
                results.append({
                    'title': link.get_text(),
                    'snippet': '' # HTML DDG snippets are harder to grab cleanly, title is usually enough
                })
        else:
            print(f"DDG Error: {r.status_code}")
    except Exception as e:
        print(f"Search error: {e}")
        return {}

    if not results:
        print("No search results found.")
        return {}

    best_match = {}
    
    # Process results trying to find meaningful data
    for res in results:
        title = res['title']
        print(f"Checking Result: {title}")
        
        # Merge dicts
        parsed = parse_string_info(title)
        
        # Accumulate data.
        for k, v in parsed.items():
            if not best_match.get(k) and v:
                best_match[k] = v
        
        # Stop if we have Brand, Material AND Color
        if best_match.get('brand') and best_match.get('material') and best_match.get('color_name'):
            break
            
    return best_match

def parse_string_info(text):
    """
    Extract Brand, Material, Color from a title string.
    """
    data = {}
    
    # 1. Brand (Expanded List)
    brands = ["Bambu Lab", "Bambu", "Overture", "eSun", "Sunlu", "Polymaker", "Hatchbox", 
              "Prusament", "Creality", "Eryone", "Amolen", "Inland", "Flashforge", "Elegoo", "Voxelab"]
    for brand in brands:
        if re.search(rf"\b{brand}\b", text, re.IGNORECASE):
            data["brand"] = brand
            # Normalize "Bambu" -> "Bambu Lab" if needed
            if brand.lower() == "bambu": data["brand"] = "Bambu Lab"
            break
            
    # 2. Material
    material_match = re.search(r"\b(PLA(?:\+| plus)?|PETG|ABS(?:-GF)?|TPU|ASA|Nylon|PC|PVA|CF)\b", text, re.IGNORECASE)
    if material_match:
        data["material"] = material_match.group(0).upper()
        # Subtypes
        subtype_match = re.search(r"(Basic|Matte|Silk|Translucent|Galaxy|Sparkle|Wood|Carbon Fiber)", text, re.IGNORECASE)
        if subtype_match:
             data["material"] = f"{data['material']} {subtype_match.group(1)}"

    # 3. Color
    colors = {
        "Black": "#000000", "White": "#FFFFFF", "Gray": "#808080", "Grey": "#808080",
        "Red": "#FF0000", "Blue": "#0000FF", "Green": "#008000", "Yellow": "#FFFF00",
        "Orange": "#FFA500", "Purple": "#800080", "Pink": "#FFC0CB", "Brown": "#A52A2A",
        "Silver": "#C0C0C0", "Gold": "#FFD700", "Copper": "#B87333", "Bronze": "#CD7F32",
        "Teal": "#008080", "Cyan": "#00FFFF", "Magenta": "#FF00FF", "Lime": "#00FF00",
        "Olive": "#808000", "Maroon": "#800000", "Navy": "#000080", "Aquamarine": "#7FFFD4",
        "Turquoise": "#40E0D0", "Violet": "#EE82EE", "Indigo": "#4B0082", "Beige": "#F5F5DC",
        "Ivory": "#FFFFF0", "Khaki": "#F0E68C", "Coral": "#FF7F50", "Salmon": "#FA8072",
        "Crimson": "#DC143C", "Lavender": "#E6E6FA", "Plum": "#DDA0DD", "Tan": "#D2B48C",
        "Mint": "#98FF98", "Peach": "#FFDAB9", "Charcoal": "#36454F", "Slate": "#708090",
        "Galaxy": "#222222", "Sparkle": "#444444", "Glow": "#CCFFCC", "Transparent": "#EFEFEF",
        "Clear": "#EFEFEF", "Natural": "#F5F5DC", "Pine Green": "#01796F"
    }
    
    # Sort by length desc to match "Pine Green" before "Green"
    for color_name in sorted(colors.keys(), key=len, reverse=True):
        if re.search(rf"\b{color_name}\b", text, re.IGNORECASE):
            data["color_name"] = color_name
            data["color_hex"] = colors[color_name]
            break
            
    # 4. Weight
    weight_match = re.search(r"(\d{1,4})\s?(g|kg)", text, re.IGNORECASE)
    if weight_match:
        val = int(weight_match.group(1))
        unit = weight_match.group(2).lower()
        if unit == 'kg': 
             val *= 1000
        data["weight_g"] = val
        
    return data
