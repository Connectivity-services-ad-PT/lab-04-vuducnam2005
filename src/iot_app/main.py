import os
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


SERVICE_NAME = os.getenv("SERVICE_NAME", "access-gate-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")


app = FastAPI(
    title="Smart Campus Access Gate Service",
    version=SERVICE_VERSION,
    description=(
        "Dockerized Lab 04 Access Gate service. Core and Analytics are "
        "collaboration boundaries verified through shared events."
    ),
)


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int = Field(..., ge=400, le=599)
    detail: Optional[str] = None
    instance: Optional[str] = None


class HealthStatus(BaseModel):
    status: str
    service: str
    time: str


class IoTEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deviceId: str
    metric: Optional[str] = None
    value: Optional[float] = None
    timestamp: datetime


class CameraEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eventType: str
    cameraId: str
    detectionId: Optional[UUID] = None
    confidenceScore: Optional[float] = None
    severity: Optional[str] = Field(default=None, pattern="^(LOW|MEDIUM|HIGH)$")
    imageRef: Optional[str] = None
    timestamp: datetime
    correlationId: UUID


class BusinessEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eventType: str
    sourceModule: Optional[str] = None
    decisionId: UUID
    policyId: Optional[str] = None
    subjectId: Optional[str] = None
    result: Optional[str] = Field(default=None, pattern="^(ALLOW|DENY|REVIEW|ESCALATE)$")
    severity: Optional[str] = Field(default=None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    riskScore: Optional[float] = Field(default=None, ge=0, le=100)
    analyticsRequired: Optional[bool] = None
    notificationRequired: Optional[bool] = None
    reason: Optional[str] = None
    timestamp: datetime
    correlationId: UUID


class AccessEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eventType: str
    gateId: str
    direction: str = Field(..., pattern="^(IN|OUT)$")
    cardIdHash: Optional[str] = None
    decision: Optional[str] = Field(default=None, pattern="^(ALLOW|DENY)$")
    timestamp: datetime
    correlationId: UUID


class AnalyticsResult(BaseModel):
    analyticsId: UUID
    resultType: str
    sourceService: str
    severity: Optional[str] = None
    confidenceScore: Optional[float] = None
    description: Optional[str] = None
    generatedAt: str
    correlationId: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None


class AnalyticsPage(BaseModel):
    items: List[AnalyticsResult]
    total: int
    page: int
    pageSize: int


EVENTS: List[Dict[str, Any]] = []
RESULTS: Dict[str, AnalyticsResult] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    problem_type: str = "about:blank",
) -> Dict[str, Any]:
    problem = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        problem["instance"] = instance
    return problem


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        problem = exc.detail
    else:
        problem = build_problem(
            status_code=exc.status_code,
            title=HTTPStatus(exc.status_code).phrase,
            detail=str(exc.detail),
            instance=str(request.url.path),
        )

    problem.setdefault("type", "about:blank")
    problem.setdefault("title", HTTPStatus(exc.status_code).phrase)
    problem.setdefault("status", exc.status_code)
    problem.setdefault("detail", "Request failed")
    problem.setdefault("instance", str(request.url.path))

    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(item) for item in first_error.get("loc", []))
    message = first_error.get("msg", "Request validation error")
    detail = f"{location}: {message}" if location else message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Unprocessable Entity",
            detail=detail,
            instance=str(request.url.path),
            problem_type="https://smart-campus.local/problems/validation-error",
        ),
        media_type="application/problem+json",
    )


def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Missing Authorization header",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )

    expected = f"Bearer {AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Invalid bearer token",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )


def persist_event(source_service: str, payload: BaseModel) -> None:
    event = payload.model_dump(mode="json")
    correlation_id = event.get("correlationId")
    event_type = event.get("eventType", source_service)

    duplicate = any(
        item.get("correlationId") == correlation_id and item.get("eventType") == event_type
        for item in EVENTS
    )
    if correlation_id and duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_problem(
                status_code=status.HTTP_409_CONFLICT,
                title="Conflict",
                detail="Duplicate event correlationId for this eventType",
                problem_type="https://smart-campus.local/problems/duplicate-event",
            ),
        )

    EVENTS.append({"sourceService": source_service, **event, "receivedAt": now_iso()})

    result = AnalyticsResult(
        analyticsId=uuid4(),
        resultType=event_type.upper().replace(".", "_"),
        sourceService=source_service,
        severity=event.get("severity") or ("HIGH" if event.get("decision") == "DENY" else "LOW"),
        confidenceScore=0.9,
        description=f"Analytics generated from {event_type}",
        generatedAt=now_iso(),
        correlationId=correlation_id,
        metadata=event,
    )
    RESULTS[str(result.analyticsId)] = result


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok", service=SERVICE_NAME, time=now_iso())


@app.post(
    "/analytics/iot-events",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
)
def ingest_iot_event(payload: IoTEvent, response: Response) -> Response:
    persist_event("iot-ingestion", payload)
    response.status_code = status.HTTP_201_CREATED
    return response


@app.post(
    "/analytics/camera-events",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
)
def ingest_camera_event(payload: CameraEvent, response: Response) -> Response:
    persist_event("camera-service", payload)
    response.status_code = status.HTTP_201_CREATED
    return response


@app.post(
    "/analytics/business-events",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
)
def ingest_business_event(payload: BusinessEvent, response: Response) -> Response:
    persist_event("core-business", payload)
    response.status_code = status.HTTP_201_CREATED
    return response


@app.post(
    "/analytics/access-events",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
)
def ingest_access_event(payload: AccessEvent, response: Response) -> Response:
    persist_event("access-gate", payload)
    response.status_code = status.HTTP_201_CREATED
    return response


@app.get(
    "/analytics/report/{id}",
    response_model=AnalyticsResult,
    dependencies=[Depends(verify_bearer_token)],
)
def get_analytics_report(id: str) -> AnalyticsResult:
    result = RESULTS.get(id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_problem(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Not Found",
                detail=f"Analytics report {id} does not exist",
                instance=f"/analytics/report/{id}",
                problem_type="https://smart-campus.local/problems/not-found",
            ),
        )
    return result


@app.get(
    "/analytics/events",
    response_model=AnalyticsPage,
    dependencies=[Depends(verify_bearer_token)],
)
def list_analytics_events() -> AnalyticsPage:
    items = list(RESULTS.values())
    return AnalyticsPage(items=items, total=len(items), page=1, pageSize=max(len(items), 10))


@app.get("/analytics/kpi", dependencies=[Depends(verify_bearer_token)])
def get_kpi_statistics() -> List[Dict[str, Any]]:
    access_events = [event for event in EVENTS if event["sourceService"] == "access-gate"]
    deny_count = sum(1 for event in access_events if event.get("decision") == "DENY")
    deny_rate = (deny_count / len(access_events) * 100) if access_events else 0

    return [
        {
            "kpiId": str(uuid4()),
            "metricName": "access-deny-rate",
            "value": round(deny_rate, 2),
            "unit": "percentage",
            "trend": "STABLE",
            "calculatedAt": now_iso(),
            "description": "Gate denied access events divided by total gate events.",
        }
    ]


@app.get("/analytics/dashboard", dependencies=[Depends(verify_bearer_token)])
def get_dashboard_metrics() -> List[Dict[str, Any]]:
    return [
        {
            "metricName": "access-events",
            "currentValue": len([event for event in EVENTS if event["sourceService"] == "access-gate"]),
            "trend": "STABLE",
            "updatedAt": now_iso(),
        },
        {
            "metricName": "core-business-events",
            "currentValue": len([event for event in EVENTS if event["sourceService"] == "core-business"]),
            "trend": "STABLE",
            "updatedAt": now_iso(),
        },
    ]
