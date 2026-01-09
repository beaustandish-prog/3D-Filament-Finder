import requests
import json

def lookup_barcode_product(barcode, barcode_type="UPC"):
    """
    Look up product information from a barcode using UPC Database API.
    Returns dict with product details if found, None otherwise.
    
    Free API: https://api.upcitemdb.com/prod/trial/lookup
    Note: Limited to 100 requests/day on free tier
    """
    
    # Try UPC Item DB API (free tier)
    try:
        url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "FilamentFinder/1.0"
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("items") and len(data["items"]) > 0:
                item = data["items"][0]
                
                # Extract relevant fields
                product_data = {
                    "brand": item.get("brand"),
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "category": item.get("category"),
                    "images": item.get("images", []),
                    "barcode": barcode,
                    "barcode_type": barcode_type
                }
                
                # Try to parse filament-specific data from title/description
                title_lower = (item.get("title") or "").lower()
                desc_lower = (item.get("description") or "").lower()
                combined_text = f"{title_lower} {desc_lower}"
                
                # Extract material
                if "pla" in combined_text:
                    product_data["material"] = "PLA"
                elif "petg" in combined_text:
                    product_data["material"] = "PETG"
                elif "abs" in combined_text:
                    product_data["material"] = "ABS"
                elif "tpu" in combined_text:
                    product_data["material"] = "TPU"
                
                # Extract weight
                import re
                weight_match = re.search(r"(\d+)\s?(kg|g)", combined_text)
                if weight_match:
                    val = int(weight_match.group(1))
                    unit = weight_match.group(2)
                    if unit == 'kg':
                        val *= 1000
                    product_data["weight_g"] = val
                
                # Extract diameter
                if "1.75" in combined_text or "1.75mm" in combined_text:
                    product_data["diameter"] = 1.75
                elif "2.85" in combined_text or "2.85mm" in combined_text:
                    product_data["diameter"] = 2.85
                
                return product_data
                
    except Exception as e:
        print(f"Barcode lookup error: {e}")
    
    return None


def enhance_with_barcode_data(parsed_data, barcode_data):
    """
    Enhance parsed OCR data with barcode lookup results.
    Only fills in missing fields, doesn't override existing data.
    """
    if not barcode_data or not barcode_data.get("data"):
        return parsed_data
    
    # Only lookup if it's a UPC/EAN barcode
    if barcode_data.get("type") not in ["EAN13", "UPCA", "EAN8", "UPCE"]:
        return parsed_data
    
    # Perform barcode lookup
    product_info = lookup_barcode_product(
        barcode_data.get("data"),
        barcode_data.get("type")
    )
    
    if not product_info:
        return parsed_data
    
    # Merge data (only fill in missing fields)
    if not parsed_data.get("brand") and product_info.get("brand"):
        parsed_data["brand"] = product_info["brand"]
    
    if not parsed_data.get("material") and product_info.get("material"):
        parsed_data["material"] = product_info["material"]
    
    if not parsed_data.get("weight_g") and product_info.get("weight_g"):
        parsed_data["weight_g"] = product_info["weight_g"]
    
    if not parsed_data.get("diameter") and product_info.get("diameter"):
        parsed_data["diameter"] = product_info["diameter"]
    
    # Store product title for reference
    if product_info.get("title"):
        parsed_data["product_title"] = product_info["title"]
    
    return parsed_data
