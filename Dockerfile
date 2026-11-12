FROM python:3.11-slim
ARG INSTALL_SEMANTIC=false
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONPATH=/app
WORKDIR /app
COPY pyproject.toml requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.lock
COPY triage ./triage
RUN pip install --no-deps . && \
    if [ "$INSTALL_SEMANTIC" = "true" ]; then pip install --no-cache-dir 'sentence-transformers>=3.4,<6'; fi && \
    useradd --create-home --uid 10001 app && mkdir -p /app/data /app/output /tmp/triage-metrics && chown -R app:app /app /tmp/triage-metrics
COPY --chown=app:app prompts ./prompts
COPY --chown=app:app corpus ./corpus
COPY --chown=app:app web ./web
COPY --chown=app:app evaluation ./evaluation
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app tests ./tests
COPY --chown=app:app loadtests ./loadtests
ENTRYPOINT ["python", "scripts/container_entrypoint.py"]
CMD ["uvicorn", "triage.api:app", "--host", "0.0.0.0", "--port", "8000"]
