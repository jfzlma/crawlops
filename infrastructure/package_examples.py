from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
output = root / "data" / "examples"
output.mkdir(parents=True, exist_ok=True)
for project in (root / "examples").iterdir():
    if project.is_dir():
        archive = output / (project.name + ".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for file in project.rglob("*"):
                if file.is_file() and "__pycache__" not in file.parts:
                    z.write(file, file.relative_to(project))
        print(archive)
