#!/usr/bin/env python3
"""Create a simple multi-page PDF from JPEG score pages without Python packages."""
from __future__ import annotations

import argparse
import glob
from pathlib import Path


def jpeg_size(data: bytes) -> tuple[int, int]:
    if data[:2] != b"\xff\xd8":
        raise ValueError("only JPEG files are supported")
    position = 2
    while position < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        marker = data[position + 1]
        position += 2
        if marker in {0xD8, 0xD9}:
            continue
        length = int.from_bytes(data[position:position + 2], "big")
        if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
            return (int.from_bytes(data[position + 5:position + 7], "big"),
                    int.from_bytes(data[position + 3:position + 5], "big"))
        position += length
    raise ValueError("JPEG dimensions not found")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", nargs="+", help="JPEG paths or glob patterns")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files = [Path(item) for pattern in args.pages for item in glob.glob(pattern)]
    if not files:
        parser.error("no JPEG pages found")
    objects: list[bytes] = []
    def add(data: bytes) -> int:
        objects.append(data); return len(objects)
    pages_id = add(b"")
    page_ids: list[int] = []
    for file in files:
        image = file.read_bytes(); width, height = jpeg_size(image)
        image_id = add((f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(image)} >>\nstream\n").encode() + image + b"\nendstream")
        content = f"q\n{width} 0 0 {height} 0 0 cm\n/Im0 Do\nQ\n".encode()
        content_id = add(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"endstream")
        page_ids.append(add(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {width} {height}] /Resources << /XObject << /Im0 {image_id} 0 R >> >> /Contents {content_id} 0 R >>".encode()))
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] /Count {len(page_ids)} >>".encode()
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"); offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result)); result.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(result); result.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    result.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    result.extend(f"trailer\n<< /Size {len(objects)+1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    args.output.write_bytes(result); print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
