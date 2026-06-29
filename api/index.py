from fastapi import FastAPI, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
import time

app = FastAPI()

TOTAL_ORDERS = 46
RATE_LIMIT = 17
WINDOW = 10

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# In-memory stores
# ------------------------------

idempotency_store = {}

rate_buckets = {}

# ------------------------------
# Rate limiting middleware
# ------------------------------

@app.middleware("http")
async def rate_limit(request: Request, call_next):

    client = request.headers.get("X-Client-Id", "anonymous")

    now = time.time()

    if client not in rate_buckets:
        rate_buckets[client] = []

    rate_buckets[client] = [
        t for t in rate_buckets[client]
        if now - t < WINDOW
    ]

    if len(rate_buckets[client]) >= RATE_LIMIT:

        retry = int(WINDOW - (now - rate_buckets[client][0])) + 1

        response = JSONResponse(
            status_code=429,
            content={"detail":"Too Many Requests"}
        )

        response.headers["Retry-After"] = str(retry)

        return response

    rate_buckets[client].append(now)

    return await call_next(request)

# ------------------------------
# Root
# ------------------------------

@app.get("/")
def root():
    return {"status":"ok"}

# ------------------------------
# Idempotent POST
# ------------------------------

@app.post("/orders", status_code=201)
def create_order(idempotency_key: str = Header(..., alias="Idempotency-Key")):

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4())
    }

    idempotency_store[idempotency_key] = order

    return order

# ------------------------------
# Pagination
# ------------------------------

@app.get("/orders")
def list_orders(limit: int = 10, cursor: str | None = None):

    start = int(cursor) if cursor else 1

    end = min(start + limit - 1, TOTAL_ORDERS)

    items = [
        {"id": i}
        for i in range(start, end + 1)
    ]

    next_cursor = None

    if end < TOTAL_ORDERS:
        next_cursor = str(end + 1)

    return {
        "items": items,
        "next_cursor": next_cursor
    }
