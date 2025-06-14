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
    columns_to_remove = ['storey_range', 'flat_model', 'lease_commence_date', 'remaining_lease']
    return_df = return_df.drop(columns=columns_to_remove)
    return(return_df)
def price_to_rgb(x):
    if x < 0.5:
        # green to yellow
        r = int(2*x*255)
        g = 255
        b = 0
        return f"rgb({r}, {g}, {b})"
    else:
        # yellow to red
        r = 255
        g = int(2*(1-x)*255)
        b = 0
        return f"rgb({r}, {g}, {b})"
def add_alpha(color_str, alpha=1.0):
    # color_str is like "rgb(r, g, b)"
    # convert to "rgba(r, g, b, alpha)"
    return color_str.replace("rgb", "rgba").replace(")", f", {alpha})")
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
def rgba_str_to_pydeck_color(rgba_str):
    # rgba_str like "rgba(209, 255, 0, 1.0)"
    parts = rgba_str.strip("rgba()").split(",")
    r, g, b = map(int, parts[:3])
    a = float(parts[3])
    a_int = int(a * 255)
    return [r, g, b, a_int]
# Get Data #############################################################################################
st.title("How much is resale HDB?")
hdb_df = download_resale_hdb_dataset()
df = pd.read_csv('postal_code_latlong_all_latlong.csv')

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
chart = alt.Chart(price_data).mark_bar().encode(
    x=alt.X('price_bin:N', 
            sort=sorted_bins,   # <-- explicitly set order here
            title=None, 
            axis=alt.Axis(labelAngle=0)),
    y=alt.Y('count:Q', title=None, axis=alt.Axis(labels=False, ticks=False)),
    tooltip=['price_bin', 'count']
).properties(height=100)
# Display chart
st.markdown(
    "<label style='font-weight: 500; font-size: 0.875rem;'>Price Distribution</label>",
    unsafe_allow_html=True
)
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
hdb_df = hdb_df.merge(
    df[["block", "street_name", "lat", "lon"]],
    on=["block", "street_name"],
    how="left"
)
# st.dataframe(hdb_df)

# Clean up those missing coordinates
missing_coords_df = hdb_df[hdb_df['lat'].isna() | hdb_df['lon'].isna()]
hdb_df = hdb_df.dropna(subset=['lat', 'lon'])


# Colouring
min_price = hdb_df["resale_price"].min()
max_price = hdb_df["resale_price"].max()
median_price = hdb_df["resale_price"].median()
hdb_df["norm_price"] = (hdb_df["resale_price"] - min_price) / median_price
hdb_df["highlight"] = hdb_df["resale_price"].between(highlight_range[0], highlight_range[1])
hdb_df["color"] = hdb_df["norm_price"].apply(price_to_rgb)
hdb_df["color"] = hdb_df.apply(
    lambda row: add_alpha(row["color"], alpha=1.0 if row["highlight"] else 0.2),
    axis=1
)
hdb_df["color"] = hdb_df["color"].apply(rgba_str_to_pydeck_color)


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
# st.dataframe(hdb_df)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=hdb_df,
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
        "html": "<b>{town}</b><br><b>{block}</b> <b>{street_name}</b><br>{flat_type}<br>${resale_price}",
        "style": {"backgroundColor": "white", "color": "black"}
    }
))

if not missing_coords_df.empty:
    st.text("Transactions for the following new blocks are new and are missing coordinate data. They will not show up on the map. ")
    st.dataframe(missing_coords_df)