# my_app/routes/schools.py
from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import School, User
from ..schemas import SchoolCreate
from .auth import login_required

router = APIRouter()

@router.post("/schools")
def create_school(
    data: SchoolCreate,
    db: Session = Depends(get_db)
):
    user = login_required(data.session_token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    if user.role != "superadmin":
        return JSONResponse({"error": "Only superadmin can create schools"}, status_code=403)

    school = School(name=data.name)
    db.add(school)
    db.commit()
    db.refresh(school)
    return {"message": "School created", "school_id": school.id}

@router.get("/schools")
def list_schools(
    session_token: str = None,
    db: Session = Depends(get_db)
):
    if not session_token:
        return JSONResponse({"error": "Session token required"}, status_code=400)
    user = login_required(session_token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    if user.role == "superadmin":
        # Superadmin can see all schools
        schools = db.query(School).all()
    else:
        # Regular users can only see their assigned school
        if not user.school_id:
            return []
        schools = db.query(School).filter(School.id == user.school_id).all()

    return [{"id": s.id, "name": s.name} for s in schools]
