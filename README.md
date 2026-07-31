# Study Desk — an AI Learning Agent (LangChain + Gemini Flash + Django)

Study Desk turns any PDF or image into a full learning session:

1. **Ingest** — upload a PDF or an image (photo, scan, screenshot). The
   agent extracts the content (PDF text extraction, or Gemini Flash
   vision for images — no separate OCR engine needed) and builds a
   searchable knowledge base from it.
2. **Understand** — a structured, concise summary is generated
   (overview, core topics, key points, important terms).
3. **Explore** — a chat interface lets you ask follow-up questions.
   The agent answers from the document when it can, and can search the
   open web when you want to go beyond it. It remembers the **entire**
   conversation history for the session.
4. **Self-assess** — generate a short multiple-choice quiz from the
   document to test what you've retained, and get instant, explained
   grading.

Built with **LangChain** (current `create_agent` API) running on
**Gemini Flash**, with a **Django** web interface.

---

## Features at a glance

| Requirement | How it's implemented |
|---|---|
| Accept PDF & image uploads | `core/forms.py` + `core/views.py::upload_view` |
| Extract meaningful content | `core/services/ingestion.py` (PyPDFLoader for PDFs, Gemini vision transcription for images) |
| Structured, concise summary | `core/services/summarizer.py` (map-reduce summarization) |
| Core topic understanding | Topics parsed from the summary + a `search_web` tool for topic expansion |
| Personal learning assistant / chatbot | `core/services/agent.py` (LangChain tool-calling agent, `create_agent`) |
| Memory of all previous questions | `core/services/memory.py` (`DjangoChatMessageHistory`, backed by the `ChatMessage` DB table) |
| Django interface | `core/templates/core/*.html` + `core/views.py` |
| Gemini Flash as the model | `core/services/llm.py` |
| Self-assessment | `core/services/quiz.py` + `core/templates/core/quiz.html` |

See **GUIDE.md** for the full architecture explanation, the API key
setup walkthrough, and the reasoning behind the Gemini Flash model
choice.

---

## Folder structure

```
learning_agent/            Django project settings/urls
core/                      The app
  models.py                 Document, ChatSession, ChatMessage, QuizAttempt
  forms.py                  Upload form
  views.py                  All page + API views
  urls.py                   App routes
  admin.py                  Django admin registration
  services/
    llm.py                  Gemini Flash chat/embeddings factory
    ingestion.py             PDF/image -> LangChain Documents
    vectorstore.py           Chroma vector store per document
    summarizer.py            Map-reduce structured summary + topics
    memory.py                Django-backed persistent chat memory
    agent.py                 The LangChain agent (retrieval + web search tools)
    quiz.py                  Structured-output quiz generator
  templates/core/            HTML templates (Study Desk theme)
  static/core/                CSS
manage.py
requirements.txt
.env.example                 Copy to .env and fill in your Gemini API key
README.md                    This file
GUIDE.md                     API key setup + architecture + troubleshooting
```

---

## Quickstart (local)

### 1. Prerequisites
- Python 3.11 or 3.12
- A Gemini API key (free) — see **GUIDE.md → "Getting a Gemini API key"** if you don't have one yet

### 2. Set up a virtual environment and install dependencies

```bash
# from the project root (the folder containing manage.py)
python3 -m venv venv

# macOS / Linux
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set:

```
GOOGLE_API_KEY=your-gemini-api-key-here
```

(Everything else in `.env` already has sensible defaults for local use.)

### 4. Set up the database

```bash
python manage.py migrate
```

### 5. (Optional) create an admin user, to browse uploads/chats/quizzes at `/admin/`

```bash
python manage.py createsuperuser
```

### 6. Run the server

```bash
python manage.py runserver
```

### 7. Open the app

Go to **http://127.0.0.1:8000/** in your browser, click **Upload
content**, choose PDF or Image, pick a file, and go.

---

## A note on how ingestion runs

Processing (extraction → embedding → summarization) happens
synchronously inside the upload request for simplicity — appropriate
for local/single-user use. If you plan to put this in front of real
users or large files, move `_process_document()` in `core/views.py`
into a background task (Celery, RQ, or Django-Q) and poll
`document.status` from the frontend instead. See **GUIDE.md → "Scaling
further"**.

## License / usage

This is a starter project generated for your use — adapt it freely.
