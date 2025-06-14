import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import requests
import urllib.parse
import json
import altair as alt
import calendar
from dateutil.relativedelta import relativedelta
from datetime import datetime
from datetime import date
from io import StringIO
from pathlib import Path

# Instantiate
current_path = Path.cwd()
datasets = [ # These datasets are from 'Resale Flat Prices' https://data.gov.sg/collections/189/view
    "d_ebc5ab87086db484f88045b47411ebc5",
    "d_43f493c6c50d54243cc1eab0df142d6a",
    "d_2d5ff9ea31397b66239f245f57751537",
    "d_ea9ed51da2787afaf8e51f827c304208",
    "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"
]

# Download datasets
@st.cache_data
def download_resale_hdb_dataset():
    temp_dfs = []
    for dataset in datasets:
        response = requests.get(
            "https://api-open.data.gov.sg/v1/public/api/datasets/"+ dataset +"/initiate-download",
            headers={"Content-Type":"application/json"}
        )
        response = requests.get(response.json().get('data').get('url'))
        response = response.content.decode('utf-8')
        temp_df = pd.read_csv(StringIO(response))
        temp_dfs.append(temp_df)
    return_df = pd.concat(temp_dfs, ignore_index=True)
    return_df['flat_type'] = return_df['flat_type'].str.replace('MULTI GENERATION', 'MULTI-GENERATION', case=False, regex=True)
    columns_to_remove = ['storey_range', 'flat_model', 'remaining_lease']
    return_df = return_df.drop(columns=columns_to_remove)
    return(return_df)
def price_to_rgb(x):
    midpoint = 0.75  # set this to 0.66 or 0.75 as needed
    if x < midpoint:
        # green to yellow
        r = int((x / midpoint) * 255)
        g = 255
        b = 0
    else:
        # yellow to red
        r = 255
        g = int(((1 - x) / (1 - midpoint)) * 255)
        b = 0
    return f"rgb({r}, {g}, {b})"
def extract_price_bin_value(x):
    if x == "≥ $1M":
        return float('inf')  # push to the end
    else:
        return int(x.replace("$", "").replace(",", ""))
def bin_price(price):
    if price >= limit:
        return "≥ $1M"
    else:
        return f"${int((price // bin_width) * bin_width):,}"
def rgb_str_to_pydeck_color(rgba_str):
    parts = rgba_str.strip("rgb()").split(",")
    r, g, b = map(int, parts[:3])
    return [r, g, b]
def extract_bin_midpoint(bin_str):
    if bin_str == "≥ $1M":
        return 1_050_000  # or some higher value to normalize
    else:
        base = int(bin_str.replace("$", "").replace(",", ""))
        return base + bin_width / 2
def format_and_filter_transactions(txns,period):
    # Get the cutoff date N months ago
    cutoff = datetime.today().replace(day=1) - relativedelta(months=period)
    # Filter and format
    return "<br>".join(
        [
            f"{t['month']}: ${int(t['resale_price']):,}"
            for t in txns
            if datetime.strptime(t['month'], "%Y-%m") >= cutoff
        ]
    )
@st.cache_data
def collate_past_transactions(df):
    collapsed_df = df.groupby(['town', 'flat_type', 'block', 'street_name']).apply(
        lambda g: pd.Series({
            'past_transactions': [
                {"month": row['month'], "resale_price": row['resale_price']}
                for _, row in g.sort_values("month", ascending=False).iterrows()
            ]
        })
    ).reset_index()
    return collapsed_df

# Get Data #############################################################################################
hdb_df = download_resale_hdb_dataset()
df = pd.read_csv('postal_code_latlong_all_latlong.csv')
past_prices_df = collate_past_transactions(hdb_df)

st.title("How much is resale HDB?")
earliest_date = pd.to_datetime(hdb_df['month'].min())
latest_date = pd.to_datetime(hdb_df['month'].max())
st.text("Property data from " + earliest_date.strftime('%b') + " " + str(earliest_date.year) + " to "+ latest_date.strftime('%b') + " " + str(latest_date.year) + " from https://data.gov.sg/collections/189/view")
st.divider()

# Filtering ############################################################################################
today = datetime.today()
records_start = pd.to_datetime(hdb_df['month'].min(), format='%Y-%m')
past_months_max_val = (today.year-records_start.year)*12+today.month
past_months = st.number_input("Use average resale price of past _ months", value=12, min_value=1, max_value=past_months_max_val)
hdb_df['month_dt'] = pd.to_datetime(hdb_df['month'], format='%Y-%m')
hdb_df.sort_values(by='month_dt', ascending=False)
cutoff_date = datetime.today() - relativedelta(months=past_months)
hdb_df = hdb_df[hdb_df['month_dt'] >= cutoff_date]

flat_types = sorted(hdb_df['flat_type'].unique())
selected_flat_type = st.pills("Desired Flat Type", options=flat_types, default=flat_types, selection_mode="multi")
hdb_df = hdb_df[(hdb_df['flat_type'].isin(selected_flat_type))]
towns = sorted(hdb_df['town'].unique())
selected_town = st.pills("Desired Towns", options=towns, default=towns, selection_mode="multi")
hdb_df = hdb_df[(hdb_df['town'].isin(selected_town))]

# Show price distribution ##############################################################################
# Define bin width and threshold
bin_width = 20000
limit = 1000000
hdb_df['price_bin'] = hdb_df['resale_price'].apply(bin_price)
# Count entries per bin and sort (custom sort to put "≥ $1M" last)
price_data = hdb_df['price_bin'].value_counts().reset_index()
price_data.columns = ['price_bin', 'count']
price_data = price_data.sort_values(
    by='price_bin',
    key=lambda col: col.map(extract_price_bin_value)
)
# Create a sorted list of categories based on your mapped numeric values
sorted_bins = price_data['price_bin'].tolist()
st.markdown(
    "<label style='font-weight: 500; font-size: 0.875rem;'>Filter by Price Distribution</label>",
    unsafe_allow_html=True
)
min_price = hdb_df["resale_price"].min()
max_price = hdb_df["resale_price"].max()
median_price = hdb_df["resale_price"].median()
price_data["mid_price"] = price_data["price_bin"].apply(extract_bin_midpoint)
price_data["norm_price"] = (price_data["mid_price"] - min_price) / median_price
price_data["color"] = price_data["norm_price"].apply(price_to_rgb)
chart = alt.Chart(price_data).mark_bar().encode(
    x=alt.X('price_bin:N', 
            sort=sorted_bins,
            title=None, 
            axis=alt.Axis(labelAngle=0)),
    y=alt.Y('count:Q', title=None, axis=alt.Axis(labels=False, ticks=False)),
    color=alt.Color('color:N', scale=None),  # disable Altair scale
    tooltip=['price_bin', 'count']
).properties(height=100)
st.altair_chart(chart, use_container_width=True)

# Range of resale_price
min_price = int(hdb_df['resale_price'].min() // bin_width * bin_width)
max_price = min(limit, int(hdb_df['resale_price'].max() // bin_width * bin_width) + bin_width)
# Streamlit slider for price range
highlight_range = st.slider(
    "", 
    label_visibility="collapsed",
    min_value=min_price, 
    max_value=max_price, 
    value=(min_price, max_price), 
    step=bin_width, 
    format="$%d"
)
# st.dataframe(hdb_df)

hdb_df = hdb_df[
    (hdb_df['flat_type'].isin(selected_flat_type)) &
    (hdb_df['town'].isin(selected_town))
    ]
columns_to_remove = ['month', 'month_dt','price_bin']
hdb_df = hdb_df.drop(columns=columns_to_remove)
hdb_df = hdb_df.groupby(['town','flat_type','block', 'street_name'], as_index=False).mean()
hdb_df = hdb_df.round().astype({col: 'int' for col in hdb_df.select_dtypes('float').columns})
hdb_df = hdb_df.merge( # merging for coordinates
    df[["block", "street_name", "lat", "lon"]],
    on=["block", "street_name"],
    how="left"
)
hdb_df = hdb_df.merge( # merging for past transactions
    past_prices_df[["flat_type","block", "street_name", "past_transactions"]],
    on=["flat_type","block", "street_name"],
    how="left"
)
# st.dataframe(hdb_df)

# Clean up those missing coordinates
missing_coords_df = hdb_df[hdb_df['lat'].isna() | hdb_df['lon'].isna()]
hdb_df = hdb_df.dropna(subset=['lat', 'lon'])


# Colouring
hdb_df["norm_price"] = (hdb_df["resale_price"] - min_price) / median_price
hdb_df["highlight"] = hdb_df["resale_price"].between(highlight_range[0], highlight_range[1])
hdb_df["color"] = hdb_df["norm_price"].apply(price_to_rgb)
# hdb_df["color"] = hdb_df.apply(
#     lambda row: add_alpha(row["color"], alpha=1.0 if row["highlight"] else 0.1),
#     axis=1
# )
hdb_df["color"] = hdb_df["color"].apply(rgb_str_to_pydeck_color)


# Take and create another df if no latlong

# st.dataframe(hdb_df)
room_types_df = (
    hdb_df.groupby(['block', 'street_name'])['flat_type']
    .unique()
    .reset_index()
    .rename(columns={'flat_type': 'room_types'})
)
room_types_df = room_types_df[room_types_df['room_types'].apply(len) > 1]
# st.dataframe(room_types_df)
# Go through each row in room_types_df
for _, row in room_types_df.iterrows():
    block = row['block']
    street = row['street_name']
    types = row['room_types']
    
    for i, room_type in enumerate(types):
        if i == 0:
            continue  # Skip the first type, leave lat unchanged

        offset = -0.000075 * i
        mask = (
            (hdb_df['block'] == block) &
            (hdb_df['street_name'] == street) &
            (hdb_df['flat_type'] == room_type)
        )
        hdb_df.loc[mask, 'lat'] += offset

hdb_df["past_transactions_html"] = hdb_df["past_transactions"].apply(
    lambda txns: format_and_filter_transactions(txns, period=12)
)
hdb_df["lease_commence_date"] = 99-(today.year-hdb_df["lease_commence_date"])
hdb_df['resale_price_formatted'] = hdb_df['resale_price'].apply(lambda x: f"{int(x):,}")

# st.dataframe(hdb_df)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=hdb_df[hdb_df['highlight']],
    get_position='[lon, lat]',
    get_radius=10,
    get_fill_color='color',
    radiusMinPixels=5,   # minimum pixel size
    radiusMaxPixels=5,   # maximum pixel size
    radiusScale=1,       # scale factor (keep at 1 if using fixed pixels)
    pickable=True
)

view_state = pdk.ViewState(
    latitude=hdb_df['lat'].mean(),
    longitude=hdb_df['lon'].mean(),
    zoom=11
)



st.pydeck_chart(pdk.Deck(
    map_style="mapbox://styles/mapbox/dark-v10",
    initial_view_state=view_state,
    layers=[layer],
    tooltip={
    "html": """
        <b>{town}</b><br>
        <b>{block}</b> <b>{street_name}</b><br>
        {flat_type} - ${resale_price_formatted}<br>
        Remaining Lease - {lease_commence_date} years<br>
        <hr style="margin:2px 0">
        <b>Past Transactions:</b><br>{past_transactions_html}
    """,
    "style": {
        "backgroundColor": "white",
        "color": "black"
    }
}
))

if not missing_coords_df.empty:
    st.text("Transactions for the following new blocks are new and are missing coordinate data. They will not show up on the map. ")
    st.dataframe(missing_coords_df)