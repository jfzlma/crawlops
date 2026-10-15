"""Bounded, link-free ZIP/TAR extraction. Never uses extractall."""

import configparser
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


class ArchiveError(ValueError):
    pass


def extract(archive: Path, destination: Path, max_bytes=250 * 1024 * 1024, max_files=5000):
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    count = 0
    names = set()

    def target(name, size):
        nonlocal total, count
        p = PurePosixPath(name)
        if "\\" in name or p.is_absolute() or ".." in p.parts or ":" in name or "\x00" in name:
            raise ArchiveError("Unsafe archive path")
        if not p.parts or p.parts[0] in {".git", ".ssh"}:
            raise ArchiveError("Disallowed archive entry")
        total += size
        count += 1
        if size < 0 or total > max_bytes or count > max_files:
            raise ArchiveError("Archive exceeds extraction limits")
        out = destination.joinpath(*p.parts)
        if not out.resolve().is_relative_to(destination.resolve()) or str(p) in names:
            raise ArchiveError("Duplicate or unsafe entry")
        names.add(str(p))
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def copy(source, out, declared):
        copied = 0
        with out.open("wb") as dest:
            while chunk := source.read(65536):
                copied += len(chunk)
                if copied > declared or copied > max_bytes:
                    raise ArchiveError("Archive data exceeds declared size")
                dest.write(chunk)

    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as z:
                for entry in z.infolist():
                    if entry.is_dir():
                        target(entry.filename.rstrip("/"), 0).mkdir(exist_ok=True)
                        continue
                    mode = entry.external_attr >> 16
                    if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0, stat.S_IFREG}):
                        raise ArchiveError("Links and special files are forbidden")
                    out = target(entry.filename, entry.file_size)
                    with z.open(entry) as src:
                        copy(src, out, entry.file_size)
        else:
            with tarfile.open(archive, "r:*") as t:
                for entry in t:
                    if entry.isdir() and entry.name in {".", "./"}:
                        continue
                    if entry.isdir() and entry.size:
                        raise ArchiveError("Directory entries must be empty")
                    if not (entry.isfile() or entry.isdir()):
                        raise ArchiveError("Links and special files are forbidden")
                    out = target(entry.name, entry.size if entry.isfile() else 0)
                    if entry.isdir():
                        out.mkdir(exist_ok=True)
                    else:
                        with t.extractfile(entry) as src:
                            copy(src, out, entry.size)
    except (tarfile.TarError, zipfile.BadZipFile, OSError) as exc:
        raise ArchiveError("Invalid archive") from exc
    configs = list(destination.rglob("scrapy.cfg"))
    if len(configs) != 1:
        raise ArchiveError("Archive must contain exactly one scrapy.cfg")
    config = configparser.ConfigParser()
    config.read(configs[0])
    if not config.has_option("settings", "default"):
        raise ArchiveError("scrapy.cfg must define [settings] default")
    return configs[0].parent


def dockerfile(root: Path, python="3.12"):
    if python not in {"3.12", "3.13"}:
        raise ArchiveError("Supported Python versions: 3.12, 3.13")
    if (root / "Dockerfile").exists():
        return
    install = ""
    if (root / "requirements.txt").exists():
        install = "RUN python -m pip install --no-cache-dir -r requirements.txt\n"
    elif (root / "pyproject.toml").exists():
        # pip uses the declared PEP 517 backend, including modern poetry-core projects.
        install = "RUN python -m pip install --no-cache-dir .\n"
    (root / "Dockerfile").write_text(
        f"FROM python:{python}-slim\nARG PIP_INDEX_URL\nARG HTTPS_PROXY\nARG HTTP_PROXY\n"
        "ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1\nWORKDIR /app\nCOPY . .\n"
        "RUN python -m pip install --no-cache-dir 'scrapy>=2.12,<3'\n"
        + install
        + 'RUN chmod -R a+rX /app\nUSER 65532:65532\nENTRYPOINT []\nCMD ["scrapy", "list"]\n'
    )
    # Never include workstation credentials or repository metadata in image contexts.
    with (root / ".dockerignore").open("a") as f:
        f.write("\n.git\n.env\n.env.*\n.venv\nvenv\n__pycache__\n*.pem\n*.key\n")
