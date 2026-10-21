#!/bin/sh
set -e
# Apply schema migrations before either the API or the worker starts.
# Both may run this at once; Alembic's version table makes the second a no-op.
alembic upgrade head
exec "$@"
