from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.rate_limit import rate_limit
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agent_service import route_to_agent, get_agents_report, AGENT_DEFINITIONS

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/")
def list_agents(auth=Depends(get_current_user)):
    """The honest inventory Family 15 demands - each agent's real
    scope and capability classification. Open to any authenticated
    user - this describes the system, not business data."""
    return {"agents": get_agents_report()}


@router.post("/{agent_key}/query", response_model=ChatResponse, dependencies=[
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
