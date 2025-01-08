import os
import asyncio
import nest_asyncio
from dotenv import load_dotenv

# Allow nested async operations
nest_asyncio.apply()
from my_app.workflows.ingestion_workflow import IngestionWorkflow, StartIngestionEvent
from my_app.workflows.curriculum_extraction_workflow import CurriculumExtractionWorkflow
from my_app.config import qdrant_client_inst

# Load environment variables
load_dotenv(override=True)

async def verify_storage(collection_name: str) -> bool:
    """Verify both vector store and document store are populated"""
    try:
        # Initialize extraction workflow to test retrieval
        extraction = CurriculumExtractionWorkflow()
        
        # Load index (this will fail if either store is not properly populated)
        extraction.load_index(collection_name)
        
        # Verify vector store
        collection_info = qdrant_client_inst.get_collection(collection_name)
        vectors_count = collection_info.points_count
        print(f"Vector store check - Points in collection: {vectors_count}")
        if vectors_count == 0:
            print("Error: No vectors found in collection")
            return False
            
        # Configure settings and imports
        from llama_index.core import Settings
        from llama_index.llms.openai import OpenAI
        from llama_index.core.retrievers import VectorIndexRetriever
        from llama_index.core.query_engine import RetrieverQueryEngine
        
        Settings.llm = OpenAI(model="gpt-3.5-turbo", temperature=0)
        
        # Create retriever
        retriever = VectorIndexRetriever(
            index=extraction.index,
            similarity_top_k=2
        )
        
        # Create query engine
        query_engine = RetrieverQueryEngine.from_args(
            retriever=retriever,
            response_mode="compact"
        )
        
        # Test retrieval synchronously
        response = query_engine.query("Summarize the content")
        if not response:
            print("Error: Could not retrieve documents")
            return False
            
        print("Storage verification successful!")
        return True
        
    except Exception as e:
        print(f"Storage verification failed: {str(e)}")
        return False

async def test_ingestion():
    """Test ingestion with storage verification"""
    # Initialize workflow
    workflow = IngestionWorkflow()
    
    # Files to process
    files = [
        {
            "path": "my_app/uploaded_files/VOTA - hyvien väestösuhteiden suunnittelutyökalu (1).pdf",
            "collection": "vota_collection",
            "id": 2
        }
    ]
    
    for file_info in files:
        print(f"\nProcessing {file_info['path']}...")
        event = StartIngestionEvent(
            file_path=file_info['path'],
            collection_name=file_info['collection'],
            curriculum_id=file_info['id']
        )
        
        try:
            # Run ingestion
            result = await workflow.run(event)
            print(f"Ingestion completed for {file_info['path']}!")
            print(result)
            
            # Verify storage
            print("\nVerifying storage...")
            storage_ok = await verify_storage(file_info['collection'])
            if not storage_ok:
                raise Exception("Storage verification failed")
            
            print("\nIngestion and verification successful!")
            
        except Exception as e:
            print(f"Error processing {file_info['path']}: {str(e)}")
            if hasattr(e, 'detail'):
                print(f"Error detail: {e.detail}")

# Run the test
if __name__ == "__main__":
    asyncio.run(test_ingestion())
