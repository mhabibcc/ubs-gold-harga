#!/usr/bin/env python3
"""Ambil harga UBS Gold Bar dari ubslifestyle.com dan perbarui file di data/.

- data/harga.json            : 13 pecahan untuk tanggal terbaru
- data/harga-sebelumnya.json : 13 pecahan untuk tanggal sebelumnya (dasar tanda naik/turun)
- data/riwayat.json          : satu baris per tanggal untuk 1 gram (buyback + beli)

Hanya pustaka standar Python. Keluar dengan kode != 0 bila pemeriksaan gagal,
dan dalam kasus itu tidak ada file yang ditulis.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = "https://ubslifestyle.com/harga-buyback-hari-ini/"
DATA = Path(__file__).resolve().parent.parent / "data"
GRAMS = [0.05, 0.1, 0.25, 0.5, 1, 2, 3, 4, 5, 10, 25, 50, 100]
MAX_JUMP = 0.15  # 1 gram buyback boleh bergeser maksimal 15% dari baris riwayat terakhir

BULAN = {
    "januari": 1, "january": 1, "februari": 2, "february": 2, "maret": 3, "march": 3,
    "april": 4, "mei": 5, "may": 5, "juni": 6, "june": 6, "juli": 7, "july": 7,
    "agustus": 8, "august": 8, "september": 9, "oktober": 10, "october": 10,
    "november": 11, "desember": 12, "december": 12,
}
DATE_RE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(BULAN) + r")\s+(\d{4})\b", re.I)
GRAM_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*gram\s*$", re.I)
RP_RE = re.compile(r"Rp\s*([\d.]+)", re.I)


class CheckError(Exception):
    pass


class _Page(HTMLParser):
    """Kumpulkan teks tiap sel tabel (termasuk kolom yang disembunyikan CSS) dan teks halaman."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.text: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = max(0, self._skip - 1)
        elif tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._skip:
            return
        self.text.append(data)
        if self._cell is not None:
            self._cell.append(data)


def rupiah(s: str) -> int:
    return int(s.replace(".", ""))


def parse(html: str) -> tuple[str, list[dict]]:
    p = _Page()
    p.feed(html)

    text = " ".join(" ".join(p.text).split())
    anchor = text.lower().find("updated")
    m = DATE_RE.search(text, anchor if anchor >= 0 else 0) or DATE_RE.search(text)
    if not m:
        raise CheckError("tanggal tidak ditemukan di halaman")
    d, mon, y = int(m.group(1)), BULAN[m.group(2).lower()], int(m.group(3))
    tanggal = f"{y:04d}-{mon:02d}-{d:02d}"

    found: dict[float, dict] = {}
    for row in p.rows:
        if not row:
            continue
        g = GRAM_RE.match(row[0])
        if not g:
            continue
        prices = [rupiah(x) for cell in row[1:] for x in RP_RE.findall(cell)]
        if len(prices) != 2:
            raise CheckError(f"baris {row[0]!r}: diharapkan 2 harga, dapat {len(prices)}")
        gram = float(g.group(1).replace(",", "."))
        gram = int(gram) if gram.is_integer() else gram
        found[gram] = {"gram": gram, "beli": prices[0], "buyback": prices[1], "tanggal": tanggal}

    if sorted(found) != GRAMS:
        raise CheckError(f"pecahan tidak lengkap: {sorted(found)}")
    return tanggal, [found[g] for g in GRAMS]


def check(tanggal: str, harga: list[dict], riwayat: list[dict]) -> None:
    for r in harga:
        if not (isinstance(r["beli"], int) and isinstance(r["buyback"], int)):
            raise CheckError(f"{r['gram']} g: harga bukan bilangan bulat")
        if r["beli"] <= r["buyback"]:
            raise CheckError(f"{r['gram']} g: harga beli tidak lebih tinggi dari buyback")
    for a, b in zip(harga, harga[1:]):
        if b["beli"] <= a["beli"] or b["buyback"] <= a["buyback"]:
            raise CheckError(f"harga tidak naik dari {a['gram']} g ke {b['gram']} g")
    if riwayat:
        last = max(riwayat, key=lambda r: r["tanggal"])
        one = next(r for r in harga if r["gram"] == 1)
        if abs(one["buyback"] - last["buyback"]) / last["buyback"] > MAX_JUMP:
            raise CheckError(f"buyback 1 g {one['buyback']} terlalu jauh dari {last['buyback']} ({last['tanggal']})")
        if tanggal < last["tanggal"]:
            raise CheckError(f"tanggal halaman {tanggal} lebih awal dari riwayat terakhir {last['tanggal']}")


def load(name: str) -> list[dict]:
    path = DATA / name
    return json.loads(path.read_text()) if path.exists() else []


def dump(name: str, rows: list[dict]) -> None:
    body = ",\n".join(json.dumps(r, separators=(",", ":")) for r in rows)
    (DATA / name).write_text("[\n" + body + "\n]\n")


def update(tanggal: str, harga: list[dict]) -> str:
    riwayat = load("riwayat.json")
    check(tanggal, harga, riwayat)

    lama = load("harga.json")
    lama_tgl = lama[0]["tanggal"] if lama else None
    if lama_tgl and tanggal > lama_tgl:
        dump("harga-sebelumnya.json", lama)  # hari baru: harga lama jadi pembanding
    dump("harga.json", harga)

    one = next(r for r in harga if r["gram"] == 1)
    baru = [r for r in riwayat if r["tanggal"] != tanggal]
    baru.append({"tanggal": tanggal, "buyback": one["buyback"], "beli": one["beli"]})
    baru.sort(key=lambda r: r["tanggal"])
    if len(baru) not in (len(riwayat), len(riwayat) + 1):
        raise CheckError("jumlah baris riwayat berubah tak wajar")
    dump("riwayat.json", baru)
    return f"{tanggal}: 1 g beli {one['beli']:,} / buyback {one['buyback']:,}".replace(",", ".")


def fetch(url: str = URL) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main(argv: list[str]) -> int:
    # Opsional: python scraper/scrape.py halaman.html  (untuk uji dengan file lokal)
    html = Path(argv[1]).read_text() if len(argv) > 1 else fetch()
    try:
        tanggal, harga = parse(html)
        print(update(tanggal, harga))
    except CheckError as e:
        print(f"GAGAL, tidak ada yang diubah: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
