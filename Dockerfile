FROM python:3.12-slim AS base

LABEL maintainer="obscorp"
LABEL description="Rebrand Service — batch document rebranding engine"

RUN groupadd --gid 1000 rebrand && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home rebrand

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

COPY src/ src/
COPY configs/ configs/
COPY templates/ templates/

RUN pip install --no-cache-dir -e .

RUN chown -R rebrand:rebrand /app

USER rebrand

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["uvicorn", "rebrand_service.api:app"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
