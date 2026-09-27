# Embeddings Module

This module provides semantic search functionality using MongoDB Atlas Vector Search and OpenAI embeddings.

## Overview

The embeddings module consists of three main components:

1. **`embedding_generator.py`** - Generates vector embeddings using OpenAI's embedding models
2. **`semantic_search.py`** - Provides semantic search capabilities using MongoDB vector search
3. **`index_documents.py`** - Script to index documents from disk into MongoDB

## Components

### EmbeddingGenerator

Generates embeddings using OpenAI or compatible APIs.

**Features:**
- Supports OpenAI embedding models (e.g., `text-embedding-3-small`)
- Configurable dimensions (default: 1536)
- Batch processing support
- Compatible with OpenAI-compatible APIs

**Usage:**
```python
from mcp_rag_agent.embeddings.embedding_generator import EmbeddingGenerator

# Initialize
generator = EmbeddingGenerator(
    api_key="your-api-key",
    model="text-embedding-3-small",
    dimensions=1536
)

# Generate single embedding
embedding = await generator.generate("Your text here")

# Generate batch embeddings
embeddings = await generator.generate_batch(["Text 1", "Text 2", "Text 3"])
```

### SemanticSearch

Semantic search engine using MongoDB vector search.

**Features:**
- Document indexing with embeddings
- Vector similarity search
- Metadata filtering
- Automatic index creation
- Batch document processing

**Usage:**
```python
from mcp_rag_agent.mongodb.client import MongoDBClient
from mcp_rag_agent.embeddings.embedding_generator import EmbeddingGenerator
from mcp_rag_agent.embeddings.semantic_search import SemanticSearch

# Initialize components
mongo_client = MongoDBClient(uri="mongodb://...", database_name="mydb")
embedding_generator = EmbeddingGenerator(api_key="your-key")

semantic_search = SemanticSearch(
    mongo_client=mongo_client,
    embedding_generator=embedding_generator,
    default_collection="vectors",
    default_index="vector_index"
)

# Create index
semantic_search.setup_index()

# Index a document
doc_id = await semantic_search.index_document(
    content="Your document content",
    metadata={"source": "example", "category": "docs"}
)

# Search
results = await semantic_search.search(
    query="search query",
    limit=10
)
```

**Demo Script:**

Run the semantic search demo:
```bash
python src/mcp_rag_agent/embeddings/semantic_search.py
```

This demo script will:
- Set up a vector search index
- Index 3 dummy documents
- Perform a test search
- Clean up dummy documents

### Production Document Ingestion Subsystem

The `index_documents.py` entry point orchestrates the production `DocumentIngestionPipeline` (`src/mcp_rag_agent/ingestion/`).

## Document Ingestion & Indexing

### Quick Start

**Standard incremental ingestion (skips duplicates):**
```bash
python -m mcp_rag_agent.embeddings.index_documents
```

**Force re-indexing of all documents:**
```bash
python -m mcp_rag_agent.embeddings.index_documents --reindex
```

**Clear existing database indexes and rebuild from scratch:**
```bash
python -m mcp_rag_agent.embeddings.index_documents --clear
```

**Ingest from a custom directory with custom chunk parameters:**
```bash
python -m mcp_rag_agent.embeddings.index_documents --folder ./data/my_docs --chunk-size 800 --chunk-overlap 80
```

### CLI Options

| Argument | Type | Default | Description |
|---|---|---|---|
| `--clear` | Flag | `False` | Delete all existing documents and vectors before indexing |
| `--reindex` | Flag | `False` | Force re-indexing of all documents even if content hashes match |
| `--folder` | String | `config.ingested_doc_dir` | Custom folder containing documents to process |
| `--chunk-size` | Integer | `config.chunk_size` (500) | Maximum characters per chunk |
| `--chunk-overlap` | Integer | `config.chunk_overlap` (50) | Overlapping characters between consecutive chunks |

### Pipeline Architecture

```
Source Document (.txt, .md, .pdf, .docx)
    │
    ▼
SHA-256 Hasher & Duplicate Detector
    ├─ Unchanged Hash & not reindex ──► [SKIP]
    └─ New Hash or reindex=True ──────► Purge Stale Chunks
                                              │
                                              ▼
                                         Format Parser (TXT/MD/PDF/DOCX)
                                              │
                                              ▼
                                         Document Cleaner (NFKC, control chars)
                                              │
                                              ▼
                                         Structure-Aware Chunker
                                              │
                                              ▼
                                         Metadata Enrichment
                                              │
                                              ▼
                                         Batch Embedding Generator
                                              ├─► documents Collection (Parent Metadata)
                                              └─► vectors Collection (Chunks + Embeddings)
```

### Supported File Formats

- **Plain Text (`.txt`)**: UTF-8 and fallback encoding support, paragraph-aware.
- **Markdown (`.md`, `.markdown`)**: Frontmatter/title extraction, partitioned by `#`, `##` headings into sections.
- **PDF (`.pdf`)**: Page-by-page extraction via `pypdf`, preserving 1-indexed `page_number`.
- **Microsoft Word (`.docx`)**: Heading and paragraph extraction via `python-docx`, preserving section hierarchy and table text.

### Document Schema

**`documents` Collection (Parent Document Records):**
```json
{
  "document_id": "doc_a1b2c3d4e5f6",
  "filename": "remote_working.pdf",
  "file_type": "pdf",
  "source_path": "/path/to/remote_working.pdf",
  "title": "Remote Working Policy",
  "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "total_chunks": 4,
  "total_characters": 1820,
  "ingestion_timestamp": "2026-09-23T08:30:00.000000+00:00",
  "created_at": "2026-09-23T08:30:00.000000+00:00"
}
```

**`vectors` Collection (Chunks with Embeddings & Enriched Metadata):**
```json
{
  "chunk_id": "doc_a1b2c3d4e5f6_c0",
  "content": "Employees may work remotely up to three days per week...",
  "embedding": [0.0123, -0.0456, ...],
  "metadata": {
    "chunk_id": "doc_a1b2c3d4e5f6_c0",
    "document_id": "doc_a1b2c3d4e5f6",
    "filename": "remote_working.pdf",
    "file_type": "pdf",
    "source_path": "/path/to/remote_working.pdf",
    "title": "Remote Working Policy",
    "section": "Eligibility Criteria",
    "page_number": 1,
    "chunk_index": 0,
    "total_chunks": 4,
    "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "ingestion_timestamp": "2026-09-23T08:30:00.000000+00:00"
  }
}
```

## Configuration

The module uses environment-driven settings from `config.py`:

```python
# Ingestion & Chunking settings
chunk_size: int = 500              # Maximum characters per chunk
chunk_overlap: int = 50            # Overlap between adjacent chunks
reindex: bool = False              # Force re-indexing of documents
ingested_doc_dir: str              # Directory containing raw policy documents

# Database & Embedding settings
db_documents_collection: str       # "documents"
db_vector_collection: str          # "vectors"
db_vector_index_name: str          # "vector_index"
embedding_model: str               # "text-embedding-3-small"
embedding_dimension: int           # 256
```

## Requirements

- MongoDB Atlas cluster with vector search support
- OpenAI API key
- Python 3.11+
- Required packages:
  - `pymongo`
  - `openai`
  - `pydantic-settings`
  - `python-dotenv`

## Notes

### Vector Search Index

MongoDB Atlas vector search indexes may take a few minutes to become fully active after creation. If searches return no results immediately after indexing, wait a few minutes and try again.

### Embedding Costs

Generating embeddings uses the OpenAI API and incurs costs based on:
- Model used (e.g., `text-embedding-3-small`)
- Number of tokens processed
- Refer to OpenAI pricing for current rates

### Best Practices

1. **Use `--clear` flag judiciously** - It deletes all existing data
2. **Monitor embedding costs** - Batch operations are more efficient
3. **Wait for index activation** - New indexes need time to build
4. **Use meaningful metadata** - Helps with filtering and organization
5. **Handle large files** - Consider chunking for very large documents

## Troubleshooting

**Issue: Search returns no results**
- Wait a few minutes for the index to become active
- Verify documents were indexed successfully
- Check that the index name matches configuration

**Issue: Import errors**
- Ensure the package is installed: `pip install -e .`
- Check that all dependencies are installed

**Issue: OpenAI API errors**
- Verify API key is correct in `.env` file
- Check API rate limits and quotas
- Ensure sufficient credits in OpenAI account

## Examples

### Basic Indexing Workflow

```python
import asyncio
from mcp_rag_agent.config import config
from mcp_rag_agent.mongodb.client import MongoDBClient
from mcp_rag_agent.embeddings.embedding_generator import EmbeddingGenerator
from mcp_rag_agent.embeddings.semantic_search import SemanticSearch

async def main():
    # Initialize
    mongo_client = MongoDBClient(uri=config.db_url, database_name=config.db_name)
    mongo_client.connect()
    
    embedding_generator = EmbeddingGenerator(
        api_key=config.model_api_key,
        model=config.embedding_model,
        dimensions=config.embedding_dimension
    )
    
    semantic_search = SemanticSearch(
        mongo_client=mongo_client,
        embedding_generator=embedding_generator
    )
    
    # Setup index
    semantic_search.setup_index()
    
    # Index documents
    docs = [
        {"content": "Document 1", "metadata": {"type": "policy"}},
        {"content": "Document 2", "metadata": {"type": "guide"}}
    ]
    
    doc_ids = await semantic_search.index_documents(docs)
    print(f"Indexed {len(doc_ids)} documents")
    
    # Search
    results = await semantic_search.search("policy information", limit=5)
    for result in results:
        print(f"Score: {result['score']}, Content: {result['content'][:100]}...")
    
    # Cleanup
    mongo_client.disconnect()

asyncio.run(main())
```

### Searching with Filters

```python
# Search with metadata filter
results = await semantic_search.search(
    query="remote work policy",
    limit=10,
    filter_query={"metadata.folder_name": "policies"}
)
```

## License

This module is part of the MCP RAG Agent project.
