IMF Real Exchange Rate Explorer

A Streamlit app (Python 3.12) that pulls monthly CPI and exchange-rate data from the IMF SDMX 3.0 API and charts the nominal and real bilateral exchange rate for any two IMF countries or the Euro area.

Definitions
S(t) – units of Country 2 currency per one unit of Country 1 currency (nominal, plotted in actual units). IMF rates are local currency per USD, so S = (C2 per USD) / (C1 per USD).
P1(t), P2(t) – monthly CPI indices ({ISO3}.CPI._T.IX.M).
RER(t) = S(t) × P1(t) / P2(t)
RER* = average of RER(t) over valid months (all of P1, P2, S present) in the selected sample. It is recalculated whenever the sample start/end changes.
Real Index(t) = 100 × RER(t) / RER* (so the sample average is 100).

Data start in January 1976 where available. The Euro area uses IMF code G163.

Run
bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
Features
Pick Country 1 and Country 2; choose Real, Nominal or Both (Both uses separate y-axes).
Month-range slider for the sample period; RER* and the Real Index update automatically.
Download CSV with every observation and calculation in the selected sample (CPIs, local-currency-per-USD rates, S, RER, RER*, Real Index, valid-month flag).
Notes
Exchange rates use {ISO3}.XDC_USD.PA_RT.M (period average, local currency per USD). If a dataflow version only has USD_XDC, the app inverts it. The USA is set to 1 if no series is returned.
The app tries several SDMX 3.0 URL styles/dataflow versions (CPI 5.0.0, ER 4.0.1, then +) because IMF versions have changed over time. If your account needs a subscription key, set IMF_SDMX_SUBSCRIPTION_KEY in the environment.
Results are cached for 6 hours. Euro-area members that adopted the euro have their own series switch to euro units from adoption; check for breaks when using such countries.
The IMF API could not be reached from the environment where this code was written, so it is untested against the live service. If a series fails to parse, check the URL/headers in _request first.
