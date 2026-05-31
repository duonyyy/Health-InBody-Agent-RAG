# Data Pipeline

Thu muc nay gom cac tai nguyen phuc vu viec chuan bi du lieu cho Health/InBody Agent RAG: du lieu goc, du lieu da xu ly, tai lieu RAG, benchmark va script tien xu ly.

## Cau Truc

```text
data_pipeline/
├── README.md
├── configs/                  # Cau hinh pipeline, mapping schema, source config
├── dataset/
│   ├── README.md
│   ├── raw/                  # Du lieu goc, khong sua truc tiep
│   ├── processed/            # Ket qua lam sach/chuan hoa
│   ├── rag_documents/        # JSONL da san sang cho RAG
│   ├── inbody_samples/       # Mau OCR/parser bao cao InBody
│   └── benchmark/            # Cau hoi va expected context de danh gia
├── utils/                    # Script xu ly, extract, validate, convert
└── logs/                     # Log chay pipeline, ingest report tam thoi
```

## Nguyen Tac

- `dataset/raw/` chi luu ban goc cua du lieu. Khong sua truc tiep file trong thu muc nay.
- Moi ket qua lam sach, parse PDF, extract text hoac normalize cot nen ghi sang `dataset/processed/`.
- Tai lieu dung de index vao Qdrant nen nam trong `dataset/rag_documents/` va theo format JSONL cua du an.
- Script trong `utils/` nen doc tu `raw/` hoac `processed/`, sau do ghi output moi thay vi ghi de file nguon.
- Benchmark tach rieng de co the danh gia retriever, reranker va LLM ma khong tron voi corpus chinh.

## Lenh Chuan Bi Embedding

Chay tu thu muc goc project:

```bash
python data_pipeline/utils/build_embedding_dataset.py
```

Output quan trong:

- `dataset/processed/embedding_documents.jsonl`: file dua vao API `/documents/index`.
- `dataset/rag_documents/health_inbody_corpus.jsonl`: corpus RAG chinh de doi chieu.
- `dataset/processed/foods_normalized.csv`: bang mon an da chuan hoa.
- `dataset/processed/ratings_normalized.csv`: ratings da loc ID loi, dung cho Collaborative Filtering.
