"""
Content ingestion for the two supported upload types: PDF and image.

- PDFs are parsed with LangChain's PyPDFLoader (text extraction per page).
- Images are handled by sending the raw image bytes straight to Gemini
  Flash's multimodal endpoint and asking it to transcribe/describe the
  page. This avoids needing a separate OCR engine (e.g. Tesseract)
  installed on the host machine, and Gemini Flash is both fast and
  accurate enough for this at very low cost.

Both paths return a list of LangChain `Document` objects (the
`langchain_core.documents.Document` schema — unrelated to our Django
`Document` model of the same name) ready to be split and embedded.
"""

"""
Content ingestion for PDF and image uploads.
"""
import base64
import mimetypes
from langchain_core.documents import Document as LCDocument
from langchain_core.messages import HumanMessage
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .llm import get_vision_llm

IMAGE_TRANSCRIBE_PROMPT = (
    "You are an OCR and content-understanding engine. Carefully read every "
    "piece of visible text in this image (handwriting, printed text, labels, "
    "captions, diagrams, tables, equations). Transcribe all text verbatim, "
    "and where the image contains a diagram/chart/photo rather than plain "
    "text, add a short factual description of what it depicts. "
    "Output plain text only, preserving structure (headings, bullet points, "
    "table rows) as best you can. Do not summarize or omit content."
)

def load_pdf(file_path: str) -> list[LCDocument]:
    loader = PyPDFLoader(file_path)
    return loader.load()

def load_image(file_path: str) -> list[LCDocument]:
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "image/png"
    with open(file_path, "rb") as f:
        image_bytes = f.read()
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    message = HumanMessage(
        content=[
            {"type": "text", "text": IMAGE_TRANSCRIBE_PROMPT},
            {"type": "image_url", "image_url": f"data:{mime_type};base64,{b64_image}"},
        ]
    )
    response = get_vision_llm().invoke([message])
    extracted_text = response.content if isinstance(response.content, str) else str(response.content)
    return [LCDocument(page_content=extracted_text, metadata={"source": file_path, "page": 0})]

def load_and_split(file_path: str, content_type: str) -> list[LCDocument]:
    if content_type == "pdf":
        raw_docs = load_pdf(file_path)
    elif content_type == "image":
        raw_docs = load_image(file_path)
    else:
        raise ValueError(f"Unsupported content_type: {content_type}")

    if not any(d.page_content.strip() for d in raw_docs):
        raise ValueError(
            "No extractable text was found in the uploaded file. If this is a "
            "scanned/handwritten PDF, try uploading it as an image instead."
        )

    # Increased chunk size to 2500 to keep chunk counts low and respect API quotas
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2500,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(raw_docs)
