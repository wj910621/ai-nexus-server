#!/bin/bash
# Daily backup cron job — add to crontab:
# 0 2 * * * /opt/comicstudio/deploy/backup-cron.sh
#
# Runs the ComicStudio backup script with default settings (DB + uploads + Redis).
# Output is appended to /var/log/comicstudio-backup.log.

set -euo pipefail

cd /opt/comicstudio/backend

# Load environment (BACKUP_ENCRYPTION_KEY, DATABASE_URL, REDIS_URL, etc.)
if [ -f /opt/comicstudio/backend/.env ]; then
    set -a
    . /opt/comicstudio/backend/.env
    set +a
fi

python scripts/backup.py --type all >> /var/log/comicstudio-backup.log 2>&1
