# The dbt runner. Build from the REPOSITORY ROOT so the root .dockerignore applies:
#   docker build -f transform/Dockerfile -t albert-dbt:<tag> .
# Run it with the gcloud login mounted read-only; nothing secret is in the image.

FROM python:3.12.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DBT_PROFILES_DIR=/usr/app \
    DBT_DATASET=l05_julius

WORKDIR /usr/app

COPY transform/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock \
    && useradd --create-home --uid 10001 dbt \
    && chown dbt /usr/app

COPY --chown=dbt transform/ ./

USER dbt
# Installs the packages the lock file pins, into the image, so a run needs no
# network for them.
RUN dbt deps

# The image IS dbt; arguments are the subcommand. The default builds everything.
ENTRYPOINT ["dbt"]
CMD ["build"]
