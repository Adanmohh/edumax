# my_app/config.py
import os
import sys
import traceback
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from typing import Tuple, List, Optional

# Load environment variables
load_dotenv()

# SQLite DB path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "demo_workflow.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Qdrant settings
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "edublend")

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")

# Validate required environment variables
if not QDRANT_URL:
    raise ValueError("QDRANT_URL environment variable is not set")
if not QDRANT_API_KEY:
    raise ValueError("QDRANT_API_KEY environment variable is not set")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

def validate_qdrant_connection(collection_name: Optional[str] = None) -> Tuple[bool, str, List[str]]:
    """
    Validate Qdrant connection and optionally check a specific collection.
    Returns: (success, message, available_collections)
    """
    try:
        collections = qdrant_client_inst.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if collection_name and collection_name not in collection_names:
            return False, f"Collection '{collection_name}' not found", collection_names
            
        if collection_name:
            info = qdrant_client_inst.get_collection(collection_name)
            if info.points_count == 0:
                return False, f"Collection '{collection_name}' exists but contains no vectors", collection_names
                
        return True, "Connection validated successfully", collection_names
    except Exception as e:
        return False, f"Qdrant validation failed: {str(e)}", []

print(f"Debug: Initializing Qdrant client with URL: {QDRANT_URL}", file=sys.stderr)

# Initialize and validate Qdrant client
try:
    print(f"Debug: Attempting to connect to Qdrant at {QDRANT_URL}", file=sys.stderr)
    
    # Instantiate Qdrant client
    qdrant_client_inst = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=10  # Add timeout for operations
    )
    
    # Test connection and basic operations
    try:
        collections = qdrant_client_inst.get_collections()
        collection_names = [c.name for c in collections.collections]
        print(f"Debug: Successfully connected to Qdrant. Available collections: {collection_names}", file=sys.stderr)
        
        # Test collection info retrieval for each collection
        for name in collection_names:
            try:
                info = qdrant_client_inst.get_collection(name)
                print(f"Debug: Collection '{name}' info - points: {info.points_count}", file=sys.stderr)
            except UnexpectedResponse as ce:
                print(f"Debug: Warning - Could not get info for collection '{name}': {str(ce)}", file=sys.stderr)
        
    except UnexpectedResponse as e:
        print(f"Debug: Failed to list collections: {str(e)}", file=sys.stderr)
        raise RuntimeError(f"Failed to list Qdrant collections: {str(e)}")
        
except Exception as e:
    print(f"Debug: Critical error initializing Qdrant client: {str(e)}", file=sys.stderr)
    print(f"Debug: Error traceback: {traceback.format_exc()}", file=sys.stderr)
    raise RuntimeError(f"Failed to initialize Qdrant client: {str(e)}")
