# Technical Decision Document (TDD): Migrating from Flask to FastAPI

**Date:** October 2023
**Status:** Proposed
**Audience:** Engineering Leadership, DevOps, and Backend Developers

---

## 1. Executive Summary
This document outlines the strategic migration of our backend services from Flask (WSGI) to FastAPI (ASGI). The goal is to modernize our infrastructure to support higher concurrency, reduce memory-related crashes, and automate API documentation and data validation.

---

## 2. Core Architecture: WSGI vs. ASGI

To understand why we are migrating, we must look at how the server handles traffic.

### 2.1 WSGI (Web Server Gateway Interface) - *The Flask Model*
*   **Synchronous:** WSGI handles requests one by one per thread. 
*   **The "Waiter" Analogy:** Imagine a restaurant with 10 waiters (threads). If a waiter takes an order and the kitchen takes 5 minutes to cook, that waiter stands still at the kitchen window for 5 minutes. They cannot serve any other customers until the food is ready.
*   **The Bottleneck:** Our current `-w 2 --threads 10` setup means we can only handle **20 simultaneous "waits."** If the 21st user arrives, they must wait for a thread to become free.

### 2.2 ASGI (Asynchronous Server Gateway Interface) - *The FastAPI Model*
*   **Asynchronous:** Built on Python's `asyncio`. It uses an **Event Loop**.
*   **The "Efficient Waiter" Analogy:** In an ASGI restaurant, the waiter takes an order, hands it to the kitchen, and **immediately** goes to serve another table while the food cooks. When the kitchen "pings" the waiter, they return to the first table.
*   **The Advantage:** A single FastAPI worker can handle **thousands** of concurrent connections because it never sits idle while waiting for a database or an external API to respond.

---

## 3. Comparison of Frameworks

| Feature | Flask (WSGI) | FastAPI (ASGI) |
| :--- | :--- | :--- |
| **Concurrency** | One request per thread | Hundreds of requests per worker |
| **Data Validation** | Manual (Risk of `KeyError`) | Automatic (via Pydantic) |
| **Documentation** | Manual / Third-party | Native / Automatic (OpenAPI) |
| **Performance** | Medium | High (Comparable to Go/Node.js) |
| **Development** | Faster to start, harder to scale | Slower initial setup, easier to maintain |

---

## 4. Technical Advantages

### 4.1 Native Data Validation (Pydantic)
In Flask, we manually parse `request.json`. In FastAPI, we define a **Schema**. 
*   **The Benefit:** FastAPI validates data types **before** the code runs. If a client sends a string where an integer is expected, FastAPI automatically rejects it with a clear error message, preventing application crashes.

### 4.2 Auto-Generated Interactive Documentation
FastAPI automatically generates an interactive **Swagger UI** at `/docs`.
*   **The Benefit:** We no longer need to manually update Postman collections or Wiki pages. Stakeholders and Frontend developers can test API endpoints directly in the browser with real-time documentation.

---

## 5. Proposed Infrastructure (Production Grade)

We will transition from a standard Uvicorn execution to a Gunicorn-managed process. This provides the "Process Management" of Gunicorn with the "Async Speed" of Uvicorn.

**Target Command:**
```bash
gunicorn src.apis.main:fapis_application \
  --bind 0.0.0.0:8000 \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 2 \
  --timeout 300 \
  --keepalive 2 \
  --max-requests 1000 \
  --max-requests-jitter 50 \
  --keyfile /tmp/server.key \
  --certfile /tmp/server.crt \
  --access-logfile - \
  --error-logfile -
