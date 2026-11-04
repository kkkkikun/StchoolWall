# Encrypted off-host backups and PITR

Status: integration provided; repository bucket, KMS/key escrow, schedule, archive latency and a successful restore are **not configured or proved by this code**. G2 stays blocked until the operator supplies the evidence.

1. In staging, build `deploy/backup/Dockerfile`, scan and push it to the private registry. Set BACKUP_POSTGRES_IMAGE to its sha256 digest. Do not change PostgreSQL major version while enabling backups.
2. Provision a private S3-compatible bucket in a separate failure domain/account. Enable provider versioning/retention and least-privilege credentials. Do not reuse the media bucket. Test endpoint connectivity/TLS and budget.
3. Copy pgbackrest.conf.example to /opt/schoolwall/shared/pgbackrest.conf. Replace every placeholder; escrow repo1-cipher-pass separately from the database host. Set ownership to the postgres UID from the chosen image and mode 0600. Never print it to CI logs.
4. Copy compose.backup.yml to /opt/schoolwall/shared/compose.backup.yml. The release scripts add that overlay automatically. Verify its absolute config path for a custom deployment root. First enabling archive_mode restarts PostgreSQL: schedule a maintenance window.
5. With the release's compose/env arguments, run db `pgbackrest --config=/run/secrets/pgbackrest.conf --stanza=schoolwall stanza-create`, then `check`, then `--type=full backup`, then `info --output=json`. Do not count an empty repository as a working backup.
6. Install an operator-owned schedule: weekly full, daily differential, WAL continuous; failures notify on-call. Alert if last archive > 30 minutes, archive failures grow, last valid backup > 26 hours or disk free < 20%. Do not use silent cron without delivery monitoring.

## Restore exercise (isolated environment only)

Create a NEW empty PostgreSQL data volume and isolated network; use the same PG15+pgBackRest image and repository config. Never run restore against production volume. Retrieve a selected point-in-time with `pgbackrest ... --type=time --target='YYYY-MM-DD HH:MM:SS+08' --target-action=promote restore`, then start PostgreSQL against that restored volume. Use official pgBackRest instructions for the installed version's recovery options.

Record selected point, actual last committed marker before/after it, restore start/end, row counts, login/feed/comment smoke checks, media references, WAL reachability and measured RPO/RTO. Target RPO <= 1 hour and RTO <= 4 hours for the initial single-school release; these are goals until measured. Restore evidence must include a dump/repo integrity check and a second engineer/operator review. Backup decryption keys require their own recovery exercise.

Local logical backup (`deploy/backup.sh`) remains an emergency export with newest-N retention and gzip validation. It is not PITR and does not back up private/public uploaded files. Approved public media needs a separate recovery and deletion/retention policy. Student-verification evidence uses a different private bucket: provider versioning, replication and backup copies are prohibited; deleting evidence must remove every exact-key version and delete marker. Never include that bucket in database/media backup replication. Restore exercises must test access controls and confirm expired/deleted verification evidence does not reappear; restored database references must be reconciled against current retention and revocation decisions before reopening service; missing deleted evidence must remain inaccessible.

## Backup freshness signals (logical backup only)

`deploy/backup.sh` records every attempt — successful or failed — in a status file (`deploy/backup_status.py`): `<BACKUP_STATUS_DIR>/backup_status.json`, holding timestamps and counters only. It carries no backup path, object-storage key, connection string or backup content, so it can be mounted read-only into the backend container. The application reads it and exposes `schoolwall_backup_last_success_age_seconds`, `schoolwall_backup_last_attempt_succeeded`, `schoolwall_backup_failures_total` and `schoolwall_backup_status_collection_ok` on `/metrics`; `deploy/monitoring/alerts.yml` alerts on a backup older than 26 hours, on failures and on an unreadable status (see `docs/production/runbook.md`).

This covers the repository-controlled logical backup only. **WAL archive latency (> 30 minutes), archive failure growth, off-host copies, encryption and PITR still come from pgBackRest and remain operator work** — point 6 above still applies, and no rule in this repository may be described as covering them.
