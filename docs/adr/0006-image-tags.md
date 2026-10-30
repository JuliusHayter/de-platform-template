# ADR-0006: Tag images with the date and the commit; Docker Hub; keep three tags

- **Status:** accepted
- **Date:** 2026-10-30
- **Author:** Julius Hayter
- **Lesson:** L06

## Context

Two jobs are images now: the ingestion jobs (`ingestion/Dockerfile`) and the dbt
runner (`transform/Dockerfile`). Lesson 7 will run them on a schedule, and it can
only do that safely if a tag names one build. A tag that can point at two
different builds on two days makes
[`docs/reproduce.md`](../reproduce.md) impossible.

Sizes as pushed (compressed, from Docker Hub): ingestion 153 MB, dbt 311 MB.

## Options considered

**What goes in a tag**

| Option | For | Against |
|---|---|---|
| `latest` | Nothing to choose | Means a different build tomorrow; rejected outright |
| Date only (`2026-10-30`) | Sorts, readable | Two builds in a day collide; says nothing about which code |
| Git short SHA only | Names the exact code | Does not sort; nothing says how old it is |
| Semantic version | Meaningful to a consumer | Needs a release process a two-job pipeline does not have |
| **Date and short SHA** (`2026-10-30-5ed84e8`) | Sorts by age and names the commit | Longer; the SHA is the commit that built it, not the latest one in the repository |

**Which registry**

| Option | For | Against |
|---|---|---|
| **Docker Hub** | Free; pulling needs no login; no setup | Public: anyone can read the code and the dbt project in the images. Tags can be re-pushed |
| Artifact Registry | Private; in the same project as the data | $0.100 per GiB-month above a free 0.5 GiB; needs a repository and permissions my account may not have |

## Decision

Tags are `<date>-<short sha of the commit the image was built from>`. No image is
tagged `latest`, and none ever will be. Registry: **Docker Hub**
(`julius24h/albert-ingestion`, `julius24h/albert-dbt`).

What it costs me: the images are public. I checked that they hold no secret (a fake
`.env` next to the code did not get in, and the dbt image only holds
`profiles.yml`, which reads the project and dataset from the environment), but the
source of the jobs and the whole dbt project are readable by anyone. The price of
privacy would have been about $0.09 a month on Artifact Registry (three tags of
each image is 1.4 GiB, of which 0.9 is billed), which is small enough that the
free price mattered less than I assumed. I chose Docker Hub because pulling needs
no credential on a new machine, which is what the reproduction tests.

A tag is a name, not a promise: Docker Hub lets anyone with access push a different
image to an existing tag. The digest is the promise, which is why the
reproduction compares digests and not tags.

## Rolling back

Find the tag you want and run it, by tag or by digest:

```bash
# what exists
curl -s "https://hub.docker.com/v2/repositories/julius24h/albert-dbt/tags?page_size=25" \
  | python3 -c 'import json,sys; [print(t["name"], t["digest"][:19]) for t in json.load(sys.stdin)["results"]]'

# run the previous build (nothing is rebuilt)
docker pull julius24h/albert-dbt:2026-10-30-5ed84e8
docker run --rm -v ~/.config/gcloud:/home/dbt/.config/gcloud:ro -e GCP_PROJECT_ID \
  julius24h/albert-dbt:2026-10-30-5ed84e8 build

# or by digest, which cannot move
docker run ... julius24h/albert-dbt@sha256:02fb8f4ff8b6a1ae9d5ab7d444f68713a2a1dc6b386a6d2f8957b5fa4aeec560 build

# rebuild from the commit in the tag, if the image is gone
git checkout 5ed84e8
docker build -f transform/Dockerfile -t albert-dbt:2026-10-30-5ed84e8 .
```

The last route rebuilds the same files but not necessarily the same bytes: the base
image is pinned by tag (`python:3.12.12-slim-bookworm`), not by digest.

## Retention policy

Per image, on Docker Hub:

1. **Keep the three newest tags.** Three is the current build, the one before it
   for a rollback, and one more.
2. **Delete a tag when a later one supersedes it because of a defect found in it.**
3. **Delete any tag that does not match `<date>-<7 hex>`**: a stray `test` or
   `latest` is a tag nobody can name a build by.

It is enforced by [`scripts/prune_dockerhub.sh`](../../scripts/prune_dockerhub.sh),
which lists by default and deletes only with `--delete`. The evidence of an
execution follows.

### Evidence: rule 2, run on 2026-10-30

Before: the first dbt image was still on Docker Hub next to its replacement. It
had ended `dbt debug` with "1 check failed" (no `git`), so it was superseded by
`2026-10-30-5ed84e8`. The script in its default mode, which deletes nothing:

```
$ ./scripts/prune_dockerhub.sh albert-dbt:2026-10-30-5185b2e
== julius24h/albert-ingestion
  keep    2026-10-30-5185b2e
== julius24h/albert-dbt
  keep    2026-10-30-5ed84e8
  would delete 2026-10-30-5185b2e  (named on the command line (superseded))
```

The run (the access token was supplied in the environment and is not shown here):

```
$ DOCKERHUB_TOKEN=... ./scripts/prune_dockerhub.sh --delete albert-dbt:2026-10-30-5185b2e
== julius24h/albert-ingestion
  keep    2026-10-30-5185b2e
== julius24h/albert-dbt
  keep    2026-10-30-5ed84e8
  DELETED 2026-10-30-5185b2e  (named on the command line (superseded))  http 204
```

After, read from Docker Hub's public API, no login:

```
== julius24h/albert-ingestion
  2026-10-30-5185b2e sha256:63dfb6f73e95
== julius24h/albert-dbt
  2026-10-30-5ed84e8 sha256:02fb8f4ff8b6
```

Rules 1 and 3 had nothing to delete: each repository holds fewer than four tags
and every tag matches the scheme. They are stated and checked, not yet exercised.

## What would change my mind

- **A second person pushing to the same repositories.** Two people can produce the
  same date and a different commit, which the SHA handles; they can also overwrite
  each other's tag, which nothing here prevents. Then: immutable tags, or one
  repository per person.
- **A bill, or sensitive code in the images.** Move to Artifact Registry, with the
  cost above, and replace the pull step in the README with `gcloud auth
  configure-docker`.
- **A rebuilt base tag.** Python publishes `3.12.12-slim-bookworm` again for
  security patches. Pin `FROM` by digest (`@sha256:593bd06e...`) if a rebuild must
  give the same bytes.
