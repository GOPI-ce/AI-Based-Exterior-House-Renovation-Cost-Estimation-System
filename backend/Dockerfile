# FacadeAI API: Docker image for a free Hugging Face Space (CPU basic, port 7860).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/user/.cache/huggingface \
    DATABASE_URL=sqlite:////home/user/app/data/facade.db

# Hugging Face Spaces run containers as user 1000; it must own the app folder (SQLite lives in ./data).
RUN useradd -m -u 1000 user \
 && mkdir -p /home/user/app/data \
 && chown -R user:user /home/user/app
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements.txt

USER user

# Bake the SAM 2.1 weights into the image so a cold start never waits for a download.
RUN python -c "from transformers import Sam2Model, Sam2Processor; \
m='facebook/sam2.1-hiera-tiny'; Sam2Processor.from_pretrained(m); Sam2Model.from_pretrained(m)"

COPY --chown=user app ./app
COPY --chown=user scripts ./scripts

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips", "*"]
