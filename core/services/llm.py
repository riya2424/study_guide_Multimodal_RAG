"""
Central place that builds the Gemini chat model and embedding model used
everywhere else in the app. Keeping this in one file means the whole
project only ever has ONE spot to change if you want to swap models.

Why Gemini *Flash* and not Pro?
--------------------------------
- Flash models are tuned for low latency and high throughput, so chat
  replies and summaries come back in ~1-3 seconds instead of ~10+.
- Flash has a much larger free-tier request quota (requests-per-minute
  and requests-per-day) than Pro, which matters a lot for a learning
  assistant that gets hit with many small calls per session (retrieval
  question + web-search tool call + quiz generation, etc.).
- Flash is priced roughly 10-20x cheaper per token than Pro, so a full
  study session (ingest + summarize + a dozen follow-up questions +
  a quiz) costs a small fraction of a cent.
- Quality-wise, Flash is more than capable for retrieval-augmented Q&A,
  summarization, and quiz generation, since the heavy lifting (finding
  the right context) is done by the retriever, not raw model reasoning.

See GUIDE.md -> "Why Gemini Flash?" for the full explanation and for
how to switch to a different Gemini model if you ever need to.
"""

"""
Central place that builds the Gemini chat model and embedding model used everywhere else in the app.
"""
from functools import lru_cache
from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.rate_limiters import InMemoryRateLimiter

# Cap requests to ~12 RPM (1 request every 5 seconds) to safely stay under the 15 RPM free tier limit.
rate_limiter = InMemoryRateLimiter(
    requests_per_second=0.2,  # 1 request / 5 seconds = 12 requests / minute
    check_every_n_seconds=0.1,
    max_bucket_size=1,
)

def _require_api_key():
    if not settings.GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your "
            "Gemini API key (see GUIDE.md for how to generate one)."
        )

@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.3) -> ChatGoogleGenerativeAI:
    """Returns a cached Gemini Flash chat model instance with strict rate limiting."""
    _require_api_key()
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_CHAT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=temperature,
        max_retries=5,
        rate_limiter=rate_limiter,
        max_output_tokens=2048,
    )

@lru_cache(maxsize=1)
def get_vision_llm() -> ChatGoogleGenerativeAI:
    """Gemini Flash vision model with strict rate limiting."""
    _require_api_key()
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_CHAT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.1,
        max_retries=5,
        rate_limiter=rate_limiter,
        max_output_tokens=2048,
    )

@lru_cache(maxsize=1)
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Cached embeddings client used to build/search the vector store."""
    _require_api_key()
    return GoogleGenerativeAIEmbeddings(
        model=settings.GEMINI_EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
    )