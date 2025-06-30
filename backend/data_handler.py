import sqlite3
import pandas as pd
from pathlib import Path
from PyPDF2 import PdfReader
from docx2txt import process  # Changed from python-docx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from backend.config import QDRANT_API_KEY, QDRANT_URL
import uuid
import re


class DataHandler:
    def __init__(self):
        self.conn = sqlite3.connect("data.db", check_same_thread=False)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.qdrant = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY
        )

    def save_structured(self, file_path: Path, file_id: str):
        if file_path.suffix == ".csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        df.to_sql(file_id, self.conn, if_exists="replace", index=False)

    def process_unstructured(self, file_path: Path, file_id: str):
        text = self._extract_text(file_path)
        chunks = self._chunk_text(text)
        embeddings = self.embedding_model.encode(chunks)
        
        self.qdrant.recreate_collection(
            collection_name=file_id,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding.tolist(),
                payload={"text": chunk}
            ) for chunk, embedding in zip(chunks, embeddings)
        ]
        self.qdrant.upload_points(file_id, points)

    def _extract_text(self, file_path: Path) -> str:
        if file_path.suffix == ".pdf":
            with open(file_path, "rb") as f:
                return "\n".join([page.extract_text() for page in PdfReader(f).pages])
        elif file_path.suffix == ".docx":
            try:
                return process(file_path)  # Using docx2txt instead of python-docx
            except Exception as e:
                raise ValueError(f"Failed to process DOCX file: {str(e)}")
        else:
            raise ValueError("Unsupported file type")

    def _chunk_text(self, text: str) -> list:
        return [text[i:i+512] for i in range(0, len(text), 512)]

    def get_sql_result(self, file_id: str, sql: str) -> list:
    # Replace any table name in SQL with the quoted file_id
        pattern = r'FROM\s+(\w+[-\w]*)'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            original_table = match.group(1)
            quoted_file_id = f'"{file_id}"'  # Quotes handle hyphens
            sql = sql.replace(original_table, quoted_file_id)

        return pd.read_sql(sql, self.conn).to_dict(orient="records")


    def semantic_search(self, query: str, file_id: str):
        embedding = self.embedding_model.encode(query).tolist()
        return [
            hit.payload["text"] 
            for hit in self.qdrant.search(
                collection_name=file_id,
                query_vector=embedding,
                limit=3
            )
        ]
