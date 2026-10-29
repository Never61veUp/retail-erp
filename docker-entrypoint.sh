#!/bin/bash
set -euo pipefail

: "${ODOO_MASTER_PASSWORD:?ODOO_MASTER_PASSWORD is required}"

grep -v -E '^[[:space:]]*admin_passwd[[:space:]]*=' /etc/odoo/odoo.conf > /tmp/odoo.conf || true
printf '\nadmin_passwd = %s\n' "${ODOO_MASTER_PASSWORD}" >> /tmp/odoo.conf
chmod 600 /tmp/odoo.conf

export ODOO_RC=/tmp/odoo.conf

exec /entrypoint.sh "$@"
