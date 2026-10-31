# RAG Provider

Client for communicating with the RAG service (vector database) for document queries and metadata retrieval.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              RAG ECOSYSTEM                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

                         ┌──────────────────────────┐
                         │   RAG Service       │
                         │ (unifai-rag-server) │
                         │       :13456             │
                         └───────────┬──────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
         │  GET /api/   │  │  GET /api/   │  │  GET /api/   │
         │  docs/avail  │  │  docs/avail  │  │  docs/query  │
         │  able.tags   │  │  able.docs   │  │  .match      │
         │  .get        │  │  .get        │  │              │
         └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
                │                 │                 │
                └─────────────────┼─────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            RagClient (client.py)                                │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐      │
│  │ get_available_tags  │  │ get_available_docs  │  │    query_match      │      │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         RagProvider (rag_provider.py)                           │
│                                                                                 │
│  High-level sync API wrapping RagClient                                         │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐      │
│  │ get_available_tags  │  │ get_available_docs  │  │       query         │      │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    RagProviderFactory + RagProviderConfig                       │
│                                                                                 │
│  Config defaults:                                                               │
│    base_url: http://unifai-rag-server:13456                                     │
│    top_k: 10                                                                    │
│    timeout: 30.0                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                  │
                 ┌────────────────┴────────────────┐
                 │                                 │
                 ▼                                 ▼
┌────────────────────────────┐     ┌────────────────────────────────────────────┐
│   DocsRagRetriever         │     │              ACTIONS                       │
│                            │     │                                            │
│  - Uses factory internally │     │  ┌─────────────────────────────────────┐   │
│  - Filters by threshold    │     │  │ rag.validate_connection             │   │
│  - Gets scope/user from    │     │  │ (uses RagClient directly)           │   │
│    context                 │     │  └─────────────────────────────────────┘   │
│                            │     │  ┌─────────────────────────────────────┐   │
│  retrieve(query) → matches │     │  │ rag.get_available_tags              │   │
└────────────────────────────┘     │  │ (uses factory)                      │   │
                                   │  └─────────────────────────────────────┘   │
                                   │  ┌─────────────────────────────────────┐   │
                                   │  │ rag.get_available_docs              │   │
                                   │  │ (uses factory)                      │   │
                                   │  └─────────────────────────────────────┘   │
                                   └────────────────────────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/docs/available.tags.get` | GET | Paginated list of available tags |
| `/api/docs/available.docs.get` | GET | Paginated list of available documents |
| `/api/docs/query.match` | GET | Query vector database for matching documents |

## Usage

### Using the Provider directly

```python
from mas.elements.providers.rag_client.rag_provider import RagProvider

provider = RagProvider(
    base_url="http://unifai-rag-server:13456",
    top_k=10,
    timeout=30.0,
)

# Query vector database
response = provider.query(
    query="How do I reset my password?",
    scope="my_scope",
    logged_in_user="user@example.com",
)

# Get available tags
tags = provider.get_available_tags(limit=50, search_regex="^test")

# Get available docs
docs = provider.get_available_docs(limit=50)
```

### Using the Factory (recommended)

```python
from elements.providers.rag_client.config import RagProviderConfig
from elements.providers.rag_client.rag_provider_factory import RagProviderFactory

config = RagProviderConfig(top_k=5)
factory = RagProviderFactory()
provider = factory.create(config)

response = provider.query(query="my search query")
```

## Files

| File | Purpose |
|------|---------|
| `identifiers.py` | Provider type key and metadata |
| `models.py` | Pydantic response models |
| `config.py` | `RagProviderConfig` with defaults |
| `client.py` | `RagClient` - sync HTTP client |
| `rag_provider.py` | `RagProvider` - high-level API |
| `rag_provider_factory.py` | Factory for creating provider from config |
| `spec/spec.py` | Element spec for auto-discovery |

