"""
Generates a concise, structured summary of the ingested content and
extracts the core topics, using a map-reduce approach so it scales to
documents of any length without blowing past Gemini Flash's context
window or running up token cost by stuffing everything into one call.

Map step:   summarize each chunk individually (cheap, parallelizable).
Reduce step: combine the chunk summaries into one structured brief.
"""

"""
Generates a concise, structured summary of the ingested content and extracts core topics.
"""
import re
from langchain_core.documents import Document as LCDocument
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .llm import get_llm

MAP_PROMPT = ChatPromptTemplate.from_template(
    "Summarize the key facts and ideas in the following excerpt in 3-5 bullet "
    "points. Be factual and specific, no fluff.\n\n---\n{text}\n---"
)

REDUCE_PROMPT = ChatPromptTemplate.from_template(
    "You are a study assistant. Below are bullet-point summaries of "
    "consecutive excerpts from one source document.\n\n{summaries}\n\n"
    "Using ONLY the information above, produce a STRUCTURED study brief in "
    "this exact markdown format:\n\n"
    "## Overview\n"
    "(2-4 sentences giving the big picture of what this document is about)\n\n"
    "## Core Topics\n"
    "- Topic 1\n- Topic 2\n(list 4-8 core topics/themes, short phrases)\n\n"
    "## Key Points\n"
    "- Point 1\n- Point 2\n(6-10 of the most important, concrete takeaways)\n\n"
    "## Important Terms\n"
    "- **Term**: one-line definition\n(list any key terminology/jargon used)\n\n"
    "Keep the whole thing concise and skimmable. Do not invent information "
    "that isn't supported by the summaries above."
)

def _map_reduce_summarize(docs: list[LCDocument]) -> str:
    llm = get_llm(temperature=0.2)
    map_chain = MAP_PROMPT | llm | StrOutputParser()
    
    inputs = [{"text": d.page_content} for d in docs]
    # Enforce sequential execution (max_concurrency=1) so the rate limiter paces calls evenly
    chunk_summaries = map_chain.batch(inputs, config={"max_concurrency": 1})
    
    combined = "\n\n".join(f"Excerpt {i+1} summary:\n{s}" for i, s in enumerate(chunk_summaries))
    reduce_chain = REDUCE_PROMPT | llm | StrOutputParser()
    return reduce_chain.invoke({"summaries": combined})

def generate_summary_and_topics(docs: list[LCDocument]) -> tuple[str, list[str]]:
    summary_markdown = _map_reduce_summarize(docs)
    topics = []
    match = re.search(r"##\s*Core Topics\s*\n((?:- .+\n?)+)", summary_markdown)
    if match:
        topics = [line.strip("- ").strip() for line in match.group(1).strip().splitlines() if line.strip()]
    return summary_markdown, topics