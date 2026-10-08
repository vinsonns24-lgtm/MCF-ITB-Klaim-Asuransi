# Prediksi Klaim Asuransi Kesehatan

Proyek untuk Data Science Competition **Mathematical Challenge Festival (MCF) ITB 2026**, dikerjakan ulang sebagai proyek portofolio.

Sebuah portofolio asuransi kesehatan individu berisi 4.096 polis dan 4.627 klaim yang terjadi antara Januari 2024 dan Juli 2025. Proyek ini menjawab dua pertanyaan:

1. **Berapa frekuensi, severity (rata-rata nilai per klaim), dan total klaim per bulan untuk Agustus sampai Desember 2025?** Dinilai dengan MAPE untuk masing-masing target, lalu dirata-rata.
2. **Faktor apa yang paling menentukan nilai sebuah klaim?** Supaya perusahaan bisa menentukan langkah seleksi risiko, pencegahan, dan deteksi dini.

## Hasil

### Forecasting

Sepuluh metode dibandingkan dengan *rolling-origin backtest*: dari setiap bulan antara Juni 2024 dan Februari 2025, metode hanya melihat data sebelumnya, memprediksi 5 bulan ke depan, lalu dicocokkan dengan data asli. Horizon 5 bulan sama dengan tugas kompetisi.

| Metode | Frekuensi | Severity | Total | Skor gabungan |
|---|---|---|---|---|
| **Rata-rata 6 bulan × 0,95 (final)** | **7,6%** | **10,5%** | **11,7%** | **9,9%** |
| Rata-rata 6 bulan | 8,1% | 10,9% | 12,4% | 10,5% |
| Rata-rata semua bulan | 9,0% | 12,0% | 14,3% | 11,8% |
| Holt dengan tren teredam | 8,7% | 14,0% | 17,8% | 13,5% |
| Tren linear | 9,8% | 16,7% | 22,8% | 16,4% |

Metode yang menangkap tren justru lebih buruk. Jumlah nasabah tidak bertambah dan deretnya hanya 19 bulan, jadi "tren" yang ditangkap lebih banyak berupa kebetulan. Faktor 0,95 dipakai karena MAPE membagi error dengan nilai aktual, sehingga prediksi terbaik menurut MAPE cenderung sedikit di bawah rata-rata. Faktor ini memperbaiki ketiga target sekaligus.

Prediksi final: sekitar **225 klaim per bulan**, severity **Rp54,5 juta**, dan total **Rp12,9 miliar** per bulan. Ketiga target diprediksi dan dinilai terpisah, jadi 225 × Rp54,5 juta (Rp12,3 miliar) tidak sama persis dengan prediksi total.

### Faktor penentu nilai klaim

Model LightGBM untuk nilai per klaim (skala log), divalidasi dengan GroupKFold per nomor polis, menjelaskan sekitar separuh variasi nilai klaim (R² 0,50, dibanding 0,15 untuk patokan rata-rata per jenis perawatan). Urutan faktor menurut SHAP:

1. **Lama rawat.** Median klaim tanpa menginap Rp2,9 juta, rawat lebih dari 10 hari Rp199 juta.
2. **Lokasi rumah sakit.** Singapura hanya 22% jumlah klaim tetapi 50% total nilai. Median klaim di Singapura Rp53 juta, di Indonesia Rp9 juta. Plan dan lokasi saling terkait: semua klaim plan M-003 terjadi di Indonesia, sedangkan separuh klaim plan M-001 di Singapura. Di model, pengaruh plan kecil setelah lokasi RS diketahui.
3. **Diagnosis.** Kanker (bab ICD C, 30%), jantung dan pembuluh darah (bab I, 16%), serta otot dan tulang (bab M, 12%) menyumbang 58% total klaim.
4. **Jenis perawatan** dan **cara klaim** (cashless atau reimburse).

Usia, plan, domisili, dan gender pengaruhnya kecil.

### Analitik asuransi lanjutan

Notebook 04 memperluas proyek ke empat pertanyaan yang dihadapi perusahaan asuransi sehari-hari.

| Pertanyaan | Metode | Hasil |
|---|---|---|
| Seberapa jauh prediksi bisa meleset? | Rentang dari rasio aktual/prediksi di backtest | Total klaim per bulan Rp10,7-16,8 miliar (rentang 80%). Diuji tanpa kebocoran, rentang ini menangkap 76% kasus |
| Berapa klaim yang sudah terjadi tapi belum dibayar (IBNR)? | Segitiga pengembangan, chain-ladder vs Bornhuetter-Ferguson, diuji di 10 tanggal valuasi | Untuk bulan terbaru, chain-ladder meleset 47-94%, Bornhuetter-Ferguson 11-12% |
| Berapa biaya klaim wajar per nasabah? | GLM Negative Binomial (frekuensi) x Gamma (severity) | Usia faktor terkuat; plan M-003 klaim sekitar separuh lebih jarang |
| Klaim mana yang layak diperiksa ulang? | Enam aturan penanda audit | 115 klaim bertanda, 29 di antaranya dua tanda atau lebih |

Tiga temuan yang paling penting:

- **Prediksi kompetisi bukan angka anggaran.** Faktor 0,95 sengaja menurunkan prediksi demi MAPE. Untuk anggaran, angka yang tepat adalah median (Rp13,2 miliar), dan untuk kesiapan kas adalah batas atas.
- **Pembayaran klaim makin cepat.** Median jeda dari pasien pulang sampai dibayar turun dari 77-79 hari (awal 2024) menjadi 52-59 hari. Chain-ladder mengasumsikan kecepatan tetap, sehingga cadangannya kebesaran. Kalau hanya melihat total, chain-ladder malah terlihat lebih akurat karena kelebihan dan kekurangannya saling menutupi.
- **Klaim berlokasi "Overseas" 71% disetujui melebihi tagihan RS**, padahal di lokasi lain kurang dari 1%. Kemungkinan selisih kurs, tetapi pola terpusat seperti ini layak dicek tim klaim.

### Dashboard Power BI

Folder [`powerbi/`](powerbi/) berisi panduan membangun dashboard klaim di Power BI dan rumus DAX-nya. Datanya disiapkan sebagai star schema oleh `src/ekspor_powerbi.py`: tabel fakta klaim dengan dimensi polis, diagnosis, lokasi, dan tanggal. Metode forecasting proyek juga ditulis ulang di DAX, dan hasilnya sama persis dengan Python (Rp12.923.668.797).

## Temuan dari data

- **Bulan klaim dihitung dari tanggal pasien masuk RS.** Data dipotong menurut tanggal ini: tanggal masuk RS persis 1 Januari 2024 sampai 31 Juli 2025, sedangkan pembayaran berlanjut sampai Desember 2025. Klaim rata-rata dibayar dua bulan setelah pasien pulang, sehingga deret per tanggal bayar terlihat rendah di awal 2024 dan anjlok di akhir 2025 karena batas periode data, bukan karena jumlah klaim berubah.
- **Jumlah nasabah tetap.** Semua polis mulai berlaku antara 2011 dan 2018, jadi tidak ada polis baru. Data tidak mencatat polis yang berhenti, sehingga diasumsikan tidak ada.
- **Klaim raksasa menggeser severity bulanan.** Median klaim Rp14,5 juta, tetapi 1% klaim terbesar (47 klaim) bernilai di atas Rp634 juta. Ke-47 klaim ini menyumbang 18,5% seluruh nilai klaim, dan di Februari 2025 sampai 36% total bulan itu. Sembilan dari sepuluh klaim terbesar adalah rawat inap di luar Indonesia.
- **Ada nilai kosong di kolom penting.** 37 klaim tanpa jenis perawatan, 37 klaim berstatus dibayar tetapi tanpa tanggal bayar, 7 tanpa lokasi RS, dan 6 tanpa kode diagnosis. 192 kode ICD tercatat dengan lebih dari satu deskripsi. Daftar lengkap dan perlakuannya dibuat otomatis oleh `src/ekspor_powerbi.py`.
- **Klaim terpusat.** Hanya 30% polis yang pernah klaim. Sepuluh polis dengan klaim terbanyak menyumbang 18% jumlah klaim, tetapi hanya 7% nilai klaim karena klaim mereka umumnya kecil. Biaya lebih ditentukan oleh klaim raksasa.

## Isi repo

```
notebooks/
  01_eksplorasi.ipynb          definisi bulan klaim, jumlah nasabah, klaim raksasa
  02_forecasting.ipynb         backtest sepuluh metode, faktor koreksi, file submission
  03_faktor_nilai_klaim.ipynb  LightGBM dan SHAP untuk faktor penentu nilai klaim
  04_analitik_asuransi.ipynb   rentang prediksi, cadangan IBNR, premi murni GLM, audit klaim
src/klaim.py                   fungsi bersama: memuat data, agregasi bulanan, metode, backtest
src/asuransi.py                fungsi analitik asuransi untuk notebook 04 dan ekspor Power BI
src/ekspor_powerbi.py          star schema (CSV + SQLite) dan laporan kualitas data
powerbi/                       panduan dashboard Power BI dan rumus DAX
submission/submission.csv      prediksi Agustus sampai Desember 2025 dalam format panitia
```

## Menjalankan

Data kompetisi tidak disertakan di repo. Unduh `Data_Klaim.csv`, `Data_Polis.csv`, dan `sample_submission.csv` dari halaman kompetisi di Kaggle, lalu simpan di folder `data/`.

Siapkan environment dengan Python 3.12:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
jupyter notebook notebooks
```

Untuk menyiapkan tabel dashboard Power BI:

```
python -m src.ekspor_powerbi
```

## Keterbatasan

- Hanya 19 bulan data, sehingga pola musiman tahunan tidak bisa diuji.
- Faktor koreksi 0,95 dipilih dari backtest yang sama dengan pemilihan metode. Nilainya sengaja dibatasi di kelipatan 0,05 supaya tidak terlalu menyesuaikan diri dengan 9 titik backtest. Faktor 0,97 memberi skor gabungan yang sama (9,9%).
- Bulan klaim diasumsikan dihitung dari tanggal pasien masuk RS. Kalau panitia memakai tanggal lain, skor resmi bisa berbeda dari hasil backtest.
- 13 klaim bernilai Rp0 tetap dihitung sebagai frekuensi, karena panitia tidak menjelaskan cara menghitungnya. Semuanya terjadi di 2024, jadi tidak memengaruhi prediksi final.
- Model faktor klaim menunjukkan hubungan, bukan sebab-akibat. Tingkat keparahan penyakit dan tindakan medis tidak ada di data.
- Data tidak memuat premi, jadi *loss ratio* tidak bisa dihitung. Semua klaim berstatus dibayar, jadi tidak ada label klaim ditolak atau terbukti curang; audit hanya memakai aturan penanda, bukan model fraud.
- Premi murni dihitung dari 19 bulan pengalaman satu portofolio. Di polis uji, model memisahkan risiko rendah dan tinggi dengan jelas, tetapi kelompok termahal diperkirakan hampir dua kali biaya aktualnya.
- Nilai "aktual" pada uji IBNR untuk Juni dan Juli 2025 belum lengkap, karena data pembayaran berhenti di Desember 2025 dan 6,4% nilai klaim baru dibayar enam bulan atau lebih setelah kejadian.
- Rumus DAX di `powerbi/` belum diuji langsung di Power BI.

## Pelajaran dari proyek ini

- Dengan deret sependek 19 bulan, metode sederhana yang dipilih lewat backtest lebih bisa dipercaya daripada model yang mengejar tren.
- Pahami metrik penilaiannya. MAPE membagi error dengan nilai aktual, sehingga prediksi yang sedikit diturunkan memberi skor lebih baik. Faktor itu tetap harus dipilih dengan hati-hati, karena 0,95 dan 0,97 sama baiknya di backtest yang sama.
- Definisi waktu menentukan hasil. Menghitung klaim per tanggal pembayaran membuat deret terlihat turun di akhir periode, padahal yang berubah hanya batas data.
- Angka ringkasan perlu didefinisikan dengan jelas. Di Februari 2025, porsi klaim raksasa bisa 36% (nilai penuh klaimnya) atau 18% (hanya bagian di atas Rp634 juta), tergantung cara menghitungnya. Begitu juga "sepuluh polis menyumbang 18% klaim": itu porsi jumlah klaim, sedangkan porsi nilainya hanya 7%. Pengaruh plan yang kecil di model juga tidak sama dengan plan yang tidak berpengaruh sama sekali.

Teknologi: Python, pandas, statsmodels (GLM, exponential smoothing), scikit-learn, LightGBM, SHAP, matplotlib, SQLite, Power BI (DAX).
