"""Selects an installed Xcode by version: the newest whose version is the one asked for or starts
with it ("26" → the newest 26.x). "default" keeps the runner's selection. Writes `available`,
`path` and `version` to $GITHUB_OUTPUT.

With --allow-missing, a version the runner doesn't have is a warning rather than an error:
`available` is then false and nothing is selected."""

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


def output(**values: str) -> None:
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as file:
        for key, value in values.items():
            file.write(f"{key}={value}\n")


def main(wanted: str, allow_missing: bool = False) -> int:
    apps = installed()
    if wanted in ("", "default"):
        developer = subprocess.run(["xcode-select", "-p"], capture_output=True, text=True, check=True).stdout.strip()
        app = Path(developer).parent.parent.resolve()
        version = next((v for _, v, a in apps if a.resolve() == app), "?")
    else:
        matches = [(v, a) for _, v, a in apps if v == wanted or v.startswith(wanted + ".")]
        if not matches:
            listing = ", ".join(v for _, v, _ in apps) or "none"
            level = "warning" if allow_missing else "error"
            print(f"::{level}::Xcode {wanted} isn't installed on this runner. Installed: {listing}.")
            output(available="false", path="", version="")
            return 0 if allow_missing else 1
        version, app = matches[-1]
        subprocess.run(["sudo", "xcode-select", "-s", str(app / "Contents/Developer")], check=True)
    subprocess.run(["xcodebuild", "-version"], check=True)
    subprocess.run(["swift", "--version"], check=True)
    output(available="true", path=str(app), version=version)
    print(f"Selected Xcode {version}: {app}")
    return 0


if __name__ == "__main__":
    arguments = [argument for argument in sys.argv[1:] if argument != "--allow-missing"]
    sys.exit(main(arguments[0] if arguments else "default", allow_missing="--allow-missing" in sys.argv))
