
# my_app/routes/curriculum.py
import os
import sys
import uuid
import aiofiles
import traceback
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Curriculum
from ..schemas import CurriculumIngest, CurriculumResponse
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
from ..workflows.curriculum_extraction_workflow import CurriculumExtractionWorkflow

router = APIRouter(prefix="/curriculum", tags=["Curriculum"])

# Workflow instances
discussion_workflow = CurriculumDiscussionWorkflow()

# List and Search

@router.get("")
async def list_curricula(
    search: Optional[str] = Query(None),
    school_id: Optional[int] = Query(None),
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    print("Starting list_curricula endpoint", file=sys.stderr)
    """List curricula with optional search and filtering"""
    print(f"Debug: Received request - search: {search}, school_id: {school_id}, token: {token}")
    
    try:
        print(f"Debug: About to check login with token: {token}")
        user = login_required(token, db)
        print(f"Debug: Login check result: {user}")
        if not user:
            print("Debug: Authentication failed - user not found or invalid token")
            return JSONResponse({"error": "Not logged in"}, status_code=401)

        print(f"Debug: Authenticated user - ID: {user.id}, Role: {user.role}, School: {user.school_id}")
    except Exception as e:
        print(f"Debug: Authentication error - {str(e)}")
        traceback_str = traceback.format_exc()
        print(f"Debug: Auth error traceback: {traceback_str}")
        return JSONResponse(
            content={
                "error": f"Authentication error: {str(e)}",
                "traceback": traceback_str,
                "type": str(type(e))
            },
            status_code=500
        )

    # Build query
    query = db.query(Curriculum)

    # Apply filters
    if user.role != "superadmin":
        query = query.filter(Curriculum.school_id == user.school_id)
    elif school_id:
        query = query.filter(Curriculum.school_id == school_id)
        
    if search:
        query = query.filter(Curriculum.name.ilike(f"%{search}%"))

    # Execute query using SQLAlchemy ORM
    print("Debug: Executing query", file=sys.stderr)
    try:
        curricula = query.all()
        print(f"Debug: Found {len(curricula)} curricula", file=sys.stderr)
        
        # Convert to response format
        # Initialize curriculum discussion workflow for context extraction
        discussion_workflow = CurriculumDiscussionWorkflow()
        
        curricula_list = []
        for c in curricula:
            print(f"Debug: Processing curriculum {c.id}", file=sys.stderr)
            try:
                # Base curriculum info
                curriculum_dict = {
                    "id": c.id,
                    "name": c.name,
                    "school_id": c.school_id,
                    "file_path": c.file_path,
                    "vector_key": c.vector_key or "",
                    "created_at": c.created_at.isoformat() if c.created_at else datetime.utcnow().isoformat(),
                    "has_embeddings": bool(c.vector_key)
                }
                
                # If curriculum has embeddings, extract additional context
                if c.vector_key:
                    try:
                        # Extract context using the curriculum extraction workflow
                        extraction_workflow = CurriculumExtractionWorkflow()
                        context = await extraction_workflow.extract_comprehensive_context(
                            collection_name=c.vector_key,
                            context_type='course'
                        )
                        
                        # Add extracted context to curriculum dict
                        curriculum_dict.update({
                            "description": context.relevant_content,
                            "learning_objectives": context.learning_objectives,
                            "key_concepts": context.key_concepts,
                            "themes": context.themes,
                            "teaching_approach": context.teaching_approach
                        })
                    except Exception as e:
                        print(f"Debug: Error extracting context for curriculum {c.id}: {str(e)}", file=sys.stderr)
                        # Continue with basic info if context extraction fails
                        pass
                
                print(f"Debug: Processed curriculum: {curriculum_dict}", file=sys.stderr)
                curricula_list.append(curriculum_dict)
            except Exception as e:
                print(f"Debug: Error processing curriculum {c.id}: {str(e)}", file=sys.stderr)
                print(f"Debug: Processing error traceback: {traceback.format_exc()}", file=sys.stderr)
                continue
        
        response_data = {"curricula": curricula_list}
        print(f"Debug: Final response: {response_data}", file=sys.stderr)
        return JSONResponse(content=response_data)
    except Exception as e:
        print(f"Debug: Error executing query: {str(e)}", file=sys.stderr)
        print(f"Debug: Query error traceback: {traceback.format_exc()}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")

@router.get("/{curriculum_id}")
async def get_curriculum(
    curriculum_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get curriculum details"""
    user = login_required(token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    cur = db.query(Curriculum).filter(Curriculum.id == curriculum_id).first()
    if not cur:
        return JSONResponse({"error": "Curriculum not found"}, status_code=404)
    
    if user.role != "superadmin" and user.school_id != cur.school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    
    return CurriculumResponse(
        id=cur.id,
        name=cur.name,
        school_id=cur.school_id,
        file_path=cur.file_path,
        vector_key=cur.vector_key,
        created_at=cur.created_at or datetime.utcnow(),
        has_embeddings=bool(cur.vector_key)
    )

# File Operations
@router.post("/upload")
async def upload_curriculum(
    file: UploadFile = File(...),
    name: str = Body(...),
    school_id: int = Body(...),
    token: str = Body(...),
    db: Session = Depends(get_db)
):
    user = login_required(token, db)
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
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """Delete a curriculum"""
    user = login_required(token, db)
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
    user = login_required(data.token, db)
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
    token: str = Body(...),
    db: Session = Depends(get_db)
):
    """Start or continue a discussion about a curriculum"""
    user = login_required(token, db)
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
