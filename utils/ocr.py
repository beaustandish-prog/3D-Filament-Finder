from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import re
import os
from pyzbar.pyzbar import decode

# Set Tesseract Path for Windows
# Common default location
tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

def preprocess_image(image_path):
    """
    Convert to grayscale and threshold to improve OCR accuracy.
    """
    try:
        img = Image.open(image_path)
        return img
    except Exception as e:
        print(f"Error processing image: {e}")
        return None

def extract_text(image):
    """
    Run Tesseract OCR on the processed image.
    Try multiple preprocessing variations to get the best result.
    """
    
    # Check if Tesseract is in PATH
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        return "ERROR: Tesseract OCR is not installed or not in PATH. Please install it from https://github.com/UB-Mannheim/tesseract/wiki"

    text_results = []
    
    try:
        # Method 1: Original (Grayscale)
        gray = image.convert("L")
        text_results.append(pytesseract.image_to_string(gray))
        
        # Method 2: High Contrast Thresholding
        enhancer = ImageEnhance.Contrast(gray)
        contrast = enhancer.enhance(2)
        thresh = contrast.point(lambda p: 255 if p > 128 else 0)
        text_results.append(pytesseract.image_to_string(thresh))
        
        # Method 3: Resize (Upscale 2x for small text)
        large = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
        text_results.append(pytesseract.image_to_string(large))

        # Combine all unique text found
        full_text = "\n".join(text_results)
        
        if not full_text.strip():
            return "No text detected. Try better lighting or get closer."
            
        return full_text
        
    except Exception as e:
        return f"OCR Error: {str(e)}"

def extract_barcode(image):
    """
    Try to decode barcode/QR code from the image.
    Returns dict with barcode data if found, None otherwise.
    """
    try:
        decoded_objects = decode(image)
        if decoded_objects:
            barcode_obj = decoded_objects[0]
            barcode_data = barcode_obj.data.decode("utf-8")
            barcode_type = barcode_obj.type
            
            return {
                "data": barcode_data,
                "type": barcode_type,  # e.g., 'EAN13', 'UPCA', 'CODE128', 'QRCODE'
                "raw": barcode_data
            }
    except Exception as e:
        print(f"Barcode Error: {e}")
    return None

def parse_filament_data(text, barcode_data=None):
    """
    Extract brand, material, weight, etc. using Regex.
    Check for 'Filament Code' or SKU.
    barcode_data: dict with 'data', 'type', 'raw' keys if barcode was found
    """
    data = {
        "brand": None,
        "material": None,
        "weight_g": None,
        "diameter": 1.75,
        "temp_nozzle": None,
        "color_name": None, 
        "filament_code": None,
        "raw_text": text,
        "barcode": None,
        "barcode_type": None
    }
    
    # 0. Barcode Data Override
    if barcode_data:
        data["barcode"] = barcode_data.get("data")
        data["barcode_type"] = barcode_data.get("type")
        
        # If it's a UPC/EAN barcode, store it as the filament code for lookup
        if barcode_data.get("type") in ["EAN13", "UPCA", "EAN8", "UPCE"]:
            data["filament_code"] = barcode_data.get("data")
        
        # If QR code contains Bambu Lab data
        if barcode_data.get("type") == "QRCODE" and "bambulab" in barcode_data.get("data", "").lower():
            data["brand"] = "Bambu Lab"
            
    # 1. Filament Code / SKU
    # Regex: Look for "Code", "SKU", "Ref" followed by a code.
    # We use a broad pattern: Keywords -> optional separator -> CODE
    # The code usually is 4-15 chars, alphanumeric.
    # We explicitly ignore "Printing" or "Temp" which might be near numbers.
    
    # Try specific "Filament Code" pattern first (handles the Bambu label)
    # The label has "Filament Code ... 13612". The dots/spaces might be messy.
    fc_match = re.search(r"Filament\s*Code.*?(\d{5})", text, re.IGNORECASE | re.DOTALL)
    if fc_match:
        data["filament_code"] = fc_match.group(1)
    else:
        # Fallback to generic SKU/Ref
        code_match = re.search(r"(?:SKU|Ref|P/N)[\s.:)]+([A-Z0-9-]{4,15})", text, re.IGNORECASE)
        if code_match:
            data["filament_code"] = code_match.group(1)
            
    # 2. Brand
    brands = ["Bambu", "Overture", "eSun", "Sunlu", "Polymaker", "Hatchbox", "Prusament", "Creality", "Eryone", "Amolen", "Inland"]
    for brand in brands:
        if re.search(rf"\b{brand}\b", text, re.IGNORECASE):
            data["brand"] = brand
            break
            
    # 3. Material
    material_match = re.search(r"\b(PLA(?:\+| plus)?|PETG|ABS(?:-GF)?|TPU|ASA|Nylon|PC|PVA|CF)\b", text, re.IGNORECASE)
    if material_match:
        data["material"] = material_match.group(0).upper()
        # Check for sub-types like "Basic", "Matte", "Translucent"
        subtype_match = re.search(r"(Basic|Matte|Silk|Translucent|Galaxy|Sparkle|Wood|Carbon Fiber)", text, re.IGNORECASE)
        if subtype_match:
             data["material"] = f"{data['material']} {subtype_match.group(1)}"
        
    # 4. Weight
    weight_match = re.search(r"(\d{1,4})\s?(g|kg)", text, re.IGNORECASE)
    if weight_match:
        val = int(weight_match.group(1))
        unit = weight_match.group(2).lower()
        if unit == 'kg' or (unit == 'g' and val < 10): 
             val *= 1000
        data["weight_g"] = val
    
    # 5. Temperature
    temp_match = re.search(r"(\d{2,3})\s?-\s?(\d{2,3})\s?°?C", text)
    if temp_match:
        data["temp_nozzle"] = f"{temp_match.group(1)}-{temp_match.group(2)}"
        
    # 6. Diameter
    dia_match = re.search(r"(1\.75|2\.85|3\.00)\s?mm", text)
    if dia_match:
        data["diameter"] = float(dia_match.group(1))

    # 7. Color Logic
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

    return data
