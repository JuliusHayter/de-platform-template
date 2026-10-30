# Reproduction from nothing

Both images were pushed to Docker Hub, deleted from this machine, pulled back by
tag, and run again. Transcripts below are the raw output of the commands, with
two edits, both marked: the long listing printed by `docker builder prune` is
cut to its total line, and the `$` lines are echoed by the script that ran them
(`docker rmi` and `docker pull` are the real commands).

| Image | Tag | Digest at push | Digest after pull |
|---|---|---|---|
| `julius24h/albert-ingestion` | `2026-10-30-5185b2e` | `sha256:63dfb6f73e95a040941615de52ff3d9dcceeafd65a2870cfd142c7963c772cd1` | `sha256:63dfb6f73e95a040941615de52ff3d9dcceeafd65a2870cfd142c7963c772cd1` |
| `julius24h/albert-dbt` | `2026-10-30-5ed84e8` | `sha256:02fb8f4ff8b6a1ae9d5ab7d444f68713a2a1dc6b386a6d2f8957b5fa4aeec560` | `sha256:02fb8f4ff8b6a1ae9d5ab7d444f68713a2a1dc6b386a6d2f8957b5fa4aeec560` |

The tag is the date and the short SHA of the commit the image was built from
([ADR-0006](adr/0006-image-tags.md)). Both pulls were made after `docker builder
prune -af`: my first attempt printed `Already exists` for every layer, meaning
Docker had kept them locally and nothing came from the registry, so I emptied the
build cache and ran it again. In the transcripts below some layers still say
`Already exists` (the Python base, shared with other images on this machine) and
the rest say `Pull complete`.

## 1. The ingestion job

The input is pinned: the company's load generator was stopped
(`docker compose stop load-generator`) for the whole reproduction, because it
restocks products and would change the table between the two runs. The job is
`extract_tables.py product`, run from the image. Reading the same table twice gives
the same Parquet **byte for byte**: the SHA-256 of the file is the same before and
after.

Push, as printed ("Mounted from library/python" is the Python base image, which
Docker Hub already had, so it was not uploaded):

```
The push refers to repository [docker.io/julius24h/albert-ingestion]
e0a183579c7c: Preparing
34bfe629993f: Preparing
db16629891c4: Preparing
32d58d2d8234: Preparing
2d83ed664372: Preparing
edc46d2649b4: Preparing
7d9e14b92a54: Preparing
100031c9cce7: Preparing
7d9e14b92a54: Waiting
100031c9cce7: Waiting
2d83ed664372: Mounted from library/python
e0a183579c7c: Pushed
db16629891c4: Pushed
32d58d2d8234: Pushed
edc46d2649b4: Mounted from library/python
100031c9cce7: Mounted from library/python
7d9e14b92a54: Mounted from library/python
34bfe629993f: Pushed
2026-10-30-5185b2e: digest: sha256:63dfb6f73e95a040941615de52ff3d9dcceeafd65a2870cfd142c7963c772cd1 size: 1993
```

Reproduction:

```
# 1. run the job from the image

$ docker run --rm --network albert-marketplace_default -e PGHOST=db -e PGPASSWORD -v /private/tmp/repro/out:/data julius24h/albert-ingestion:2026-10-30-5185b2e python extract_tables.py product
product: 42859 rows, 6 columns

$ ls -l out/bronze/product_pg/part-0.parquet
-rw-r--r--  1 julius  wheel  5121036 30 oct.  13:48 out/bronze/product_pg/part-0.parquet

$ shasum -a 256 out/bronze/product_pg/part-0.parquet
b3d691f4ece66282480af134f035ac518f561cde7d0d97f248572b6da6e27553  out/bronze/product_pg/part-0.parquet
# 2. delete the image from this machine

$ docker rmi -f julius24h/albert-ingestion:2026-10-30-5185b2e albert-ingestion:2026-10-30-5185b2e albert-ingestion:2026-10-30
Untagged: julius24h/albert-ingestion:2026-10-30-5185b2e
Untagged: julius24h/albert-ingestion@sha256:63dfb6f73e95a040941615de52ff3d9dcceeafd65a2870cfd142c7963c772cd1
Deleted: sha256:2ec7d870c6137d99b90adb776328bc0eb548b09cd69725c12214c9e5e7d6cfd7
Error response from daemon: No such image: albert-ingestion:2026-10-30-5185b2e
Error response from daemon: No such image: albert-ingestion:2026-10-30

$ docker builder prune -af
[47 build-cache entries elided from this listing]
Total:	2.869GB

$ bash -c docker images | grep albert-ingestion || echo "(no albert-ingestion image on this machine)"
(no albert-ingestion image on this machine)
# 3. pull it back by tag

$ docker pull julius24h/albert-ingestion:2026-10-30-5185b2e
2026-10-30-5185b2e: Pulling from julius24h/albert-ingestion
eb04ef52de3a: Already exists
2a131c235be7: Already exists
7d7d63e37187: Already exists
b00559a184b3: Already exists
e502fae0e8d8: Already exists
3f646356b292: Pulling fs layer
dbd1d6879693: Pulling fs layer
6f61a110f714: Pulling fs layer
3f646356b292: Download complete
6f61a110f714: Verifying Checksum
6f61a110f714: Download complete
3f646356b292: Pull complete
dbd1d6879693: Verifying Checksum
dbd1d6879693: Download complete
dbd1d6879693: Pull complete
6f61a110f714: Pull complete
Digest: sha256:63dfb6f73e95a040941615de52ff3d9dcceeafd65a2870cfd142c7963c772cd1
Status: Downloaded newer image for julius24h/albert-ingestion:2026-10-30-5185b2e
docker.io/julius24h/albert-ingestion:2026-10-30-5185b2e
# 4. run the job again

$ docker run --rm --network albert-marketplace_default -e PGHOST=db -e PGPASSWORD -v /private/tmp/repro/out:/data julius24h/albert-ingestion:2026-10-30-5185b2e python extract_tables.py product
product: 42859 rows, 6 columns

$ ls -l out/bronze/product_pg/part-0.parquet
-rw-r--r--  1 julius  wheel  5121036 30 oct.  13:48 out/bronze/product_pg/part-0.parquet

$ shasum -a 256 out/bronze/product_pg/part-0.parquet
b3d691f4ece66282480af134f035ac518f561cde7d0d97f248572b6da6e27553  out/bronze/product_pg/part-0.parquet
```

Same row count (42,859), same file size (5,121,036 bytes), same SHA-256
(`b3d691f4ece6...`), same digest.

## 2. The dbt runner

`dbt build` writes the same BigQuery tables each time, so the evidence is the
summary line, which is identical: **PASS=75 WARN=4 ERROR=0**. The first run in
step 1 used the image from this machine; the second used the one pulled back. The
listing after `docker rmi` shows an older image of mine, `5185b2e`, still on the
machine: that is the first build of the dbt image, superseded below, not the one
under test.

Push:

```
=== docker push julius24h/albert-dbt:2026-10-30-5ed84e8
The push refers to repository [docker.io/julius24h/albert-dbt]
6443e39e0e30: Preparing
e33dbdc37987: Preparing
b063e994be16: Preparing
1f2a9dd4a8bf: Preparing
198a9274d366: Preparing
de070ce5181b: Preparing
2d83ed664372: Preparing
edc46d2649b4: Preparing
de070ce5181b: Waiting
7d9e14b92a54: Preparing
100031c9cce7: Preparing
2d83ed664372: Waiting
edc46d2649b4: Waiting
100031c9cce7: Waiting
7d9e14b92a54: Waiting
e33dbdc37987: Pushed
6443e39e0e30: Pushed
1f2a9dd4a8bf: Pushed
2d83ed664372: Layer already exists
edc46d2649b4: Layer already exists
7d9e14b92a54: Layer already exists
100031c9cce7: Layer already exists
de070ce5181b: Pushed
198a9274d366: Pushed
b063e994be16: Pushed
2026-10-30-5ed84e8: digest: sha256:02fb8f4ff8b6a1ae9d5ab7d444f68713a2a1dc6b386a6d2f8957b5fa4aeec560 size: 2417
```

Reproduction:

```
# 1. run the job from the image

$ docker run --rm -v ~/.config/gcloud:/home/dbt/.config/gcloud:ro -e GCP_PROJECT_ID julius24h/albert-dbt:2026-10-30-5ed84e8 build   (summary lines only)
12:54:21  Finished running 5 table models, 62 data tests, 12 view models in 0 hours 0 minutes and 22.99 seconds (22.99s).
12:54:21  Done. PASS=75 WARN=4 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=79
# 2. delete the image from this machine

$ docker rmi -f julius24h/albert-dbt:2026-10-30-5ed84e8 albert-dbt:2026-10-30-5ed84e8
Untagged: julius24h/albert-dbt:2026-10-30-5ed84e8
Untagged: julius24h/albert-dbt@sha256:02fb8f4ff8b6a1ae9d5ab7d444f68713a2a1dc6b386a6d2f8957b5fa4aeec560
Untagged: albert-dbt:2026-10-30-5ed84e8
Deleted: sha256:c2621f0594bce03dfea3e3c4f71f8ccceff4c1d89805f6cf4fd509c521355691

$ docker builder prune -af
[13 build-cache entries elided from this listing]
Total:	912.2MB

$ bash -c docker images | grep albert-dbt || echo "(no albert-dbt image on this machine)"
julius24h/albert-dbt                2026-10-30-5185b2e      4aea0eec098c   13 minutes ago   968MB
albert-dbt                          2026-10-30              4aea0eec098c   13 minutes ago   968MB
albert-dbt                          2026-10-30-5185b2e      4aea0eec098c   13 minutes ago   968MB
# 3. pull it back by tag

$ docker pull julius24h/albert-dbt:2026-10-30-5ed84e8
2026-10-30-5ed84e8: Pulling from julius24h/albert-dbt
eb04ef52de3a: Already exists
2a131c235be7: Already exists
7d7d63e37187: Already exists
b00559a184b3: Already exists
0fde80fd4e88: Pulling fs layer
1205e8f0cc2f: Pulling fs layer
349cc4e2213a: Pulling fs layer
87b676875228: Pulling fs layer
34f9fff0249b: Pulling fs layer
9e152581c187: Pulling fs layer
87b676875228: Waiting
34f9fff0249b: Waiting
9e152581c187: Waiting
349cc4e2213a: Verifying Checksum
349cc4e2213a: Download complete
0fde80fd4e88: Download complete
0fde80fd4e88: Pull complete
34f9fff0249b: Verifying Checksum
34f9fff0249b: Download complete
9e152581c187: Verifying Checksum
9e152581c187: Download complete
1205e8f0cc2f: Download complete
1205e8f0cc2f: Pull complete
349cc4e2213a: Pull complete
87b676875228: Verifying Checksum
87b676875228: Download complete
87b676875228: Pull complete
34f9fff0249b: Pull complete
9e152581c187: Pull complete
Digest: sha256:02fb8f4ff8b6a1ae9d5ab7d444f68713a2a1dc6b386a6d2f8957b5fa4aeec560
Status: Downloaded newer image for julius24h/albert-dbt:2026-10-30-5ed84e8
docker.io/julius24h/albert-dbt:2026-10-30-5ed84e8
# 4. run the job again

$ docker run --rm -v ~/.config/gcloud:/home/dbt/.config/gcloud:ro -e GCP_PROJECT_ID julius24h/albert-dbt:2026-10-30-5ed84e8 build   (summary lines only)
12:55:32  Finished running 5 table models, 62 data tests, 12 view models in 0 hours 0 minutes and 22.33 seconds (22.33s).
12:55:32  Done. PASS=75 WARN=4 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=79
```

## The earlier dbt tag

The first dbt image, `2026-10-30-5185b2e` (digest `sha256:9b87804e8b66fa8a1b666e0f4db4f828a7004bd93d95b2f0e7df1bc1b5f80a02`),
ended `dbt debug` with "1 check failed: git". I added a pinned git and pushed
`2026-10-30-5ed84e8`. The old tag is retired under the retention policy in
[ADR-0006](adr/0006-image-tags.md), with the deletion shown there.

## What this does not prove

- The reproduction ran on the same machine that built the image. Another machine
  would add one thing this cannot show: that nothing was left over in my local
  Docker state. Emptying the build cache removes most of that doubt, not all.
- `docker pull` verifies the digest. The Parquet file equal to the byte is a
  property of this job and this input, not of Docker.
