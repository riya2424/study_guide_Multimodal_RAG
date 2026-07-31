"""
Builds the actual "personal learning assistant" agent used by the chat
interface.

This uses LangChain's current `create_agent` factory (the supported,
non-deprecated agent API as of LangChain 1.x — it replaces the older
`create_tool_calling_agent` + `AgentExecutor` pattern seen in most
pre-2026 tutorials, which is now deprecated in favor of this
LangGraph-backed implementation).

Two tools are exposed to the agent:

  1. `search_document` - retrieves relevant chunks from the uploaded
                          document's vector store (grounds answers in
                          what the user actually uploaded).
  2. `search_web`      - a free DuckDuckGo search tool used when the
                          user wants to go beyond the document itself
                          and explore how a topic is discussed more
                          broadly on the web ("knowledge expansion").

Memory: `create_agent` normally persists short-term memory via a
LangGraph checkpointer keyed by a thread_id, but that only stores
history in memory/sqlite outside of Django's data model. To satisfy
requirement #2 ("memory retention for all previous questions") in a
way that's simple, transparent, and durable across server restarts,
this project instead manages history explicitly: every prior
human/AI turn is loaded from the ChatMessage table (via
DjangoChatMessageHistory), passed to the agent as part of the
`messages` input, and the new turn is written straight back to the
database once the agent responds. No hidden state, no extra moving
parts — just the Django database as the single source of truth.
"""

from langchain.agents import create_agent
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool

from .llm import get_llm
from .vectorstore import get_retriever
from .memory import DjangoChatMessageHistory

SYSTEM_PROMPT = """\
You are an upbeat, precise personal learning assistant helping a student \
understand a document they uploaded (a PDF or an image that was transcribed \
to text).

Behavior rules:
- For questions about the uploaded content, ALWAYS use the `search_document` \
tool first and ground your answer in what it returns. Quote or paraphrase \
faithfully; do not invent facts that aren't supported by the retrieved text.
- If the user asks to go deeper, explore related ideas, get real-world \
examples, or understand how a topic is discussed more broadly, use the \
`search_web` tool to expand beyond the document, and clearly say which parts \
of your answer come from the document vs. from the web.
- If a question is unrelated to the document and doesn't need document \
context, you may answer directly from general knowledge or use `search_web`.
- Keep answers clear and structured (short paragraphs or bullet points). \
Use the conversation history to avoid repeating yourself and to build on \
earlier answers - the student may refer back to something they asked before.
- If you're unsure or the document doesn't cover something, say so plainly \
instead of guessing.
"""


def _make_document_search_tool(collection_name: str):
    retriever = get_retriever(collection_name)

    @tool
    def search_document(query: str) -> str:
        """Search the uploaded document for passages relevant to the query.
        Always use this first for any question about the document's content."""
        docs = retriever.invoke(query)
        if not docs:
            return "No relevant passages were found in the document."
        return "\n\n---\n\n".join(d.page_content for d in docs)

    return search_document


def build_agent_for_document(collection_name: str):
    tools = [
        _make_document_search_tool(collection_name),
        DuckDuckGoSearchRun(
            name="search_web",
            description=(
                "Search the public web for background, related concepts, or "
                "real-world examples that go beyond the uploaded document. "
                "Use this for 'explore further' or 'how does this apply in "
                "general' style questions."
            ),
        ),
    ]
    llm = get_llm(temperature=0.3)
    return create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)


def ask(collection_name: str, session_id: str, question: str) -> str:
    """
    Runs one turn of the conversation: loads the full prior history for this
    session from the database, asks the agent the new question with that
    history as context, then persists both the question and answer.
    """
    history = DjangoChatMessageHistory(session_id)
    agent = build_agent_for_document(collection_name)
    
    messages = history.messages + [HumanMessage(content=question)]
    result = agent.invoke({"messages": messages})
    final_message = result["messages"][-1]
    
    # --- FIX: Properly extract text from structured Gemini responses ---
    if isinstance(final_message.content, str):
        answer = final_message.content
    elif isinstance(final_message.content, list):
        # Join text from the list of dictionaries returned by the Gemini API
        answer = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in final_message.content
        )
    else:
        answer = str(final_message.content)
    # -------------------------------------------------------------------
    
    history.add_message(HumanMessage(content=question))
    history.add_message(AIMessage(content=answer))
    
    return answer
