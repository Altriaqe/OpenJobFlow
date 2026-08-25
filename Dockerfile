FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLCONFIGDIR=/tmp/jobflow-matplotlib

WORKDIR /app

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_DEFAULT_TIMEOUT=120
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

RUN apt-get update \
    && apt-get install --yes --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system jobflow \
    && adduser --system --ingroup jobflow jobflow \
    && mkdir -p "${MPLCONFIGDIR}" \
    && chown jobflow:jobflow "${MPLCONFIGDIR}"

COPY pyproject.toml README.md ./
COPY src ./src

RUN HTTP_PROXY="${HTTP_PROXY}" \
    HTTPS_PROXY="${HTTPS_PROXY}" \
    NO_PROXY="${NO_PROXY}" \
    pip install \
    --no-cache-dir \
    --index-url "${PIP_INDEX_URL}" \
    --default-timeout "${PIP_DEFAULT_TIMEOUT}" \
    .

USER jobflow

CMD ["uvicorn", "jobflow.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
