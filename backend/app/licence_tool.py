"""The owner's tool for licences (run on the owner's own computer, never on a rented server).

    python -m app.licence_tool keygen owner-key.pem         # once: a private key file and the public key
    python -m app.licence_tool issue owner-key.pem "Tashkilot nomi" 2027-12-31 --members 2000

Keep ``owner-key.pem`` secret. Put the printed public key into ``LICENCE_PUBLIC_KEY`` of every rented
copy and the issued licence into ``LICENCE_KEY`` (with ``LICENCE_REQUIRED=true``).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from app.core import licence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="licence_tool")
    commands = parser.add_subparsers(dest="command", required=True)
    keygen = commands.add_parser("keygen", help="make the owner's key pair")
    keygen.add_argument("private_key_file")
    issue = commands.add_parser("issue", help="sign a licence for one organisation")
    issue.add_argument("private_key_file")
    issue.add_argument("organization")
    issue.add_argument("until", type=date.fromisoformat)
    issue.add_argument("--members", type=int, default=None)
    args = parser.parse_args(argv)

    if args.command == "keygen":
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        path = Path(args.private_key_file)
        if path.exists():
            print(f"{path} allaqachon bor — ustiga yozilmaydi.", file=sys.stderr)
            return 1
        private = Ed25519PrivateKey.generate()
        path.write_bytes(
            private.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        )
        path.chmod(0o600)
        public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        print(f"Maxfiy kalit: {path} (hech kimga bermang)")
        print(f"LICENCE_PUBLIC_KEY={licence.b64encode(public)}")
        return 0
    key = licence.sign(
        Path(args.private_key_file).read_bytes(), organization=args.organization, until=args.until, members=args.members
    )
    print(f"LICENCE_KEY={key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
