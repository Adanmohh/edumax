import os
import sys
import json
from typing import List, Dict, Optional
from datetime import datetime
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    Settings,
    Response,
    ServiceContext
)
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.text_splitter import TokenTextSplitter
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from pydantic import BaseModel
from fastapi import HTTPException

from ..config import (
    qdrant_client_inst,
    OPENAI_API_KEY, MODEL_NAME, EMBEDDING_MODEL,
    QDRANT_URL, QDRANT_API_KEY,
    validate_qdrant_connection
)

class CurriculumContext(BaseModel):
    """Enhanced context extracted from curriculum for AI generation"""
    # Basic context
    relevant_content: str
    learning_objectives: List[str]
    key_concepts: List[str]
    skill_level: str
    domain_context: str
    
    # Additional context
    themes: List[str]
    progression_path: Dict[str, List[str]]
    teaching_approach: Dict[str, str]
    core_competencies: List[str]
    
    # Cache metadata
    extraction_timestamp: datetime
    context_type: str  # 'course', 'module', or 'lesson'
    parent_context_id: Optional[int] = None  # ID of parent (course/module) for context hierarchy

class CurriculumExtractionWorkflow:
    def __init__(self):
        if not all([OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY]):
            raise HTTPException(
                status_code=500,
                detail="Missing required environment variables"
            )
        
        # Configure OpenAI models with specific parameters
        Settings.llm = OpenAI(
            model=MODEL_NAME,
            api_key=OPENAI_API_KEY,
            temperature=0.0,  # Deterministic output
            max_tokens=1500,  # Longer responses
            timeout=60  # Longer timeout
        )
        Settings.embed_model = OpenAIEmbedding(
            model=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY,
            embed_batch_size=100  # Process more text at once
        )
        print("Debug: OpenAI models configured", file=sys.stderr)
        
        self.current_collection = None
        self.index = None
        self.query_cache = {}

    def load_index(self, collection_name: str):
        """Load and validate vector store index with dual storage setup"""
        try:
            print(f"Debug: Starting load_index for collection: {collection_name}", file=sys.stderr)
            
            success, message, available_collections = validate_qdrant_connection(collection_name)
            print(f"Debug: Qdrant validation result - success: {success}, message: {message}", file=sys.stderr)
            
            if not success:
                if "not found" in message:
                    raise HTTPException(status_code=404, detail=message)
                elif "no vectors" in message:
                    raise HTTPException(
                        status_code=400,
                        detail="Curriculum has not been processed yet. Please run curriculum ingestion first via /curriculum/ingest endpoint"
                    )
                else:
                    raise HTTPException(status_code=500, detail=message)

            # Initialize vector store with proper configuration
            vector_store = QdrantVectorStore(
                client=qdrant_client_inst,
                collection_name=collection_name,
                prefer_grpc=False,
                timeout=10
            )
            
            # Initialize document store
            doc_store = SimpleDocumentStore()
            
            # Create storage context with both stores
            storage_context = StorageContext.from_defaults(
                docstore=doc_store,
                vector_store=vector_store
            )
            
            # Configure settings for document processing
            Settings.text_splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=50)
            Settings.node_parser = SimpleNodeParser.from_defaults(
                chunk_size=512,
                chunk_overlap=50
            )
            
            # Create index from vector store
            self.index = VectorStoreIndex.from_vector_store(
                vector_store,
                storage_context=storage_context,
                show_progress=True,
                use_async=True
            )
            
            # Ensure index is properly initialized
            if not self.index:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to initialize index from vector store"
                )
                
            # Initialize the retriever
            self.index._retriever = self.index.as_retriever()
            
            # Verify index is initialized
            if not self.index:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to initialize VectorStoreIndex"
                )
            
            self.current_collection = collection_name
            print("Debug: Successfully loaded index with dual storage", file=sys.stderr)

        except HTTPException as he:
            raise he
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load curriculum index: {str(e)}"
            )

    async def _execute_query(self, query_engine, query: str, cache_key: str = None, metadata_filters: dict = None) -> str:
        """Execute query with caching"""
        try:
            if cache_key and cache_key in self.query_cache:
                print(f"Debug: Cache hit for {cache_key}", file=sys.stderr)
                return self.query_cache[cache_key]
            
            print(f"Debug: Executing query: {query}", file=sys.stderr)
            
            # Apply filters to the query engine's retriever if needed
            if metadata_filters and hasattr(query_engine.retriever, 'filters'):
                query_engine.retriever.filters = metadata_filters
                print(f"Debug: Applied filters: {metadata_filters}", file=sys.stderr)
            
            try:
                response = await query_engine.aquery(query)
                print(f"Debug: Raw response: {response}", file=sys.stderr)
            finally:
                # Reset filters after query
                if metadata_filters and hasattr(query_engine.retriever, 'filters'):
                    query_engine.retriever.filters = None
            print(f"Debug: Query response received", file=sys.stderr)
            
            if not response:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get response for query: {query}"
                )
            
            result = str(response).strip()
            if cache_key:
                self.query_cache[cache_key] = result
            return result
            
        except Exception as e:
            print(f"Debug: Query execution error: {str(e)}", file=sys.stderr)
            raise HTTPException(
                status_code=500,
                detail=f"Query execution failed: {str(e)}"
            )

    def _parse_bullet_points(self, text: str) -> List[str]:
        """Parse bullet points from response text"""
        if not text or not isinstance(text, str):
            print(f"Debug: Invalid response text for parsing: {text}", file=sys.stderr)
            return []
            
        try:
            lines = text.split('\n')
            points = []
            for line in lines:
                line = line.strip().lstrip('•-*').strip()
                if line:
                    points.append(line)
            return points
        except Exception as e:
            print(f"Debug: Error parsing bullet points: {str(e)}", file=sys.stderr)
            return []

    async def extract_comprehensive_context(
        self,
        collection_name: str,
        context_type: str = 'course',
        parent_context_id: int = None,
        specific_focus: str = None
    ) -> CurriculumContext:
        """Extract comprehensive curriculum context with caching"""
        try:
            if not self.index or self.current_collection != collection_name:
                self.load_index(collection_name)

            # Configure query engine
            if not self.index:
                raise HTTPException(
                    status_code=500,
                    detail="Index not initialized"
                )

            # Configure custom retriever
            from llama_index.core.retrievers import VectorIndexRetriever
            
            retriever = VectorIndexRetriever(
                index=self.index,
                similarity_top_k=5  # Number of chunks to retrieve
            )
            
            # Create query engine with custom retriever and response synthesis
            query_engine = self.index.as_query_engine(
                retriever=retriever,
                response_mode="tree_summarize",  # More robust response synthesis
                node_postprocessors=[],  # Remove postprocessors for now
                verbose=True,  # Enable verbose mode for debugging
                use_async=True,  # Enable async mode
                similarity_top_k=5,  # Consistent with retriever setting
                streaming=False  # Disable streaming for better error handling
            )
            
            if not query_engine:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to initialize query engine"
                )
            
            print("Debug: Query engine initialized with custom retriever", file=sys.stderr)

            # Enhanced context queries with metadata filtering
            objectives = await self._execute_query(
                query_engine,
                "Extract and list the main learning objectives and outcomes. Focus on measurable and actionable objectives.",
                f"{collection_name}_objectives",
                {"keywords": ["objective", "outcome", "goal"]}
            )
            
            concepts = await self._execute_query(
                query_engine,
                "Identify and explain key concepts, terminology, and their relationships. Include definitions where available.",
                f"{collection_name}_concepts",
                {"keywords": ["concept", "term", "definition"]}
            )
            
            skill_level = await self._execute_query(
                query_engine,
                "Analyze the skill level and prerequisites. Consider progression of difficulty and prior knowledge requirements.",
                f"{collection_name}_skill_level",
                {"keywords": ["prerequisite", "difficulty", "level"]}
            )

            # Enhanced context queries with advanced prompting
            themes = await self._execute_query(
                query_engine,
                "Analyze the main themes and their interconnections. Identify overarching patterns and relationships between topics.",
                f"{collection_name}_themes",
                {"keywords": ["theme", "topic", "subject"]}
            )
            
            progression = await self._execute_query(
                query_engine,
                "Map the learning progression and knowledge building sequence. Include dependencies and recommended order.",
                f"{collection_name}_progression",
                {"keywords": ["sequence", "progression", "order"]}
            )
            
            approach = await self._execute_query(
                query_engine,
                "Evaluate recommended teaching approaches and methodologies. Include practical implementation suggestions.",
                f"{collection_name}_approach",
                {"keywords": ["method", "approach", "strategy"]}
            )
            
            competencies = await self._execute_query(
                query_engine,
                "Identify core competencies and skills students should develop. Include both technical and soft skills.",
                f"{collection_name}_competencies",
                {"keywords": ["competency", "skill", "ability"]}
            )

            # Context-specific query
            if specific_focus:
                relevant = await self._execute_query(
                    query_engine,
                    f"Provide detailed information about {specific_focus}.",
                    f"{collection_name}_{specific_focus}"
                )
            else:
                relevant = await self._execute_query(
                    query_engine,
                    "Summarize the key content and its practical applications.",
                    f"{collection_name}_general"
                )

            # Parse and structure the context
            return CurriculumContext(
                relevant_content=relevant,
                learning_objectives=self._parse_bullet_points(objectives),
                key_concepts=self._parse_bullet_points(concepts),
                skill_level=skill_level,
                domain_context=relevant,
                themes=self._parse_bullet_points(themes),
                progression_path={"sequence": self._parse_bullet_points(progression)},
                teaching_approach={"methodology": approach},
                core_competencies=self._parse_bullet_points(competencies),
                extraction_timestamp=datetime.utcnow(),
                context_type=context_type,
                parent_context_id=parent_context_id
            )

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to extract curriculum context: {str(e)}"
            )

    async def extract_context_for_task(
        self,
        collection_name: str,
        task_type: str,
        task_context: dict = None
    ) -> CurriculumContext:
        """Legacy method for backward compatibility"""
        context_type = 'course'
        specific_focus = None
        
        if task_type == "module_outline":
            context_type = 'module'
        elif task_type == "lesson_outline":
            context_type = 'lesson'
            specific_focus = task_context.get("module_name") if task_context else None
            
        return await self.extract_comprehensive_context(
            collection_name,
            context_type,
            specific_focus=specific_focus
        )
