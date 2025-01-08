# my_app/routes/auth.py
import uuid
from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..schemas import UserCreate
from fastapi.responses import JSONResponse

router = APIRouter()

# Demo-only: store tokens in memory
LOGGED_IN_USERS = {}  # {token: user_id}

@router.get("/test")  # Will be prefixed with /auth by the router
def test_auth():
    """Test endpoint to verify server state"""
    return {
        "status": "ok",
        "active_users": len(LOGGED_IN_USERS),
        "tokens": list(LOGGED_IN_USERS.keys())
    }

@router.post("/register")
def register_user(data: UserCreate, db: Session = Depends(get_db)):
    user = User(
        username=data.username,
        password=data.password,
        role=data.role,
        school_id=data.school_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User registered", "user_id": user.id}

@router.post("/login")
def login(credentials: dict = Body(...), db: Session = Depends(get_db)):
    print("\n=== Login Request ===")
    print("Raw request body:", credentials)
    print("Request type:", type(credentials))
    username = credentials.get("username")
    password = credentials.get("password")
    print(f"Extracted credentials - username: '{username}', password: '{password}'")
    
    # Debug database query
    try:
        print("Querying database for user...")
        user = db.query(User).filter(User.username == username).first()
        if user:
            print(f"Found user: {user.__dict__}")
            if user.password == password:
                print("Password match successful")
            else:
                print(f"Password mismatch. Expected: {user.password}, Got: {password}")
        else:
            print(f"No user found with username: '{username}'")
            print("All users in database:")
            all_users = db.query(User).all()
            for u in all_users:
                print(f"- {u.__dict__}")
    except Exception as e:
        print(f"Database error: {str(e)}")
    
    # Debug database query
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            print(f"Found user in database: id={user.id}, username='{user.username}', password='{user.password}', role='{user.role}'")
            if user.password == password:
                print("Password match successful")
            else:
                print("Password mismatch")
        else:
            print(f"No user found with username: '{username}'")
    except Exception as e:
        print(f"Database error: {str(e)}")
    if not user or user.password != password:
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)

    token = uuid.uuid4().hex
    LOGGED_IN_USERS[token] = user.id
    return {"message": "Logged in", "token": token, "role": user.role, "school_id": user.school_id}

def login_required(token: str, db: Session) -> User:
    print(f"\n=== Auth Check ===")
    print(f"Checking token: {token}")
    print(f"Active sessions: {LOGGED_IN_USERS}")
    
    if token not in LOGGED_IN_USERS:
        print("Token not found in active sessions")
        return None
        
    user_id = LOGGED_IN_USERS[token]
    print(f"Found user_id: {user_id}")
    
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        print(f"Found user: id={user.id}, username='{user.username}', role='{user.role}', school={user.school_id}")
    else:
        print("User not found in database")
    
    return user
