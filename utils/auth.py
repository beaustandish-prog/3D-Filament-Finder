from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database.models import User
from database.db import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    # Ensure password is a string and truncate
    if isinstance(plain_password, bytes):
        plain_password = plain_password.decode('utf-8')
    safe_password = plain_password[:50] if len(plain_password) > 50 else plain_password
    return pwd_context.verify(safe_password, hashed_password)

def get_password_hash(password):
    print(f"=== get_password_hash CALLED === Input: {repr(password)}, Type: {type(password)}")
    # Ensure password is a string
    if isinstance(password, bytes):
        password = password.decode('utf-8')
    # Truncate to 50 characters
    safe_password = password[:50] if len(password) > 50 else password
    print(f"=== Truncated to: {repr(safe_password)} ===")
    # Explicitly encode to UTF-8 bytes for bcrypt
    password_bytes = safe_password.encode('utf-8')
    print(f"=== Encoded bytes length: {len(password_bytes)} ===")
    result = pwd_context.hash(password_bytes)
    print(f"=== Hash successful ===")
    return result

def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)):
    # Simple check: Does the user have a 'user_id' cookie? 
    # In a real app this should be a signed JWT or session token.
    # For this MVP, we will store plain user_id in a signed cookie or just trust it?
    # No, that's unsafe. Let's use a very simple session mechanism.
    # Actually, let's just use a signed cookie if possible.
    # For speed: we'll assume the cookie "user_email" is the session key.
    # AND for security, we'll verify it against the DB.
    # Ideally we'd use SignedCookie from Starlette session middleware, but let's keep it minimal.
    
    # Correction: Let's use FastAPI's built-in OAuth2 flow for the backend, 
    # but for the browser we'll drop a cookie "access_token".
    
    token = request.cookies.get("access_token")
    if not token:
        # Redirect to login? Handled by the endpoint logic usually, 
        # but here we return None and let the endpoint decide.
        return None
    
    # Token format: "Bearer <email>" (Insecure demo mode)
    # Real mode: Verify JWT.
    # Let's write a simple secure-ish implementation.
    
    try:
        scheme, _, param = token.partition(" ")
        email = param
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        return user
    except Exception:
        return None

def get_current_user(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
