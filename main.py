from fastapi import FastAPI, Depends, HTTPException, status, Form, Response, Request, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import os
import shutil
import uuid
import io
import base64

from database import models
from database.db import engine, get_db
from database.models import Inventory, User, SpoolHistory
from utils.auth import get_current_user, get_password_hash, verify_password, get_current_user_from_cookie
from datetime import datetime

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Filament Finder")


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Auth Endpoints ---

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/register")
def register(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    print(f"REGISTER ATTEMPT: {username}")
    db_user = db.query(User).filter(User.email == username).first()
    if db_user:
        print("REGISTER FAIL: Email already exists")
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(password)
    new_user = User(email=username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    print("REGISTER SUCCESS")
    return {"message": "User created successfully"}

@app.post("/token")
def login(response: Response, username: str = Form(...), password: str = Form(...), remember_me: bool = Form(False), db: Session = Depends(get_db)):
    print(f"LOGIN ATTEMPT: {username} | remember_me={remember_me}")
    user = db.query(User).filter(User.email == username).first()
    if not user:
        print("LOGIN FAIL: User not found")
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    if not verify_password(password, user.hashed_password):
        print("LOGIN FAIL: Password mismatch")
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    print("LOGIN SUCCESS")
    
    # Set simple cookie
    token_value = f"Bearer {user.email}"
    
    # 30 days if remember me is checked, else session only
    max_age = 60 * 60 * 24 * 30 if remember_me else None
    
    response.set_cookie(key="access_token", value=token_value, httponly=True, max_age=max_age)
    return {"message": "Logged in"}

@app.get("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return RedirectResponse(url="/login")


@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login")

    # Get Inventory (Filtered by User)
    inventory = db.query(Inventory).filter(Inventory.user_id == user.id).all()
    
    # Get Filter Options
    brands = sorted(list(set([i.brand for i in inventory if i.brand])))
    materials = sorted(list(set([i.material for i in inventory if i.material])))
    colors = sorted(list(set([i.color_name for i in inventory if i.color_name])))
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "inventory": inventory, 
        "brands": brands,
        "materials": materials,
        "colors": colors,
        "user_email": user.email
    })

@app.get("/add", response_class=HTMLResponse)
def add_spool_page(request: Request, db: Session = Depends(get_db)):
    if not get_current_user_from_cookie(request, db):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("add_spool.html", {"request": request})

@app.post("/api/inventory")
def create_item(
    brand: str = "", material: str = "PLA", color_name: str = "", color_hex: str = "#000000", 
    weight_initial_g: int = 1000, weight_remaining_g: int = 1000, 
    temp_nozzle: str = "", diameter: float = 1.75, 
    location: str = "", image_path: str = "", quantity: int = 1,
    filament_code: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    item = Inventory(
        brand=brand, material=material, color_name=color_name, 
        color_hex=color_hex, weight_initial_g=weight_initial_g,
        weight_remaining_g=weight_remaining_g, temp_nozzle=temp_nozzle,
        diameter=diameter, location=location, image_path=image_path,
        quantity=quantity, filament_code=filament_code,
        user_id=user.id # Assign Owner
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@app.delete("/api/inventory/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Ensure user owns item
    item = db.query(Inventory).filter(Inventory.id == item_id, Inventory.user_id == user.id).first()
    if not item:
        return JSONResponse(status_code=404, content={"message": "Item not found or access denied"})
    
    db.delete(item)
    db.commit()
    return {"message": "Item deleted"}

@app.delete("/api/inventory")
def delete_all_inventory(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Delete ONLY user's items
    db.query(Inventory).filter(Inventory.user_id == user.id).delete()
    db.commit()
    return {"message": "All inventory cleared"}

@app.post("/api/inventory/combine")
def combine_spools(
    request: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Combine multiple spools into one.
    - Keeps the first spool as the primary
    - Adds quantities from other spools
    - Deletes the other spools
    """
    spool_ids = request.get("spool_ids", [])
    
    if len(spool_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 spools to combine")
    
    # Get all spools (verify ownership)
    spools = db.query(Inventory).filter(
        Inventory.id.in_(spool_ids),
        Inventory.user_id == user.id
    ).all()
    
    if len(spools) != len(spool_ids):
        raise HTTPException(status_code=404, detail="Some spools not found")
    
    # Use first spool as primary
    primary_spool = spools[0]
    
    # Combine quantities
    total_quantity = sum(s.quantity for s in spools)
    primary_spool.quantity = total_quantity
    
    # Merge data (fill in missing fields from other spools)
    for spool in spools[1:]:
        if not primary_spool.brand and spool.brand:
            primary_spool.brand = spool.brand
        if not primary_spool.material and spool.material:
            primary_spool.material = spool.material
        if not primary_spool.color_name and spool.color_name:
            primary_spool.color_name = spool.color_name
        if not primary_spool.color_hex and spool.color_hex:
            primary_spool.color_hex = spool.color_hex
        if not primary_spool.temp_nozzle and spool.temp_nozzle:
            primary_spool.temp_nozzle = spool.temp_nozzle
        if not primary_spool.location and spool.location:
            primary_spool.location = spool.location
        if not primary_spool.filament_code and spool.filament_code:
            primary_spool.filament_code = spool.filament_code
        # Keep the image from the first spool with an image
        if not primary_spool.image_path and spool.image_path:
            primary_spool.image_path = spool.image_path
    
    # Delete other spools
    for spool in spools[1:]:
        db.delete(spool)
    
    db.commit()
    
    return {
        "message": f"Combined {len(spools)} spools",
        "primary_spool_id": primary_spool.id,
        "total_quantity": total_quantity
    }

@app.post("/api/inventory/{item_id}/consume")
def consume_spool(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Mark a spool as consumed:
    - If quantity > 1: Decrease quantity by 1
    - If quantity == 1: Move to history and delete from inventory
    """
    item = db.query(Inventory).filter(Inventory.id == item_id, Inventory.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Create history record
    history_entry = SpoolHistory(
        user_id=user.id,
        brand=item.brand,
        material=item.material,
        color_name=item.color_name,
        color_hex=item.color_hex,
        weight_initial_g=item.weight_initial_g,
        diameter=item.diameter,
        temp_nozzle=item.temp_nozzle,
        location=item.location,
        filament_code=item.filament_code,
        image_path=item.image_path,
        date_added=item.date_added,
        date_consumed=datetime.utcnow()
    )
    db.add(history_entry)
    
    # Update or delete inventory
    low_stock_warning = False
    remaining_quantity = 0
    
    if item.quantity > 1:
        item.quantity -= 1
        remaining_quantity = item.quantity
        if item.quantity == 1:
            low_stock_warning = True
    else:
        db.delete(item)
    
    db.commit()
    
    return {
        "message": "Spool consumed",
        "low_stock_warning": low_stock_warning,
        "remaining_quantity": remaining_quantity
    }

@app.get("/history", response_class=HTMLResponse)
def view_history(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login")
    
    """Display spool usage history"""
    history = db.query(SpoolHistory).filter(SpoolHistory.user_id == user.id).order_by(SpoolHistory.date_consumed.desc()).all()
    
    # Calculate statistics
    total_consumed = len(history)
    materials_used = {}
    for entry in history:
        mat = entry.material or "Unknown"
        materials_used[mat] = materials_used.get(mat, 0) + 1
    
    return templates.TemplateResponse("history.html", {
        "request": request,
        "history": history,
        "total_consumed": total_consumed,
        "materials_used": materials_used,
        "user_email": user.email
    })

@app.get("/scan", response_class=HTMLResponse)
def scan_page(request: Request, db: Session = Depends(get_db)):
    if not get_current_user_from_cookie(request, db):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("scan.html", {"request": request})

@app.post("/api/scan")
async def process_scan(image: UploadFile = File(...)):
    # Save image temporarily
    file_id = str(uuid.uuid4())
    file_location = f"static/scan_{file_id}.jpg"
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(image.file, file_object)
    
    # Process Image
    from utils.ocr import preprocess_image, extract_text, extract_barcode, parse_filament_data
    from utils.lookup import lookup_filament_code

    processed_img = preprocess_image(file_location)
    
    if processed_img:
        # 1. Try Barcode/QR Code
        barcode_data = extract_barcode(processed_img)
        print(f"DEBUG: Barcode detection result: {barcode_data}")
        
        # 2. Extract Text
        raw_text = extract_text(processed_img)
        print(f"DEBUG: OCR text length: {len(raw_text) if raw_text else 0}")
        
        # 3. Parse Data
        parsed_data = parse_filament_data(raw_text, barcode_data)
        print(f"DEBUG: Parsed data keys: {list(parsed_data.keys())}")
        print(f"DEBUG: Brand={parsed_data.get('brand')}, Material={parsed_data.get('material')}, Barcode={parsed_data.get('barcode')}")
        
        # 3.5. Barcode Product Lookup (if barcode detected)
        if barcode_data:
            from utils.barcode_lookup import enhance_with_barcode_data
            parsed_data = enhance_with_barcode_data(parsed_data, barcode_data)
            print(f"Barcode detected: {barcode_data.get('type')} - {barcode_data.get('data')}")
        
        # 4. Web Lookup Fallback
        # Trigger if we have a Code AND we are missing ANY key field (Brand, Material, or Color)
        # (Previously only checked Brand/Material)
        if parsed_data.get('filament_code') and (
            not parsed_data.get('brand') or 
            not parsed_data.get('material') or 
            not parsed_data.get('color_name')
        ):
            print(f"--- WEB LOOKUP START: {parsed_data['filament_code']} ---")
            web_data = lookup_filament_code(parsed_data['filament_code'])
            print(f"Web Lookup Result: {web_data}")
            
            # Merge Web Data
            for k, v in web_data.items():
                if not parsed_data.get(k) and v:
                    parsed_data[k] = v
                    print(f"Updated {k} from web: {v}")
        
        return {
            "status": "success",
            "file_path": file_location,
            "ocr_data": parsed_data,
            "debug_text": raw_text
        }
    else:
        return {
            "status": "error",
            "message": "Failed to process image"
        }

if __name__ == "__main__":
    # Get local IP for convenience
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"
    
    print(f"\nExample Network URL: https://{local_ip}:8000\n")

    # Check for SSL certs
    if os.path.exists("key.pem") and os.path.exists("cert.pem"):
        uvicorn.run(app, host="0.0.0.0", port=8000, ssl_keyfile="key.pem", ssl_certfile="cert.pem")
    else:
        print("Warning: SSL certificates not found. Running in HTTP mode (Camera access may be blocked on mobile).")
        uvicorn.run(app, host="0.0.0.0", port=8000)
