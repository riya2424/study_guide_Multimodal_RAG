"""
Persistent memory backend.

Requirement #2 asks for "memory retention for all the previous questions
asked". A plain in-memory buffer would forget everything the moment the
Django worker process restarts (or if a different worker handles the
next request). To make memory genuinely durable, every human/AI turn is
written straight to the ChatMessage table (see core/models.py) and
reloaded from the database on every request through this class, which
implements LangChain's BaseChatMessageHistory interface.

`services/agent.py` reads `.messages` before calling the agent (so the
full prior conversation is passed in as context) and calls
`.add_message(...)` after the agent responds (so the new question and
answer are saved). That's it — no separate checkpointer or cache to keep
in sync, just the Django database as the single source of truth.
"""

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage

from core.models import ChatSession, ChatMessage


class DjangoChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id: str):
        self.session_id = session_id

    @property
    def messages(self) -> list[BaseMessage]:
        session = ChatSession.objects.get(id=self.session_id)
        history = []
        for msg in session.messages.all():
            if msg.role == "human":
                history.append(HumanMessage(content=msg.content))
            else:
                history.append(AIMessage(content=msg.content))
        return history

    def add_message(self, message: BaseMessage) -> None:
        session = ChatSession.objects.get(id=self.session_id)
        role = "human" if isinstance(message, HumanMessage) else "ai"
        ChatMessage.objects.create(session=session, role=role, content=message.content)

    def clear(self) -> None:
        ChatMessage.objects.filter(session_id=self.session_id).delete()
