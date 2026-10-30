# The dbt runner. Build from the REPOSITORY ROOT so the root .dockerignore applies:
#   docker build -f transform/Dockerfile -t albert-dbt:<tag> .
# Run it with the gcloud login mounted read-only; nothing secret is in the image.

FROM python:3.12.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DBT_PROFILES_DIR=/usr/app \
    DBT_DATASET=l05_julius

WORKDIR /usr/app

# git, because `dbt debug` fails without it even when no package comes from git.
# The Debian version is pinned: if the mirror ever drops it the build fails loudly,
# which is better than quietly installing a different git.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git=1:2.39.5-0+deb12u3 \
    && rm -rf /var/lib/apt/lists/*

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
