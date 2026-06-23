FROM python:3.11-slim
USER root
WORKDIR /root/

# git
RUN apt-get update && apt-get install -y git \
    && rm -rf /var/lib/apt/lists/*

# uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_NO_DEV=1
RUN uv sync

ARG githash
ENV GITHASH=$githash

ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./


# Run app
CMD gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
CMD ["sh", "-c", "uv run gunicorn --bind :${PORT:-8080} --workers 1 --threads 8 --timeout 0 main:app"]
