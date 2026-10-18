#!/usr/bin/env python3
"""Revokes the development certificates a TestFlight job created on its runner.

Xcode's automatic signing creates an Apple Development certificate when the keychain has none, and
a hosted runner's keychain goes with the runner, so every run would leave one more certificate on
the team until Apple's limit stops the next archive. `record` notes the serial numbers of the
certificates the keychain holds before the archive. `revoke` revokes, through the App Store Connect
API, the development certificates whose serial numbers the keychain gained since. It never revokes
another kind, a distribution certificate among them, or a certificate the keychain held before.

`revoke` reads the API key from ASC_KEY_ID, ASC_ISSUER_ID and ASC_KEY_PATH (the `.p8` file). A
problem is a warning, not a failure: the job's builds are already archived or uploaded by then.

Standard library only. The API's token is signed with the `openssl` command.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

API = "https://api.appstoreconnect.apple.com"
# The kinds `revoke` may revoke: what Xcode's automatic signing creates.
DEVELOPMENT_TYPES = ("DEVELOPMENT", "IOS_DEVELOPMENT", "MAC_APP_DEVELOPMENT")
PEM = re.compile(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.DOTALL)


class CertificateError(Exception):
    pass


# The keychain


def keychain_certificates() -> str:
    """Every certificate in the keychain search list, as PEM."""
    result = subprocess.run(["security", "find-certificate", "-a", "-p"], capture_output=True, text=True)
    if result.returncode != 0 and not result.stdout:
        return ""
    return result.stdout


def normalized(serial: str) -> str:
    """A serial number as one way of writing it: hex digits in uppercase, without colons or leading zeros."""
    return serial.replace(":", "").strip().upper().lstrip("0") or "0"


def serials(pem: str) -> set[str]:
    """The serial numbers of the PEM certificates in `pem`; any that openssl can't read are skipped."""
    found = set()
    for block in PEM.findall(pem):
        result = subprocess.run(["openssl", "x509", "-noout", "-serial"], input=block + "\n",
                                capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.startswith("serial="):
            found.add(normalized(result.stdout.split("=", 1)[1]))
    return found


# The API's token: an ES256 JSON Web Token (App Store Connect API, "Generating tokens").


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def raw_signature(der: bytes) -> bytes:
    """An ECDSA signature as JWT wants it, r and s as 32 bytes each, from the DER that openssl writes."""

    def integer(data: bytes, at: int) -> tuple[bytes, int]:
        if data[at] != 0x02:
            raise CertificateError("Not a DER ECDSA signature.")
        length = data[at + 1]
        return data[at + 2:at + 2 + length], at + 2 + length

    if len(der) < 8 or der[0] != 0x30:
        raise CertificateError("Not a DER ECDSA signature.")
    at = 3 if der[1] & 0x80 else 2
    r, at = integer(der, at)
    s, _ = integer(der, at)
    return b"".join(value.lstrip(b"\0").rjust(32, b"\0") for value in (r, s))


def token(key_id: str, issuer_id: str, key_path: str, now: int | None = None) -> str:
    """A token for the API, valid for 20 minutes, signed with the `.p8` key at `key_path`."""
    now = int(time.time()) if now is None else now
    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    claims = {"iss": issuer_id, "iat": now, "exp": now + 20 * 60, "aud": "appstoreconnect-v1"}
    signing_input = f"{b64url(json.dumps(header).encode())}.{b64url(json.dumps(claims).encode())}"
    try:
        der = subprocess.run(["openssl", "dgst", "-sha256", "-sign", key_path],
                             input=signing_input.encode(), capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as error:
        raise CertificateError(f"openssl couldn't sign with the key: {error.stderr.decode().strip()}") from error
    return f"{signing_input}.{b64url(raw_signature(der))}"


# The API


class Client:
    def __init__(self, token: str):
        self.token = token

    def request(self, method: str, url: str) -> dict:
        url = url if url.startswith("https://") else f"{API}{url}"
        request = urllib.request.Request(url, method=method, headers={"Authorization": f"Bearer {self.token}"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            raise CertificateError(f"{method} {url}: {error.code} {error.read().decode(errors='replace')[:300]}") from error
        except urllib.error.URLError as error:
            raise CertificateError(f"{method} {url}: {error.reason}") from error
        return json.loads(body) if body else {}

    def development_certificates(self) -> list[dict]:
        """The team's development certificates, every page of them."""
        query = urllib.parse.urlencode({
            "filter[certificateType]": ",".join(DEVELOPMENT_TYPES),
            "fields[certificates]": "name,displayName,serialNumber,certificateType",
            "limit": "200",
        })
        url: str | None = f"/v1/certificates?{query}"
        found: list[dict] = []
        while url:
            page = self.request("GET", url)
            found += page.get("data", [])
            url = page.get("links", {}).get("next")
        return found

    def revoke(self, certificate_id: str) -> None:
        self.request("DELETE", f"/v1/certificates/{urllib.parse.quote(certificate_id)}")


def to_revoke(certificates: list[dict], gained: set[str]) -> list[dict]:
    """The development certificates among `certificates` whose serial number is one of `gained`."""
    chosen = []
    for certificate in certificates:
        attributes = certificate.get("attributes") or {}
        serial = attributes.get("serialNumber")
        if attributes.get("certificateType") in DEVELOPMENT_TYPES and serial and normalized(serial) in gained:
            chosen.append(certificate)
    return chosen


def describe(certificate: dict) -> str:
    attributes = certificate.get("attributes") or {}
    name = attributes.get("name") or attributes.get("displayName") or certificate.get("id")
    return f"{name} ({attributes.get('certificateType')}, serial {attributes.get('serialNumber')})"


# The commands


def record(state: Path, pem: str) -> None:
    found = serials(pem)
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("".join(f"{serial}\n" for serial in sorted(found)))
    print(f"The keychain holds {len(found)} certificates before signing.")


def revoke(state: Path, pem: str, client_for: Callable[[], Client]) -> None:
    if not state.exists():
        print("No certificates were recorded before signing, so none are revoked.")
        return
    gained = serials(pem) - set(state.read_text().split())
    if not gained:
        print("The keychain gained no certificates, so none are revoked.")
        return
    client = client_for()
    chosen = to_revoke(client.development_certificates(), gained)
    if not chosen:
        print(f"The keychain gained {len(gained)} certificates, none of them a development certificate of the team.")
        return
    for certificate in chosen:
        client.revoke(certificate["id"])
        print(f"Revoked {describe(certificate)}")


def client_from_environment() -> Client:
    key_id, issuer_id, key_path = (os.environ.get(name, "") for name in ("ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_KEY_PATH"))
    if not (key_id and issuer_id and key_path and Path(key_path).is_file()):
        raise CertificateError("Needs ASC_KEY_ID, ASC_ISSUER_ID and ASC_KEY_PATH to revoke certificates.")
    return Client(token(key_id, issuer_id, key_path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("record", "revoke"))
    parser.add_argument("--state", type=Path, required=True, help="Where `record` writes the serial numbers.")
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            record(args.state, keychain_certificates())
        else:
            revoke(args.state, keychain_certificates(), client_from_environment)
    except CertificateError as error:
        print(f"::warning::Couldn't revoke the runner's development certificate: {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
