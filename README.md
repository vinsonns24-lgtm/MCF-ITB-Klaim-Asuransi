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

Metode yang menangkap tren justru lebih buruk. Jumlah nasabah tidak bertambah dan deretnya hanya 19 bulan, jadi "tren" yang ditangkap lebih banyak berupa kebetulan. Faktor 0,95 dipakai karena MAPE menghukum prediksi yang terlalu tinggi lebih berat daripada yang terlalu rendah. Faktor ini memperbaiki ketiga target sekaligus.

Prediksi final: sekitar **225 klaim per bulan**, severity **Rp54,5 juta**, dan total **Rp12,9 miliar** per bulan. Ketiga target diprediksi dan dinilai terpisah, jadi 225 × Rp54,5 juta (Rp12,3 miliar) tidak sama persis dengan prediksi total.

### Faktor penentu nilai klaim

Model LightGBM untuk nilai per klaim (skala log), divalidasi dengan GroupKFold per nomor polis, menjelaskan sekitar separuh variasi nilai klaim (R² 0,50, dibanding 0,15 untuk patokan rata-rata per jenis perawatan). Urutan faktor menurut SHAP:

1. **Lama rawat.** Median klaim tanpa menginap Rp2,9 juta, rawat lebih dari 10 hari Rp199 juta.
2. **Lokasi rumah sakit.** Singapura hanya 22% jumlah klaim tetapi 50% total nilai. Median klaim di Singapura Rp53 juta, di Indonesia Rp9 juta. Plan dan lokasi saling terkait: semua klaim plan M-003 terjadi di Indonesia, sedangkan separuh klaim plan M-001 di Singapura. Di model, pengaruh plan kecil setelah lokasi RS diketahui.
3. **Diagnosis.** Kanker (bab ICD C, 30%), jantung dan pembuluh darah (bab I, 16%), serta otot dan tulang (bab M, 12%) menyumbang 58% total klaim.
4. **Jenis perawatan** dan **cara klaim** (cashless atau reimburse).

Usia, plan, domisili, dan gender pengaruhnya kecil.

## Temuan dari data

- **Bulan klaim dihitung dari tanggal pasien masuk RS.** Klaim rata-rata dibayar dua bulan setelah pasien pulang, sehingga deret per tanggal bayar terlihat rendah di awal 2024 dan anjlok di akhir 2025 karena batas periode data, bukan karena jumlah klaim berubah.
- **Jumlah nasabah tetap.** Semua polis mulai berlaku antara 2011 dan 2018.
- **Klaim raksasa menggeser severity bulanan.** Median klaim Rp14,5 juta, tetapi 1% klaim terbesar (47 klaim) bernilai di atas Rp634 juta. Ke-47 klaim ini menyumbang 18,5% seluruh nilai klaim, dan di Februari 2025 sampai 36% total bulan itu. Sembilan dari sepuluh klaim terbesar adalah rawat inap di luar Indonesia.
- **Klaim terpusat.** Hanya 30% polis yang pernah klaim, dan sepuluh polis menyumbang 18% seluruh klaim.

## Isi repo

```
notebooks/
  01_eksplorasi.ipynb          definisi bulan klaim, jumlah nasabah, klaim raksasa
  02_forecasting.ipynb         backtest sepuluh metode, faktor koreksi, file submission
  03_faktor_nilai_klaim.ipynb  LightGBM dan SHAP untuk faktor penentu nilai klaim
src/klaim.py                   fungsi bersama: memuat data, agregasi bulanan, metode, backtest
submission/submission.csv      prediksi Agustus sampai Desember 2025 dalam format panitia
```

## Menjalankan

Data kompetisi tidak disertakan di repo. Unduh `Data_Klaim.csv`, `Data_Polis.csv`, dan `sample_submission.csv` dari halaman kompetisi di Kaggle, lalu simpan di folder `data/`.

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
jupyter notebook notebooks
```

## Keterbatasan

- Hanya 19 bulan data, sehingga pola musiman tahunan tidak bisa diuji.
- Faktor koreksi 0,95 dipilih dari backtest yang sama dengan pemilihan metode. Nilainya sengaja dibatasi di kelipatan 0,05 supaya tidak terlalu menyesuaikan diri dengan 9 titik backtest. Faktor 0,97 memberi skor gabungan yang sama (9,9%).
- Bulan klaim diasumsikan dihitung dari tanggal pasien masuk RS. Kalau panitia memakai tanggal lain, skor resmi bisa berbeda dari hasil backtest.
- Model faktor klaim menunjukkan hubungan, bukan sebab-akibat. Tingkat keparahan penyakit dan tindakan medis tidak ada di data.

## Pelajaran dari proyek ini

- Dengan deret sependek 19 bulan, metode sederhana yang dipilih lewat backtest lebih bisa dipercaya daripada model yang mengejar tren.
- Pahami metrik penilaiannya. MAPE menghukum prediksi yang terlalu tinggi lebih berat, sehingga prediksi yang sedikit diturunkan memberi skor lebih baik. Faktor itu tetap harus dipilih dengan hati-hati, karena 0,95 dan 0,97 sama baiknya di backtest yang sama.
- Definisi waktu menentukan hasil. Menghitung klaim per tanggal pembayaran membuat deret terlihat turun di akhir periode, padahal yang berubah hanya batas data.
- Angka ringkasan perlu dibaca teliti. Porsi 18% ternyata hanya bagian klaim raksasa di atas Rp634 juta, sedangkan nilai penuhnya mencapai 36% di bulan terburuk. Pengaruh plan yang kecil di model juga tidak sama dengan plan yang tidak berpengaruh sama sekali.

Teknologi: Python, pandas, statsmodels, scikit-learn, LightGBM, SHAP, matplotlib.
