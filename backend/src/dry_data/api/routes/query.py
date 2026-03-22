"""Natural language query route."""

from fastapi import APIRouter, Depends, HTTPException

from dry_data.api.dependencies import get_query_service
from dry_data.exceptions import LLMError, QueryError, WarehouseError
from dry_data.models.api import QueryRequest, QueryResponse
from dry_data.services.query_service import QueryService

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    service: QueryService = Depends(get_query_service),
) -> QueryResponse:
    """Translate a natural language question into SQL, run it, and narrate.

    Raises:
        400: If the generated SQL is unsafe or fails to execute.
        502: If the LLM API is unavailable.
        500: If an unexpected warehouse error occurs.
    """
    try:
        return await service.answer_question(request.question)
    except QueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except WarehouseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
