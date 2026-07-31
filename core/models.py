import uuid

from django.db import models


class Document(models.Model):
    """A single uploaded PDF or image, plus everything the agent derived from it."""

    CONTENT_TYPES = [
        ("pdf", "PDF"),
        ("image", "Image"),
    ]

    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to="uploads/")
    original_name = models.CharField(max_length=512)
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="uploaded")
    error_message = models.TextField(blank=True, default="")

    # Structured summary produced by the summarizer service (markdown text)
    summary = models.TextField(blank=True, default="")
    # Comma separated list of core topics extracted from the content
    topics = models.TextField(blank=True, default="")

    # Name of the per-document Chroma collection
    vectorstore_collection = models.CharField(max_length=64, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.original_name} ({self.status})"


class ChatSession(models.Model):
    """One learning conversation, always tied to a source document."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="sessions")
    title = models.CharField(max_length=255, blank=True, default="New chat")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session {self.id} on {self.document.original_name}"


class ChatMessage(models.Model):
    """
    Persisted turn of the conversation. This is what gives the agent
    long-term memory: every question/answer pair is stored here and
    reloaded into LangChain's memory object on every request, so the
    agent remembers the full history of a session even across page
    reloads or server restarts.
    """

    ROLE_CHOICES = [
        ("human", "Human"),
        ("ai", "AI"),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}"


class QuizAttempt(models.Model):
    """A self-assessment quiz generated for a document, and the user's score."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="quizzes")
    questions_json = models.TextField()  # JSON: list of {question, options, answer_index, explanation}
    answers_json = models.TextField(blank=True, default="")  # JSON: list of selected indices
    score = models.IntegerField(null=True, blank=True)
    total = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quiz for {self.document.original_name} ({self.score}/{self.total})"
