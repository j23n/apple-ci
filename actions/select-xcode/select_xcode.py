"""Selects an installed Xcode by version: the newest whose version is the one asked for or starts
with it ("26" → the newest 26.x). "default" keeps the runner's selection. Writes `path` and
`version` to $GITHUB_OUTPUT."""

import os
import plistlib
import subprocess
import sys
from pathlib import Path


def installed() -> list[tuple[tuple[int, ...], str, Path]]:
    found = []
    for app in Path("/Applications").glob("Xcode*.app"):
        if app.is_symlink():
            continue
        try:
            with open(app / "Contents/Info.plist", "rb") as file:
                version = plistlib.load(file)["CFBundleShortVersionString"]
        except (OSError, KeyError, plistlib.InvalidFileException):
            continue
        key = tuple(int(part) for part in version.split(".") if part.isdigit())
        found.append((key, version, app))
    return sorted(found)


def main(wanted: str) -> int:
    apps = installed()
    if wanted in ("", "default"):
        developer = subprocess.run(["xcode-select", "-p"], capture_output=True, text=True, check=True).stdout.strip()
        app = Path(developer).parent.parent.resolve()
        version = next((v for _, v, a in apps if a.resolve() == app), "?")
    else:
        matches = [(v, a) for _, v, a in apps if v == wanted or v.startswith(wanted + ".")]
        if not matches:
            listing = ", ".join(v for _, v, _ in apps) or "none"
            print(f"::error::Xcode {wanted} isn't installed on this runner. Installed: {listing}.")
            return 1
        version, app = matches[-1]
        subprocess.run(["sudo", "xcode-select", "-s", str(app / "Contents/Developer")], check=True)
    subprocess.run(["xcodebuild", "-version"], check=True)
    subprocess.run(["swift", "--version"], check=True)
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as output:
        output.write(f"path={app}\nversion={version}\n")
    print(f"Selected Xcode {version}: {app}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "default"))
