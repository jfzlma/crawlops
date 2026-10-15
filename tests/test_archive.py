import stat
import tarfile
import zipfile

import pytest
from crawlops.archive import ArchiveError, dockerfile, extract


def make_zip(tmp_path, entries):
    path = tmp_path / "source.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name, content in entries.items():
            z.writestr(name, content)
    return path


@pytest.mark.parametrize("path", ["../escape", "/absolute", "a/../../escape", "C:\\windows", "a\\..\\escape"])
def test_traversal(tmp_path, path):
    archive = make_zip(tmp_path, {path: "bad"})
    with pytest.raises(ArchiveError):
        extract(archive, tmp_path / "out")


def test_zip_symlink(tmp_path):
    archive = tmp_path / "source.zip"
    entry = zipfile.ZipInfo("link")
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(entry, "/etc/passwd")
    with pytest.raises(ArchiveError):
        extract(archive, tmp_path / "out")


def test_tar_symlink(tmp_path):
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as t:
        entry = tarfile.TarInfo("link")
        entry.type = tarfile.SYMTYPE
        entry.linkname = "/etc/passwd"
        t.addfile(entry)
    with pytest.raises(ArchiveError):
        extract(archive, tmp_path / "out")


def test_decompression_limit(tmp_path):
    archive = make_zip(tmp_path, {"big": "a" * 1000})
    with pytest.raises(ArchiveError, match="limits"):
        extract(archive, tmp_path / "out", max_bytes=100)


def test_nested_project_and_dependencies(tmp_path):
    archive = make_zip(
        tmp_path,
        {
            "repo/project/scrapy.cfg": "[settings]\ndefault=demo.settings",
            "repo/project/requirements.txt": "scrapy",
        },
    )
    root = extract(archive, tmp_path / "out")
    assert root.name == "project"
    dockerfile(root)
    assert "-r requirements.txt" in (root / "Dockerfile").read_text()
    assert "USER 65532" in (root / "Dockerfile").read_text()


def test_duplicate_entries(tmp_path):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("same", "first")
        with pytest.warns(UserWarning):
            z.writestr("same", "second")
    with pytest.raises(ArchiveError):
        extract(archive, tmp_path / "out")
