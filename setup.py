from setuptools import setup, find_packages

setup(
    name="my_app",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        # Web Framework
        "fastapi>=0.109.2",
        "uvicorn[standard]>=0.27.1",
        "python-multipart>=0.0.7",
        "python-jose[cryptography]>=3.3.0",
        "passlib[bcrypt]>=1.7.4",
        
        # Database
        "sqlalchemy>=2.0.27",
        "alembic>=1.13.1",
        
        # LlamaIndex and AI
        "llama-index-core>=0.10.27",
        "llama-index-readers-file>=0.1.31",
        "llama-index-llms-openai>=0.1.14",
        "llama-index-embeddings-openai>=0.1.7",
        "llama-index-vector-stores-qdrant>=0.1.2",
        "openai>=1.12.0",
        "pypdf>=3.17.4",
        "qdrant-client>=1.7.0",
        
        # Utilities
        "python-dotenv>=1.0.0",
        "typing-extensions>=4.9.0",
        "python-dateutil>=2.8.2",
        "requests>=2.31.0",
        "aiofiles>=23.2.1",
    ],
) 