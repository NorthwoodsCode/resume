#!/usr/bin/env python3
"""Generate qr-resume.svg, the QR code printed on the PDF/paper resume.

The code points at the live site so a printed copy leads back to the
interactive one. The SVG is committed (it only changes if the URL changes),
so this script is run by hand, not at deploy time.

    python3 scripts/gen_qr.py            # writes qr-resume.svg at the repo root
    python3 scripts/gen_qr.py --url ...  # encode a different URL

Requires the `qrcode` package (python3-qrcode on Debian/Ubuntu/Mint).
"""
import argparse
from pathlib import Path

import qrcode
import qrcode.image.svg

REPO = Path(__file__).resolve().parent.parent
DEFAULT_URL = "https://northwoodscode.github.io/resume/"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--out", default=str(REPO / "qr-resume.svg"))
    args = p.parse_args()
    # Error correction M survives the usual print smudges; the 4-module quiet zone
    # the spec asks for keeps the code scannable when it sits next to text.
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(args.url)
    qr.make(fit=True)
    img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    img.save(args.out)
    print(f"Saved {args.out} for {args.url} (version {qr.version}, {qr.modules_count} modules)")


if __name__ == "__main__":
    main()
