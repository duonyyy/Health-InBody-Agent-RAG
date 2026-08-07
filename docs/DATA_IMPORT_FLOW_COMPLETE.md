# DATA IMPORT FLOW - Health/InBody RAG Corpus

## Overview

Đây là quy trình import dữ liệu Health/InBody từ file JSONL đã xử lý vào Qdrant vector database, với embedding semantic từ BGE-M3/custom embedding service.

**Input hiện tại**: `data_pipeline/dataset/processed/embedding_documents.jsonl`  
**Output**: Vectors lưu trong Qdrant + Search index  
**Duration**: ~5-10 phút tùy dữ liệu

---

## 🔄 Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   DATA IMPORT FLOW                          │
└─────────────────────────────────────────────────────────────┘

1. INPUT (embedding_documents.jsonl)
   ↓
   {"question": "BMI và PBF khác nhau như thế nào?", "content": "Nội dung sức khỏe/InBody..."}
   {"title": "Mỡ nội tạng", "content": "Khuyến nghị dinh dưỡng và tập luyện..."}
   
2. PARSE JSON
   ├─ Question (Câu hỏi)
   ├─ Content (Tài liệu)
   └─ ID (Document ID)
   ↓
   
3. DOCUMENT CHUNKING
   ├─ Input: Combined text (question + context)
   ├─ Method: SemanticSplitterNodeParser
   │  └─ Breaks at semantic boundaries (not random)
   └─ Output: [Chunk1, Chunk2, Chunk3, ...]
   ↓
   
4. EMBEDDING GENERATION
   ├─ Model: BAAI/bge-m3 (1024-dim)
   ├─ Service: Custom Embedding API (Port 5001)
   └─ Output: Vector [0.123, -0.456, ..., 0.789]
   ↓
   
5. BATCH COLLECTION
   ├─ Group vectors (default: 50 vectors/batch)
   ├─ Attach metadata:
   │  ├─ question
   │  ├─ content (chunk text)
   │  ├─ source
   │  └─ doc_id
   └─ Queue for insertion
   ↓
   
6. QDRANT INSERTION
   ├─ Connection: http://qdrant-db:6333
   ├─ Collection: "nmk_chatbot_collection" (1024-dim vectors)
   ├─ Distance: DOT (dot product)
   └─ Storage: qdrant_volume (persistent)
   ↓
   
7. SEARCH INDEX INITIALIZATION
   ├─ Convert docs to LlamaIndex format
   ├─ Initialize BM25 retriever
   └─ Store docstore in memory
   ↓
   
✅ COMPLETED
   └─ Vectors in Qdrant + Search index ready
```

---

## 📝 Step-by-Step Breakdown

### **STEP 1: File Input & Validation**

```python
# Location: backend/src/pipelines/import_data.py
# Function: import_qa_data()

DATA_FILE_PATH = "/usr/src/app/data/train.jsonl"
```

**Input format (train.jsonl)**:
```json
{"question": "Luật Lao động bao gồm những nội dung gì?", "context": "Luật Lao động là bộ luật quy định..."}
{"question": "Xác định quyền của người lao động?", "context": "Người lao động có quyền..."}
```

**Kiểm tra**:
- ✅ File tồn tại
- ✅ File size (MB)
- ✅ Readable encoding (UTF-8)

```python
if not os.path.exists(data_file_path):
    logger.error(f"❌ Data file not found: {data_file_path}")
    return False

file_size = os.path.getsize(data_file_path)
logger.info(f"📊 File size: {file_size / (1024*1024):.2f} MB")
```

---

### **STEP 2: Create Qdrant Collection**

```python
# Import function từ backend/src/vectorize.py
from rag.qdrant.client import create_collection

# Collection configuration
create_collection(
    name="llm",
    vector_size=1024  # BAAI/bge-m3 embedding dimension
)
```

**Docker Service** (backend/docker-compose.yml):
```yaml
qdrant-db:
  image: qdrant/qdrant:latest
  ports:
    - "6333:6333"    # REST API
    - "6334:6334"    # gRPC
  volumes:
    - qdrant_volume:/qdrant/storage
```

**Output**: Collection "llm" ready để nhận vectors

---

### **STEP 3: Read JSONL Line by Line**

```python
# backend/src/pipelines/import_data.py - Main loop

success_count = 0
error_count = 0
vectors_batch = {}
total_vectors_processed = 0
documents_for_search = []

with open(data_file_path, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        # Progress logging
        if idx % 50 == 0:
            logger.info(f"📊 Processing line {idx + 1}...")
        
        # Parse JSON
        data = json.loads(line.strip())
        question = data.get("question", "")
        context = data.get("context", "")
        
        # Validate
        if not question or not context:
            error_count += 1
            continue
```

**Output**:
- `question`: "Luật Lao động bao gồm những nội dung gì?"
- `context`: "Luật Lao động là bộ luật quy định..."
- `idx`: 0 (line number)

---

### **STEP 4: Document Chunking (Semantic Split)**

```python
# Import từ backend/src/splitter.py
from splitter import split_document

# Combine question + context
text = f"{question} {context}"

# Split thành semantic chunks
nodes = split_document(text, use_semantic=True)
```

**splitter.py code**:
```python
from llama_index.core.node_parser import SemanticSplitterNodeParser
from custom_embedding import get_custom_embedding

def split_document(text, metadata={"course": "LLM"}, use_semantic=True):
    doc = Document(text=text, metadata=metadata)
    
    if use_semantic:
        # Semantic splitter - splits at semantic boundaries
        embed_model = CustomEmbeddingWrapper()
        splitter = SemanticSplitterNodeParser(
            buffer_size=1,                    # Group sentences for similarity
            breakpoint_percentile_threshold=95, # Split threshold
            embed_model=embed_model,
        )
    else:
        # Fallback: Token splitter
        splitter = TokenTextSplitter(
            chunk_size=512,
            chunk_overlap=50,
        )
    
    nodes = splitter.get_nodes_from_documents([doc])
    return nodes
```

**Ví dụ Output**:
```
Original text (1000 chars)
    ↓
Semantic splitting (BAAI/bge-m3 detects boundaries)
    ↓
Chunk 1: "Luật Lao động bao gồm... [semantic boundary] ..."
Chunk 2: "Nội dung gồm có quyền của người lao động..."
Chunk 3: "Điều khoản về giảng dạy..."
```

---

### **STEP 5: Generate Embeddings**

```python
# Import từ backend/src/brain.py
from llm.client import get_embedding

for node in nodes:
    # Get embedding from custom service
    vector = get_embedding(node.text)
```

**brain.py code**:
```python
from custom_embedding import get_custom_embedding

def get_embedding(text):
    """Get embedding from custom model service"""
    try:
        embedding = get_custom_embedding(text)
        return embedding
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        raise
```

**custom_embedding.py code**:
```python
class CustomEmbeddingService:
    def __init__(self, api_url="http://3.80.119.178:5001"):
        self.api_url = api_url
        self.embedding_endpoint = f"{self.api_url}/embed"
    
    def get_embedding(self, text):
        response = requests.post(
            self.embedding_endpoint,
            json={"texts": [text], "batch_size": 32},
            timeout=30
        )
        data = response.json()
        return data.get("embeddings")[0]  # Return 1024-dim vector
```

**Embedding Service** (embed_serving/serve_model.py):
```python
from sentence_transformers import SentenceTransformer

# Flask API serving BAAI/bge-m3
@app.route("/embed", methods=["POST"])
def embed():
    data = request.get_json()
    texts = data["texts"]
    
    # Generate embeddings
    embeddings = model.encode(texts, show_progress_bar=False)
    
    return jsonify({
        "embeddings": embeddings.tolist(),
        "embedding_dim": 1024
    })
```

**Output**: Vector [1024 dimensions]
```
[0.123, -0.456, 0.789, ..., -0.234]  (1024 values)
```

---

### **STEP 6: Batch Collection & Metadata Attachment**

```python
# backend/src/pipelines/import_data.py

# Create unique ID for chunk
point_id = idx * 1000 + chunk_idx

# Add to batch with metadata
vectors_batch[point_id] = {
    "vector": vector,  # 1024-dim embedding
    "payload": {
        "question": question,           # Original question
        "content": node.text,           # Chunk content
        "source": "train",              # Data source
        "doc_id": idx,                  # Document index
    }
}

# When batch reaches threshold
if len(vectors_batch) >= batch_size:
    add_vector(
        collection_name="llm",
        vectors=vectors_batch,
        batch_size=50
    )
    vectors_batch = {}  # Reset
```

**Batch Structure**:
```python
{
    1000: {
        "vector": [0.123, -0.456, ..., -0.234],
        "payload": {
            "question": "Luật Lao động bao gồm những nội dung gì?",
            "content": "Luật Lao động là bộ luật quy định...",
            "source": "train",
            "doc_id": 1
        }
    },
    1001: {
        "vector": [...],
        "payload": {...}
    },
    ...
}
```

---

### **STEP 7: Insert into Qdrant**

```python
# backend/src/vectorize.py
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

client = QdrantClient(url="http://qdrant-db:6333")

def add_vector(collection_name, vectors, batch_size=100):
    # Convert dict to PointStruct
    points = [
        PointStruct(
            id=k,
            vector=v["vector"],
            payload={
                **v["payload"],
                "doc_length": len(v["payload"].get("content", "")),
                "has_question": bool(v["payload"].get("question", "")),
                "content_type": detect_content_type(v["payload"].get("content", ""))
            }
        )
        for k, v in vectors.items()
    ]
    
    # Batch insert
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        result = client.upsert(
            collection_name=collection_name,
            wait=True,
            points=batch
        )
        logger.info(f"Processed batch {i//batch_size + 1}")
```

**Qdrant Storage** (docker-compose.yml):
```yaml
volumes:
  - qdrant_volume:/qdrant/storage
```

**Output**: Vectors stored in Qdrant with metadata indexed

---

### **STEP 8: Search Index Initialization**

```python
# backend/src/pipelines/import_data.py

from rag.search import initialize_search_index

# Collect documents
documents_for_search = [
    {
        "question": question,
        "content": context,
        "source": "train",
        "doc_id": idx
    }
    for question, context, idx in documents
]

# Initialize search index
initialize_search_index(documents_for_search)
```

**search.py code**:
```python
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.retrievers.bm25 import BM25Retriever

def initialize_search_index(documents):
    global _docstore, _bm25_retriever
    
    # Convert to LlamaIndex format
    llama_docs = [
        Document(
            text=f"{doc['question']} {doc['content']}",
            metadata={
                "question": doc.get('question'),
                "content": doc.get('content'),
                "source": doc.get('source'),
                "doc_id": doc.get('doc_id')
            }
        )
        for doc in documents
    ]
    
    # Split into nodes
    splitter = SentenceSplitter(chunk_size=2048)
    nodes = splitter.get_nodes_from_documents(llama_docs)
    
    # Initialize docstore
    _docstore = SimpleDocumentStore()
    _docstore.add_documents(nodes)
    
    # Initialize BM25 retriever
    _bm25_retriever = BM25Retriever.from_defaults(
        docstore=_docstore,
        similarity_top_k=5
    )
    
    return True
```

**Output**: 
- SimpleDocumentStore (in-memory)
- BM25Retriever ready for keyword search

---

## 📊 Data Flow Summary

| Stage | Input | Process | Output |
|-------|-------|---------|--------|
| **1** | train.jsonl | File validation | Confirmed file path |
| **2** | File path | Create collection | Collection "llm" (empty) |
| **3** | JSON lines | Parse Q&A | question, context, idx |
| **4** | Combined text | Semantic splitting | [Node1, Node2, ...] |
| **5** | Node text | BAAI/bge-m3 API | Vector (1024-dim) |
| **6** | Vector + text | Attach metadata | Point with payload |
| **7** | Batch points | Qdrant upsert | Stored in DB |
| **8** | Documents | BM25 indexing | Search index ready |

---

## 🎯 Performance Metrics

**Typical Processing**:
- **Batch size**: 50 vectors
- **Vectors per document**: 1-3 (depending on chunking)
- **Embedding time**: ~100ms per text (API latency)
- **Insert time**: ~50ms per batch (50 vectors)
- **Total time**: ~5-10 phút cho 10k documents

**Example Timeline**:
```
Line 1-50:     80s (embeddings + insert)
Line 51-100:   80s
Line 101-150:  80s
...
Total: 10,000 lines → ~500s (≈8 minutes)
```

---

## 🐛 Error Handling

### Missing Fields
```python
if not question or not context:
    logger.warning(f"⚠️ Line {idx + 1}: Missing question or context, skipping")
    error_count += 1
    continue
```

### JSON Parse Error
```python
except json.JSONDecodeError as e:
    logger.error(f"Line {idx + 1}: JSON decode error - {e}")
    error_count += 1
```

### Embedding Service Down
```python
except Exception as e:
    logger.error(f"❌ Error getting embedding from custom service: {e}")
    raise
```

### Qdrant Connection Failed
```python
except Exception as e:
    logger.error(f"Failed to process batch {i//batch_size + 1}: {e}")
    results.append({"error": str(e)})
```

---

## 🚀 Running the Import

### Via Docker
```bash
cd backend
docker-compose up -d

# After services are running
docker-compose exec chatbot-api python -c "from import_data import import_qa_data; import_qa_data()"
```

### Locally (with services running)
```bash
cd backend/src
python -c "from import_data import import_qa_data; import_qa_data()"
```

### With Limit (testing)
```python
from import_data import import_qa_data

# Only import 100 records
import_qa_data(limit=100)
```

---

## 📋 Checklist

Before running:
- [ ] `train.jsonl` exists at `/usr/src/app/data/train.jsonl`
- [ ] Qdrant service running (`docker-compose up -d qdrant-db`)
- [ ] Embedding service running (port 5001)
- [ ] MySQL/Redis accessible
- [ ] Sufficient disk space for vectors

After import:
- [ ] Check Qdrant dashboard: `http://localhost:6333/dashboard`
- [ ] Verify collection "llm" exists
- [ ] Check vector count matches documents
- [ ] Test search functionality

---

## 🔗 Related Files

**Core Files**:
- [backend/src/pipelines/import_data.py](../backend/src/pipelines/import_data.py) - Main import script
- [backend/src/splitter.py](../backend/src/splitter.py) - Document chunking
- [backend/src/vectorize.py](../backend/src/vectorize.py) - Qdrant operations
- [backend/src/brain.py](../backend/src/brain.py) - Embedding retrieval
- [backend/src/custom_embedding.py](../backend/src/custom_embedding.py) - Embedding API client

**Configuration**:
- [backend/docker-compose.yml](../backend/docker-compose.yml) - Services setup
- [embed_serving/scripts/serve_model.py](../embed_serving/scripts/serve_model.py) - Embedding service

**Search**:
- [backend/src/search.py](../backend/src/search.py) - Search index initialization

---

## 💡 Key Takeaways

1. **Semantic Chunking**: Tài liệu pháp lý được tách tại ranh giới ngữ nghĩa, không phải ngẫu nhiên
2. **Custom Embeddings**: Sử dụng BAAI/bge-m3 thay vì OpenAI (tiết kiệm cost)
3. **Batch Processing**: Insert 50 vectors cùng lúc (optimize I/O)
4. **Metadata Rich**: Mỗi vector lưu câu hỏi, nội dung, nguồn để tracking
5. **Dual Retrieval**: Kết hợp vector search (semantic) + BM25 (keyword)

---

**Last Updated**: April 2026  
**Status**: ✅ Complete & Production Ready
