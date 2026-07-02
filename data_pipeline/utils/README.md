# Pipeline Utils

Thu muc nay danh cho script xu ly du lieu, vi du:

- Extract text tu PDF sang `dataset/processed/extracted_text/`.
- Normalize `foods.csv` va `ratings.csv`.
- Convert document thanh JSONL dung chung cho backend indexing.
- Validate metadata bat buoc: `doc_id`, `source`, `content_type`, `domain`, `language`.

Quy uoc an toan: script khong ghi de file trong `dataset/raw/`.

## Gop Raw Thanh Mot File

Chay lenh sau tu thu muc goc project:

```bash
python data_pipeline/utils/merge_raw_sources.py
```

Output:

- `data_pipeline/dataset/processed/all_raw_sources.jsonl`
- `data_pipeline/dataset/processed/merge_report.json`

Luu y: CSV va JSON duoc convert thanh record JSONL. PDF hien duoc ghi thanh placeholder cho den khi co buoc extract text.

## Chuan Bi Dataset De Embedding

```bash
python data_pipeline/utils/build_embedding_dataset.py
```

Output:

- `data_pipeline/dataset/processed/embedding_documents.jsonl`
- `data_pipeline/dataset/processed/embedding_report.json`
- `data_pipeline/dataset/processed/embedding_build_report.json`
- `data_pipeline/dataset/rag_documents/health_inbody_corpus.jsonl`
- `data_pipeline/dataset/processed/foods_normalized.csv`
- `data_pipeline/dataset/processed/ratings_normalized.csv`

Dataset embedding se bo qua `ratings` va cac PDF placeholder chua extract text, sau do them mot so tai lieu noi bo ve InBody, dinh duong, tap luyen va an toan y te. Ratings duoc tach rieng cho Collaborative Filtering, khong dua vao vector database.

Neu `pypdf` da duoc cai, `build_embedding_dataset.py` se extract text tu PDF vao `dataset/processed/extracted_text/` truoc khi merge sources.

## Index MVP Dataset Vao Backend/Qdrant

Khi `backend` va `qdrant-db` da chay:

```bash
python data_pipeline/utils/index_mvp_dataset.py --batch-size 50
```

Test nhanh voi it document truoc:

```bash
python data_pipeline/utils/index_mvp_dataset.py --limit 20 --batch-size 10
```
