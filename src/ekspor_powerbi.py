"""Membangun star schema untuk dashboard Power BI dan laporan kualitas data.

Pemakaian (dari folder utama proyek):
    python -m src.ekspor_powerbi

Hasilnya di data/powerbi/ (ikut di-gitignore bersama folder data/, karena isinya turunan data
kompetisi): satu file CSV per tabel, plus klaim.db (SQLite) berisi tabel yang sama untuk dicek
dengan SQL.
"""
import sqlite3
import warnings

import numpy as np
import pandas as pd

from . import asuransi, klaim

KELUAR = klaim.DATA / "powerbi"
TIDAK_TERCATAT = "Tidak tercatat"
BULAN_PREDIKSI = ["2025-08", "2025-09", "2025-10", "2025-11", "2025-12"]
VALUASI_IBNR = "2025-07"

LUAR_NEGERI = ["Singapore", "Malaysia", "Taiwan", "Hong Kong", "Japan", "Tiongkok", "Australia"]

# Bab ICD-10 ditentukan huruf pertama, kecuali D dan H yang terbelah dua menurut angkanya.
BAB_ICD = {
    "A": "Infeksi dan parasit", "B": "Infeksi dan parasit", "C": "Neoplasma (kanker dan tumor)",
    "E": "Endokrin, gizi, dan metabolik", "F": "Gangguan mental", "G": "Sistem saraf",
    "I": "Jantung dan pembuluh darah", "J": "Pernapasan", "K": "Pencernaan", "L": "Kulit",
    "M": "Otot, tulang, dan sendi", "N": "Saluran kemih dan kelamin", "O": "Kehamilan",
    "P": "Kondisi perinatal", "Q": "Kelainan bawaan", "R": "Gejala tidak spesifik",
    "S": "Cedera dan keracunan", "T": "Cedera dan keracunan", "V": "Penyebab luar",
    "W": "Penyebab luar", "X": "Penyebab luar", "Y": "Penyebab luar",
    "Z": "Faktor kesehatan dan layanan",
}


def nama_bab(kode: str) -> str:
    if kode == TIDAK_TERCATAT:
        return TIDAK_TERCATAT
    huruf, angka = kode[0], kode[1:3]
    if huruf == "D":
        return "Neoplasma (kanker dan tumor)" if angka.isdigit() and int(angka) < 50 else "Darah dan imunitas"
    if huruf == "H":
        return "Mata" if angka.isdigit() and int(angka) < 60 else "Telinga"
    return BAB_ICD.get(huruf, "Lainnya")


def kelompok_lokasi(lokasi: str) -> str:
    if lokasi == "Indonesia":
        return "Indonesia"
    if lokasi in LUAR_NEGERI:
        return "Luar negeri"
    return "Tidak spesifik"


def bangun_tabel() -> tuple[dict, pd.DataFrame]:
    k = klaim.muat_klaim()
    p = klaim.muat_polis()
    audit = asuransi.tandai_audit(k)
    kosong = k[["Inpatient/Outpatient", "ICD Diagnosis", "Lokasi RS"]].isna()

    # Nilai kosong di kolom penghubung tabel diganti label, supaya Power BI tidak memunculkan
    # baris "(Blank)" dan relasi antartabel tetap utuh.
    k["kode_icd"] = k["ICD Diagnosis"].str.strip().str.upper().fillna(TIDAK_TERCATAT)
    k["ICD Description"] = k["ICD Description"].fillna(TIDAK_TERCATAT)
    k["Lokasi RS"] = k["Lokasi RS"].fillna(TIDAK_TERCATAT)
    k["Inpatient/Outpatient"] = k["Inpatient/Outpatient"].fillna(TIDAK_TERCATAT)

    # ------------------------------------------------ dimensi
    deskripsi = (k.groupby(["kode_icd", "ICD Description"]).size().reset_index(name="n")
                   .sort_values(["kode_icd", "n"], ascending=[True, False])
                   .drop_duplicates("kode_icd"))
    dim_diagnosis = pd.DataFrame({
        "kode_icd": deskripsi["kode_icd"],
        "deskripsi": deskripsi["ICD Description"].str.capitalize(),
        "bab_icd": deskripsi["kode_icd"].map(nama_bab),
    })

    dim_lokasi = pd.DataFrame({"lokasi_rs": sorted(k["Lokasi RS"].unique())})
    dim_lokasi["kelompok"] = dim_lokasi["lokasi_rs"].map(kelompok_lokasi)

    tanggal = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    dim_tanggal = pd.DataFrame({
        "tanggal": tanggal, "tahun": tanggal.year, "bulan": tanggal.month,
        "nama_bulan": tanggal.strftime("%b"), "kuartal": "Q" + tanggal.quarter.astype(str),
        "bulan_tahun": tanggal.strftime("%Y-%m"), "awal_bulan": tanggal.to_period("M").to_timestamp(),
    })

    polis = asuransi.siapkan_polis(p, k)
    frek = asuransi.latih_frekuensi(polis)
    klaim_polis = k.merge(polis[["Nomor Polis", "plan", "kel_usia", "gender", "domisili"]], on="Nomor Polis")
    sev, _, beban = asuransi.latih_severity(klaim_polis)
    polis["premi_murni"] = asuransi.premi_murni(polis, frek, sev, beban)
    dim_polis = pd.DataFrame({
        "nomor_polis": polis["Nomor Polis"], "plan": polis["plan"], "gender": polis["gender"],
        "usia_awal_2024": polis["usia"].round(1), "kel_usia": polis["kel_usia"],
        # Kolom bantu "Sort by column" di Power BI; tanpa ini "<30" diurutkan setelah "70+".
        "urut_usia": polis["kel_usia"].map({lv: i for i, lv in enumerate(asuransi.LABEL_USIA, 1)}),
        "domisili": polis["Domisili"], "domisili_kelompok": polis["domisili"],
        "tanggal_efektif": polis["Tanggal Efektif Polis"],
        "premi_murni_tahunan": polis["premi_murni"].round(0),
    })

    # ------------------------------------------------ fakta
    penanda = [c for c in audit.columns if c[:2] in {"A_", "B_", "C_", "D_", "E_", "F_"}]
    fakta_klaim = pd.DataFrame({
        "claim_id": k["Claim ID"], "nomor_polis": k["Nomor Polis"],
        "tanggal_masuk": k[asuransi.TGL_MASUK], "tanggal_keluar": k[asuransi.TGL_KELUAR],
        "tanggal_bayar": k[asuransi.TGL_BAYAR],
        "umur_bayar_bulan": (k[asuransi.TGL_BAYAR].dt.to_period("M") - k["bulan"])
                             .apply(lambda x: x.n if pd.notna(x) else np.nan),
        "jenis_perawatan": k["Inpatient/Outpatient"],
        "cara_klaim": k["Reimburse/Cashless"].map({"R": "Reimburse", "C": "Cashless"}),
        "kode_icd": k["kode_icd"], "lokasi_rs": k["Lokasi RS"],
        "nilai_disetujui": k[klaim.NILAI], "biaya_rs": k[asuransi.BIAYA_RS],
        "lama_rawat_hari": audit["lama_rawat"], "jumlah_penanda": audit["jumlah_penanda"],
    })
    for c in penanda:
        fakta_klaim[c.lower()] = audit[c].astype(int)

    # ------------------------------------------------ tabel analitik
    g = klaim.per_bulan(k)
    final = klaim.dikali(klaim.rata_rata(6), 0.95)
    rentang = asuransi.rentang_prediksi(g, final, asuransi.rasio_backtest(g, final), BULAN_PREDIKSI)
    aktual = g.reset_index().melt(id_vars="bulan", var_name="target", value_name="aktual")
    aktual["bulan"] = aktual["bulan"].astype(str)
    bulanan = pd.concat([aktual, rentang], ignore_index=True)
    bulanan["awal_bulan"] = pd.PeriodIndex(bulanan["bulan"], freq="M").to_timestamp()
    bulanan["target"] = bulanan["target"].map({"Claim_Frequency": "Frekuensi", "Claim_Severity": "Severity",
                                               "Total_Claim": "Total klaim"})

    d = asuransi.siapkan_pembayaran(k)
    ibnr = asuransi.estimasi_ultimate(asuransi.segitiga_kumulatif(d, VALUASI_IBNR), VALUASI_IBNR)
    ibnr["aktual_sampai_des_2025"] = d.groupby("bulan")[klaim.NILAI].sum().reindex(ibnr.index).values
    ibnr = ibnr.reset_index(names="bulan_kejadian")
    ibnr["bulan_kejadian"] = ibnr["bulan_kejadian"].astype(str)
    ibnr["valuasi"] = VALUASI_IBNR

    kualitas = laporan_kualitas(k, audit, kosong)

    tabel = {
        "fakta_klaim": fakta_klaim, "dim_polis": dim_polis, "dim_diagnosis": dim_diagnosis,
        "dim_lokasi": dim_lokasi, "dim_tanggal": dim_tanggal,
        "prediksi_bulanan": bulanan, "ibnr": ibnr, "kualitas_data": kualitas,
    }
    return tabel, kualitas


def laporan_kualitas(k: pd.DataFrame, audit: pd.DataFrame, kosong: pd.DataFrame) -> pd.DataFrame:
    """Daftar masalah kualitas data beserta jumlah baris yang terdampak dan perlakuannya."""
    icd = k["ICD Diagnosis"].dropna().str.strip()
    kode_kecil = (icd != icd.str.upper()).sum()
    banyak_deskripsi = int((k.groupby("kode_icd")["ICD Description"].nunique() > 1).sum())
    baris = [
        ("Jenis perawatan kosong", int(kosong["Inpatient/Outpatient"].sum()), f"Diisi '{TIDAK_TERCATAT}'"),
        ("Kode diagnosis kosong", int(kosong["ICD Diagnosis"].sum()), f"Diisi '{TIDAK_TERCATAT}'"),
        ("Lokasi RS kosong", int(kosong["Lokasi RS"].sum()),
         f"Diisi '{TIDAK_TERCATAT}', masuk kelompok 'Tidak spesifik'"),
        ("Status PAID tanpa tanggal bayar", int(audit["F_dibayar_tanpa_tanggal"].sum()),
         "Tetap dihitung di frekuensi dan nilai; tidak bisa masuk segitiga IBNR"),
        ("Nilai disetujui Rp0", int((k[klaim.NILAI] == 0).sum()),
         "Tetap dihitung di frekuensi karena panitia tidak menjelaskan aturannya"),
        ("Disetujui melebihi biaya RS (lebih dari 1%)", int(audit["A_disetujui_melebihi_biaya_RS"].sum()),
         "Ditandai untuk audit (aturan A)"),
        ("Klaim kembar persis", int(audit["B_klaim_kembar"].sum()),
         "Ditandai untuk audit (aturan B); tidak dihapus karena bisa item terpisah"),
        ("Rawat jalan dengan tanggal keluar berbeda", int(audit["D_rawat_jalan_menginap"].sum()),
         "Ditandai untuk audit (aturan D)"),
        ("Lokasi RS tidak spesifik (Overseas/Others)", int(audit["C_lokasi_tidak_spesifik"].sum()),
         "Kelompok lokasi 'Tidak spesifik'"),
        ("Kode ICD ditulis huruf kecil", int(kode_kecil), "Diubah ke huruf besar"),
        ("Kode ICD dengan lebih dari satu deskripsi", banyak_deskripsi,
         "Dimensi diagnosis memakai deskripsi yang paling sering muncul"),
        ("Klaim dengan tanggal keluar sebelum tanggal masuk", int((audit["lama_rawat"] < 0).sum()), "-"),
        ("Klaim dari polis yang tidak ada di data polis",
         int((~k["Nomor Polis"].isin(klaim.muat_polis()["Nomor Polis"])).sum()), "-"),
    ]
    return pd.DataFrame(baris, columns=["masalah", "jumlah", "perlakuan"])


def tulis(tabel: dict) -> None:
    KELUAR.mkdir(parents=True, exist_ok=True)
    for nama, df in tabel.items():
        df.to_csv(KELUAR / f"{nama}.csv", index=False, date_format="%Y-%m-%d")
    with sqlite3.connect(KELUAR / "klaim.db") as conn:
        for nama, df in tabel.items():
            df.to_sql(nama, conn, if_exists="replace", index=False)


def main():
    warnings.filterwarnings("ignore")
    tabel, kualitas = bangun_tabel()
    tulis(tabel)
    print(f"Tabel ditulis ke {KELUAR}")
    for nama, df in tabel.items():
        print(f"  {nama:<18}{len(df):>7,} baris".replace(",", "."))
    print("\nLaporan kualitas data")
    for _, r in kualitas.iterrows():
        print(f"  {r['jumlah']:>5}  {r['masalah']}")


if __name__ == "__main__":
    main()
