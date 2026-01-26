import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import costs, exports, tags

app = FastAPI(title="Unified Cost Center")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("API_KEY")


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    if not API_KEY or request.url.path == "/health":
        return await call_next(request)
    if request.headers.get("x-api-key") != API_KEY:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


app.include_router(costs.router)
app.include_router(tags.router)
app.include_router(exports.router)
