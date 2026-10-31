"""Download only pinned validation archives, resume safely, verify full SHA256."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8*1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_range(status, headers, offset, size):
    if status == 206:
        expected = f"bytes {offset}-{size-1}/{size}"
        if headers.get("Content-Range") != expected:
            raise ValueError(f"Invalid range response; expected {expected}")
    elif status != 200 or offset != 0:
        raise ValueError("Server ignored resume range; refusing append")
    if headers.get("Content-Length") and int(headers["Content-Length"]) != size-offset:
        raise ValueError("Remote length differs from pinned size")


def download(split, metadata, revision, root):
    target = root / (split + ".tar")
    partial = root / (split + ".tar.part")
    size, expected_sha = metadata["size"], metadata["sha256"]
    started = time.monotonic()
    if target.exists():
        if target.stat().st_size != size or sha256(target) != expected_sha:
            raise ValueError(f"Existing {target.name} fails integrity; preserved for inspection")
        print(f"{split}: existing archive verified", flush=True)
        return
    for attempt in range(4):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > size:
            raise ValueError("Partial download exceeds expected size; preserved")
        if offset == size:
            break
        url = f"https://huggingface.co/datasets/fly1113/LCVN/resolve/{revision}/{split}.tar?download=true&offset={offset}"
        request = urllib.request.Request(url, headers={"Range":f"bytes={offset}-", "Accept-Encoding":"identity"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                check_range(response.status, response.headers, offset, size)
                with partial.open("ab") as stream:
                    last = time.monotonic()
                    while chunk := response.read(4*1024*1024):
                        if stream.tell()+len(chunk) > size:
                            raise ValueError("Download exceeds pinned size")
                        stream.write(chunk)
                        if time.monotonic()-last >= 20:
                            print(f"{split}: {stream.tell()/size:.1%} ({stream.tell()} bytes)", flush=True)
                            last = time.monotonic()
            if partial.stat().st_size == size:
                break
        except (OSError, TimeoutError) as exc:
            print(f"{split}: attempt {attempt+1} failed: {type(exc).__name__}; partial preserved", flush=True)
            if attempt == 3:
                raise
            time.sleep(min(30, 2**(attempt+1)))
    if not partial.exists() or partial.stat().st_size != size:
        raise ValueError(f"{split}: incomplete archive; partial preserved")
    actual = sha256(partial)
    if actual != expected_sha:
        raise ValueError(f"{split}: SHA256 mismatch; partial preserved, no extraction")
    partial.rename(target)
    record = dict(split=split, revision=revision, bytes=size, sha256=actual,
                  verified=True, seconds=time.monotonic()-started)
    (root / (split+".verified.json")).write_text(json.dumps(record, indent=2)+"\n")
    print(json.dumps(record), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--metadata", type=Path, default=ROOT/"configs/datasets.json")
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text())
    root = args.data_root.resolve() / "archives"
    root.mkdir(parents=True, exist_ok=True)
    remaining = sum(max(0, m["size"]-sum(p.stat().st_size for p in
        [root/(s+".tar"), root/(s+".tar.part")] if p.exists())) for s,m in metadata["splits"].items())
    if shutil.disk_usage(root).free < remaining + 5*1024**3:
        raise RuntimeError("Insufficient disk for validation archives plus 5 GiB reserve")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(download, split, item, metadata["revision"], root)
                   for split,item in metadata["splits"].items()]
        for future in futures:
            future.result()


if __name__ == "__main__":
    main()
