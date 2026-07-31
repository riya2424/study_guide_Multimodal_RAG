# Guide: API Keys, Model Choice, Architecture & Troubleshooting

## 1. Getting a Gemini API key

1. Go to **Google AI Studio**: https://aistudio.google.com/apikey
   (sign in with any Google account).
2. Click **"Create API key"**.
3. Choose **"Create API key in new project"** if you don't already have
   a Google Cloud project you want to use — this is the fastest path
   and works fine for the free tier used by this project.
4. Copy the generated key (it looks like `AIzaSy...`).
5. In the project folder, copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
6. Open `.env` and paste your key:
   ```
   GOOGLE_API_KEY=AIzaSy...your-real-key...
   ```
7. Save the file. **Never commit `.env` to version control** —
   `.gitignore` already excludes it.

### Checking your quota / usage
Google AI Studio shows your current rate limits and usage under
**"Usage & billing"** in the left sidebar of https://aistudio.google.com.
The free tier is generous for development and personal use (see
section 2 below for specifics on Flash vs Pro).

### If you see a 403 / API key errors
- Double check there are no extra spaces or quote marks around the key
  in `.env`.
- Make sure the **Generative Language API** is enabled for the project
  the key belongs to (Google AI Studio normally does this
  automatically when you create a key).
- Regenerate the key from AI Studio if you suspect it was revoked.

---

## 2. Why Gemini *Flash*, and how to change the model

This project defaults to `gemini-2.5-flash` (set in `.env` as
`GEMINI_CHAT_MODEL`). Here's the reasoning, so you can make an informed
choice if you want to change it:

**Speed.** Flash models are distilled/optimized specifically for low
latency. In a chat-style learning assistant, the user is waiting on
screen for each answer — a multi-second wait per message feels
sluggish. Flash typically returns short-to-medium answers in a couple
of seconds; Pro-tier models are noticeably slower.

**Free-tier quota.** Google's free tier gives Flash models a much
higher requests-per-minute and requests-per-day allowance than Pro
models. This matters a lot here because a single user "turn" in this
app can cost 2–4 API calls under the hood (e.g. a chat question that
triggers the `search_document` tool, then a follow-up model call to
compose the final answer, and possibly a `search_web` call) — on top
of the calls made during ingestion (one call per chunk during
summarization, one per quiz). Flash's headroom means you're unlikely
to hit the free-tier ceiling during normal use; Pro's much lower daily
cap can get used up quickly.

**Cost.** Flash is priced roughly an order of magnitude lower per
token than Pro. Even paid usage of this app (ingesting a large PDF,
asking a dozen questions, taking a quiz) costs a small fraction of a
cent.

**Quality is sufficient here.** The hardest part of this app's job —
finding the *right* passage to answer a question — is done by the
retriever (Chroma similarity search over embeddings), not by the LLM's
raw reasoning. Flash is more than capable of turning "here are the
relevant passages" into a clear, well-structured answer, a summary, or
a quiz question.

### When would you want Pro instead?
If you're working with very long, information-dense documents where
answers require multi-step reasoning across several retrieved chunks
(e.g. legal contracts, dense academic papers), a Pro-tier model may
give more careful synthesis at the cost of speed and quota headroom.
To switch:

```
# in .env
GEMINI_CHAT_MODEL=gemini-2.5-pro
```

No code changes needed — `core/services/llm.py` reads this value from
settings.

### Keeping the model name current
Google renames/retires Gemini models periodically (Flash "2.0" models,
for example, were retired mid-2026). If you get a 404 model-not-found
error, check the current model list at
https://ai.google.dev/gemini-api/docs/models and update
`GEMINI_CHAT_MODEL` in `.env` — you do not need to touch any Python
code.

---

## 3. Architecture walkthrough

```
Upload (PDF/image)
        │
        ▼
core/services/ingestion.py
  - PDF  → PyPDFLoader (text per page)
  - Image → Gemini Flash vision call, transcribes text +
            describes diagrams/photos
        │
        ▼  (RecursiveCharacterTextSplitter → chunks)
core/services/vectorstore.py
  - Chroma vector store, one persisted collection per document
  - Embeddings via Gemini's text-embedding-004 model
        │
        ├──────────────────────────────┐
        ▼                              ▼
core/services/summarizer.py     core/services/agent.py
  - map: summarize each chunk     - LangChain create_agent
  - reduce: structured brief        (Gemini Flash + tools)
    (Overview / Core Topics /     - tool 1: search_document
     Key Points / Terms)            (searches the Chroma store)
                                   - tool 2: search_web
                                     (DuckDuckGo, free, no API key)
                                   - memory: loads/saves every turn
                                     via core/services/memory.py
                                     (Django ChatMessage table)
        │                              │
        ▼                              ▼
   Document.summary/.topics      Chat UI (core/templates/core/chat.html)
   → summary.html                 fetch()'s core/views.py::chat_api

                              core/services/quiz.py
                                - structured-output MCQ generator
                                - drawn from the same Chroma store
```

### Why memory is implemented as a plain Django table (not LangGraph's checkpointer)
LangChain's current agent API (`create_agent`, from `langchain.agents`)
is built on LangGraph and supports a `thread_id`-based checkpointer for
short-term memory. This project instead manages history explicitly: 
`DjangoChatMessageHistory` (in `core/services/memory.py`) loads every
prior message for a session from the `ChatMessage` table, and
`core/services/agent.py::ask()` passes that full history to the agent
as part of the input, then writes the new question/answer back to the
same table. This keeps the persistence mechanism transparent, durable
across server restarts, easy to inspect (`python manage.py shell` or
the Django admin), and easy to extend (e.g. exporting a transcript) —
without introducing a second, separate storage layer to keep in sync.

### Why LangChain's `create_agent` (not `AgentExecutor`)
Many older LangChain tutorials use
`create_tool_calling_agent()` + `AgentExecutor`. Both are now
deprecated in favor of `create_agent`, which is built on LangGraph and
is the API LangChain currently recommends for new projects. This
project uses `create_agent` throughout so you're not starting on a
legacy pattern.

---

## 4. Running the pieces individually (debugging)

You can exercise each service from a Django shell without going
through the web UI — useful when isolating a problem:

```bash
python manage.py shell
```

```python
from core.services.ingestion import load_and_split
from core.services.vectorstore import build_vectorstore
from core.services.summarizer import generate_summary_and_topics

docs = load_and_split("/path/to/file.pdf", "pdf")
build_vectorstore("debug_collection", docs)
summary, topics = generate_summary_and_topics(docs)
print(summary)
print(topics)
```

```python
from core.services.agent import ask
# session_id must be a real ChatSession UUID that already exists
print(ask("debug_collection", "<session-uuid>", "What is this document about?"))
```

---

## 5. Troubleshooting

**"GOOGLE_API_KEY is not set" error**
`.env` wasn't created, or Django wasn't restarted after editing it.
Confirm `.env` sits next to `manage.py` and re-run `python manage.py
runserver`.

**"No extractable text was found in the uploaded file"**
This fires when a PDF has no selectable text (e.g. a pure image scan
saved as PDF). Try re-uploading it with content type **Image** instead
— the Gemini vision path will OCR/transcribe it.

**Chat answers ignore the document**
Check that the document's `status` is `ready` (visible on the
summary page) — the chat route only becomes available once ingestion
finishes. If ingestion `failed`, check `document.error_message` (also
shown in the Django admin).

**DuckDuckGo search tool returns nothing / errors**
`duckduckgo-search` occasionally rate-limits aggressive querying from
one IP. It doesn't need an API key, so there's nothing to configure —
if it becomes unreliable for you, swap in a keyed provider (e.g.
Tavily) inside `core/services/agent.py::build_agent_for_document`.

**Large PDFs take a long time to upload**
Ingestion (chunking → embedding → per-chunk summarization) is
synchronous and scales with document length. See "Scaling further"
below.

**"Model not found" / 404 from the Gemini API**
Google occasionally retires older Gemini model names. Update
`GEMINI_CHAT_MODEL` in `.env` to a currently-supported model — see
section 2 above.

---

## 6. Scaling further (optional, beyond local use)

- **Background processing**: move `_process_document()` in
  `core/views.py` into a Celery/RQ/Django-Q task; have the upload view
  return immediately and poll `document.status` from the frontend
  (e.g. via a small JS interval hitting a `status` JSON endpoint).
- **Multiple chat sessions per document**: the data model already
  supports many `ChatSession`s per `Document` (`ChatSession.document`
  is a normal foreign key) — the current UI just auto-creates/reuses
  one session per document for simplicity. Add a "new chat" button
  that creates another `ChatSession` to support parallel conversations.
- **Swapping the vector store**: `core/services/vectorstore.py` is the
  only file that talks to Chroma — swap in Pinecone/pgvector/etc.
  there without touching the rest of the app.
- **Auth / multi-user**: add Django's built-in auth, and scope
  `Document.objects` queries by `request.user` in `views.py`.
