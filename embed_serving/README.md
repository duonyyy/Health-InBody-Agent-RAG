# Embed Serving

`embed_serving/` cung cap mot REST API nho gon de sinh embedding cho he thong RAG. Service load model duoc cau hinh qua `MODEL_PATH`, chay tren CPU mac dinh va expose cac endpoint de backend goi khi index du lieu hoac semantic search.

## Cau truc folder

```text
embed_serving/
├── .env.serving.template           # Mau bien moi truong
├── docker-compose.serving.yml      # Compose CPU mac dinh
├── docker-compose.gpu.yml          # Override CUDA/FP16
├── Dockerfile.cpu-serving          # Docker image cho CPU serving
├── Dockerfile.gpu-serving          # Docker image cho CUDA serving
├── requirements_serving.txt        # Python dependencies
├── GPU_CPU_DEPLOYMENT_GUIDE.md     # Ghi chu deployment
└── scripts/
    ├── serve_model.py              # Flask API: /health, /embed, /similarity
    └── download_model_from_spaces.py
```

## Service nay dung de lam gi

- Sinh vector embedding cho text tieng Viet.
- Tinh do tuong dong cosine giua hai nhom cau.
- Phuc vu `backend/src/custom_embedding.py` qua HTTP API.

Backend hien tai mac dinh goi service nay qua:

```env
CUSTOM_EMBEDDING_API_URL=http://host.docker.internal:5001
```

Neu chay cung Docker network voi backend, co the doi thanh:

```env
CUSTOM_EMBEDDING_API_URL=http://embedding-api:5000
```

## Yeu cau

- Python 3.10+ neu chay local
- Docker Desktop neu chay bang container
- Co model trong `embed_serving/models/bge-m3` hoac mount vao `/app/models/bge-m3`

## Tai model

Chay trong folder `embed_serving/`:

```bash
pip install -r requirements_serving.txt
python scripts/download_model_from_spaces.py
```

Script se download model `BAAI/bge-m3` vao:

```text
embed_serving/models/bge-m3
```

## Chay local

Chay trong folder `embed_serving/`:

```bash
pip install -r requirements_serving.txt
copy .env.serving.template .env.serving
python scripts/serve_model.py
```

Mac dinh service se mo tai:

```text
http://localhost:5000
```

## Chay bang Docker Compose

Chay trong folder `embed_serving/`:

```bash
copy .env.serving.template .env.serving
docker compose -f docker-compose.serving.yml up --build
```

Port mapping mac dinh:

- Container: `5000`
- Host: `5001`

Sau khi chay, service se san sang tai:

```text
http://localhost:5001
```

GPU chi nen bat sau khi CUDA smoke test thanh cong:

```bash
docker compose \
  -f docker-compose.serving.yml \
  -f docker-compose.gpu.yml \
  up --build
```

Tren may hien tai, CPU `ENCODE_BATCH_SIZE=8` duoc chon tu benchmark cung 32
doan van: 3.20 text/giay so voi 1.79 text/giay o batch 2. Can benchmark lai
neu doi CPU, model hoac do dai corpus.

## Bien moi truong

| Bien | Mac dinh | Y nghia |
| --- | --- | --- |
| `MODEL_PATH` | `/app/models/bge-m3` | Thu muc model da download |
| `LOCAL_MODEL_DIR` | `./models` | Thu muc model local khi thao tac tay |
| `API_HOST` | `0.0.0.0` | Host bind Flask |
| `API_PORT` | `5000` | Port trong process/container |
| `DEBUG` | `false` | Bat/tat Flask debug |
| `MAX_BATCH_SIZE` | `32` | So text toi da moi request |
| `ENCODE_BATCH_SIZE` | `8` tren CPU | Batch noi bo cua `SentenceTransformer.encode` |
| `EMBEDDING_DEVICE` | `cpu` | `cpu`, `cuda` hoac `auto` |
| `EMBEDDING_DTYPE` | `float32` tren CPU | `float32`, hoac `float16` khi dung CUDA |

## API contract

### `GET /health`

Kiem tra model da load thanh cong hay chua.

Vi du response:

```json
{
  "status": "healthy",
  "model_loaded": true,
  "device": "cpu",
  "timestamp": 1710000000.0,
  "embedding_dim": 1024
}
```

### `POST /embed`

Sinh embedding cho danh sach text.

Request:

```json
{
  "texts": [
    "BMI va PBF khac nhau nhu the nao?",
    "Mo noi tang cao co nguy hiem khong?"
  ]
}
```

Response:

```json
{
  "embeddings": [[0.1, 0.2], [0.3, 0.4]],
  "embedding_dim": 1024,
  "num_texts": 2,
  "inference_time": 0.123
}
```

### `POST /similarity`

Tinh cosine similarity giua hai nhom text.

Request:

```json
{
  "texts1": ["BMI cao co can giam can khong?"],
  "texts2": [
    "Chi so BMI danh gia can nang theo chieu cao",
    "Lich tap cho nguoi moi"
  ]
}
```

Response:

```json
{
  "similarities": [[0.91, 0.63]],
  "shape": [1, 2],
  "inference_time": 0.087
}
```

## Test nhanh

Health check:

```bash
curl http://localhost:5001/health
```

Embedding:

```bash
curl -X POST http://localhost:5001/embed \
  -H "Content-Type: application/json" \
  -d "{\"texts\": [\"xin chao\", \"tu van dinh duong\"]}"
```

Similarity:

```bash
curl -X POST http://localhost:5001/similarity \
  -H "Content-Type: application/json" \
  -d "{\"texts1\": [\"chi so BMI\"], \"texts2\": [\"danh gia can nang\", \"lich tap gym\"]}"
```

## Luong tich hop voi backend

1. Backend nhan query hoac document can index.
2. `backend/src/custom_embedding.py` goi `POST /embed`.
3. Service tra ve vector 1024 chieu.
4. Backend dung vector do de index/search trong Qdrant.

Luu y: `VECTOR_SIZE` ben backend va kich thuoc embedding cua model phai cung la `1024`.

## Loi thuong gap

- `Model not loaded`: kiem tra `MODEL_PATH` co dung va model da duoc download chua.
- `Batch size exceeds limit`: giam so phan tu trong `texts` hoac tang `MAX_BATCH_SIZE`.
- Backend khong ket noi duoc service: kiem tra `CUSTOM_EMBEDDING_API_URL`, port `5001`, va mapping host/container.
- Loi dimension khi index Qdrant: dam bao model dang dung la `bge-m3` va collection duoc tao voi `VECTOR_SIZE=1024`.

## Tai lieu lien quan

- [docs/embed/EMBEDDING_SERVING_DOCUMENTATION.md](../docs/embed/EMBEDDING_SERVING_DOCUMENTATION.md)
- [backend/src/custom_embedding.py](../backend/src/custom_embedding.py)
- [backend/README.md](../backend/README.md)
