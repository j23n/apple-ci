"""Tests for runner_certificates.py: `python3 -m unittest` in this folder. Needs the `openssl` command."""

import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import runner_certificates as rc


def certificate(serial: int, name: str = "Apple Development: Test (AAAA111111)") -> str:
    """A self-signed certificate with the serial number `serial`, as PEM."""
    with tempfile.TemporaryDirectory() as folder:
        key = Path(folder, "key.pem")
        subprocess.run(["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", key],
                       check=True, capture_output=True)
        return subprocess.run(
            ["openssl", "req", "-x509", "-new", "-key", key, "-subj", f"/CN={name}", "-days", "1",
             "-set_serial", str(serial)],
            check=True, capture_output=True, text=True,
        ).stdout


def listed(certificate_id: str, serial: str, kind: str = "DEVELOPMENT") -> dict:
    return {"id": certificate_id, "attributes": {"name": certificate_id, "serialNumber": serial, "certificateType": kind}}


class FakeClient:
    def __init__(self, certificates: list[dict]):
        self.certificates = certificates
        self.revoked: list[str] = []

    def development_certificates(self) -> list[dict]:
        return self.certificates

    def revoke(self, certificate_id: str) -> None:
        self.revoked.append(certificate_id)


class SerialTests(unittest.TestCase):
    def test_one_way_of_writing_a_serial(self):
        self.assertEqual(rc.normalized("0a:1B:2c"), "A1B2C")
        self.assertEqual(rc.normalized("00FF"), "FF")
        self.assertEqual(rc.normalized("0"), "0")

    def test_reads_every_certificate_in_a_bundle(self):
        pem = certificate(0x1A2B) + "junk between\n" + certificate(0x3C4D)
        self.assertEqual(rc.serials(pem), {"1A2B", "3C4D"})

    def test_no_certificates(self):
        self.assertEqual(rc.serials(""), set())


class ChoiceTests(unittest.TestCase):
    def test_only_gained_development_certificates(self):
        certificates = [
            listed("gained", "1a2b"),
            listed("gained-ios", "00AA", "IOS_DEVELOPMENT"),
            listed("held-before", "3C4D"),
            listed("distribution", "1A2B", "DISTRIBUTION"),
            listed("no-serial", ""),
        ]
        chosen = rc.to_revoke(certificates, {"1A2B", "AA"})
        self.assertEqual([c["id"] for c in chosen], ["gained", "gained-ios"])


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.state = Path(self.folder.name, "state.txt")
        self.before = certificate(0x10)
        self.created = certificate(0x20)

    def tearDown(self):
        self.folder.cleanup()

    def test_revokes_what_the_keychain_gained(self):
        rc.record(self.state, self.before)
        client = FakeClient([listed("before", "10"), listed("created", "20"), listed("other-runner", "30")])
        rc.revoke(self.state, self.before + self.created, lambda: client)
        self.assertEqual(client.revoked, ["created"])

    def test_nothing_gained_needs_no_key(self):
        rc.record(self.state, self.before)

        def no_client():
            raise AssertionError("asked for the API without new certificates")

        rc.revoke(self.state, self.before, no_client)

    def test_nothing_recorded_revokes_nothing(self):
        def no_client():
            raise AssertionError("asked for the API without a record")

        rc.revoke(self.state, self.created, no_client)

    def test_a_missing_key_is_a_warning(self):
        rc.record(self.state, "")
        with unittest.mock.patch.object(rc, "keychain_certificates", return_value=self.created), \
                unittest.mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(rc.main(["revoke", "--state", str(self.state)]), 0)


class TokenTests(unittest.TestCase):
    def test_raw_signature_pads_r_and_s(self):
        r, s = b"\x00" + b"\x80" + b"\x01" * 31, b"\x02" * 31
        der = bytes([0x30, 4 + len(r) + len(s), 0x02, len(r)]) + r + bytes([0x02, len(s)]) + s
        self.assertEqual(rc.raw_signature(der), b"\x80" + b"\x01" * 31 + b"\x00" + b"\x02" * 31)

    def test_a_token_has_three_parts(self):
        with tempfile.TemporaryDirectory() as folder:
            key = Path(folder, "AuthKey.p8")
            subprocess.run(["openssl", "genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256",
                            "-out", key], check=True, capture_output=True)
            parts = rc.token("KEY", "ISSUER", str(key), now=0).split(".")
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(rc.base64.urlsafe_b64decode(parts[2] + "==")), 64)


if __name__ == "__main__":
    unittest.main()
