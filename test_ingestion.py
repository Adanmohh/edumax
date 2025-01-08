import os
import asyncio
from dotenv import load_dotenv
from my_app.workflows.ingestion_workflow import IngestionWorkflow, StartIngestionEvent

# Load environment variables
load_dotenv(override=True)

async def test_ingestion():
    # Initialize workflow
    workflow = IngestionWorkflow()
    
    # Create test event
    event = StartIngestionEvent(
        file_path="my_app/uploaded_files/VOTA - hyvien väestösuhteiden suunnittelutyökalu (1).pdf",
        collection_name="test_collection_2",  # Use the collection we just created
        curriculum_id=1
    )
    
    try:
        # Run workflow
        result = await workflow.run(event)
        print("Ingestion successful!")
        print(result)
    except Exception as e:
        print(f"Error during ingestion: {str(e)}")
        if hasattr(e, 'detail'):
            print(f"Error detail: {e.detail}")

# Run the test
if __name__ == "__main__":
    asyncio.run(test_ingestion())
