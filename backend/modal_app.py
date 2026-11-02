"""Serverless deployment on Modal (https://modal.com): the same Docker image as the Hugging Face Space.

    cd backend && modal deploy modal_app.py

The container starts on the first request and stops after SCALEDOWN_S idle seconds, so the free monthly
compute allowance covers normal use; the web app shows a "waking up" notice during a cold start.
Configuration comes from the Modal secret `facade-api` (GEMINI_API_KEY, DATABASE_URL, CORS_ORIGINS,
CORS_ORIGIN_REGEX). Use a Postgres DATABASE_URL: the container's disk does not survive a restart.
"""

import modal

SCALEDOWN_S = 600

image = (
    modal.Image.from_dockerfile("Dockerfile", context_dir=".")
    .dockerfile_commands(["USER root"])
    # Modal's proxy adds the caller's IP to X-Forwarded-For; rate limits must use it, not the proxy's.
    .env({"TRUSTED_PROXY_HOPS": "1"})
)
app = modal.App("facade-ai", image=image)


@app.function(
    cpu=2.0,
    memory=4096,
    timeout=300,
    scaledown_window=SCALEDOWN_S,
    max_containers=1,  # rate limits and loaded models live in memory: one container serves everyone
    secrets=[modal.Secret.from_name("facade-api")],
)
@modal.concurrent(max_inputs=16)
@modal.asgi_app(label="facade-ai-api")
def api():
    import os
    import sys

    os.chdir("/home/user/app")
    sys.path.insert(0, "/home/user/app")
    from app.main import app as fastapi_app

    return fastapi_app
