"""Generate private local credentials without publishing fixed administrator secrets."""

import base64
import os
from pathlib import Path
import secrets

path = Path(".env")
if path.exists():
    raise SystemExit(".env already exists; refusing to overwrite credentials")
values = {
    "POSTGRES_PASSWORD": secrets.token_hex(24),
    "CRAWLOPS_ADMIN_EMAIL": "admin@crawlops.local",
    "CRAWLOPS_ADMIN_PASSWORD": secrets.token_urlsafe(24),
    "CRAWLOPS_AGENT_TOKEN": secrets.token_urlsafe(40),
    "CRAWLOPS_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
    "CRAWLOPS_PORT": "8080",
}
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as output:
    output.write("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
print("Created .env. Read CRAWLOPS_ADMIN_PASSWORD there to sign in; keep this file private.")
