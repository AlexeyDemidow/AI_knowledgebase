from pypdf import PdfReader
from docx import Document as DocxDocument

from sentence_transformers import SentenceTransformer


def extract_text(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text

    if file_path.endswith(".docx"):
        doc = DocxDocument(file_path)
        return "\n".join(p.text for p in doc.paragraphs)

    if file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    raise ValueError("Unsupported file format")


def split_text(text, chunk_size=800):
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunks.append(text[i:i+chunk_size])
    return chunks


model = SentenceTransformer("all-MiniLM-L6-v2")

def create_embedding(text):
    return model.encode(text).tolist()
