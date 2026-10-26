Real & nominal exchange-rate explorer using IMF SDMX 3.0 data.

S(t)   = units of Country 2 currency per 1 unit of Country 1 currency
RER(t) = S(t) * P1(t) / P2(t)
RER*   = mean of RER(t) over valid months in the selected sample
Real Index(t) = 100 * RER(t) / RER*
"""
from __future__ import annotations

import os
import re
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

BASE_URL = "https://api.imf.org/external/sdmx/3.0"
START = pd.Timestamp("1976-01-01")
HEADERS = {"Accept": "application/vnd.sdmx.data+json;version=2.0.0, application/json;q=0.9"}
_sub_key = os.environ.get("IMF_SDMX_SUBSCRIPTION_KEY")
if _sub_key:
    HEADERS["Ocp-Apim-Subscription-Key"] = _sub_key

# Dataflow id -> versions to try (newest known first, then wildcard)
FLOWS = {"CPI": ["5.0.0", "+"], "ER": ["4.0.1", "+"]}

# IMF country / area codes (ISO3 + G163 for the Euro area). Availability is checked at fetch time.
COUNTRIES = {
    "AFG": "Afghanistan", "ALB": "Albania", "DZA": "Algeria", "AGO": "Angola", "ATG": "Antigua and Barbuda",
    "ARG": "Argentina", "ARM": "Armenia", "ABW": "Aruba", "AUS": "Australia", "AUT": "Austria",
    "AZE": "Azerbaijan", "BHS": "Bahamas", "BHR": "Bahrain", "BGD": "Bangladesh", "BRB": "Barbados",
    "BLR": "Belarus", "BEL": "Belgium", "BLZ": "Belize", "BEN": "Benin", "BTN": "Bhutan",
    "BOL": "Bolivia", "BIH": "Bosnia and Herzegovina", "BWA": "Botswana", "BRA": "Brazil",
    "BRN": "Brunei Darussalam", "BGR": "Bulgaria", "BFA": "Burkina Faso", "BDI": "Burundi",
    "CPV": "Cabo Verde", "KHM": "Cambodia", "CMR": "Cameroon", "CAN": "Canada",
    "CAF": "Central African Republic", "TCD": "Chad", "CHL": "Chile", "CHN": "China", "COL": "Colombia",
    "COM": "Comoros", "COD": "Congo, Dem. Rep.", "COG": "Congo, Rep.", "CRI": "Costa Rica",
    "CIV": "Côte d'Ivoire", "HRV": "Croatia", "CYP": "Cyprus", "CZE": "Czech Republic", "DNK": "Denmark",
    "DJI": "Djibouti", "DMA": "Dominica", "DOM": "Dominican Republic", "ECU": "Ecuador", "EGY": "Egypt",
    "SLV": "El Salvador", "GNQ": "Equatorial Guinea", "ERI": "Eritrea", "EST": "Estonia",
    "SWZ": "Eswatini", "ETH": "Ethiopia", "G163": "Euro area", "FJI": "Fiji", "FIN": "Finland",
    "FRA": "France", "GAB": "Gabon", "GMB": "Gambia", "GEO": "Georgia", "DEU": "Germany", "GHA": "Ghana",
    "GRC": "Greece", "GRD": "Grenada", "GTM": "Guatemala", "GIN": "Guinea", "GNB": "Guinea-Bissau",
    "GUY": "Guyana", "HTI": "Haiti", "HND": "Honduras", "HKG": "Hong Kong SAR", "HUN": "Hungary",
    "ISL": "Iceland", "IND": "India", "IDN": "Indonesia", "IRN": "Iran", "IRQ": "Iraq", "IRL": "Ireland",
    "ISR": "Israel", "ITA": "Italy", "JAM": "Jamaica", "JPN": "Japan", "JOR": "Jordan",
    "KAZ": "Kazakhstan", "KEN": "Kenya", "KIR": "Kiribati", "KOR": "Korea, Rep.", "KWT": "Kuwait",
    "KGZ": "Kyrgyz Republic", "LAO": "Lao P.D.R.", "LVA": "Latvia", "LBN": "Lebanon", "LSO": "Lesotho",
    "LBR": "Liberia", "LBY": "Libya", "LTU": "Lithuania", "LUX": "Luxembourg", "MAC": "Macao SAR",
    "MDG": "Madagascar", "MWI": "Malawi", "MYS": "Malaysia", "MDV": "Maldives", "MLI": "Mali",
    "MLT": "Malta", "MRT": "Mauritania", "MUS": "Mauritius", "MEX": "Mexico", "FSM": "Micronesia",
    "MDA": "Moldova", "MNG": "Mongolia", "MNE": "Montenegro", "MAR": "Morocco", "MOZ": "Mozambique",
    "MMR": "Myanmar", "NAM": "Namibia", "NPL": "Nepal", "NLD": "Netherlands", "NZL": "New Zealand",
    "NIC": "Nicaragua", "NER": "Niger", "NGA": "Nigeria", "MKD": "North Macedonia", "NOR": "Norway",
    "OMN": "Oman", "PAK": "Pakistan", "PAN": "Panama", "PNG": "Papua New Guinea", "PRY": "Paraguay",
    "PER": "Peru", "PHL": "Philippines", "POL": "Poland", "PRT": "Portugal", "QAT": "Qatar",
    "ROU": "Romania", "RUS": "Russian Federation", "RWA": "Rwanda", "WSM": "Samoa",
    "STP": "São Tomé and Príncipe", "SAU": "Saudi Arabia", "SEN": "Senegal", "SRB": "Serbia",
    "SYC": "Seychelles", "SLE": "Sierra Leone", "SGP": "Singapore", "SVK": "Slovak Republic",
    "SVN": "Slovenia", "SLB": "Solomon Islands", "SOM": "Somalia", "ZAF": "South Africa",
    "SSD": "South Sudan", "ESP": "Spain", "LKA": "Sri Lanka", "KNA": "St. Kitts and Nevis",
    "LCA": "St. Lucia", "VCT": "St. Vincent and the Grenadines", "SDN": "Sudan", "SUR": "Suriname",
    "SWE": "Sweden", "CHE": "Switzerland", "SYR": "Syria", "TWN": "Taiwan Province of China",
    "TJK": "Tajikistan", "TZA": "Tanzania", "THA": "Thailand", "TLS": "Timor-Leste", "TGO": "Togo",
    "TON": "Tonga", "TTO": "Trinidad and Tobago", "TUN": "Tunisia", "TUR": "Türkiye",
    "TKM": "Turkmenistan", "UGA": "Uganda", "UKR": "Ukraine", "ARE": "United Arab Emirates",
    "GBR": "United Kingdom", "USA": "United States", "URY": "Uruguay", "UZB": "Uzbekistan",
    "VUT": "Vanuatu", "VEN": "Venezuela", "VNM": "Vietnam", "YEM": "Yemen", "ZMB": "Zambia",
    "ZWE": "Zimbabwe",
}

_PERIOD_RE = re.compile(r"^(\d{4})-?(?:M)?(\d{2})$")


# --------------------------------------------------------------------------- data access
def _parse_period(p: str) -> Optional[pd.Timestamp]:
    m = _PERIOD_RE.match(str(p).strip())
    if not m:
        return None
    return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)


def _parse_sdmx_json(payload: dict) -> pd.Series:
    Parse an SDMX-JSON (1.0 or 2.0) message into a monthly Series (first series found).
    data = payload.get("data", payload)
    datasets = data.get("dataSets") or []
    if not datasets:
        return pd.Series(dtype=float)
    structure = data.get("structure")
    if structure is None:
        structures = data.get("structures") or []
        structure = structures[0] if structures else {}
    obs_dims = (structure.get("dimensions") or {}).get("observation") or []
    time_dim = next((d for d in obs_dims if d.get("id") == "TIME_PERIOD"), obs_dims[0] if obs_dims else None)
    if time_dim is None:
        return pd.Series(dtype=float)
    time_values = [v.get("id") or v.get("value") or v.get("name") for v in time_dim.get("values", [])]

    series_map = datasets[0].get("series") or {}
    if not series_map:
        return pd.Series(dtype=float)
    first = next(iter(series_map.values()))
    rows = {}
    for idx, obs in (first.get("observations") or {}).items():
        try:
            ts = _parse_period(time_values[int(idx)])
            val = obs[0] if isinstance(obs, list) else obs
            if ts is not None and val is not None:
                rows[ts] = float(val)
        except (ValueError, IndexError, TypeError):
            continue
    return pd.Series(rows, dtype=float).sort_index()


def _request(flow: str, key: str) -> pd.Series:
    Try several SDMX 3.0 URL styles / versions until one returns data.
    for version in FLOWS[flow]:
        urls = [
            f"{BASE_URL}/data/IMF.STA,{flow},{version}/{key}",
            f"{BASE_URL}/data/dataflow/IMF.STA/{flow}/{version}/{key}",
        ]
        for url in urls:
            try:
                r = requests.get(url, headers=HEADERS, timeout=60)
            except requests.RequestException:
                continue
            if r.status_code != 200:
                continue
            try:
                s = _parse_sdmx_json(r.json())
            except ValueError:
                continue
            if not s.empty:
                return s
    return pd.Series(dtype=float)


@st.cache_data(show_spinner=False, ttl=6 * 3600)
def fetch_cpi(iso: str) -> pd.Series:
    s = _request("CPI", f"{iso}.CPI._T.IX.M")
    return s[s.index >= START]


@st.cache_data(show_spinner=False, ttl=6 * 3600)
def fetch_lcu_per_usd(iso: str) -> pd.Series:
    Local-currency units per USD, period average, monthly.
    s = _request("ER", f"{iso}.XDC_USD.PA_RT.M")
    if s.empty:
        # Some dataflow versions publish the inverse (USD per local unit)
        inv = _request("ER", f"{iso}.USD_XDC.PA_RT.M")
        if not inv.empty:
            s = 1.0 / inv.replace(0, np.nan)
    if s.empty and iso == "USA":
        s = pd.Series(1.0, index=pd.date_range(START, pd.Timestamp.today().normalize().replace(day=1), freq="MS"))
    return s[s.index >= START].dropna()


# --------------------------------------------------------------------------- calculations
def build_panel(iso1: str, iso2: str) -> pd.DataFrame:
    p1, p2 = fetch_cpi(iso1), fetch_cpi(iso2)
    e1, e2 = fetch_lcu_per_usd(iso1), fetch_lcu_per_usd(iso2)
    df = pd.concat(
        {"CPI_1": p1, "CPI_2": p2, "LCU_per_USD_1": e1, "LCU_per_USD_2": e2}, axis=1
    ).sort_index()
    df.index.name = "date"
    # S = C2 units per C1 unit = (C2 per USD) / (C1 per USD)
    df["S"] = df["LCU_per_USD_2"] / df["LCU_per_USD_1"]
    df["RER"] = df["S"] * df["CPI_1"] / df["CPI_2"]
    df["valid"] = df[["CPI_1", "CPI_2", "S"]].notna().all(axis=1) & np.isfinite(df["RER"])
    return df


def apply_sample(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, float]:
    sample = df.loc[(df.index >= start) & (df.index <= end)].copy()
    rer_star = sample.loc[sample["valid"], "RER"].mean()
    sample["RER_star"] = rer_star
    sample["Real_Index"] = np.where(sample["valid"], 100.0 * sample["RER"] / rer_star, np.nan)
    return sample, rer_star


# --------------------------------------------------------------------------- UI
def make_chart(sample: pd.DataFrame, mode: str, n1: str, n2: str, c1: str, c2: str) -> go.Figure:
    real = go.Scatter(x=sample.index, y=sample["Real_Index"], name="Real Index (RER/RER* × 100)",
                      mode="lines", line=dict(color="#1f77b4", width=2), connectgaps=False)
    nom = go.Scatter(x=sample.index, y=sample["S"], name=f"Nominal S ({n2} per {n1})",
                     mode="lines", line=dict(color="#d62728", width=2, dash="dot" if mode == "Both" else "solid"),
                     connectgaps=False)
    if mode == "Both":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(real, secondary_y=False)
        fig.add_trace(nom, secondary_y=True)
        fig.update_yaxes(title_text="Real Index (sample average = 100)", secondary_y=False)
        fig.update_yaxes(title_text=f"Nominal S: {n2} per 1 {n1}", secondary_y=True, showgrid=False)
    else:
        fig = go.Figure(real if mode == "Real" else nom)
        if mode == "Real":
            fig.add_hline(y=100, line_dash="dash", line_color="gray")
            fig.update_yaxes(title_text="Real Index (sample average = 100)")
        else:
            fig.update_yaxes(title_text=f"Nominal S: {n2} per 1 {n1}")
    fig.update_layout(hovermode="x unified", height=520, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=1.08), title=f"{n1} → {n2}")
    fig.update_xaxes(title_text="Month", rangeslider=dict(visible=True))
    return fig


def main() -> None:
    st.set_page_config(page_title="IMF Real Exchange Rate Explorer", layout="wide")
    st.title("Real vs. nominal exchange rate (IMF data)")
    st.caption("S(t) = units of Country 2 currency per 1 unit of Country 1 currency · "
               "RER(t) = S(t) × P1(t) / P2(t) · Real Index = 100 × RER(t) / RER*")

    names = {iso: f"{n} ({iso})" for iso, n in COUNTRIES.items()}
    ordered = sorted(COUNTRIES, key=lambda k: COUNTRIES[k])
    with st.sidebar:
        st.header("Selection")
        iso1 = st.selectbox("Country 1 (base)", ordered, index=ordered.index("USA"), format_func=names.get)
        iso2 = st.selectbox("Country 2 (quote)", ordered, index=ordered.index("G163"), format_func=names.get)
        mode = st.radio("Chart", ["Real", "Nominal", "Both"], horizontal=True)

    if iso1 == iso2:
        st.warning("Please choose two different countries/areas.")
        return

    with st.spinner("Fetching IMF data…"):
        panel = build_panel(iso1, iso2)

    missing = [lbl for lbl, col in [(f"CPI – {COUNTRIES[iso1]}", "CPI_1"), (f"CPI – {COUNTRIES[iso2]}", "CPI_2"),
                                    (f"Exchange rate – {COUNTRIES[iso1]}", "LCU_per_USD_1"),
                                    (f"Exchange rate – {COUNTRIES[iso2]}", "LCU_per_USD_2")]
               if panel[col].dropna().empty]
    if missing:
        st.error("No data returned from the IMF for: " + "; ".join(missing) +
                 ". Try another country, or check your network / IMF API access.")
        return

    valid_idx = panel.index[panel["valid"]]
    if valid_idx.empty:
        st.error("The two series have no overlapping valid months.")
        return

    months = list(pd.date_range(valid_idx.min(), valid_idx.max(), freq="MS"))
    with st.sidebar:
        start, end = st.select_slider("Sample period", options=months, value=(months[0], months[-1]),
                                      format_func=lambda d: d.strftime("%Y-%m"))
    sample, rer_star = apply_sample(panel, start, end)
    n1, n2 = COUNTRIES[iso1], COUNTRIES[iso2]

    c1, c2, c3 = st.columns(3)
    c1.metric("RER* (sample average of RER)", f"{rer_star:,.4f}")
    c2.metric("Valid months in sample", f"{int(sample['valid'].sum())}")
    c3.metric("Latest Real Index", f"{sample['Real_Index'].dropna().iloc[-1]:,.1f}")

    st.plotly_chart(make_chart(sample, mode, n1, n2, iso1, iso2), use_container_width=True)

    out = sample.reset_index().rename(columns={
        "CPI_1": f"P1_CPI_{iso1}", "CPI_2": f"P2_CPI_{iso2}",
        "LCU_per_USD_1": f"{iso1}_LCU_per_USD", "LCU_per_USD_2": f"{iso2}_LCU_per_USD",
        "S": f"S_{iso2}_per_{iso1}", "RER": "RER", "RER_star": "RER_star",
        "Real_Index": "Real_Index", "valid": "valid_month",
    })
    out["date"] = out["date"].dt.strftime("%Y-%m")
    st.download_button("Download CSV (selected sample)", out.to_csv(index=False).encode("utf-8"),
                       file_name=f"rer_{iso1}_{iso2}_{start:%Y%m}_{end:%Y%m}.csv", mime="text/csv")
    with st.expander("Show data"):
        st.dataframe(out, use_container_width=True, hide_index=True)
    st.caption("Source: IMF SDMX 3.0 API (CPI and Exchange Rates dataflows). Months missing any input "
               "are excluded from RER* and left blank in the Real Index.")


if __name__ == "__main__":
    main()
