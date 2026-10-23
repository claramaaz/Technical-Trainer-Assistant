"""Download one FAA handbook listed in corpus/handbooks.csv and verify it.

Usage (from the repository root):
    python ingestion/download_handbook.py FAA-H-8083-15B

What it does, in order:
 1. Looks up the handbook id in corpus/handbooks.csv (URL + licence).
 2. Asks the server for the file size BEFORE downloading (brief, section 3, step 2).
 3. Streams the PDF to data/raw/<id>.pdf in 1 MB pieces (works for 200 MB files).
 4. Verifies: byte count matches the server's size, file starts with %PDF-,
    file ends with %%EOF.
 5. Writes data/raw/<id>.meta.json with source URL, licence, retrieval date,
    size and SHA-256 (business rule BR-001).

Only the Python standard library is used, so nothing needs to be installed.
"""
import csv
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = REPO_ROOT / "corpus" / "handbooks.csv"
RAW_DIR = REPO_ROOT / "data" / "raw"          # data/ is in .gitignore
CHUNK = 1024 * 1024                            # 1 MB
# Some CDNs reject Python's default user agent; identify like the curl commands in the brief.
HEADERS = {"User-Agent": "curl/8.0 (ESIB P7 student project)"}


def find_handbook(handbook_id):
    with open(CATALOGUE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["id"] == handbook_id:
                return row
    sys.exit(f"ERROR: {handbook_id} is not listed in {CATALOGUE}")


def remote_size(url):
    req = urllib.request.Request(url, method="HEAD", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        size = resp.headers.get("Content-Length")
        return int(size) if size else None


def download(url, dest):
    tmp = dest.with_suffix(".part")            # never leave a half file named .pdf
    sha = hashlib.sha256()
    written = 0
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as resp, open(tmp, "wb") as out:
        while True:
            block = resp.read(CHUNK)
            if not block:
                break
            out.write(block)
            sha.update(block)
            written += len(block)
            print(f"\r  {written / 1e6:8.1f} MB", end="", flush=True)
    print()
    tmp.replace(dest)
    return written, sha.hexdigest()


def looks_like_pdf(path):
    with open(path, "rb") as f:
        head = f.read(5)
        f.seek(-1024, 2)                       # last 1 KB
        tail = f.read()
    return head == b"%PDF-" and b"%%EOF" in tail


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python ingestion/download_handbook.py <handbook-id>")
    hb = find_handbook(sys.argv[1])
    if not hb["licence"].strip():
        sys.exit("ERROR: no licence recorded for this handbook (BR-001). Not downloading.")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / f"{hb['id']}.pdf"

    expected = remote_size(hb["url"])
    print(f"Server reports size: {expected} bytes" if expected else "Server did not report a size")

    print(f"Downloading {hb['url']}")
    written, sha256 = download(hb["url"], dest)

    errors = []
    if expected is not None and written != expected:
        errors.append(f"size mismatch: got {written}, server said {expected}")
    if not looks_like_pdf(dest):
        errors.append("file does not start with %PDF- or has no %%EOF marker")
    if errors:
        sys.exit("DOWNLOAD FAILED: " + "; ".join(errors))

    meta = {
        "id": hb["id"],
        "title": hb["title"],
        "source_url": hb["url"],
        "licence": hb["licence"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": written,
        "sha256": sha256,
    }
    (RAW_DIR / f"{hb['id']}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"OK: {dest} ({written} bytes, sha256 {sha256[:12]}...)")


if __name__ == "__main__":
    main()
