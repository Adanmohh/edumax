import asyncio
from my_app.database import SessionLocal
from my_app.models import Curriculum
from my_app.workflows.ingestion_workflow import IngestionWorkflow, StartIngestionEvent

async def process_existing_curriculum():
    print("Processing existing curriculum...")
    
    # Get curriculum from database
    db = SessionLocal()
    try:
        curriculum = db.query(Curriculum).filter(Curriculum.id == 1).first()
        if not curriculum:
            print("No curriculum found with ID 1")
            return
            
        print(f"Found curriculum: {curriculum.name}")
        print(f"File path: {curriculum.file_path}")
        
        # Create workflow instance
        workflow = IngestionWorkflow()
        
        # Create event
        collection_name = f"school_{curriculum.school_id}_{curriculum.id}"
        event = StartIngestionEvent(
            file_path=curriculum.file_path,
            collection_name=collection_name,
            curriculum_id=curriculum.id
        )
        
        # Run workflow
        print("\nStarting ingestion workflow...")
        result = await workflow.run(event)
        print(f"Workflow result: {result}")
        
        # Update vector_key
        curriculum.vector_key = collection_name
        db.commit()
        print(f"\nUpdated curriculum vector_key to: {collection_name}")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(process_existing_curriculum())
