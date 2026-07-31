import json
import logging

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .forms import UploadForm
from .models import Document, ChatSession, QuizAttempt
from .services.ingestion import load_and_split
from .services.vectorstore import build_vectorstore
from .services.summarizer import generate_summary_and_topics
from .services.agent import ask
from .services.quiz import generate_quiz

logger = logging.getLogger(__name__)


def home(request):
    documents = Document.objects.order_by("-created_at")[:20]
    return render(request, "core/home.html", {"documents": documents})


def upload_view(request):
    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data["file"]
            content_type = form.cleaned_data["content_type"]

            document = Document.objects.create(
                file=uploaded_file,
                original_name=uploaded_file.name,
                content_type=content_type,
                status="processing",
            )
            document.vectorstore_collection = f"doc_{document.id.hex}"
            document.save(update_fields=["vectorstore_collection"])

            try:
                _process_document(document)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to process document %s", document.id)
                document.status = "failed"
                document.error_message = str(exc)
                document.save(update_fields=["status", "error_message"])
                messages.error(request, f"Could not process file: {exc}")
                return redirect("home")

            return redirect("document_detail", doc_id=document.id)
    else:
        form = UploadForm()

    return render(request, "core/upload.html", {"form": form})


def _process_document(document: Document):
    """
    Synchronous ingestion pipeline: extract -> chunk -> embed -> summarize.
    Kept synchronous for simplicity/local use; for production, move this
    into a background task (e.g. Celery/RQ) and poll `document.status`
    from the frontend instead. See GUIDE.md -> "Scaling further".
    """
    docs = load_and_split(document.file.path, document.content_type)
    build_vectorstore(document.vectorstore_collection, docs)

    summary_markdown, topics = generate_summary_and_topics(docs)
    document.summary = summary_markdown
    document.topics = ", ".join(topics)
    document.status = "ready"
    document.save(update_fields=["summary", "topics", "status"])


def document_detail(request, doc_id):
    document = get_object_or_404(Document, id=doc_id)
    topics = [t.strip() for t in document.topics.split(",") if t.strip()]
    return render(request, "core/summary.html", {"document": document, "topics": topics})


def chat_view(request, doc_id):
    document = get_object_or_404(Document, id=doc_id, status="ready")
    session, _ = ChatSession.objects.get_or_create(
        document=document, defaults={"title": f"Chat about {document.original_name}"}
    )
    history = session.messages.all()
    return render(
        request,
        "core/chat.html",
        {"document": document, "session": session, "history": history},
    )


@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request, doc_id, session_id):
    document = get_object_or_404(Document, id=doc_id, status="ready")
    get_object_or_404(ChatSession, id=session_id, document=document)

    try:
        payload = json.loads(request.body.decode("utf-8"))
        question = payload.get("question", "").strip()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not question:
        return JsonResponse({"error": "Question cannot be empty"}, status=400)

    try:
        answer = ask(document.vectorstore_collection, str(session_id), question)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent call failed for session %s", session_id)
        return JsonResponse({"error": f"The assistant hit an error: {exc}"}, status=500)

    return JsonResponse({"answer": answer})


def quiz_view(request, doc_id):
    document = get_object_or_404(Document, id=doc_id, status="ready")

    if request.method == "POST":
        quiz_id = request.POST.get("quiz_id")
        attempt = get_object_or_404(QuizAttempt, id=quiz_id, document=document)
        questions = json.loads(attempt.questions_json)

        selected = []
        score = 0
        for i, q in enumerate(questions):
            chosen = request.POST.get(f"q{i}")
            chosen_idx = int(chosen) if chosen is not None else -1
            selected.append(chosen_idx)
            if chosen_idx == q["answer_index"]:
                score += 1

        attempt.answers_json = json.dumps(selected)
        attempt.score = score
        attempt.total = len(questions)
        attempt.save(update_fields=["answers_json", "score", "total"])

        results = []
        for i, q in enumerate(questions):
            option_rows = []
            for idx, option in enumerate(q["options"]):
                option_rows.append(
                    {
                        "text": option,
                        "is_correct": idx == q["answer_index"],
                        "is_selected": idx == selected[i],
                    }
                )
            results.append(
                {
                    "question": q["question"],
                    "explanation": q["explanation"],
                    "options": option_rows,
                }
            )

        return render(
            request,
            "core/quiz.html",
            {
                "document": document,
                "attempt": attempt,
                "results": results,
                "graded": True,
            },
        )

    # GET: generate a fresh quiz
    num_questions = int(request.GET.get("n", 5))
    try:
        questions = generate_quiz(document.vectorstore_collection, num_questions)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Quiz generation failed for document %s", doc_id)
        messages.error(request, f"Could not generate quiz: {exc}")
        return redirect("document_detail", doc_id=doc_id)

    attempt = QuizAttempt.objects.create(
        document=document,
        questions_json=json.dumps(questions),
        total=len(questions),
    )
    return render(
        request,
        "core/quiz.html",
        {"document": document, "attempt": attempt, "questions": questions, "graded": False},
    )
