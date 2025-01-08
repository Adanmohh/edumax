# my_app/workflows/ingestion_workflow.py
import os
import sys
import numpy as np
from datetime import datetime
from typing import List
from llama_index.core import (
    StorageContext,
    Document,
    Settings,
    VectorStoreIndex,
    ServiceContext
)
from llama_index.core.ingestion import IngestionPipeline, IngestionCache
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.extractors import (
    TitleExtractor,
    KeywordExtractor,
    QuestionsAnsweredExtractor,
    SummaryExtractor
)
from llama_index.core.text_splitter import TokenTextSplitter
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.docling import DoclingReader
from docling import document_converter
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
    # Configure HuggingFace cache and disable symlinks on Windows
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"  # Use HTTPS instead of git
    os.environ["TRANSFORMERS_CACHE"] = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
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

        try:
            # First load the document using LlamaIndex's built-in reader
            print(f"[Workflow] Loading document: {file_path}")
            base_reader = SimpleDirectoryReader(
                input_files=[file_path],
                filename_as_id=True
            )
            raw_docs = base_reader.load_data()
            
            if not raw_docs:
                raise HTTPException(
                    status_code=500,
                    detail="No document content could be extracted from the file"
                )
            
            print(f"[Workflow] Initial load successful, parsing with Docling")
            
            # Skip Docling for now and use raw documents directly
            documents = raw_docs
            
            print(f"[Workflow] Processing {len(documents)} documents")
            
            # Simple node parser for basic text chunking
            node_parser = SimpleNodeParser.from_defaults(
                chunk_size=512,  # Smaller chunks for better processing
                chunk_overlap=50
            )
            
            processed_documents = []
            for i, doc in enumerate(documents):
                if not doc or not isinstance(doc.text, str) or not doc.text.strip():
                    continue
                
                try:
                    # Basic text sanitization
                    text = doc.text.encode('utf-8', errors='replace').decode('utf-8')
                    
                    # Create simple metadata
                    metadata = {
                        "doc_id": i,
                        "filename": os.path.basename(file_path)
                    }
                    
                    # Create document with sanitized text
                    processed_documents.append(
                        Document(
                            text=text,
                            metadata=metadata
                        )
                    )
                except Exception as e:
                    print(f"[Workflow] Error processing document {i}: {str(e)}")
                    continue
            
            if not processed_documents:
                raise HTTPException(
                    status_code=500,
                    detail="No valid content could be extracted from the document"
                )
            
            return ChunksReadyEvent(
                file_path=file_path,
                collection_name=ev.collection_name,
                curriculum_id=ev.curriculum_id,
                documents=processed_documents
            )
            
        except Exception as e:
            print(f"Error processing document: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Document processing failed: {str(e)}"
            )
        

    async def store_in_vector_db(self, ev: ChunksReadyEvent) -> StoredEvent:
        """
        Step 2: Store documents using dual-store pattern (document store + vector store)
        """
        print(f"[Workflow] store_in_vector_db: storing to collection '{ev.collection_name}'")

        try:
            # Initialize vector store
            vector_store = QdrantVectorStore(
                client=qdrant_client_inst,
                collection_name=ev.collection_name,
                prefer_grpc=False,
                timeout=10
            )

            # Initialize document store
            doc_store = SimpleDocumentStore()

            # Configure settings for document processing
            Settings.text_splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=50)
            Settings.node_parser = SimpleNodeParser.from_defaults(
                chunk_size=512,
                chunk_overlap=50
            )

            # Create storage context
            storage_context = StorageContext.from_defaults(
                vector_store=vector_store,
                docstore=doc_store
            )

            # Create index directly with documents
            index = VectorStoreIndex.from_documents(
                documents=ev.documents,
                storage_context=storage_context,
                show_progress=True
            )

            print(f"Debug: Successfully stored {len(ev.documents)} documents with dual storage", file=sys.stderr)
            
            return StoredEvent(
                curriculum_id=ev.curriculum_id,
                message=f"Data stored in Qdrant collection '{ev.collection_name}'"
            )

        except Exception as e:
            print(f"Error storing documents: {str(e)}", file=sys.stderr)
            if hasattr(e, 'response'):
                print(f"Response content: {e.response.content}", file=sys.stderr)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to store documents: {str(e)}"
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
