
# IMF Real Exchange Rate Explorer

A Streamlit application for comparing monthly nominal and real bilateral
exchange rates using IMF CPI and exchange-rate observations.

## Features

- Select Country 1 and Country 2, including the Euro area (G163).
- Request monthly IMF data from January 1976 where available.
- Calculate the nominal bilateral exchange rate in the requested direction.
- Calculate the real exchange rate using the two countries' CPIs.
- Normalize the real index to 100 at the selected sample average.
- Recalculate the benchmark whenever the sample dates change.
- Display Real, Nominal, or Both series in interactive Plotly charts.
- Use separate vertical axes when both series are displayed.
- Download the selected sample observations and calculations as CSV.
- Display diagnostic details when an IMF request fails.

## Requirements

- Python 3.12
- GitHub repository
- Streamlit Community Cloud or a local Streamlit installation
- Internet access to the IMF API

## Files

```text
.
├── app.py
├── requirements.txt
└── README.md
```

## Run locally

Create and activate a virtual environment if desired.

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the application:

```bash
python -m streamlit run app.py
```

Streamlit will print a local URL, usually:

```text
http://localhost:8501
```

Open that URL in your browser.

## Deploy on Streamlit Community Cloud

1. Push all three files to a GitHub repository.
2. Open https://share.streamlit.io/.
3. Create a new app and connect your GitHub repository.
4. Select `app.py` as the main file.
5. Deploy the application.

## Definitions

Let:

- `X1(t)` = Country 1 currency units per USD.
- `X2(t)` = Country 2 currency units per USD.
- `P1(t)` = Country 1 monthly CPI.
- `P2(t)` = Country 2 monthly CPI.

The nominal bilateral exchange rate is:

```text
S(t) = X2(t) / X1(t)
```

Its units are Country 2 currency per one unit of Country 1 currency.

The real exchange rate is:

```text
RER(t) = S(t) * P1(t) / P2(t)
```

For the selected sample, calculate the arithmetic mean over valid months:

```text
RER* = mean(RER(t) for valid months in the selected sample)
```

The real index is:

```text
Real Index(t) = 100 * RER(t) / RER*
```

Changing either sample date recalculates `RER*`.

The nominal series is not normalized.

## Missing data

Historical coverage varies by country and series. January 1976 is the
earliest requested month, not a guarantee of availability.

The application does not interpolate missing observations. RER is
calculated only when both CPIs and both exchange-rate observations are
positive and available for that month.

## IMF API

The application uses the IMF SDMX 3.0 API:

https://api.imf.org/external/sdmx/3.0

Official API information:

https://data.imf.org/en/Resource-Pages/IMF-API

The CPI and exchange-rate dataflow identifiers and series keys must
match the current IMF catalogue. If a series cannot be retrieved,
check the application's technical error details and verify the flow
and key against the IMF API documentation.

## CSV export

The CSV contains all monthly rows in the selected sample, including
available source values and calculated columns:

- Date
- Country1 and Country2
- P1_CPI and P2_CPI
- X1_per_USD and X2_per_USD
- S_nominal
- RER
- Sample_RER_Mean
- Real_Index

Missing values are exported as empty cells.

## Disclaimer

The sample-average benchmark is a normalization reference. It is not
necessarily an estimate of the equilibrium real exchange rate.

This project is for research and educational purposes. Verify data
coverage, series definitions, and calculations before relying on the
results for policy or investment decisions.
