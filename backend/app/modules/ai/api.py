"""AI domain API routes: agent query endpoints (agents_router) and
chat/capabilities/learning-candidate endpoints (chat_router). Combines
the former api/agents.py and api/chat.py."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.platform.database import get_db
from app.platform.security import get_current_user
from app.platform.security import rate_limit
from app.platform.config import settings
from app.modules.ai.contracts import ChatRequest, ChatResponse
from app.modules.ai.contracts import route_to_agent, get_agents_report, AGENT_DEFINITIONS
from fastapi import APIRouter, Depends, Request
from app.platform.security import get_current_user, require_role
from app.modules.ai.orchestration import ChatService
from app.modules.ai.contracts import get_capabilities_report


# --- api/agents.py ---
agents_router = APIRouter(prefix="/api/agents", tags=["agents"])


@agents_router.get("/")
def list_agents(auth=Depends(get_current_user)):
    """The honest inventory this demands - each agent's real
    scope and capability classification. Open to any authenticated
    user - this describes the system, not business data."""
    return {"agents": get_agents_report()}


@agents_router.post("/{agent_key}/query", response_model=ChatResponse, dependencies=[
    Depends(rate_limit("chat", settings.RATE_LIMIT_CHAT_PER_MINUTE))
])
def query_agent(agent_key: str, data: ChatRequest, db: Session = Depends(get_db),
                 auth=Depends(get_current_user)):
    """Every agent query goes through the identical authorized pipeline
    the chatbot itself uses (see agent_service.route_to_agent's
    docstring for why) - agent_key selects which named agent answered,
    never a different permission or retrieval path. Rate-limited on
    the same basis as /api/chat/, since this is the same expensive
    operation under a different name."""
    if agent_key not in AGENT_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_key}'.")
    response, suggestions, proposed_action, clarification, records = route_to_agent(
        agent_key, data.message, db, user_role=auth.get("role", "user"), context=data.context,
        current_employee_id=auth.get("employee_id"),
    )
    last_entity = None
    if data.context:
        entity_type, entity_id = data.context.resolved_with_reference(data.message)
        if entity_type and entity_id:
            last_entity = {"type": entity_type, "id": entity_id}
    return ChatResponse(response=response, suggestions=suggestions, proposed_action=proposed_action,
                         clarification=clarification, records=records, last_entity=last_entity)


# --- api/chat.py ---
chat_router = APIRouter(prefix="/api/chat", tags=["chat"])


@chat_router.get("/capabilities")
def ai_capabilities(auth=Depends(get_current_user)):
    """An explicit honesty requirement: a plain classification
    of what this AI layer actually does right now (IMPLEMENTED),
    what depends on infrastructure not yet connected
    (EXTERNAL-SERVICE DEPENDENT), and what is not genuinely verified
    to exist (NOT VERIFIED). Open to any authenticated user - this is
    a description of the system, not business data."""
    return {"capabilities": get_capabilities_report()}


@chat_router.post("/", response_model=ChatResponse, dependencies=[
    Depends(rate_limit("chat", settings.RATE_LIMIT_CHAT_PER_MINUTE))
])
def send_message(data: ChatRequest, request: Request, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    response, suggestions, proposed_action, clarification, records = ChatService.process_message(
        data.message, db, user_role=auth.get("role", "user"), context=data.context,
        current_employee_id=auth.get("employee_id"), request=request, auth=auth,
    )
    # Whatever record (if any) this message was actually about - via
    # page context or a resolved deictic reference - carried forward
    # so a follow-up like "usme kya scene hai" can resolve next turn.
    last_entity = None
    if data.context:
        entity_type, entity_id = data.context.resolved_with_reference(data.message)
        if entity_type and entity_id:
            last_entity = {"type": entity_type, "id": entity_id}
    return ChatResponse(response=response, suggestions=suggestions, proposed_action=proposed_action,
                         clarification=clarification, records=records, last_entity=last_entity)


@chat_router.get("/learning-candidates")
def list_learning_candidates(status: str = "pending", db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    """The review queue a master works through.
    Defaults to "pending" (the actionable queue); pass status=approved
    or status=rejected to see history. Never auto-applied - listing
    here is purely informational until an explicit approve call."""
    from app.modules.ai.contracts import ChatLearningCandidate
    candidates = (
        db.query(ChatLearningCandidate)
        .filter(ChatLearningCandidate.status == status)
        .order_by(ChatLearningCandidate.occurrence_count.desc())
        .limit(100).all()
    )
    return {"candidates": [
        {
            "id": c.id, "phrase": c.phrase, "resolved_tool": c.resolved_tool,
            "occurrence_count": c.occurrence_count, "status": c.status,
            "reviewed_by": c.reviewed_by, "review_notes": c.review_notes,
        } for c in candidates
    ]}


@chat_router.post("/learning-candidates/{candidate_id}/approve")
def approve_learning_candidate(candidate_id: int, db: Session = Depends(get_db),
                                auth=Depends(require_role("master"))):
    """The candidate -> approval -> active rule. Approving
    only flips a status column - it never generates, modifies, or
    executes code. See chat_service.py's _check_learned_intent() for
    where an approved row actually gets consulted (a plain database
    lookup, not a rule engine)."""
    from app.modules.ai.contracts import ChatLearningCandidate
    from fastapi import HTTPException
    candidate = db.query(ChatLearningCandidate).filter(ChatLearningCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Learning candidate not found")
    candidate.status = "approved"
    candidate.reviewed_by = auth.get("email") or str(auth.get("user_id"))
    db.commit()
    return {"id": candidate.id, "status": candidate.status}


@chat_router.post("/learning-candidates/{candidate_id}/reject")
def reject_learning_candidate(candidate_id: int, db: Session = Depends(get_db),
                               auth=Depends(require_role("master"))):
    """The reversal path required ("reversible") - a
    rejected or previously-approved candidate can be set back to
    rejected at any time, immediately stopping
    _check_learned_intent() from matching it again."""
    from app.modules.ai.contracts import ChatLearningCandidate
    from fastapi import HTTPException
    candidate = db.query(ChatLearningCandidate).filter(ChatLearningCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Learning candidate not found")
    candidate.status = "rejected"
    candidate.reviewed_by = auth.get("email") or str(auth.get("user_id"))
    db.commit()
    return {"id": candidate.id, "status": candidate.status}
