
from __future__ import annotations

import io
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

try:
    import pycountry
except ImportError:
    pycountry = None


# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="IMF Real Exchange Rate Explorer",
    page_icon="📈",
    layout="wide",
)

API_BASE = "https://api.imf.org/external/sdmx/3.0"
START_MONTH = "1976-01"
EURO_CODE = "G163"
TIMEOUT = 40

# The series keys follow the user's supplied IMF data hints.
# CPI and exchange-rate data may be published in different flows.
SERIES = {
    "CPI": {
        "key": "{code}.CPI._T.IX.M",
        "flows": [
            ("IMF.STA", "CPI"),
        ],
    },
    "FX": {
        "key": "{code}.XDC_USD.PA_RT.M",
        "flows": [
            ("IMF.STA", "IFS"),
            ("IMF.STA", "ER"),
            ("IMF.STA", "EXR"),
        ],
    },
}


# =========================================================
# COUNTRY OPTIONS
# =========================================================

@st.cache_data
def get_countries():
    """Build an ISO alpha-3 selector and add the Euro area."""

    countries = {"Euro area (G163)": EURO_CODE}

    if pycountry is not None:
        for item in pycountry.countries:
            code = getattr(item, "alpha_3", None)
            name = getattr(item, "name", None)
            if code and name:
                countries[f"{name} ({code})"] = code

    # Add common economy codes that can be absent from ISO lists.
    countries["Kosovo (UVK)"] = "UVK"
    countries["Taiwan (TWN)"] = "TWN"

    return dict(sorted(
        countries.items(),
        key=lambda item: (
            item[1] != EURO_CODE,
            item[0].casefold(),
        ),
    ))


# =========================================================
# IMF API
# =========================================================

def parse_period(value):
    """Convert SDMX monthly periods to pandas timestamps."""

    value = str(value).strip()

    # SDMX monthly dates often look like 2024-M01.
    value = value.replace("-M", "-")

    try:
        return pd.Period(value, freq="M").to_timestamp()
    except (ValueError, TypeError):
        return pd.NaT


def fetch_series(
    code: str,
    kind: str,
    end_month: str,
) -> pd.Series:
    """
    Fetch one IMF series using the SDMX 3.0 CSV response.

    A request uses the latest flow version (~). The flow candidates
    are tried in order because the exchange-rate flow must be
    confirmed against the current IMF catalogue.
    """

    spec = SERIES[kind]
    key = spec["key"].format(code=code)
    errors = []

    for agency, flow in spec["flows"]:
        url = (
            f"{API_BASE}/data/dataflow/"
            f"{agency}/{flow}/~/{key}"
        )

        params = {
            "startPeriod": START_MONTH,
            "endPeriod": end_month,
        }

        try:
            response = requests.get(
                url,
                params=params,
                headers={"Accept": "text/csv"},
                timeout=TIMEOUT,
            )

            if response.status_code == 204:
                errors.append(f"{flow}: no data returned")
                continue

            if response.status_code in (400, 404):
                errors.append(
                    f"{flow}: HTTP {response.status_code}"
                )
                continue

            response.raise_for_status()

            content = response.text.strip()
            if not content:
                errors.append(f"{flow}: empty response")
                continue

            # IMF may return a structured error rather than CSV.
            if content.startswith("<"):
                errors.append(
                    f"{flow}: XML response instead of CSV"
                )
                continue

            frame = pd.read_csv(io.StringIO(content))

            # Normalize column names.
            frame.columns = [
                str(col).strip().upper()
                for col in frame.columns
            ]

            if not {"TIME_PERIOD", "OBS_VALUE"}.issubset(
                frame.columns
            ):
                errors.append(
                    f"{flow}: missing TIME_PERIOD/OBS_VALUE "
                    f"columns; got {list(frame.columns)}"
                )
                continue

            frame["Date"] = frame["TIME_PERIOD"].map(parse_period)
            frame["Value"] = pd.to_numeric(
                frame["OBS_VALUE"],
                errors="coerce",
            )

            frame = frame.dropna(subset=["Date", "Value"])
            frame = frame[
                (frame["Date"] >= pd.Timestamp(START_MONTH))
                & (
                    frame["Date"]
                    <= pd.Period(end_month, freq="M").to_timestamp()
                )
            ]

            if frame.empty:
                errors.append(
                    f"{flow}: no monthly observations for {code}"
                )
                continue

            result = (
                frame.sort_values("Date")
                .drop_duplicates("Date", keep="last")
                .set_index("Date")["Value"]
                .astype(float)
            )

            result.name = kind
            return result

        except (
            requests.RequestException,
            pd.errors.ParserError,
            ValueError,
        ) as exc:
            errors.append(f"{flow}: {type(exc).__name__}: {exc}")

    raise RuntimeError(
        f"Could not retrieve {kind} for {code}. "
        "The series may be unavailable or the IMF flow may differ. "
        + " | ".join(errors)
    )


@st.cache_data(ttl=21600, show_spinner=False)
def load_country(code: str, end_month: str) -> pd.DataFrame:
    """Load monthly CPI and local-currency-per-USD exchange rates."""

    cpi = fetch_series(code, "CPI", end_month)
    fx = fetch_series(code, "FX", end_month)

    cpi.name = "CPI"
    fx.name = "Local_currency_per_USD"

    return pd.concat([cpi, fx], axis=1).sort_index()


# =========================================================
# CALCULATIONS
# =========================================================

def calculate_sample(
    country1: pd.DataFrame,
    country2: pd.DataFrame,
    name1: str,
    name2: str,
    start_date: date,
    end_date: date,
):
    """Calculate nominal S, RER, sample mean, and real index."""

    a = country1.rename(columns={
        "CPI": "P1_CPI",
        "Local_currency_per_USD": "X1_per_USD",
    })

    b = country2.rename(columns={
        "CPI": "P2_CPI",
        "Local_currency_per_USD": "X2_per_USD",
    })

    df = a.join(b, how="outer").sort_index()
    df.index.name = "Date"

    start = pd.Timestamp(start_date).to_period("M").to_timestamp()
    end = pd.Timestamp(end_date).to_period("M").to_timestamp()

    df = df.loc[(df.index >= start) & (df.index <= end)].copy()

    # X1 and X2 are local-currency units per USD.
    # Therefore X2 / X1 is units of currency 2 per currency 1.
    valid_fx = (
        df["X1_per_USD"].gt(0)
        & df["X2_per_USD"].gt(0)
    )

    df["S_nominal"] = (
        df["X2_per_USD"] / df["X1_per_USD"]
    ).where(valid_fx)

    valid_cpi = df["P1_CPI"].gt(0) & df["P2_CPI"].gt(0)

    df["RER"] = (
        df["S_nominal"] * df["P1_CPI"] / df["P2_CPI"]
    ).where(valid_fx & valid_cpi)

    df["RER"] = df["RER"].where(
        df["RER"].map(
            lambda x: pd.notna(x) and abs(x) != float("inf")
        )
    )

    # Mean over valid RER months in the selected sample.
    rer_star = (
        float(df["RER"].dropna().mean())
        if df["RER"].notna().any()
        else float("nan")
    )

    if pd.notna(rer_star) and rer_star != 0:
        df["Real_Index"] = 100.0 * df["RER"] / rer_star
    else:
        df["Real_Index"] = float("nan")

    df["Country1"] = name1
    df["Country2"] = name2
    df["Sample_RER_Mean"] = rer_star

    return df.reset_index(), rer_star


# =========================================================
# CHART
# =========================================================

def create_chart(df, mode, name1, name2):
    """Create a Plotly chart, with separate axes for Both."""

    if mode == "Both":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    else:
        fig = go.Figure()

    if mode in ("Real", "Both"):
        trace = go.Scatter(
            x=df["Date"],
            y=df["Real_Index"],
            name="Real Index",
            mode="lines",
            connectgaps=False,
            line={"color": "#1769AA", "width": 2},
            hovertemplate=(
                "%{x|%Y-%m}<br>Real Index: %{y:.4f}"
                "<extra></extra>"
            ),
        )
        if mode == "Both":
            fig.add_trace(trace, secondary_y=False)
        else:
            fig.add_trace(trace)

    if mode in ("Nominal", "Both"):
        trace = go.Scatter(
            x=df["Date"],
            y=df["S_nominal"],
            name=f"Nominal ({name2} per {name1})",
            mode="lines",
            connectgaps=False,
            line={"color": "#D97706", "width": 2},
            hovertemplate=(
                "%{x|%Y-%m}<br>Nominal S: %{y:.8g}"
                "<extra></extra>"
            ),
        )
        if mode == "Both":
            fig.add_trace(trace, secondary_y=True)
        else:
            fig.add_trace(trace)

    fig.update_layout(
        template="plotly_white",
        title=f"{name1} / {name2}",
        hovermode="x unified",
        height=560,
        legend={"orientation": "h", "y": 1.12},
        margin={"l": 30, "r": 30, "t": 85, "b": 35},
    )

    if mode == "Both":
        fig.update_yaxes(
            title_text="Real Index (sample mean = 100)",
            secondary_y=False,
        )
        fig.update_yaxes(
            title_text=f"Nominal S ({name2} per {name1})",
            secondary_y=True,
        )
    elif mode == "Real":
        fig.update_yaxes(title_text="Real Index (sample mean = 100)")
    else:
        fig.update_yaxes(
            title_text=f"Nominal S ({name2} per {name1})"
        )

    fig.update_xaxes(
        title_text="Month",
        rangeslider_visible=True,
    )

    return fig


# =========================================================
# USER INTERFACE
# =========================================================

st.title("IMF Real Exchange Rate Explorer")

st.write(
    "Compare monthly nominal and CPI-adjusted exchange rates. "
    "Historical observations are requested from January 1976, "
    "where available."
)

st.info(
    "The real index is normalized to the mean RER over the selected "
    "sample. Changing the date range recalculates the mean. "
    "The nominal rate is never normalized."
)

countries = get_countries()
labels = list(countries)

default1 = next(
    (i for i, label in enumerate(labels) if countries[label] == "USA"),
    0,
)
default2 = next(
    (i for i, label in enumerate(labels) if countries[label] == "JPN"),
    min(1, len(labels) - 1),
)

col1, col2 = st.columns(2)

with col1:
    label1 = st.selectbox("Country 1", labels, index=default1)

with col2:
    label2 = st.selectbox("Country 2", labels, index=default2)

code1 = countries[label1]
code2 = countries[label2]

if code1 == code2:
    st.error("Please choose two different economies.")
    st.stop()

today = date.today()
this_month = pd.Timestamp(today).to_period("M").to_timestamp().date()
earliest = date(1976, 1, 1)

d1, d2 = st.columns(2)

with d1:
    start_date = st.date_input(
        "Start month",
        value=earliest,
        min_value=earliest,
        max_value=this_month,
        key="sample_start",
    )

with d2:
    end_date = st.date_input(
        "End month",
        value=this_month,
        min_value=earliest,
        max_value=this_month,
        key="sample_end",
    )

mode = st.radio(
    "Chart",
    ["Real", "Nominal", "Both"],
    horizontal=True,
)

if start_date > end_date:
    st.error("Start month must not be after end month.")
    st.stop()

end_month = pd.Timestamp(end_date).strftime("%Y-%m")

try:
    with st.spinner("Downloading IMF monthly data..."):
        data1 = load_country(code1, end_month)
        data2 = load_country(code2, end_month)

    sample, rer_star = calculate_sample(
        data1,
        data2,
        label1,
        label2,
        start_date,
        end_date,
    )

except Exception as exc:
    st.error("Unable to load the selected IMF series.")
    st.markdown(
        "The IMF flow or series may be unavailable, or the API may "
        "have changed its response. Expand the details below to "
        "identify the failing request."
    )
    with st.expander("Technical error details", expanded=True):
        st.code(f"{type(exc).__name__}: {exc}")
    st.link_button(
        "Open IMF API documentation",
        "https://data.imf.org/en/Resource-Pages/IMF-API",
    )
    st.stop()

if sample.empty:
    st.warning("No observations are available in this sample period.")
    st.stop()

valid_rer = int(sample["RER"].notna().sum())
valid_nominal = int(sample["S_nominal"].notna().sum())

m1, m2, m3 = st.columns(3)
m1.metric("Months in sample", f"{len(sample):,}")
m2.metric("Valid RER months", f"{valid_rer:,}")
m3.metric(
    "Sample mean RER*",
    f"{rer_star:.6g}" if pd.notna(rer_star) else "Unavailable",
)

if valid_rer == 0:
    st.warning(
        "No months have valid CPI and exchange-rate observations "
        "for both economies. The nominal rate may still be available."
    )

st.plotly_chart(
    create_chart(sample, mode, code1, code2),
    use_container_width=True,
)

# =========================================================
# OBSERVATIONS TABLE
# =========================================================

st.subheader("Observations and calculations")

columns = [
    "Date",
    "Country1",
    "Country2",
    "P1_CPI",
    "P2_CPI",
    "X1_per_USD",
    "X2_per_USD",
    "S_nominal",
    "RER",
    "Sample_RER_Mean",
    "Real_Index",
]

table = sample[columns].copy()
table["Date"] = pd.to_datetime(table["Date"]).dt.strftime("%Y-%m")

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
)

# =========================================================
# CSV DOWNLOAD
# =========================================================

csv_data = sample[columns].to_csv(
    index=False,
    na_rep="",
    date_format="%Y-%m-%d",
).encode("utf-8")

filename = (
    f"rer_{code1}_{code2}_"
    f"{pd.Timestamp(start_date).strftime('%Y%m')}_"
    f"{pd.Timestamp(end_date).strftime('%Y%m')}.csv"
)

st.download_button(
    "Download all sample observations as CSV",
    data=csv_data,
    file_name=filename,
    mime="text/csv",
)

# =========================================================
# METHODOLOGY
# =========================================================

with st.expander("Methodology"):
    st.markdown(
        r"""
        **Nominal exchange rate**

        The IMF exchange-rate series is local currency units per USD.
        Let \(X_1(t)\) and \(X_2(t)\) be those series.

        \[
        S(t) = \frac{X_2(t)}{X_1(t)}
        \]

        This gives units of Country 2 currency per unit of Country 1
        currency.

        **Real exchange rate**

        \[
        RER(t) = S(t) \times \frac{P_1(t)}{P_2(t)}
        \]

        **Selected-sample mean**

        \[
        RER^* = \frac{1}{N}\sum_{t \in V} RER(t)
        \]

        Here, \(V\) is the set of valid months in the selected period.

        **Real index**

        \[
        RealIndex(t) = 100 \times \frac{RER(t)}{RER^*}
        \]

        The real index averages 100 over valid observations in the
        selected sample. This benchmark is not necessarily an
        equilibrium exchange rate.

        Missing observations are not interpolated.
        """
    )

st.caption(
    "Source: IMF. January 1976 is the earliest requested month; "
    "actual data availability varies by economy and series."
)
