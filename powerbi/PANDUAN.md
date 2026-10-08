# Panduan Membangun Dashboard Klaim di Power BI

Panduan ini untuk yang baru pertama kali memakai Power BI. Datanya sudah disiapkan dalam bentuk
**star schema**: satu tabel fakta berisi transaksi klaim, dikelilingi tabel dimensi yang
menjelaskan siapa, apa, di mana, dan kapan.

```
                 dim_polis
                     |
dim_diagnosis -- fakta_klaim -- dim_lokasi
                     |
                 dim_tanggal

prediksi_bulanan   ibnr   kualitas_data      (berdiri sendiri, tanpa relasi)
```

## 0. Persiapan

1. **Kosongkan drive C minimal 3-4 GB.** Power BI Desktop terpasang di drive C.
2. **Pasang Power BI Desktop** (gratis) dari Microsoft Store.
3. **Buat tabelnya.** Dari folder utama proyek:

   ```
   venv\Scripts\activate
   python -m src.ekspor_powerbi
   ```

   Hasilnya ada di `data/powerbi/`: satu file CSV per tabel, plus `klaim.db` (SQLite) berisi
   tabel yang sama untuk dicek dengan SQL.

## 1. Atur format angka sebelum impor

Ini langkah yang paling sering terlewat. File CSV memakai titik sebagai desimal (`28093653.0`).
Kalau Windows memakai pengaturan Indonesia, Power BI bisa membaca titik itu sebagai pemisah
ribuan, sehingga nilai klaim menjadi sepuluh kali lipat.

**File → Options and settings → Options → Current File → Regional Settings → Locale for import:
English (United States).**

## 2. Impor tabel

**Home → Get data → Text/CSV**, lalu pilih file satu per satu dari `data/powerbi/`:

| File | Isi |
|---|---|
| `fakta_klaim.csv` | Satu baris per klaim, plus penanda audit A-F |
| `dim_polis.csv` | Plan, usia, gender, domisili, premi murni per polis |
| `dim_diagnosis.csv` | Kode ICD, deskripsi, bab diagnosis |
| `dim_lokasi.csv` | Lokasi RS dan kelompoknya (Indonesia, luar negeri, tidak spesifik) |
| `dim_tanggal.csv` | Kalender harian 2024-2025 |
| `prediksi_bulanan.csv` | Aktual dan prediksi dengan batas bawah/atas |
| `ibnr.csv` | Estimasi cadangan chain-ladder dan Bornhuetter-Ferguson |
| `kualitas_data.csv` | Daftar masalah data dan perlakuannya |

Untuk setiap file, klik **Transform Data** (bukan Load) supaya bisa mengecek tipe kolomnya dulu.

## 3. Cek tipe kolom di Power Query

Klik ikon di kiri judul kolom untuk mengganti tipe:

- Semua kolom `tanggal...` dan `awal_bulan` → **Date**
- `nilai_disetujui`, `biaya_rs`, `premi_murni_tahunan`, dan kolom angka di `prediksi_bulanan` serta `ibnr` → **Decimal Number**
- Kolom penanda `a_...` sampai `f_...`, `jumlah_penanda`, `urut_usia` → **Whole Number**

Lalu **Close & Apply**.

## 4. Buat relasi

Buka **Model view** (ikon ketiga di kiri), lalu tarik kolom dari tabel fakta ke tabel dimensi:

| Dari `fakta_klaim` | Ke | Jenis |
|---|---|---|
| `nomor_polis` | `dim_polis[nomor_polis]` | banyak ke satu |
| `kode_icd` | `dim_diagnosis[kode_icd]` | banyak ke satu |
| `lokasi_rs` | `dim_lokasi[lokasi_rs]` | banyak ke satu |
| `tanggal_masuk` | `dim_tanggal[tanggal]` | banyak ke satu |

Arah filter biarkan **Single**. Bulan klaim dihitung dari tanggal masuk RS, sama dengan seluruh
proyek, jadi relasi tanggal memakai `tanggal_masuk`, bukan `tanggal_bayar`.

Jangan buat relasi untuk `prediksi_bulanan`, `ibnr`, dan `kualitas_data`.

## 5. Tandai tabel kalender

Klik kanan `dim_tanggal` → **Mark as date table** → pilih kolom `tanggal`. Tanpa langkah ini,
measure perbandingan waktu seperti "bulan lalu" dan "rata-rata 6 bulan" memberi hasil salah.

Selagi di sini, atur urutan kelompok usia: pilih kolom `dim_polis[kel_usia]` → **Sort by column**
→ `urut_usia`. Tanpa itu, "<30" diurutkan setelah "70+".

## 6. Buat measure

Measure adalah rumus yang dihitung ulang setiap kali filter berubah. Semua rumusnya ada di
[`measures.dax`](measures.dax).

1. Buat tabel kosong untuk menampung measure: **Home → Enter data**, beri nama `_Measure`, Load.
2. Pilih tabel `_Measure`, lalu **New measure**.
3. Salin satu rumus dari `measures.dax`, misalnya `Jumlah Klaim = COUNTROWS ( fakta_klaim )`.
4. Ulangi untuk semua rumus, **berurutan dari atas**, karena measure di bawah memakai measure di atasnya.
5. Atur format: pilih measure, lalu di tab **Measure tools** pilih Currency atau Percentage.

## 7. Susun halaman

### Halaman 1 — Ringkasan

- **Card**: Jumlah Klaim, Total Klaim, Severity, Rasio Persetujuan, Porsi Luar Negeri
- **Line chart**: sumbu `dim_tanggal[awal_bulan]`, nilai `Total Klaim`
- **Slicer**: `dim_polis[plan]`, `fakta_klaim[jenis_perawatan]`, `dim_lokasi[kelompok]`

### Halaman 2 — Prediksi dan cadangan

- **Line chart**: sumbu `prediksi_bulanan[awal_bulan]`, nilai `Aktual Total`, `Prediksi Total`,
  `Batas Bawah Total`, `Batas Atas Total`
- **Card**: IBNR Bornhuetter-Ferguson, IBNR Chain-Ladder
- **Table**: kolom `ibnr[bulan_kejadian]`, `dibayar`, `ultimate_CL`, `ultimate_BF`, `aktual_sampai_des_2025`

### Halaman 3 — Diagnosis dan lokasi

- **Bar chart**: `dim_diagnosis[bab_icd]` dengan `Total Klaim`, diurutkan dari terbesar
- **Matrix**: baris `dim_lokasi[kelompok]`, kolom `fakta_klaim[jenis_perawatan]`, nilai `Total Klaim`

### Halaman 4 — Audit

- **Card**: Klaim Ditandai, Klaim Prioritas Audit, Nilai Klaim Ditandai
- **Card** atau **bar chart**: enam measure Aturan A sampai F
- **Table**: `claim_id`, `nomor_polis`, `lokasi_rs`, `nilai_disetujui`, `biaya_rs`, `jumlah_penanda`,
  dengan filter visual `jumlah_penanda` lebih dari atau sama dengan 2

### Halaman 5 — Premi murni

- **Matrix**: baris `dim_polis[kel_usia]`, kolom `dim_polis[plan]`, nilai `Premi Murni Rata-rata`
- Tambahkan conditional formatting (background color) supaya kelompok mahal langsung terlihat

## 8. Cek angkamu

Angka di Power BI harus sama dengan hasil Python. Kalau berbeda, biasanya penyebabnya format angka
(langkah 1), relasi (langkah 4), atau tabel kalender yang belum ditandai (langkah 5).

| Yang dicek | Filter | Angka yang benar |
|---|---|---|
| Jumlah Klaim | tanpa filter | 4.627 |
| Total Klaim | tanpa filter | Rp254.618.833.553 |
| Rasio Persetujuan | tanpa filter | 91,79% |
| Porsi Luar Negeri | tanpa filter | 57,08% |
| Polis Pernah Klaim | tanpa filter | 1.210 |
| Klaim Ditandai | tanpa filter | 115 |
| Jumlah Klaim | Juli 2025 | 264 |
| Total Klaim | Juli 2025 | Rp13.699.226.392 |
| Perubahan vs Bulan Lalu | Juli 2025 | 2,44% |
| Rata-rata 6 Bulan | tanpa filter | Rp13.603.861.892 |
| Prediksi Kompetisi | tanpa filter | Rp12.923.668.797 (sama dengan prediksi notebook 02) |

Baris terakhir adalah bukti terkuat: metode forecasting Python dan rumus DAX memberi angka yang
persis sama.

## 9. Simpan dan bagikan

- Simpan sebagai `powerbi/dashboard_klaim.pbix`. **File `.pbix` tidak ikut di-commit** (sudah
  di-gitignore), karena di dalamnya tersimpan salinan data kompetisi.
- Untuk portofolio, ambil screenshot tiap halaman, simpan di `powerbi/gambar/`, lalu tampilkan di
  README. Bisa juga **File → Export → Export to PDF**.
- **Publish to web** di Power BI Service butuh akun kerja atau sekolah, dan sering dimatikan oleh
  admin kampus. Screenshot dan PDF adalah cara paling pasti.

## Catatan

Rumus di `measures.dax` belum diuji langsung di Power BI, karena Power BI tidak terpasang di
komputer tempat rumus ini ditulis. Angka pembanding di langkah 8 dihitung dari data yang sama
dengan Python. Kalau ada rumus yang error atau angkanya berbeda, catat pesan error-nya untuk
ditelusuri.
