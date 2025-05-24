import requests
import json
import pandas as pd
import calendar
import streamlit as st
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
months = list(calendar.month_name)[1:]
today = datetime.today()

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

def calc_cpf_oa_increase(age):
    if age <= 35:
        return 0.6217
    elif age <= 45: 
        return 0.5677
    elif age <= 50:
        return 0.5136
    elif age <= 55:
        return 0.4055
    elif age <= 60:
        return 0.3694
    elif age <= 65:
        return 0.149
    elif age <= 70:
        return 0.0607
    else:
        return 0.08

# Main function here
hdb_df = download_resale_hdb_dataset()

# Header
st.title("Can you afford a resale HDB?")
earliest_date = pd.to_datetime(hdb_df['month'].min())
latest_date = pd.to_datetime(hdb_df['month'].max())
st.text("Property data from " + earliest_date.strftime('%b') + " " + str(earliest_date.year) + " to "+ latest_date.strftime('%b') + " " + str(latest_date.year) + " from https://data.gov.sg/collections/189/view")
st.divider()

# Inputs
st.subheader("Timeline")
age_col1, age_col2 = st.columns(2)
with age_col1:
    birthday = st.date_input("Birthday",min_value=date(today.year-99, 1, 1),
    max_value=date(today.year+99, 12, 31))
with age_col2:
    age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
    st.text_input("Current Age", value=age, disabled=True)
target_col1, target_col2= st.columns(2)
with target_col1:
    buying_age = st.number_input("Buying Age", value=35)
with target_col2:
    future_birthday = birthday + relativedelta(years=buying_age)
    buy_date = st.text_input("Buying Date", value=(f'{calendar.month_name[future_birthday.month]} {future_birthday.year}'), disabled=True)
st.subheader("Cashflow")
bank_col1, bank_col2, bank_col3 = st.columns(3)
with bank_col1:
    bank_bal = st.number_input("Bank Balance")
with bank_col2:
    bank_bal_inc = st.number_input("Bank Savings (per month)")
with bank_col3:
    bank_annual_interest = st.number_input("Bank Interest Rate (%)", value=2.5,step=0.01, format="%.2f")
sal_col1, sal_col2, sal_col3 = st.columns(3)
with sal_col1:
    salary = st.number_input("Current Salary (per month)")
with sal_col2:
    salary_raise = st.number_input("Expected Salary Increase per Year (%)")
with sal_col3:
    sal_raise_month = st.selectbox("Annual Raise Month", months)
cpf_bal = st.number_input("Current CPF(O/A) Balance")

st.subheader(f"Your Projection")

if bank_bal and bank_bal_inc and cpf_bal and age>0:
    cpf_bal_inc = salary*0.37*calc_cpf_oa_increase(age)
    columns = [
        'Salary',
        'Bank Increase',
        'Bank Interest',
        'Bank Balance',
        'CPF Increase',
        'CPF(OA) Interest',
        'CPF(OA) Balance',
        'Total balance'
    ]
    next_row = {
        'Salary': salary,
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
    for row in range(0,months_diff(future_birthday.year,future_birthday.month)-1):
        next_date += relativedelta(months=1)
        # Age
        if next_date.month == birthday.month:
            age += 1
            cpf_bal_inc = salary*0.37*calc_cpf_oa_increase(age)
            next_row['CPF Increase']=cpf_bal_inc
        ## Count Bank Balance
        # Annual increment month
        if next_date.month == datetime.strptime(sal_raise_month, "%B").month:
            salary += salary_raise/100*salary
            bank_bal_inc += salary_raise/100*bank_bal_inc
            cpf_bal_inc += salary_raise/100*cpf_bal_inc
            next_row['Salary']=salary
            next_row['Bank Increase']=bank_bal_inc
            next_row['CPF Increase']=cpf_bal_inc
        next_row['Bank Interest']=next_row['Bank Balance']*bank_annual_interest/12/100
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
    st.success(f"You will have ${next_row['Total balance']:,.2f} on {buy_date}. ")
    st.info("Note: The projection assumes your saving/spending habits remain proportional to your salary. CPF(OA) interest accrued for earlier months of the current year are not included. ")
else:
    st.info("Please fill up all 'Timeline' and 'Cashflow' fields for your projection to be generated. ")
st.divider()

st.subheader("Downpayment")
if bank_bal and bank_bal_inc and cpf_bal and age>0:
    col1, col2 = st.columns([4, 1])
    col3, col4 = st.columns([4, 1])
    bank_usage = col1.slider("I would like to use this much from my bank balance", 0.0, proj_df.loc[proj_df.index[-1], 'Bank Balance'],step=1000.0)
    cpf_usage = col3.slider("I would like to use this much from my CPF(OA) balance", 0.0, proj_df.loc[proj_df.index[-1], 'CPF(OA) Balance'],step=1000.0)
    col2.markdown(f"**Bank Balance:**  \n${proj_df.loc[proj_df.index[-1], 'Bank Balance'] - bank_usage:,.2f}")
    col4.markdown(f"**CPF(OA) Balance:**  \n${proj_df.loc[proj_df.index[-1], 'CPF(OA) Balance'] - cpf_usage:,.2f}")
    downpayment_percentage = st.number_input("I am making downpayment of __% property value", value=25)
    expected_grants = st.number_input("Expected grant(s) of $__", value=40000)
    max_property = ((bank_usage+cpf_usage)/downpayment_percentage*100)+expected_grants
    if bank_usage>0 or cpf_usage>0:
        st.success(f"You can afford a property up to ${max_property:,.2f}. ")
    st.info("Please refer to [CPF Housing Grant for Singles](https://www.hdb.gov.sg/residential/buying-a-flat/understanding-your-eligibility-and-housing-loan-options/flat-and-grant-eligibility/singles/cpf-housing-grant-for-resale-flats-singles) "
        "and [CPF Housing Grants for Families](https://www.hdb.gov.sg/residential/buying-a-flat/understanding-your-eligibility-and-housing-loan-options/flat-and-grant-eligibility/couples-and-families/cpf-housing-grants-for-resale-flats-families) "
        "for more information on grants.")        
    if bank_usage>0 or cpf_usage>0:
        st.info("Note that there are other upfront payments beyond the downpayment, and to maintain enough savings / emergency funds. ")
else:
    st.info("Please fill up all 'Timeline' and 'Cashflow' fields for your Downpayment options to be available. ")
st.divider()
# Filters for options
st.subheader("HDB Projection")
flat_types = sorted(hdb_df['flat_type'].unique())
selected_flat_type = st.selectbox("Desired Flat Type", options=flat_types, index=2)

towns = sorted(hdb_df[hdb_df['flat_type']==selected_flat_type]['town'].unique())
selected_town = st.pills("Desired Towns (click to select)", options=towns, selection_mode="multi")
filtered_df = hdb_df[
    (hdb_df['flat_type']==selected_flat_type) &
    (hdb_df['town'].isin(selected_town))
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

# Appreciation hdb_df
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
    past_appreciation_df[past_appreciation_df.select_dtypes(include="number").columns] = \
    past_appreciation_df.select_dtypes(include="number").round(2)
    st.dataframe(past_appreciation_df)
    col1, col2 = st.columns(2)
    with col1:
        appreciation_rate = st.selectbox("Use Average Property Inflation Rate of Last __",past_appreciation_df.index,index=2)
    with col2:
        proj_period = st.number_input("Number of Years to Project", step=1, value=future_birthday.year-today.year)

    # Another hdb_df to show projection
    future_years = list(range(datetime.now().year,datetime.now().year+proj_period+1))

    # Future hdb_df
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
    combined_df = pd.concat([pivot,future_df])
    styled_df = combined_df.style.format("{:.2f}")
    show_past = st.toggle("Show previous years")
    if show_past:
        st.dataframe(styled_df)
    else:
        st.dataframe(future_df)

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
    try:
        sorted_df = pd.DataFrame({
            'Town': sorted_last_row.index,
            'Value': sorted_last_row.values,
            'Downpayment': sorted_last_row.values/100*downpayment_percentage,
            'Balance (of initial Bank+OA)': bank_usage+cpf_usage-sorted_last_row.values/100*downpayment_percentage
        })
    except: 
        sorted_df = pd.DataFrame({
        'Town': sorted_last_row.index,
        'Value': sorted_last_row.values 
        })
    # Show in Streamlit
    sorted_df.index = range(1, len(sorted_df) + 1)
    sorted_df.index.name = "Rank"
    try:
        st.dataframe(
            sorted_df.style.apply(highlight_negative_row, axis=1)
                .format({
                    col: '{:,.2f}' for col in sorted_df.select_dtypes(include='number').columns
                })
        )
    except:
        # Round numeric columns to 2 decimals *in the data itself*
        rounded_df = sorted_df.copy()
        numeric_cols = rounded_df.select_dtypes(include=["number"]).columns
        rounded_df[numeric_cols] = rounded_df[numeric_cols].round(1)
        st.dataframe(rounded_df)
        st.warning("Complete the sections 'Your Projection' and 'Downpayment' sections to see balances after downpayment.")