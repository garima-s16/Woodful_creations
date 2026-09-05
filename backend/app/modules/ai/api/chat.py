from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.platform.security.rate_limit import rate_limit
from app.platform.configuration.config import settings
from app.modules.ai.schemas import ChatRequest, ChatResponse
from app.modules.ai.orchestration import ChatService
from app.modules.ai.security import get_capabilities_report

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/capabilities")
def ai_capabilities(auth=Depends(get_current_user)):
    """An explicit honesty requirement: a plain classification
    of what this AI layer actually does right now (IMPLEMENTED),
    what depends on infrastructure not yet connected
    (EXTERNAL-SERVICE DEPENDENT), and what is not genuinely verified
    to exist (NOT VERIFIED). Open to any authenticated user - this is
    a description of the system, not business data."""
    return {"capabilities": get_capabilities_report()}


@router.post("/", response_model=ChatResponse, dependencies=[
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


@router.get("/learning-candidates")
def list_learning_candidates(status: str = "pending", db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    """The review queue a master works through.
    Defaults to "pending" (the actionable queue); pass status=approved
    or status=rejected to see history. Never auto-applied - listing
    here is purely informational until an explicit approve call."""
    from app.modules.ai.models import ChatLearningCandidate
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


@router.post("/learning-candidates/{candidate_id}/approve")
def approve_learning_candidate(candidate_id: int, db: Session = Depends(get_db),
                                auth=Depends(require_role("master"))):
    """The candidate -> approval -> active rule. Approving
    only flips a status column - it never generates, modifies, or
    executes code. See chat_service.py's _check_learned_intent() for
    where an approved row actually gets consulted (a plain database
    lookup, not a rule engine)."""
    from app.modules.ai.models import ChatLearningCandidate
    from fastapi import HTTPException
    candidate = db.query(ChatLearningCandidate).filter(ChatLearningCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Learning candidate not found")
    candidate.status = "approved"
    candidate.reviewed_by = auth.get("email") or str(auth.get("user_id"))
    db.commit()
    return {"id": candidate.id, "status": candidate.status}


@router.post("/learning-candidates/{candidate_id}/reject")
def reject_learning_candidate(candidate_id: int, db: Session = Depends(get_db),
                               auth=Depends(require_role("master"))):
    """The reversal path required ("reversible") - a
    rejected or previously-approved candidate can be set back to
    rejected at any time, immediately stopping
    _check_learned_intent() from matching it again."""
    from app.modules.ai.models import ChatLearningCandidate
    from fastapi import HTTPException
    candidate = db.query(ChatLearningCandidate).filter(ChatLearningCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Learning candidate not found")
    candidate.status = "rejected"
    candidate.reviewed_by = auth.get("email") or str(auth.get("user_id"))
    db.commit()
    return {"id": candidate.id, "status": candidate.status}
