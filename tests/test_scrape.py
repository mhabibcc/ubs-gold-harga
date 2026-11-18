"""Jalankan: python -m unittest discover tests"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scraper"))
import scrape  # noqa: E402

ROWS = [
    ("0.05", 208500, 112000), ("0.1", 332400, 224000), ("0.25", 756700, 561000),
    ("0.5", 1364600, 1122000), ("1", 2417600, 2244000), ("2", 4774100, 4488000),
    ("3", 7144100, 6732000), ("4", 9490200, 8976000), ("5", 11706800, 11220000),
    ("10", 23208000, 22441000), ("25", 57833400, 56104000), ("50", 115260000, 112208000),
    ("100", 230361800, 224416000),
]


def rp(n):
    return "Rp" + f"{n:,}".replace(",", ".")


def page(rows=ROWS, date="17 November 2026"):
    trs = "".join(
        f'<tr><td>{g} Gram</td><td style="display:none" class="beli">{rp(b)}</td><td>{rp(s)}</td></tr>'
        for g, b, s in rows
    )
    return f"""<html><body><nav>Menu</nav><script>var x = "1 Januari 2020";</script>
    <h1>Harga BuyBack UBS Gold Bar</h1><h6>Updated</h6><div>Date</div><div>{date}</div>
    <div>Time</div><div>09:39:28 WIB</div>
    <table><tr><th>Pecahan</th><th>Harga Beli</th><th>Harga Jual<br>(Buyback)</th></tr>{trs}</table>
    </body></html>"""


class ParseTest(unittest.TestCase):
    def test_parse_full_table(self):
        tanggal, harga = scrape.parse(page())
        self.assertEqual(tanggal, "2026-11-17")
        self.assertEqual(len(harga), 13)
        self.assertEqual(harga[4], {"gram": 1, "beli": 2417600, "buyback": 2244000, "tanggal": "2026-11-17"})
        self.assertEqual(harga[0]["gram"], 0.05)

    def test_missing_row_fails(self):
        with self.assertRaises(scrape.CheckError):
            scrape.parse(page(ROWS[:-1]))

    def test_beli_not_above_buyback_fails(self):
        rows = list(ROWS)
        rows[4] = ("1", 2000000, 2244000)
        tanggal, harga = scrape.parse(page(rows))
        with self.assertRaises(scrape.CheckError):
            scrape.check(tanggal, harga, [])


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        src = Path(__file__).resolve().parent.parent / "data"
        for f in src.glob("*.json"):
            shutil.copy(f, self.tmp / f.name)
        self._data = scrape.DATA
        scrape.DATA = self.tmp

    def tearDown(self):
        scrape.DATA = self._data
        shutil.rmtree(self.tmp)

    def read(self, name):
        return json.loads((self.tmp / name).read_text())

    def test_same_day_rerun_keeps_previous(self):
        before_prev = self.read("harga-sebelumnya.json")
        n = len(self.read("riwayat.json"))
        scrape.update(*scrape.parse(page()))
        self.assertEqual(self.read("harga-sebelumnya.json"), before_prev)
        self.assertEqual(len(self.read("riwayat.json")), n)

    def test_new_day_rotates_and_appends(self):
        old = self.read("harga.json")
        n = len(self.read("riwayat.json"))
        scrape.update(*scrape.parse(page(date="18 November 2026")))
        self.assertEqual(self.read("harga-sebelumnya.json"), old)
        self.assertEqual(self.read("harga.json")[0]["tanggal"], "2026-11-18")
        riw = self.read("riwayat.json")
        self.assertEqual(len(riw), n + 1)
        self.assertEqual(riw[-1]["tanggal"], "2026-11-18")

    def test_older_date_rejected(self):
        with self.assertRaises(scrape.CheckError):
            scrape.update(*scrape.parse(page(date="1 November 2026")))


if __name__ == "__main__":
    unittest.main()
