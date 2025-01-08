# my_app/workflows/ingestion_workflow.py
import os
from typing import List
from llama_index.core import (
    StorageContext,
    Document,
    Settings,
)
from llama_index.core.indices import VectorStoreIndex
from llama_index.readers.file import PDFReader
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.vector_stores.types import VectorStore
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models

from pydantic import BaseModel
from fastapi import HTTPException
from ..config import (
    qdrant_client_inst, BASE_DIR, 
    OPENAI_API_KEY, MODEL_NAME, EMBEDDING_MODEL,
    QDRANT_URL, QDRANT_API_KEY
)

def check_environment():
    """Check if all required environment variables are set"""
    missing = []
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not QDRANT_URL:
        missing.append("QDRANT_URL")
    if not QDRANT_API_KEY:
        missing.append("QDRANT_API_KEY")
    
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing required environment variables: {', '.join(missing)}"
        )

def configure_llama_index():
    """Configure LlamaIndex settings"""
    check_environment()
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    Settings.llm = OpenAI(model=MODEL_NAME, api_key=OPENAI_API_KEY, temperature=0)
    Settings.embed_model = OpenAIEmbedding(model=EMBEDDING_MODEL, api_key=OPENAI_API_KEY)

############################
# MODELS
############################
class StartIngestionEvent(BaseModel):
    """
    The workflow will be triggered with a StartIngestionEvent.
    We store metadata like file_path, collection_name, etc.
    """
    file_path: str
    collection_name: str
    curriculum_id: int

class ChunksReadyEvent(BaseModel):
    """
    Emitted after chunking the doc. 
    We'll store the doc chunks in memory or reference them via self.ctx.
    """
    file_path: str
    collection_name: str
    curriculum_id: int
    documents: List[Document]

class StoredEvent(BaseModel):
    """
    Emitted after the chunks are stored in Qdrant.
    """
    curriculum_id: int
    message: str

############################
# THE WORKFLOW
############################
class IngestionWorkflow:
    def __init__(self):
        self.ctx = {}

    async def chunk_doc(self, ev: StartIngestionEvent) -> ChunksReadyEvent:
        """
        Step 1: We'll read the file, chunk it, and store the doc in context.
        (But won't push to Qdrant yet)
        """
        file_path = ev.file_path
        print(f"[Workflow] chunk_doc: reading from {file_path}")

        # Configure reader with chunk size and overlap
        reader = PDFReader()
        documents = reader.load_data(file_path)

        return ChunksReadyEvent(
            file_path=file_path,
            collection_name=ev.collection_name,
            curriculum_id=ev.curriculum_id,
            documents=documents
        )

    async def store_in_vector_db(self, ev: ChunksReadyEvent) -> StoredEvent:
        """
        Step 2: We retrieve the docs from context, build a VectorStoreIndex with Qdrant.
        """
        print(f"[Workflow] store_in_vector_db: storing to collection '{ev.collection_name}'")

        # Load environment variables directly from .env
        from dotenv import dotenv_values
        env_vars = dotenv_values(".env")
        url = env_vars["QDRANT_URL"].rstrip('/')  # Remove any trailing slash
        api_key = env_vars["QDRANT_API_KEY"].strip()  # Remove any whitespace
        print(f"Connecting to Qdrant at: {url}")
        print(f"API Key length: {len(api_key)}")
        print(f"API Key first 10 chars: {api_key[:10]}")
        
        # Try with headers
        client = QdrantClient(
            url=url,
            timeout=10,
            prefer_grpc=False,
            headers={
                "api-key": api_key,
                "Authorization": f"Bearer {api_key}"
            }
        )

        # Verify collection exists
        if not client.collection_exists(ev.collection_name):
            print(f"Creating collection '{ev.collection_name}'")
            client.create_collection(
                collection_name=ev.collection_name,
                vectors_config=models.VectorParams(
                    size=1536,
                    distance=models.Distance.COSINE,
                    on_disk=True
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    memmap_threshold=20000
                ),
                timeout=30
            )

        # Get embeddings for documents
        embed_model = OpenAIEmbedding(model=EMBEDDING_MODEL, api_key=OPENAI_API_KEY)
        
        # Process each document
        for i, doc in enumerate(ev.documents):
            try:
                # Clean and validate document text
                print(f"Getting embedding for document {i+1}")
                text = doc.text.strip()
                if not text:
                    print(f"Skipping empty document {i+1}")
                    continue
                    
                # Ensure text is valid UTF-8
                text = text.encode('utf-8', errors='ignore').decode('utf-8')
                
                # Get embedding
                embedding = embed_model.get_text_embedding(text)
                print(f"Embedding generated successfully, length: {len(embedding)}")
                
                # Convert embedding to numpy array
                import numpy as np
                embedding_array = np.array(embedding, dtype=np.float32)
                
                # Print first few values for debugging
                print(f"First 5 values of embedding: {embedding_array[:5]}")
                print(f"Min value: {embedding_array.min()}, Max value: {embedding_array.max()}")
                
                # Print document info
                print(f"Document text length: {len(doc.text)}")
                print(f"Document text preview: {doc.text[:100]}...")
                
                # Add point to collection with minimal payload
                print(f"Adding point to Qdrant")
                vector_list = embedding_array.tolist()
                print(f"Vector type after tolist: {type(vector_list)}")
                print(f"Vector length after tolist: {len(vector_list)}")
                client.upsert(
                    collection_name=ev.collection_name,
                    points=[
                        models.PointStruct(
                            id=i,
                            vector=embedding_array.tolist(),
                            payload={"text": doc.text[:100]}  # Only use first 100 chars for testing
                        )
                    ]
                )
                print(f"Added document {i+1}/{len(ev.documents)}")
            except Exception as e:
                print(f"Error processing document {i+1}: {str(e)}")
                if hasattr(e, 'response'):
                    print(f"Response content: {e.response.content}")
                raise

        return StoredEvent(
            curriculum_id=ev.curriculum_id,
            message=f"Data stored in Qdrant collection '{ev.collection_name}'"
        )

    async def run(self, ev: StartIngestionEvent) -> str:
        """
        Run the workflow from start to finish
        """
        try:
            configure_llama_index()
            chunks_ready = await self.chunk_doc(ev)
            stored = await self.store_in_vector_db(chunks_ready)
            print("[Workflow] stop_ingestion: ingestion complete.")
            return stored.message
        except HTTPException as e:
            # Re-raise HTTP exceptions
            raise e
        except Exception as e:
            # Convert other exceptions to HTTP exceptions
            raise HTTPException(
                status_code=500,
                detail=f"Ingestion workflow failed: {str(e)}"
            )
