"""IT ticket endpoints; lifecycle decisions are delegated to domain services."""

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from mcp_rag_agent.api.dependencies import get_config, get_it_ticket_service
from mcp_rag_agent.api.schemas.it_tickets import (
    TicketCreate,
    TicketOperationResult,
    TicketPatch,
    TicketRecord,
)
from mcp_rag_agent.api.services.it_ticket_service import ITTicketAPIService
from mcp_rag_agent.core.config import Config
from mcp_rag_agent.it_support.tickets.service import InvalidTicketTransitionError
from mcp_rag_agent.it_support.tickets.store import TicketNotFoundError

router = APIRouter(prefix="/it/tickets", tags=["IT Tickets"])


def _ensure_enabled(cfg: Config) -> None:
    if not cfg.ff_it_support:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IT support capability is disabled.",
        )


@router.post(
    "", response_model=TicketOperationResult, status_code=status.HTTP_201_CREATED
)
async def create_ticket(
    payload: TicketCreate,
    response: Response,
    service: ITTicketAPIService = Depends(get_it_ticket_service),
    cfg: Config = Depends(get_config),
) -> TicketOperationResult:
    _ensure_enabled(cfg)
    result = service.create(payload)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/{ticket_id}", response_model=TicketRecord)
async def get_ticket(
    ticket_id: str = Path(...),
    service: ITTicketAPIService = Depends(get_it_ticket_service),
    cfg: Config = Depends(get_config),
) -> TicketRecord:
    _ensure_enabled(cfg)
    try:
        return service.get(ticket_id)
    except TicketNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found.",
        )


@router.patch("/{ticket_id}", response_model=TicketRecord)
async def patch_ticket(
    ticket_id: str,
    payload: TicketPatch,
    service: ITTicketAPIService = Depends(get_it_ticket_service),
    cfg: Config = Depends(get_config),
) -> TicketRecord:
    _ensure_enabled(cfg)
    try:
        return service.patch(ticket_id, payload)
    except TicketNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found.",
        )
    except InvalidTicketTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
