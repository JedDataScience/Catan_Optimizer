# Container for the FastAPI backend, built and run by Render (see render.yaml
# at the repo root). Also works locally:
#   docker build -t catan-backend backend
#   docker run --rm -p 8000:8000 catan-backend

FROM python:3.12-slim

# uv, copied in from its official image (pinned to the version used locally)
COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /uvx /bin/

# Run as an ordinary user rather than root, so a bug in the app can't
# change anything outside its own folder
RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app

# Install dependencies first, in their own layer, so code-only changes
# rebuild fast. --frozen: use uv.lock exactly; --no-dev: skip pytest etc.
# (the calibration and benchmark groups aren't installed by default either)
COPY --chown=user pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Only what the API needs at runtime: the app modules, plus the calibration
# summary that /scoring-info reads (tests, calibration code, benchmarks stay out)
COPY --chown=user *.py ./
COPY --chown=user calibration/summary.json calibration/summary.json

# Use the environment uv built, without going through uv at runtime.
# CORS_ORIGINS isn't set here: Render sets it (render.yaml), and locally the
# app's default allows the Vite dev server.
ENV PATH="/home/user/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Render tells the app which port to listen on through $PORT (10000 there);
# fall back to 8000, the port the frontend expects locally. The shell form
# (sh -c) is needed so ${PORT} gets filled in; exec hands the process over to
# uvicorn so it receives Render's shutdown signal directly.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
