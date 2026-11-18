# Harga Emas UBS

Halaman statis harga beli dan buyback UBS Gold Bar (13 pecahan) dengan tanda ▲/▼ dibanding hari sebelumnya, plus grafik riwayat 1 gram. Data diambil otomatis dari <https://ubslifestyle.com/harga-buyback-hari-ini/> oleh GitHub Actions.

```
index.html                    halaman (tanpa build, tanpa pustaka luar)
data/harga.json               13 pecahan, tanggal terbaru
data/harga-sebelumnya.json    13 pecahan, tanggal sebelumnya (dasar ▲/▼)
data/riwayat.json             1 gram per tanggal: buyback (sejak Nov 2023) + beli (sejak 16 Nov 2026)
scraper/scrape.py             pengambil data, hanya pustaka standar Python
.github/workflows/update.yml  jadwal Senin–Jumat 10:17 & 13:17 WIB
tests/                        python -m unittest discover tests
```

## Pasang di GitHub Pages

1. Buat repo baru, push isi folder ini.
2. **Settings → Pages**: Source = *Deploy from a branch*, branch `main`, folder `/ (root)`.
3. **Actions → Update harga UBS → Run workflow** sekali untuk memastikan scraper jalan dari server GitHub.

Workflow butuh izin tulis (`permissions: contents: write` sudah diset). Kalau repo ada di organisasi yang membatasi, aktifkan *Read and write permissions* di Settings → Actions → General.

## Buka di PC lokal

`fetch()` tidak jalan dari `file://`, jadi pakai server lokal:

```bash
python -m http.server 8000      # lalu buka http://localhost:8000
python scraper/scrape.py        # perbarui data manual
```

## Pengaman

Scraper tidak menulis apa pun (dan keluar dengan kode 1, sehingga run Actions gagal dan GitHub mengirim email) bila: tabel tidak lengkap 13 baris, harga beli ≤ buyback, harga tidak naik seiring gram, buyback 1 gram bergeser > 15% dari riwayat terakhir, atau tanggal halaman lebih lama dari riwayat. Run ulang di tanggal yang sama hanya menimpa baris tanggal itu.
