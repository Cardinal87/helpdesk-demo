#!/bin/sh
set -eu

alembic upgrade head
exec telegram-crm
