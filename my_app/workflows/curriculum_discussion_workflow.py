import os
from typing import List
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    Settings,
    Response
)
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from pydantic import BaseModel
from fastapi import HTTPException

from ..config import (
    qdrant_client_inst,
    OPENAI_API_KEY, MODEL_NAME, EMBEDDING_MODEL,
    QDRANT_URL, QDRANT_API_KEY
)

class DiscussionQuery(BaseModel):
    """Input for curriculum discussion"""
    collection_name: str
    query: str
    chat_history: List[dict] = []  # List of {"role": "user/assistant", "content": "msg"}

class DiscussionResponse(BaseModel):
    """Response from curriculum discussion"""
    answer: str
    sources: List[str]

class CurriculumDiscussionWorkflow:
    def __init__(self):
        """Initialize the discussion workflow with LlamaIndex settings"""
        if not all([OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY]):
            raise HTTPException(
                status_code=500,
                detail="Missing required environment variables"
            )
        
        # Configure LlamaIndex
        Settings.llm = OpenAI(model=MODEL_NAME, api_key=OPENAI_API_KEY)
        Settings.embed_model = OpenAIEmbedding(model=EMBEDDING_MODEL, api_key=OPENAI_API_KEY)
        
        self.vector_store = None
        self.index = None

    def load_index(self, collection_name: str):
        """Load the vector store index for the curriculum"""
        try:
            # Initialize Qdrant vector store
            vector_store = QdrantVectorStore(
                client=qdrant_client_inst,
                collection_name=collection_name
            )
            
            # Create storage context
            storage_context = StorageContext.from_defaults(
                vector_store=vector_store
            )
            
            # Load the index
            self.index = VectorStoreIndex.from_vector_store(
                vector_store,
                storage_context=storage_context
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load curriculum index: {str(e)}"
            )

    async def get_response(self, query: DiscussionQuery) -> DiscussionResponse:
        """Get response for a curriculum discussion query"""
        try:
            # Load index if not already loaded or if collection changed
            if not self.index or self.vector_store != query.collection_name:
                self.load_index(query.collection_name)
                self.vector_store = query.collection_name
            
            # Create query engine with chat history
            query_engine = self.index.as_query_engine(
                chat_history=[
                    (msg["content"], msg["role"])
                    for msg in query.chat_history
                ],
                similarity_top_k=3,  # Number of source chunks to consider
                response_mode="tree_summarize"  # Summarize across multiple chunks
            )
            
            # Get response
            response: Response = await query_engine.aquery(query.query)
            
            # Extract source texts
            sources = []
            if response.source_nodes:
                sources = [
                    node.node.text[:200] + "..."  # First 200 chars of each source
                    for node in response.source_nodes
                ]
            
            return DiscussionResponse(
                answer=str(response),
                sources=sources
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process query: {str(e)}"
            )
