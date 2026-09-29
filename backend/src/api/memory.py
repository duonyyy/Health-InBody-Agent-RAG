"""Authenticated conversation and confirmed memory lifecycle."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from auth.context import CurrentUser, get_current_user
from api.personalization import _execute, _require_trusted_memory_identity
from memory import store, sync

router = APIRouter(prefix="/me", tags=["memory"])


class FactProposal(BaseModel):
    message_id: UUID
    kind: Literal["response_preference", "dietary_preference", "exercise_preference"]
    text: str = Field(min_length=3, max_length=240)


@router.post("/conversations", status_code=201)
def create_conversation(user: CurrentUser = Depends(get_current_user)):
    return _execute(store.open_conversation, user.subject)


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: UUID, user: CurrentUser = Depends(get_current_user)):
    return {"conversation_id": str(conversation_id), "messages": _execute(store.load_history, user.subject, str(conversation_id))}


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: UUID, user: CurrentUser = Depends(get_current_user)):
    _execute(store.delete_conversation, user.subject, str(conversation_id))
    return Response(status_code=204)


@router.get("/memory/facts")
def facts(user: CurrentUser = Depends(get_current_user)):
    return _execute(store.list_facts, user.subject)


@router.post("/memory/facts", status_code=201)
def propose(data: FactProposal, user: CurrentUser = Depends(get_current_user)):
    return _execute(store.propose_fact, user.subject, str(data.message_id), data.kind, data.text)


@router.post("/memory/facts/{fact_id}/confirm")
def confirm(fact_id: UUID, user: CurrentUser = Depends(get_current_user)):
    return _execute(store.confirm_fact, user.subject, str(fact_id))


@router.delete("/memory/facts/{fact_id}", status_code=204)
def delete_fact(fact_id: UUID, user: CurrentUser = Depends(get_current_user)):
    _execute(store.delete_fact, user.subject, str(fact_id))
    return Response(status_code=204)


@router.post("/memory/sync")
def synchronize(user: CurrentUser = Depends(get_current_user)):
    _require_trusted_memory_identity(user)
    return _execute(sync.sync_confirmed, user.subject)
