"""Analitik asuransi lanjutan: rentang prediksi, cadangan IBNR, premi murni, dan audit klaim.

Dipakai oleh notebook 04 dan skrip ekspor Power BI, supaya kedua tempat menghitung angka yang sama.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from . import klaim as K

TGL_BAYAR = "Tanggal Pembayaran Klaim"
TGL_MASUK = "Tanggal Pasien Masuk RS"
TGL_KELUAR = "Tanggal Pasien Keluar RS"
BIAYA_RS = "Nominal Biaya RS Yang Terjadi"


# ---------------------------------------------------------------- 1. rentang prediksi

def rasio_backtest(g: pd.DataFrame, fungsi, awal="2024-06", akhir="2025-02", h=5) -> pd.DataFrame:
    """Rasio aktual/prediksi dari rolling-origin backtest yang sama dengan pemilihan metode.

    Rasio dipakai, bukan selisih, karena kesalahan klaim bersifat relatif: meleset Rp1 miliar
    di bulan Rp12 miliar sama beratnya dengan meleset 20 klaim dari 225.
    """
    baris = []
    for origin in pd.period_range(awal, akhir, freq="M"):
        uji = g.loc[origin + 1: origin + h]
        for t in K.TARGET:
            pred = fungsi(g.loc[:origin, t].values, len(uji))
            for langkah, (a, p) in enumerate(zip(uji[t].values, pred), 1):
                baris.append({"origin": str(origin), "target": t, "langkah": langkah, "rasio": a / p})
    return pd.DataFrame(baris)


def rentang_prediksi(g: pd.DataFrame, fungsi, rasio: pd.DataFrame, bulan, bawah=0.1, atas=0.9) -> pd.DataFrame:
    """Prediksi titik plus batas bawah dan atas dari kuantil rasio backtest."""
    baris = []
    for t in K.TARGET:
        titik = fungsi(g[t].values, len(bulan))
        lo, mid, hi = rasio.loc[rasio.target == t, "rasio"].quantile([bawah, 0.5, atas])
        for b, v in zip(bulan, titik):
            baris.append({"bulan": b, "target": t, "prediksi": v, "median": v * mid,
                          "batas_bawah": v * lo, "batas_atas": v * hi})
    return pd.DataFrame(baris)


def cakupan_interval(rasio: pd.DataFrame, bawah=0.1, atas=0.9) -> pd.Series:
    """Uji jujur rentang prediksi: kuantil dihitung tanpa origin yang sedang diuji."""
    hasil = {}
    for t in K.TARGET:
        r = rasio[rasio.target == t]
        kena = []
        for o in r.origin.unique():
            lo, hi = r.loc[r.origin != o, "rasio"].quantile([bawah, atas])
            kena += list(r.loc[r.origin == o, "rasio"].between(lo, hi))
        hasil[t] = np.mean(kena)
    return pd.Series(hasil)


# ---------------------------------------------------------------- 2. cadangan IBNR

def siapkan_pembayaran(k: pd.DataFrame) -> pd.DataFrame:
    """Klaim yang punya tanggal bayar, dengan bulan bayar dan umur pengembangan (bulan)."""
    d = k.dropna(subset=[TGL_BAYAR]).copy()
    d["bulan_bayar"] = d[TGL_BAYAR].dt.to_period("M")
    d["umur"] = (d["bulan_bayar"] - d["bulan"]).apply(lambda x: x.n)
    return d


def segitiga_kumulatif(d: pd.DataFrame, valuasi, nilai=K.NILAI, awal="2024-01") -> pd.DataFrame:
    """Segitiga pembayaran kumulatif per bulan kejadian x umur, sebatas yang terlihat pada tanggal valuasi.

    Sel yang belum mungkin teramati (bulan kejadian + umur melewati valuasi) diisi NaN, bukan 0,
    supaya tidak ikut menurunkan faktor pengembangan.
    """
    valuasi = pd.Period(valuasi, "M")
    terlihat = d[(d["bulan_bayar"] <= valuasi) & (d["bulan"] <= valuasi)]
    baris = pd.period_range(awal, valuasi, freq="M")
    kolom = range(0, (valuasi - pd.Period(awal, "M")).n + 1)
    tri = terlihat.pivot_table(index="bulan", columns="umur", values=nilai, aggfunc="sum", fill_value=0)
    kum = tri.reindex(index=baris, columns=kolom, fill_value=0).cumsum(axis=1).astype(float)
    for b in kum.index:
        kum.loc[b, kum.columns > (valuasi - b).n] = np.nan
    return kum


def faktor_pengembangan(kum: pd.DataFrame) -> np.ndarray:
    """Faktor chain-ladder berbobot volume: jumlah kolom j+1 dibagi jumlah kolom j pada baris yang lengkap."""
    faktor = []
    for j in range(kum.shape[1] - 1):
        a, b = kum.iloc[:, j], kum.iloc[:, j + 1]
        m = a.notna() & b.notna()
        faktor.append(b[m].sum() / a[m].sum() if m.any() and a[m].sum() > 0 else 1.0)
    return np.array(faktor)


def estimasi_ultimate(kum: pd.DataFrame, valuasi, umur_matang=6, n_prior=6) -> pd.DataFrame:
    """Estimasi nilai akhir klaim tiap bulan kejadian dengan chain-ladder dan Bornhuetter-Ferguson.

    Chain-ladder: dibayar x faktor kumulatif. Gagal kalau yang dibayar masih ~0, karena nol
    dikali faktor apa pun tetap nol.
    Bornhuetter-Ferguson: dibayar + (porsi yang belum dibayar) x patokan awal. Patokannya adalah
    rata-rata nilai akhir bulan-bulan yang sudah matang, yaitu metode yang sama dengan forecasting.
    """
    valuasi = pd.Period(valuasi, "M")
    f = faktor_pengembangan(kum)
    kumulatif = np.append(np.cumprod(f[::-1])[::-1], 1.0)
    umur = {b: (valuasi - b).n for b in kum.index}
    dibayar = pd.Series({b: kum.loc[b].iloc[j] for b, j in umur.items()})
    ult_cl = pd.Series({b: dibayar[b] * kumulatif[j] for b, j in umur.items()})
    matang = [b for b, j in umur.items() if j >= umur_matang][-n_prior:]
    prior = ult_cl[matang].mean()
    belum = pd.Series({b: 1 - 1 / kumulatif[j] for b, j in umur.items()})
    return pd.DataFrame({
        "umur": pd.Series(umur), "dibayar": dibayar, "porsi_belum_dibayar": belum,
        "ultimate_CL": ult_cl, "ultimate_BF": dibayar + belum * prior, "patokan_BF": prior,
    })


def uji_ibnr(d: pd.DataFrame, valuasi_list, n_bulan=6) -> pd.DataFrame:
    """Backtest cadangan: estimasi pada tiap valuasi dibandingkan dengan pembayaran yang terjadi kemudian."""
    akhir = d.groupby("bulan")[K.NILAI].sum()
    baris = []
    for v in valuasi_list:
        est = estimasi_ultimate(segitiga_kumulatif(d, v), v).tail(n_bulan)
        est["aktual"] = akhir.reindex(est.index).values
        est["valuasi"] = str(v)
        baris.append(est)
    h = pd.concat(baris)
    for m in ["CL", "BF"]:
        h[f"error_{m}"] = (h[f"ultimate_{m}"] - h["aktual"]) / h["aktual"]
    return h


# ---------------------------------------------------------------- 3. premi murni (GLM)

KELAS_USIA = [0, 30, 40, 50, 60, 70, 120]
LABEL_USIA = ["<30", "30-39", "40-49", "50-59", "60-69", "70+"]
RUMUS_FAKTOR = ("C(plan) + C(kel_usia, Treatment('50-59')) + C(gender)"
                " + C(domisili, Treatment('JAKARTA'))")


def siapkan_polis(p: pd.DataFrame, k: pd.DataFrame, tanggal_acuan="2024-01-01",
                  bulan_eksposur=19, min_domisili=150) -> pd.DataFrame:
    """Satu baris per polis dengan faktor tarif dan jumlah klaim.

    Hanya informasi yang diketahui saat polis dijual yang dipakai sebagai faktor (plan, usia,
    gender, domisili). Lokasi RS dan diagnosis baru diketahui setelah klaim terjadi, jadi tidak
    boleh menentukan harga. Eksposur 19 bulan untuk semua polis karena tidak ada polis baru dan
    data tidak mencatat polis berhenti.
    """
    x = p.copy()
    acuan = pd.Timestamp(tanggal_acuan)
    x["usia"] = (acuan - x["Tanggal Lahir"]).dt.days / 365.25
    x["kel_usia"] = pd.cut(x["usia"], KELAS_USIA, labels=LABEL_USIA, right=False).astype(str)
    besar = x["Domisili"].value_counts()
    x["domisili"] = x["Domisili"].where(x["Domisili"].map(besar) >= min_domisili, "LAINNYA")
    x = x.rename(columns={"Plan Code": "plan", "Gender": "gender"})
    x["n_klaim"] = x["Nomor Polis"].map(k.groupby("Nomor Polis").size()).fillna(0)
    x["biaya"] = x["Nomor Polis"].map(k.groupby("Nomor Polis")[K.NILAI].sum()).fillna(0)
    x["eksposur"] = bulan_eksposur / 12
    return x


def latih_frekuensi(polis: pd.DataFrame):
    """Negative Binomial dengan eksposur. Poisson tidak dipakai karena varians jumlah klaim jauh
    di atas rata-ratanya (sebagian kecil nasabah klaim puluhan sampai ratusan kali)."""
    return smf.negativebinomial(f"n_klaim ~ {RUMUS_FAKTOR}", polis,
                                exposure=polis["eksposur"]).fit(disp=0, maxiter=300)


def latih_severity(klaim_polis: pd.DataFrame, persentil_batas=0.99):
    """Gamma dengan link log pada nilai klaim yang dipotong di persentil 99.

    Klaim raksasa dipisah karena satu klaim Rp5 miliar akan menyeret koefisien seluruh segmen.
    Bagian di atas batas dikembalikan lewat faktor beban klaim besar yang sama untuk semua segmen.
    """
    x = klaim_polis[klaim_polis[K.NILAI] > 0].copy()
    batas = x[K.NILAI].quantile(persentil_batas)
    x["nilai_potong"] = x[K.NILAI].clip(upper=batas)
    model = smf.glm(f"nilai_potong ~ {RUMUS_FAKTOR}", x,
                    family=sm.families.Gamma(sm.families.links.Log())).fit()
    beban = x[K.NILAI].sum() / x["nilai_potong"].sum()
    return model, batas, beban


def premi_murni(polis: pd.DataFrame, model_frek, model_sev, beban: float) -> pd.Series:
    """Biaya klaim yang diharapkan per polis per tahun = frekuensi tahunan x severity x beban klaim besar."""
    satu_tahun = polis.assign(eksposur=1.0)
    frek = model_frek.predict(satu_tahun, exposure=satu_tahun["eksposur"])
    return frek * model_sev.predict(polis) * beban


def relativitas(model, nama_faktor: dict) -> pd.DataFrame:
    """Koefisien GLM log diubah jadi pengali terhadap segmen acuan (1,00 = sama dengan acuan)."""
    baris = []
    for param, nilai in model.params.items():
        if param in ("Intercept", "alpha"):
            continue
        faktor = next((label for kunci, label in nama_faktor.items() if kunci in param), param)
        level = param.split("[T.")[-1].rstrip("]")
        baris.append({"faktor": faktor, "level": level, "pengali": np.exp(nilai),
                      "p_value": model.pvalues[param]})
    hasil = pd.DataFrame(baris)
    # Kelompok usia diurutkan dari muda ke tua; urutan bawaan statsmodels alfabetis, jadi "<30" jatuh di akhir.
    urut_faktor = {f: i for i, f in enumerate(dict.fromkeys(hasil["faktor"]))}
    urut_level = hasil["level"].map({lv: i for i, lv in enumerate(LABEL_USIA)}).fillna(0)
    return (hasil.assign(_f=hasil["faktor"].map(urut_faktor), _l=urut_level)
                 .sort_values(["_f", "_l"], kind="stable").drop(columns=["_f", "_l"]).reset_index(drop=True))


# ---------------------------------------------------------------- 4. audit klaim

LOKASI_TAK_SPESIFIK = ["Overseas", "Others"]


def tandai_audit(k: pd.DataFrame, z_batas=3.5, min_grup=30) -> pd.DataFrame:
    """Aturan penanda klaim untuk diperiksa ulang. Penanda berarti layak dicek, bukan bukti kecurangan.

    Tidak ada klaim berstatus ditolak di data, jadi tidak ada label fraud untuk melatih model.
    Yang bisa dilakukan adalah aturan yang alasannya bisa dijelaskan ke tim klaim.
    """
    x = k.copy()
    x["lama_rawat"] = (x[TGL_KELUAR] - x[TGL_MASUK]).dt.days
    x["bab_icd"] = x["ICD Diagnosis"].str[0]

    log_nilai = np.log1p(x[K.NILAI])
    grup = log_nilai.groupby([x["bab_icd"], x["Inpatient/Outpatient"]])
    tengah = grup.transform("median")
    sebaran = grup.transform(lambda s: (s - s.median()).abs().median())
    cukup = grup.transform("size") >= min_grup
    z = 0.6745 * (log_nilai - tengah) / sebaran.replace(0, np.nan)

    x["A_disetujui_melebihi_biaya_RS"] = x[K.NILAI] > x[BIAYA_RS] * 1.01
    x["B_klaim_kembar"] = x.duplicated(["Nomor Polis", TGL_MASUK, "ICD Diagnosis", K.NILAI], keep=False) & (x[K.NILAI] > 0)
    x["C_lokasi_tidak_spesifik"] = x["Lokasi RS"].isin(LOKASI_TAK_SPESIFIK)
    x["D_rawat_jalan_menginap"] = (x["Inpatient/Outpatient"] == "OP") & (x["lama_rawat"] > 0)
    x["E_nilai_tak_wajar"] = cukup & (z > z_batas)
    x["F_dibayar_tanpa_tanggal"] = x[TGL_BAYAR].isna()

    aturan = [c for c in x.columns if c[:2] in {"A_", "B_", "C_", "D_", "E_", "F_"}]
    x["jumlah_penanda"] = x[aturan].sum(axis=1)
    x["z_nilai"] = z
    return x


def ringkasan_audit(x: pd.DataFrame) -> pd.DataFrame:
    aturan = [c for c in x.columns if c[:2] in {"A_", "B_", "C_", "D_", "E_", "F_"}]
    return pd.DataFrame({
        "klaim": [int(x[a].sum()) for a in aturan],
        "nilai_disetujui": [x.loc[x[a], K.NILAI].sum() for a in aturan],
    }, index=aturan)
