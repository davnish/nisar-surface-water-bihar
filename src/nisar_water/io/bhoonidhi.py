"""Bhoonidhi (NRSC/ISRO) STAC API client for NISAR S-band (SSAR) products.

API: https://bhoonidhi.nrsc.gov.in/bhoonidhi-api/ (Data Access SIS). Credentials are read from a local env
file (default `bhoonidhi.env`, git-ignored: USERNAME=..., PASSWORD=...) and are never logged.
Rate limits (per IP): auth 20/h, search 3/s, download 2/min and <= 5 concurrent; the token is cached on
disk (data/.bhoonidhi_token.json, git-ignored) and refreshed instead of re-requested.
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path

import requests

from nisar_water import REPO_ROOT

API = "https://bhoonidhi-api.nrsc.gov.in"
TOKEN_CACHE = REPO_ROOT / "data" / ".bhoonidhi_token.json"


def _creds(env_file: Path) -> tuple[str, str]:
    kv = {}
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            kv[k.strip()] = v.strip().strip('"').strip("'")
    user = kv.get("USERNAME") or kv.get("USER") or kv.get("NAME") or kv.get("USERID")
    if not user or "PASSWORD" not in kv:
        raise KeyError(f"{env_file.name} needs USERNAME and PASSWORD")
    return user, kv["PASSWORD"]


class Bhoonidhi:
    def __init__(self, env_file: Path = REPO_ROOT / "bhoonidhi.env"):
        self.env_file = env_file
        self.user, self._pw = _creds(env_file)
        self.s = requests.Session()
        self.tok: dict = {}
        if TOKEN_CACHE.exists():
            t = json.loads(TOKEN_CACHE.read_text())
            if t.get("userId") == self.user:
                self.tok = t

    def _save(self, t: dict) -> None:
        t["obtained"] = time.time()
        self.tok = t
        TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE.write_text(json.dumps(t))
        TOKEN_CACHE.chmod(0o600)

    def token(self) -> str:
        age = time.time() - self.tok.get("obtained", 0)
        if self.tok and age < float(self.tok.get("expires_in", 1200)) - 60:
            return self.tok["access_token"]
        if self.tok.get("refresh_token"):
            r = self.s.post(f"{API}/auth/token", json={"userId": self.user, "refresh_token": self.tok["refresh_token"],
                                                       "grant_type": "refresh_token"}, timeout=60)
            if r.ok:
                self._save(r.json())
                return self.tok["access_token"]
        r = self.s.post(f"{API}/auth/token", json={"userId": self.user, "password": self._pw, "grant_type": "password"},
                        timeout=60)
        if not r.ok:
            raise RuntimeError(f"Bhoonidhi auth failed: HTTP {r.status_code} {r.text[:200]}")
        self._save(r.json())
        return self.tok["access_token"]

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.token()}"}

    def collections(self) -> list[dict]:
        r = self.s.get(f"{API}/data/collections", headers=self._h(), timeout=60)
        r.raise_for_status()
        return r.json().get("collections", [])

    def search(self, collections: list[str], intersects: dict | None = None, datetime: str | None = None,
               filt: dict | None = None, limit: int = 500) -> list[dict]:
        body = {"collections": collections, "limit": limit}
        if intersects:
            body["intersects"] = intersects
        if datetime:
            body["datetime"] = datetime
        if filt:
            body.update({"filter": filt, "filter-lang": "cql2-json"})
        feats, url = [], f"{API}/data/search"
        while url:
            r = self.s.post(url, json=body, headers=self._h(), timeout=120)
            r.raise_for_status()
            j = r.json()
            feats += j.get("features", [])
            nxt = [l for l in j.get("links", []) if l.get("rel") == "next"]
            url, body = (nxt[0]["href"], nxt[0].get("body", body)) if nxt and j.get("features") else (None, None)
            time.sleep(0.5)
        return feats

    def download(self, item_id: str, collection: str, out_dir: Path, chunk_mb: int = 8) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        for attempt in range(6):
            r = self.s.get(f"{API}/download", params={"id": item_id, "collection": collection}, headers=self._h(),
                           stream=True, timeout=600, allow_redirects=True)
            if r.status_code in (429, 412, 504):
                time.sleep(60 * (attempt + 1))
                continue
            r.raise_for_status()
            cd = r.headers.get("content-disposition", "")
            name = cd.split("filename=")[-1].strip('"; ') if "filename=" in cd else f"{item_id}.h5"
            out = out_dir / name
            if out.exists() and out.stat().st_size == int(r.headers.get("content-length", -1)):
                r.close()
                return out
            tmp = out.with_suffix(out.suffix + ".part")
            with open(tmp, "wb") as f:
                for b in r.iter_content(chunk_mb * 2**20):
                    f.write(b)
            tmp.rename(out)
            return out
        raise RuntimeError(f"download of {item_id} failed after retries")


class RangeFile(io.RawIOBase):
    """Read-only, seekable file object over a Bhoonidhi download URL using HTTP range requests.

    Lets h5py read just the HDF5 metadata and the chunks of a bbox window instead of the full 12.6 GB granule.
    Blocks of `block_mb` are cached on disk (restart-safe). Requests are spaced >= `min_interval` s apart
    (download endpoint limit: 2 requests/min per IP) and retried after HTTP 429.
    """

    def __init__(self, client: "Bhoonidhi", item_id: str, collection: str, cache_dir: Path,
                 block_mb: float = 4, min_interval: float = 31.0, log=print):
        self.c, self.id, self.col = client, item_id, collection
        self.B = int(block_mb * 2**20)
        self.cache = cache_dir / item_id
        self.cache.mkdir(parents=True, exist_ok=True)
        self.min_interval, self.log = min_interval, log
        self.pos, self.n_fetch, self._last = 0, 0, 0.0
        size_f = self.cache / "size"
        if size_f.exists():
            self.size = int(size_f.read_text())
        else:
            self.size = int(self._get(0, 0)[1])
            size_f.write_text(str(self.size))

    def __str__(self):
        return f"{self.id}.h5"

    def _get(self, start: int, end: int) -> tuple[bytes, str]:
        for attempt in range(40):
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            r = self.c.s.get(f"{API}/download", params={"id": self.id, "collection": self.col},
                             headers={**self.c._h(), "Range": f"bytes={start}-{end}"}, timeout=600)
            if r.status_code == 206:
                return r.content, r.headers["Content-Range"].split("/")[-1]
            if r.status_code in (429, 412, 504, 502, 503):
                time.sleep(35)
                continue
            raise RuntimeError(f"range request failed: HTTP {r.status_code} {r.text[:200]}")
        raise RuntimeError("range request: too many retries")

    def _block(self, i: int) -> bytes:
        p = self.cache / f"{i}.bin"
        if p.exists():
            return p.read_bytes()
        t0 = time.time()
        data, _ = self._get(i * self.B, min(self.size, (i + 1) * self.B) - 1)
        p.write_bytes(data)
        self.n_fetch += 1
        self.log(f"  block {i} ({len(data) / 2**20:.1f} MB) in {time.time() - t0:.0f} s; fetched {self.n_fetch}")
        return data

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        out, got = memoryview(b), 0
        while got < n:
            i, o = divmod(self.pos + got, self.B)
            blk = self._block(i)
            k = min(n - got, len(blk) - o)
            out[got:got + k] = blk[o:o + k]
            got += k
        self.pos += n
        return n
