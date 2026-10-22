"""FastAPI application: error format, request IDs, CORS and routers.

Layout: core/ shared infrastructure, api/<feature>_router.py thin HTTP routers,
services/<feature>_service.py business rules, jobs/<name>_worker.py background
workers, scripts/ manual seeds.
"""

import logging
import os
import uuid

from fastapi import APIRouter, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api import alerts_router, auth_router, bins_router
from .core.db import get_database
from .core.errors import CODES


log = logging.getLogger("smartwaste.api")

app = FastAPI(title="Smart Waste API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = (
        request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
    )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def error_response(request, status_code, code, message, details=None):
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", None),
            "details": details or {},
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    code = getattr(exc, "code", None) or CODES.get(exc.status_code, "ERROR")
    return error_response(
        request, exc.status_code, code, str(exc.detail), getattr(exc, "details", None)
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
        for error in jsonable_encoder(exc.errors())
    ]
    return error_response(request, 422, "VALIDATION", "Dữ liệu không hợp lệ", {"errors": errors})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(request, 500, "INTERNAL", "Lỗi máy chủ")


api = APIRouter(prefix="/api/v1")


@api.get("/health")
def health():
    try:
        get_database().command("ping")
    except PyMongoError:
        return JSONResponse(status_code=503, content={"status": "degraded", "mongo": "down"})
    return {"status": "ok", "mongo": "ok"}


api.include_router(auth_router.router)
api.include_router(bins_router.router)
api.include_router(alerts_router.router)
app.include_router(api)
