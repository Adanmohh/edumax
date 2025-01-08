
# my_app/routes/curriculum.py
import os
import aiofiles
import uuid
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import Curriculum
from ..schemas import CurriculumIngest
from .auth import login_required
from ..config import BASE_DIR
from ..workflows.ingestion_workflow import (
    IngestionWorkflow, StartIngestionEvent
)
from ..workflows.curriculum_discussion_workflow import (
    CurriculumDiscussionWorkflow,
    DiscussionQuery,
    DiscussionResponse
)

router = APIRouter(prefix="/curriculum", tags=["curriculum"])

# Workflow instances
discussion_workflow = CurriculumDiscussionWorkflow()

# List and Search
@router.get("")
async def list_curricula(
    search: Optional[str] = Query(None),
    school_id: Optional[int] = Query(None),
    session_token: str = Query(...),
    db: Session = Depends(get_db)
):
    """List curricula with optional search and filtering"""
    print(f"Debug: Received request - search: {search}, school_id: {school_id}, token: {session_token}")
    
    user = login_required(session_token, db)
    if not user:
        print("Debug: Authentication failed - user not found or invalid token")
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    print(f"Debug: Authenticated user - ID: {user.id}, Role: {user.role}, School: {user.school_id}")

    # Build query
    query = db.query(Curriculum)
    
    # Apply school filter based on user role
    if user.role != "superadmin":
        query = query.filter(Curriculum.school_id == user.school_id)
        print(f"Debug: Filtering by user's school_id: {user.school_id}")
    elif school_id:
        query = query.filter(Curriculum.school_id == school_id)
        print(f"Debug: Filtering by provided school_id: {school_id}")
    
    # Apply search if provided
    if search:
        query = query.filter(Curriculum.name.ilike(f"%{search}%"))
        print(f"Debug: Applying search filter: {search}")
    
    curricula = query.all()
    print(f"Debug: Found {len(curricula)} curriculum items")
    
    result = {
        "curricula": [
            {
                "id": c.id,
                "name": c.name,
                "school_id": c.school_id,
                "file_path": c.file_path,
                "vector_key": c.vector_key,
                "has_embeddings": bool(c.vector_key),
                "created_at": c.created_at
            } for c in curricula
        ]
    }
    print(f"Debug: Returning response: {result}")
    return result

@router.get("/{curriculum_id}")
async def get_curriculum(
    curriculum_id: int,
    session_token: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get curriculum details"""
    user = login_required(session_token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    cur = db.query(Curriculum).filter(Curriculum.id == curriculum_id).first()
    if not cur:
        return JSONResponse({"error": "Curriculum not found"}, status_code=404)
    
    if user.role != "superadmin" and user.school_id != cur.school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    
    return {
        "id": cur.id,
        "name": cur.name,
        "school_id": cur.school_id,
        "has_embeddings": bool(cur.vector_key),
        "created_at": cur.created_at
    }

# File Operations
@router.post("/upload")
async def upload_curriculum(
    file: UploadFile = File(...),
    name: str = Body(...),
    school_id: int = Body(...),
    session_token: str = Body(...),
    db: Session = Depends(get_db)
):
    user = login_required(session_token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)
    if user.role != "superadmin" and user.school_id != school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    # 1) Save file to disk
    save_dir = os.path.join(BASE_DIR, "uploaded_files")
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, file.filename)

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # 2) Create a Curriculum row (no embeddings yet!)
    curriculum = Curriculum(
        name=name,
        file_path=file_path,
        vector_key="",  # We'll set this after the workflow runs
        school_id=school_id
    )
    db.add(curriculum)
    db.commit()
    db.refresh(curriculum)

    return {
        "message": "Curriculum file saved, no embeddings yet.",
        "curriculum_id": curriculum.id,
        "file_path": file_path
    }


@router.delete("/{curriculum_id}")
async def delete_curriculum(
    curriculum_id: int,
    session_token: str = Query(...),
    db: Session = Depends(get_db)
):
    """Delete a curriculum"""
    user = login_required(session_token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    cur = db.query(Curriculum).filter(Curriculum.id == curriculum_id).first()
    if not cur:
        return JSONResponse({"error": "Curriculum not found"}, status_code=404)
    
    if user.role != "superadmin" and user.school_id != cur.school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    
    # Delete file if exists
    if os.path.exists(cur.file_path):
        os.remove(cur.file_path)
    
    # Delete from database
    db.delete(cur)
    db.commit()
    
    return {"message": "Curriculum deleted successfully"}

# Ingestion Workflow
@router.post("/ingest")
async def start_ingestion_workflow(
    data: CurriculumIngest,
    db: Session = Depends(get_db),
):
    """
    Trigger the workflow to chunk + store doc in Qdrant.
    """
    user = login_required(data.session_token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    # Retrieve the curriculum record
    cur = db.query(Curriculum).filter(Curriculum.id == data.curriculum_id).first()
    if not cur:
        return JSONResponse({"error": "Curriculum not found"}, status_code=404)

    if user.role != "superadmin" and user.school_id != cur.school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    # We'll store collection_name in the vector_key once done
    if not os.path.exists(cur.file_path):
        return JSONResponse({"error": "File does not exist on disk"}, status_code=400)

    # 1) Create the workflow instance and start event
    workflow = IngestionWorkflow()
    event = StartIngestionEvent(
        file_path=cur.file_path,
        collection_name=data.collection_name,
        curriculum_id=cur.id
    )

    # 2) Start the workflow
    wfid = str(uuid.uuid4())
    try:
        # Check if file is PDF
        if not cur.file_path.lower().endswith('.pdf'):
            return JSONResponse(
                {"error": "Only PDF files are supported at this time"},
                status_code=400
            )

        # Check if file exists and is readable
        if not os.path.exists(cur.file_path) or not os.access(cur.file_path, os.R_OK):
            return JSONResponse(
                {"error": "File not found or not readable"},
                status_code=400
            )

        # Run workflow
        result = await workflow.run(event)
        
        # Update curriculum with vector key
        cur.vector_key = data.collection_name
        db.commit()
        
        return {
            "workflow_id": wfid,
            "status": "completed",
            "result": result
        }
    except HTTPException as e:
        # Pass through HTTP exceptions with their status codes
        return JSONResponse(
            {"error": str(e.detail)},
            status_code=e.status_code
        )
    except Exception as e:
        # Log the full error for debugging
        print(f"Workflow error: {str(e)}")
        return JSONResponse(
            {"error": "Failed to process curriculum. Please check if all required environment variables are set (OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY)."},
            status_code=500
        )

# Discussion Endpoints
@router.post("/discuss")
async def discuss_curriculum(
    curriculum_id: int = Query(...),
    query: str = Body(...),
    chat_history: List[dict] = Body(default=[]),
    session_token: str = Body(...),
    db: Session = Depends(get_db)
):
    """Start or continue a discussion about a curriculum"""
    user = login_required(session_token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    # Get curriculum
    cur = db.query(Curriculum).filter(Curriculum.id == curriculum_id).first()
    if not cur:
        return JSONResponse({"error": "Curriculum not found"}, status_code=404)
    
    if user.role != "superadmin" and user.school_id != cur.school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    
    if not cur.vector_key:
        return JSONResponse(
            {"error": "Curriculum has not been processed for discussion yet"},
            status_code=400
        )
    
    # Process query through RAG
    discussion_query = DiscussionQuery(
        collection_name=cur.vector_key,
        query=query,
        chat_history=chat_history
    )
    
    try:
        response = await discussion_workflow.get_response(discussion_query)
        return response
    except HTTPException as e:
        return JSONResponse({"error": str(e.detail)}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to process discussion: {str(e)}"},
            status_code=500
        )
