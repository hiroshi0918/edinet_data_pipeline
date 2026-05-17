FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY src ./src

# editable install: src/ への編集が再ビルド無しで反映される
# (compose.yml で `.:/app` が mount されている前提)
RUN pip install --upgrade pip && pip install -e .[dev,viz]

CMD ["bash"]
