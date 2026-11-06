# Bond Terminal

Dashboard bergaya terminal yang memantau bond market terhadap aset berisiko. Data ditarik otomatis dari FRED setiap hari kerja oleh GitHub Actions, dianalisa dengan aturan sederhana, lalu ditampilkan lewat GitHub Pages.

Indikator utama:

| Seri FRED | Peran |
|---|---|
| `BAMLH0A0HYM2` | HY credit spread, sinyal **cepat** (pengukur rasa takut) |
| `T10Y2Y` | Selisih 10Y-2Y, sinyal **lambat** (prakiraan cuaca) |
| `DGS10`, `DGS2` | Yield Treasury 10Y dan 2Y (harga uang) |
| `BAMLC0A0CM` | IG credit spread (pembanding) |
| `SP500`, `VIXCLS`, `CBBTCUSD` | Aset berisiko: saham, volatilitas, Bitcoin |

## Cara pasang (sekitar 5 menit)

1. Di GitHub, buat repo baru (misalnya `bond-terminal`). Public paling mudah, karena Pages gratis untuk repo public.
2. Unggah seluruh isi folder ini ke repo (termasuk folder tersembunyi `.github`). Lewat web: **Add file > Upload files**, atau pakai `git push`.
3. **Settings > Pages**: Source = *Deploy from a branch*, Branch = `main`, folder = `/docs`. Simpan.
4. **Settings > Actions > General > Workflow permissions**: pilih *Read and write permissions*. Simpan.
5. Buka tab **Actions > update-data > Run workflow** untuk menjalankan pertama kali.
6. Setelah selesai (sekitar 1 menit), dashboard muncul di `https://<username>.github.io/<nama-repo>/`.

Setelah itu, workflow berjalan otomatis Selasa-Sabtu pukul 08:00 WIB (data penutupan hari bursa AS sebelumnya).

## Menjalankan di komputer sendiri

```bash
python scripts/update.py          # tarik data + hitung analisa
python -m http.server -d docs     # buka http://localhost:8000
```

Butuh Python 3.10+. Tidak ada library tambahan dan tidak perlu API key.

## Mengubah ambang

Edit `config.json`. Semua ambang adalah asumsi awal (bukan standar baku): HY spread waspada 3,5% / bahaya 4,0%, dan kenaikan 0,25 / 0,5 poin dalam 5 observasi.

## Cara kerja analisa

- **Status spread**: TENANG / WASPADA / BAHAYA dari level HY spread dan kecepatan kenaikannya dalam 5 observasi.
- **Kuadran**: yield (naik atau tidak dalam 20 observasi) x spread (tipis atau melebar) menghasilkan salah satu dari optimisme pertumbuhan, stagflasi, Goldilocks, atau resesi.
- **Kurva**: Normal / Datar / Inversi, plus catatan bila baru keluar dari inversi.
- **Aset berisiko**: perubahan 20 hari, jarak dari puncak, VIX, dan korelasi 60 hari antara perubahan yield dan return S&P 500.
- Semua teks analisa dibuat dari aturan tetap di `scripts/update.py`, tidak memakai AI saat berjalan.

## Uji offline

```bash
python tests/make_fixtures.py /tmp/fx      # data SINTETIS, bukan data pasar
python scripts/update.py --fixtures /tmp/fx
```

Hapus folder `data/` dan `docs/data.json` hasil uji sebelum commit.

## Catatan

- Data FRED biasanya terlambat satu hari kerja. Seri ICE BofA (`BAML...`) kemungkinan hanya menampilkan sekitar 3 tahun terakhir karena batasan lisensi.
- GitHub bisa menonaktifkan workflow terjadwal pada repo yang tidak aktif lama. Bila itu terjadi, aktifkan kembali dari tab Actions.
- Bukan saran investasi.
