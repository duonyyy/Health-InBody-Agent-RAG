# Data Pipeline

Thu muc nay gom cac tai nguyen phuc vu viec chuan bi du lieu cho Health/InBody Multi-Agent RAG MVP: du lieu goc, du lieu da xu ly, corpus RAG, du lieu recommender tach rieng va script tien xu ly.

## Cau Truc

```text
data_pipeline/
├── README.md
├── configs/                  # Cau hinh pipeline, mapping schema, source config
├── dataset/
│   ├── README.md
│   ├── raw/                  # Du lieu goc, khong sua truc tiep
│   ├── processed/            # Ket qua lam sach/chuan hoa
│   └── rag_documents/        # JSONL da san sang cho RAG
├── utils/                    # Script xu ly, extract, validate, convert
└── logs/                     # Tao khi can log chay pipeline/ingest report
```

## Nguyen Tac

- `dataset/raw/` chi luu ban goc cua du lieu. Khong sua truc tiep file trong thu muc nay.
- Moi ket qua lam sach, parse PDF, extract text hoac normalize cot nen ghi sang `dataset/processed/`.
- Tai lieu dung de index vao Qdrant nen nam trong `dataset/rag_documents/` va theo format JSONL cua du an.
- Script trong `utils/` nen doc tu `raw/` hoac `processed/`, sau do ghi output moi thay vi ghi de file nguon.
- `foods_normalized.csv` va `ratings_normalized.csv` phuc vu recommender/experiments, khong dua truc tiep vao vector database.
- Benchmark va InBody OCR samples hien la roadmap; chua co thu muc chinh thuc trong MVP hien tai.

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

## Trang Thai Corpus Hien Tai

Lan build gan nhat tao `5345` documents RAG:

- `4918` nutrition documents.
- `407` exercise documents.
- `15` InBody metric seed documents.
- `4` medical safety seed documents.
- `1` general health seed document.

Seed documents InBody/safety hien la curated knowledge de bo sung cac chu de kho tim dataset cong khai tot: BMI, PBF, SMM, BFM, visceral fat, BIA limitations va red flags. Metadata cua cac seed docs co `source_name` va `source_url` de backend/RAG co the hien thi nguon khi can.

Tat ca documents trong `embedding_documents.jsonl` co `domain=health_inbody` va collection mac dinh la `nmk_chatbot_collection`.
