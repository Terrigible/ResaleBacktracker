import requests
import json
import pandas as pd
import calendar
import streamlit as st
from dateutil.relativedelta import relativedelta
from datetime import datetime
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
months = list(calendar.month_name)[1:]

# Download datasets
@st.cache_data
def download_datasets():
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
    columns_to_remove = ['block', 'street_name', 'storey_range', 'floor_area_sqm', 'flat_model', 'lease_commence_date', 'remaining_lease']
    return_df = return_df.drop(columns=columns_to_remove)
    return(return_df)

# Months diff
def months_diff(future_year, future_month):
    today = datetime.today()
    year_diff = future_year - today.year
    month_diff = future_month - today.month
    total_months = year_diff * 12 + month_diff
    return total_months

# Main function here
df = download_datasets()

# Form inputs below
################################################################################################
st.title("Can you afford a resale HDB?")
earliest_date = pd.to_datetime(df['month'].min())
latest_date = pd.to_datetime(df['month'].max())
st.text("Property data from " + earliest_date.strftime('%b') + " " + str(earliest_date.year) + " to "+ latest_date.strftime('%b') + " " + str(latest_date.year) + " from https://data.gov.sg/collections/189/view.")
st.divider()
################################################################################################
st.write("### Bank+CPF(OA) Projections")
st.write("###### Bank Details")
bank_bal = st.number_input("Current Bank Balance")
bank_bal_inc = st.number_input("Average Bank Increase per Month")
bank_annual_int = st.number_input("Annual Bank Interest (%)", value=2.5,step=0.01, format="%.2f")
st.write("###### CPF(OA) Details")
cpf_bal = st.number_input("Current CPF(OA) Balance")
cpf_bal_inc = st.number_input("Average CPF(OA) Increase per Month")
#cpf_annual_int = st.number_input("Annual CPF(OA) Interest (%)", value=2.5,step=0.01, format="%.2f")
st.write("###### Annual Raise Details")
expected_annual_raise = st.number_input("Expected Annual Raise (%)", value=3.0,step=0.01, format="%.2f")
expected_annual_raise_month = st.selectbox("Annual Raise Month", months)
st.divider()
################################################################################################
st.write("### Your Timeline")
current_age = st.number_input("Current Age", value=0)
buying_age = st.number_input("Buying Age", value=35)
years_to = int(buying_age)-int(current_age)
buying_year = datetime.today().year + years_to
buying_month = st.selectbox("Buying Month", months)
month_number = datetime.strptime(buying_month, "%B").month
months_to = months_diff(buying_year, month_number)
if current_age>0 and buying_age and buying_month:
    st.success(f"You are buying in {months_to} months time, on {buying_month} {buying_year}. ")
st.divider()
################################################################################################
if bank_bal and bank_bal_inc and cpf_bal and cpf_bal_inc and current_age>0:
    st.write(f"### Your {months_to} Months Projection")
    columns = [
        'Bank Increase',
        'Bank Interest',
        'Bank Balance',
        'CPF Increase',
        'CPF(OA) Interest',
        'CPF(OA) Balance',
        'Total balance'
    ]
    next_row = {
        'Bank Increase': bank_bal_inc,
        'Bank Interest': 0,
        'Bank Balance': bank_bal,
        'CPF Increase': cpf_bal_inc,
        'CPF(OA) Interest': 0,
        'CPF(OA) Balance': cpf_bal,
        'Total balance': 0
    }
    proj_df = pd.DataFrame(columns=columns)
    current_date = datetime.today()
    next_date = current_date + relativedelta(months=1)
    pending_cpf = []
    for row in range(0,months_to-1):
        next_date += relativedelta(months=1)
        ## Count Bank Balance
        # Annual increment month
        if next_date.month == datetime.strptime(expected_annual_raise_month, "%B").month:
            bank_bal_inc += expected_annual_raise/100*bank_bal_inc
            cpf_bal_inc += expected_annual_raise/100*cpf_bal_inc
            next_row['Bank Increase']=bank_bal_inc
            next_row['CPF Increase']=cpf_bal_inc
        next_row['Bank Interest']=next_row['Bank Balance']*bank_annual_int/12/100
        next_row['Bank Balance']=next_row['Bank Balance']+next_row['Bank Interest']+bank_bal_inc
        ## Count CPF Balance
        if next_date.month == 1:
            for interest in pending_cpf:
                next_row['CPF(OA) Balance'] += interest
            pending_cpf = []
        next_row['CPF(OA) Interest']=next_row['CPF(OA) Balance']*2.5/12/100
        pending_cpf.append(next_row['CPF(OA) Interest'])
        next_row['CPF(OA) Balance'] += next_row['CPF Increase']
        # Add row
        next_row['Total balance']=next_row['Bank Balance']+next_row['CPF(OA) Balance']
        next_row_pd = pd.DataFrame([next_row],index=[next_date.strftime("%Y-%m")])
        proj_df = pd.concat([proj_df, next_row_pd])
    # Create an empty DataFrame with the specified columns
    proj_df.index.name = 'Year/Month'
    proj_df = proj_df.round(2)
    st.dataframe(proj_df)
    st.success(f"You will have ${next_row['Total balance']:,.2f} on {buying_month} {buying_year}. ")
    st.divider()
################################################################################################
    st.write("### Usage for Downpayment")
    col1, col2 = st.columns([4, 1])
    col3, col4 = st.columns([4, 1])
    bank_usage = col1.slider("I would like to use this much from my bank balance", 0.0, proj_df.loc[proj_df.index[-1], 'Bank Balance'],step=1000.0)
    cpf_usage = col3.slider("I would like to use this much from my CPF(OA) balance", 0.0, proj_df.loc[proj_df.index[-1], 'CPF(OA) Balance'],step=1000.0)
    col2.markdown(f"**Bank Balance:**  \n${proj_df.loc[proj_df.index[-1], 'Bank Balance'] - bank_usage:,.2f}")
    col4.markdown(f"**CPF(OA) Balance:**  \n${proj_df.loc[proj_df.index[-1], 'CPF(OA) Balance'] - cpf_usage:,.2f}")
    downpayment_percentage = st.number_input("I am making downpayment of __% property value", value=25)
    max_property = (bank_usage+cpf_usage)/downpayment_percentage*100
    if bank_usage>0 or cpf_usage>0:
        st.success(f"You can afford a property up to ${max_property:,.2f}. ")
        st.info("Note that there are other upfront payments beyond the downpayment, and to maintain enough savings / emergency funds. ")
    st.divider()
################################################################################################
    # Filters for options
    st.write("### HDB Filters")
    flat_types = sorted(df['flat_type'].unique())
    selected_flat_type = st.selectbox("Desired Flat Type", options=flat_types, index=2)

    towns = sorted(df['town'].unique())
    selected_town = st.pills("Desired Towns (click to select)", options=towns, selection_mode="multi")
    filtered_df = df[
        (df['flat_type']==selected_flat_type) &
        (df['town'].isin(selected_town))
        ]

    @st.cache_data
    def generate_pivot(filtered_df):
        filtered_df = filtered_df.copy()
        filtered_df['year'] = pd.to_datetime(filtered_df['month']).dt.year
        pivot = pd.pivot_table(
            filtered_df,
            values='resale_price',
            index='year',
            columns='town',
            aggfunc='mean'
        )
        pivot.index.name = 'Year'
        return pivot.round(2)

    pivot = generate_pivot(filtered_df)

    # Another df to show projection
    future_years = list(range(datetime.now().year,buying_year+1))

    # Appreciation df
    if selected_town:
        st.text('Average Annual Appreciation Over Last __ Years by Town (For Reference)')
        average_appreciation_df = pivot.tail(16).copy()
        for col in average_appreciation_df.columns:
            for row in reversed(average_appreciation_df.index[1:]):
                i = average_appreciation_df.index.get_loc(row)
                prev_row = average_appreciation_df.index[i - 1]
                value = average_appreciation_df.loc[row, col] / average_appreciation_df.loc[prev_row, col]
                average_appreciation_df.loc[row, col] = average_appreciation_df.loc[row, col] / average_appreciation_df.loc[prev_row, col]
        average_appreciation_df = average_appreciation_df.drop(average_appreciation_df.index[0]) # Remove first row, as it is not an inflation rate
        # Appreciation rate over past years
        past_appreciation_df = pivot.tail(1).copy()
        past_appreciation_df = past_appreciation_df.drop(past_appreciation_df.index[0])
        for last_n in [1,3,5,10,15]:
            average_row = (average_appreciation_df.tail(last_n).mean(numeric_only=True) - 1) * 100  # calculates average for numeric columns only
            past_appreciation_df.loc[f'{last_n} Years'] = average_row
        past_appreciation_df.index.name = 'Appreciation Over Last'
        st.dataframe(past_appreciation_df)
        appreciation_rate = st.selectbox("Use Property Inflation Rate of Last __ Years",past_appreciation_df.index)


        # Future df
        st.text('Historical and Projected Average Resale HDB Prices by Year and Town')
        future_df = pd.DataFrame(index=future_years, columns=pivot.columns)
        future_df.index.name = 'Year'
        for col in pivot.columns:
            future_df.loc[future_df.index[0],col] = pivot.loc[pivot.index[-1],col]
            for idx in future_df.index[1:]:
                i = future_df.index.get_loc(idx)
                prev_row = future_df.index[i - 1]
                value = future_df.loc[prev_row, col]*(1+past_appreciation_df.loc[appreciation_rate,col]/100)
                future_df.loc[idx, col] = value
        future_df = future_df.round(2)
        future_df = future_df.iloc[1:]
        # st.dataframe(future_df.style.format("{:.2f}"))

        combined_df = pd.concat([pivot,future_df])
        styled_df = combined_df.style.format("{:.2f}")
        st.dataframe(styled_df)

        def highlight_negative_row(row):
            if row['Balance (of initial Bank+OA)'] < 0:
                return ['color: red'] * len(row)  # apply red text color to entire row
            else:
                return [''] * len(row)  # no style
        st.text('Most to Least Affordable Towns')
        # Get last row as a Series
        last_row = combined_df.iloc[-1]
        # Sort values descending
        sorted_last_row = last_row.sort_values(ascending=True)
        # Convert to DataFrame with 'Town' and 'Value' columns
        sorted_df = pd.DataFrame({
            'Town': sorted_last_row.index,
            'Value': sorted_last_row.values,
            'Downpayment': sorted_last_row.values/100*downpayment_percentage,
            'Balance (of initial Bank+OA)': bank_usage+cpf_usage-sorted_last_row.values/100*downpayment_percentage
        })
        # Show in Streamlit
        sorted_df.index = range(1, len(sorted_df) + 1)
        sorted_df.index.name = "Rank"
        st.dataframe(
            sorted_df.style.apply(highlight_negative_row, axis=1)
                .format({
                    col: '{:,.2f}' for col in sorted_df.select_dtypes(include='number').columns
                })
        )