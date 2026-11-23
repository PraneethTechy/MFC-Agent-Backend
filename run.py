"""
Production runner for Manufacturing Cost Agent FastAPI backend.
Binds to 0.0.0.0 and reads platform-assigned PORT environment variable (e.g., Render, Railway, AWS ECS).
"""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting Manufacturing Cost Agent Backend on {host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
