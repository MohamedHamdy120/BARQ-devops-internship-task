#!/bin/bash
set -e
FILE="$1"
if [ -z "$FILE" ]; then
  echo "Usage: ./restore.sh <backup_file>"
  exit 1
fi
docker exec postgres psql -U barq_app barq_tasks -c "TRUNCATE records RESTART IDENTITY CASCADE;"
cat "$FILE" | docker exec -i postgres psql -U barq_app barq_tasks
echo "Restored from $FILE"