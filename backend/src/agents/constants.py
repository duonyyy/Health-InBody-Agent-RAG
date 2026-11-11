"""Constants, agent identifiers, and runtime budget configurations."""

import os

INBODY_AGENT = "InBodyAgent"
RAG_AGENT = "RAGAgent"
NUTRITION_AGENT = "NutritionAgent"
TRAINING_AGENT = "TrainingAgent"
WEB_SEARCH_AGENT = "WebSearchAgent"
GENERAL_CHAT_AGENT = "GeneralChatAgent"
SAFETY_AGENT = "SafetyAgent"
RESPONSE_COMPOSER_AGENT = "ResponseComposerAgent"
SUPERVISOR_AGENT = "SupervisorAgent"
PERSONALIZATION_CONTEXT_AGENT = "PersonalizationContextAgent"

# Public specialist groups. The older names below remain internal capability IDs
# so routing, retrieval filters and tool behavior keep their existing semantics.
LIFESTYLE_AGENT = "LifestyleAgent"
KNOWLEDGE_AGENT = "KnowledgeAgent"
SPECIALIST_BY_CAPABILITY = {
    INBODY_AGENT: INBODY_AGENT,
    NUTRITION_AGENT: LIFESTYLE_AGENT,
    TRAINING_AGENT: LIFESTYLE_AGENT,
    RAG_AGENT: KNOWLEDGE_AGENT,
    WEB_SEARCH_AGENT: KNOWLEDGE_AGENT,
    GENERAL_CHAT_AGENT: KNOWLEDGE_AGENT,
    "PersonalMemoryAgent": KNOWLEDGE_AGENT,
}


def public_specialists(capabilities):
    """Return ordered, unique public specialists for selected capabilities."""
    selected = []
    for capability in capabilities:
        specialist = SPECIALIST_BY_CAPABILITY.get(capability)
        if specialist and specialist not in selected:
            selected.append(specialist)
    return selected

AGENT_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "50")
)
AGENT_COMPOSER_RESERVE_SECONDS = float(
    os.getenv("AGENT_COMPOSER_RESERVE_SECONDS", "15")
)
RAG_EMBEDDING_TIMEOUT_SECONDS = float(
    os.getenv("RAG_EMBEDDING_TIMEOUT_SECONDS", "15")
)
QDRANT_SEARCH_RESERVE_SECONDS = float(
    os.getenv("QDRANT_SEARCH_RESERVE_SECONDS", "5")
)
RAG_MAX_RETRIEVAL_QUERIES = max(
    1,
    int(os.getenv("RAG_MAX_RETRIEVAL_QUERIES", "1")),
)
RAG_COMPOSER_MAX_DOCS = max(
    1,
    int(os.getenv("RAG_COMPOSER_MAX_DOCS", "3")),
)
RAG_COMPOSER_MAX_CHARS_PER_DOC = max(
    200,
    int(os.getenv("RAG_COMPOSER_MAX_CHARS_PER_DOC", "700")),
)
AGENT_MAX_RETRIEVAL_CALLS = max(1, min(3, int(os.getenv("AGENT_MAX_RETRIEVAL_CALLS", "2"))))
AGENT_MAX_COMPOSER_CALLS = max(1, min(2, int(os.getenv("AGENT_MAX_COMPOSER_CALLS", "2"))))
