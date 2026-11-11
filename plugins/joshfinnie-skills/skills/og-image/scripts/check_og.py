#!/usr/bin/env python3
"""Check a page's Open Graph / Twitter card tags and the image they point to.

Usage: check_og.py <page-url> [--out path/to/save.png]
Exits non-zero if a required tag is missing or the image is not a 1200x630 PNG/JPEG.
"""

import argparse
import html.parser
import struct
import sys
import urllib.parse
import urllib.request

REQUIRED = ["og:title", "og:image", "twitter:card"]
RECOMMENDED = ["og:description", "og:image:alt", "og:image:width", "og:image:height", "twitter:image"]
UA = "Mozilla/5.0 (compatible; og-check/1.0; +https://ogp.me)"


class MetaParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        a = dict(attrs)
        key = a.get("property") or a.get("name")
        if key and (key.startswith("og:") or key.startswith("twitter:")) and key not in self.tags:
            self.tags[key] = a.get("content", "")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def image_size(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return "png", w, h
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                return "jpeg", w, h
            i += 2 + struct.unpack(">H", data[i + 2 : i + 4])[0]
    return "unknown", None, None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--out")
    args = p.parse_args()

    problems = []
    status, _, body = fetch(args.url)
    parser = MetaParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    tags = parser.tags

    print(f"page {args.url} -> {status}")
    for k in REQUIRED + RECOMMENDED:
        v = tags.get(k)
        mark = "ok  " if v else ("MISS" if k in REQUIRED else "warn")
        print(f"  {mark} {k}: {v if v else '-'}")
        if not v and k in REQUIRED:
            problems.append(f"missing {k}")

    if tags.get("twitter:card") and tags["twitter:card"] != "summary_large_image":
        problems.append(f"twitter:card is {tags['twitter:card']!r}, want 'summary_large_image'")

    img = tags.get("og:image")
    if img:
        if not urllib.parse.urlparse(img).scheme:
            problems.append("og:image is relative; unfurlers need an absolute URL (set metadataBase / site)")
            img = urllib.parse.urljoin(args.url, img)
        s, ctype, data = fetch(img)
        kind, w, h = image_size(data)
        print(f"image {img} -> {s} {ctype} {kind} {w}x{h} {len(data) // 1024}KB")
        if s != 200:
            problems.append(f"image returned {s}")
        if (w, h) != (1200, 630):
            problems.append(f"image is {w}x{h}, want 1200x630")
        if len(data) > 5 * 1024 * 1024:
            problems.append("image is over 5MB; some platforms drop it")
        if args.out:
            with open(args.out, "wb") as f:
                f.write(data)
            print(f"saved {args.out}")

    if problems:
        print("\nproblems:")
        for pr in problems:
            print(f"  - {pr}")
        sys.exit(1)
    print("\nall good")


if __name__ == "__main__":
    main()
