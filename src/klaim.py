"""Fungsi bersama untuk proyek prediksi klaim asuransi kesehatan (DSC MCF ITB 2026).

Semua notebook memakai fungsi di sini, supaya definisi bulan klaim, metrik, dan
metode forecasting hanya ditulis sekali.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

NILAI = "Nominal Klaim Yang Disetujui"
TARGET = ["Claim_Frequency", "Claim_Severity", "Total_Claim"]


# ---------------------------------------------------------------- data

def muat_klaim() -> pd.DataFrame:
    """Data klaim dengan kolom tanggal sudah diubah menjadi datetime.

    Bulan klaim diambil dari tanggal pasien masuk RS (tanggal kejadian). Tanggal pembayaran
    tidak dipakai karena pembayaran rata-rata keluar dua bulan setelah pasien pulang: deret per
    tanggal bayar terlihat rendah di awal 2024 (klaim dari 2023 tidak ada di data) dan anjlok di
    akhir 2025 (klaim belum dibayar), padahal jumlah kejadiannya tidak berubah.
    """
    k = pd.read_csv(DATA / "Data_Klaim.csv")
    for kolom in ["Tanggal Pembayaran Klaim", "Tanggal Pasien Masuk RS", "Tanggal Pasien Keluar RS"]:
        k[kolom] = pd.to_datetime(k[kolom], errors="coerce")
    k["bulan"] = k["Tanggal Pasien Masuk RS"].dt.to_period("M")
    return k


def muat_polis() -> pd.DataFrame:
    p = pd.read_csv(DATA / "Data_Polis.csv")
    for kolom in ["Tanggal Lahir", "Tanggal Efektif Polis"]:
        p[kolom] = pd.to_datetime(p[kolom].astype(str), format="%Y%m%d", errors="coerce")
    return p


def per_bulan(k: pd.DataFrame) -> pd.DataFrame:
    """Frekuensi, total, dan severity (total dibagi frekuensi) per bulan kejadian."""
    g = k.groupby("bulan").agg(Claim_Frequency=(NILAI, "size"), Total_Claim=(NILAI, "sum"))
    g["Claim_Severity"] = g["Total_Claim"] / g["Claim_Frequency"]
    return g[TARGET]


# ---------------------------------------------------------------- metrik

def mape(aktual, prediksi) -> float:
    aktual, prediksi = np.asarray(aktual, float), np.asarray(prediksi, float)
    return float(np.mean(np.abs((aktual - prediksi) / aktual)) * 100)


# ---------------------------------------------------------------- metode forecasting
# Setiap metode menerima deret historis (array) dan jumlah bulan ke depan, lalu mengembalikan array prediksi.

def rata_rata(n=None):
    def f(y, h):
        y = y if n is None else y[-n:]
        return np.repeat(y.mean(), h)
    return f


def median(n=None):
    def f(y, h):
        y = y if n is None else y[-n:]
        return np.repeat(np.median(y), h)
    return f


def terakhir(y, h):
    return np.repeat(y[-1], h)


def tren_linear(y, h):
    x = np.arange(len(y))
    koef = np.polyfit(x, y, 1)
    return np.polyval(koef, np.arange(len(y), len(y) + h))


def ses(y, h):
    from statsmodels.tsa.holtwinters import SimpleExpSmoothing
    return SimpleExpSmoothing(y, initialization_method="estimated").fit().forecast(h)


def holt_teredam(y, h):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    model = ExponentialSmoothing(y, trend="add", damped_trend=True, initialization_method="estimated")
    return model.fit().forecast(h)


def dikali(fungsi, faktor):
    """Prediksi dikalikan faktor. Faktor < 1 dipakai karena MAPE menghukum prediksi yang
    terlalu tinggi lebih berat daripada yang terlalu rendah."""
    def f(y, h):
        return faktor * fungsi(y, h)
    return f


METODE = {
    "Rata-rata semua bulan": rata_rata(),
    "Rata-rata 12 bulan": rata_rata(12),
    "Rata-rata 6 bulan": rata_rata(6),
    "Rata-rata 3 bulan": rata_rata(3),
    "Median semua bulan": median(),
    "Median 6 bulan": median(6),
    "Bulan terakhir": terakhir,
    "Tren linear": tren_linear,
    "Simple exponential smoothing": ses,
    "Holt dengan tren teredam": holt_teredam,
}


# ---------------------------------------------------------------- backtest

def backtest(g: pd.DataFrame, metode: dict, awal="2024-06", akhir="2025-02", h=5) -> pd.DataFrame:
    """Rolling-origin backtest.

    Untuk setiap titik awal (origin) dari `awal` sampai `akhir`, metode hanya melihat data sampai
    origin, lalu memprediksi `h` bulan berikutnya. Horizon 5 bulan sama dengan tugas kompetisi
    (Agustus sampai Desember). Hasilnya MAPE rata-rata per metode dan per target.
    """
    import warnings
    baris = []
    for origin in pd.period_range(awal, akhir, freq="M"):
        uji = g.loc[origin + 1: origin + h]
        for nama, fungsi in metode.items():
            for target in TARGET:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    pred = fungsi(g.loc[:origin, target].values, len(uji))
                baris.append({"origin": str(origin), "metode": nama, "target": target,
                              "MAPE": mape(uji[target].values, pred)})
    hasil = pd.DataFrame(baris)
    tabel = hasil.pivot_table(index="metode", columns="target", values="MAPE", aggfunc="mean")[TARGET]
    tabel["Skor gabungan"] = tabel.mean(axis=1)
    return tabel.sort_values("Skor gabungan")


def buat_submission(g: pd.DataFrame, fungsi, bulan=("2025-08", "2025-09", "2025-10", "2025-11", "2025-12")):
    """File submission dalam format panitia: satu baris per bulan per target."""
    baris = []
    prediksi = {t: fungsi(g[t].values, len(bulan)) for t in TARGET}
    for i, b in enumerate(bulan):
        for t in TARGET:
            baris.append({"id": f"{b.replace('-', '_')}_{t}", "value": float(prediksi[t][i])})
    return pd.DataFrame(baris)
