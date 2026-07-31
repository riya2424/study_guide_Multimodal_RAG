"""
Self-assessment: turns the ingested document into a short multiple-choice
quiz so the user can test what they've retained. Uses Gemini Flash's
structured-output support (JSON schema) so we get back reliably
parseable data instead of having to regex-scrape free text.
"""

import json

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .llm import get_llm
from .vectorstore import load_vectorstore


class QuizQuestion(BaseModel):
    question: str = Field(description="The quiz question text")
    options: list[str] = Field(description="Exactly 4 answer options")
    answer_index: int = Field(description="Index (0-3) of the correct option")
    explanation: str = Field(description="One sentence explaining why the answer is correct")


class Quiz(BaseModel):
    questions: list[QuizQuestion]


QUIZ_PROMPT = ChatPromptTemplate.from_template(
    "Based ONLY on the following study material, write {num_questions} "
    "multiple-choice self-assessment questions that test real understanding "
    "(not trivial recall of exact wording). Each question must have exactly "
    "4 options with only one correct answer.\n\n"
    "STUDY MATERIAL:\n{context}\n"
)


def generate_quiz(collection_name: str, num_questions: int = 5) -> list[dict]:
    vectorstore = load_vectorstore(collection_name)
    # Pull a broad sample of the document's content to draw questions from.
    docs = vectorstore.similarity_search("summary overview key concepts", k=8)
    context = "\n\n".join(d.page_content for d in docs)

    llm = get_llm(temperature=0.4)
    structured_llm = llm.with_structured_output(Quiz)
    chain = QUIZ_PROMPT | structured_llm

    quiz: Quiz = chain.invoke({"context": context, "num_questions": num_questions})
    return json.loads(quiz.model_dump_json())["questions"]
