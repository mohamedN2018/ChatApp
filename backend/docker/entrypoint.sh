#!/usr/bin/env bash
# Container entrypoint: block until Postgres/Redis are reachable, then exec the
# role-specific command (web / worker / beat) passed as CMD. Migrations are run
# by the web service's command, not here, to avoid concurrent migrate races.
set -euo pipefail

python manage.py wait_for_services --timeout "${WAIT_TIMEOUT:-60}"

exec "$@"
