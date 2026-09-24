#!/bin/bash
set -e
mkdir -p backups
FILE="backups/backup_$(date +%Y%m%d_%H%M%S).sql"
docker exec postgres pg_dump -U barq_app --data-only --column-inserts barq_tasks > "$FILE"
echo "Backup saved to $FILE"