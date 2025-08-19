# test_runner.py
import pandas as pd
from optimization_engine import DA_Dispatch, ID_Dispatch, plot_market_revenue

# --- 1. Set Control Parameters ---
# These are the same parameters you had in your notebook.
# You can adjust them here to test different scenarios.
DA_forecasting_error = 0.00
ID_forecasting_error = 0.00
DA_Cycles = 1
ID_Cycles = 2
BESS_Size = 50
BESS_Duration = 2
BESS_Power = BESS_Size / BESS_Duration
BESS_Efficiency = 0.95
Intial_SOC = 0.1
SOC_Min = 0.1
SOC_Max = 1.0
BESS_Degradation = 0.000054

# --- 2. Load and Prepare Price Data ---
price_df = pd.read_csv("price_dataset.csv")
date_range = pd.date_range(start="2021-01-01 00:00:00", end="2025-01-01 00:00:00", freq="30min")
price_df.drop(["UTC_PERIOD_START_DATETIME"], axis=1, inplace=True)
price_df.rename(columns={"N2EX": "DA[GBP/MWh]", "MIP": "ID[GBP/MWh]"}, inplace=True)
price_df.index = date_range

# Use a shorter period for quick testing
start_date_dispatch = pd.Timestamp("2023-01-01 00:00:00")
end_date_dispatch = pd.Timestamp("2023-01-31 23:30:00") # Using just one month for testing
selected_price = price_df.loc[start_date_dispatch:end_date_dispatch]

# --- 3. Run Day-Ahead (DA) Optimization Loop ---
print("--- Starting Day-Ahead Dispatch Simulation ---")
battery_params_da = {
    'capacity_mwh': BESS_Size, 'duration_hours': BESS_Duration, 'max_power_mw': BESS_Power,
    'charge_efficiency': BESS_Efficiency, 'discharge_efficiency': BESS_Efficiency,
    'max_cycles_per_day': DA_Cycles, 'degradation_per_mwh_discharged': BESS_Degradation,
    'initial_soc_[%]': Intial_SOC, 'soc_min_[%]': SOC_Min,
    'soc_max_[%]': SOC_Max, 'soh_initial_mwh': BESS_Size,
    'DA_noise_[%]': DA_forecasting_error, 'ID_noise_[%]': ID_forecasting_error
}

final_DA_results_df = pd.DataFrame()
total_days = len(selected_price) // 48

for day in range(total_days):
    print(f"Processing DA for day {day + 1} of {total_days}...")
    daily_price = selected_price.iloc[48*day:48*(day+1)]
    daily_results = DA_Dispatch(daily_price, battery_params_da)
    final_DA_results_df = pd.concat([final_DA_results_df, daily_results])
    
    # Update battery state for the next day's simulation
    battery_params_da['initial_soc_[%]'] = float(daily_results['DA_SoC_MWh'].iloc[-1] / battery_params_da['capacity_mwh'])
    battery_params_da['soh_initial_mwh'] = float(daily_results['DA_SoH_MWh'].iloc[-1])

# --- 4. Run Intra-Day (ID) Optimization Loop ---
print("\n--- Starting Intra-Day Dispatch Simulation ---")
battery_params_id = {
    'capacity_mwh': BESS_Size, 'duration_hours': BESS_Duration, 'max_power_mw': BESS_Power,
    'charge_efficiency': BESS_Efficiency, 'discharge_efficiency': BESS_Efficiency,
    'max_cycles_per_day': ID_Cycles, 'degradation_per_mwh_discharged': BESS_Degradation,
    'initial_soc_[%]': Intial_SOC, 'soc_min_[%]': SOC_Min,
    'soc_max_[%]': SOC_Max, 'soh_initial_mwh': BESS_Size,
    'DA_noise_[%]': DA_forecasting_error, 'ID_noise_[%]': ID_forecasting_error
}

final_ID_results_df = pd.DataFrame()
for day in range(total_days):
    print(f"Processing ID for day {day + 1} of {total_days}...")
    daily_price = selected_price.iloc[48*day:48*(day+1)]
    da_results_for_day = final_DA_results_df.iloc[48*day:48*(day+1)]
    
    daily_results = ID_Dispatch(daily_price, battery_params_id, da_results_for_day)
    final_ID_results_df = pd.concat([final_ID_results_df, daily_results])

    # Update battery state for the next day's simulation
    battery_params_id['initial_soc_[%]'] = float(daily_results['SoC_Final_MWh'].iloc[-1] / battery_params_id['capacity_mwh'])
    battery_params_id['soh_initial_mwh'] = float(daily_results['SoH_Final_MWh'].iloc[-1])

# --- 5. Combine and Display Results ---
total_final_results = pd.concat([final_DA_results_df, final_ID_results_df], axis=1)
print("\n--- Optimization Complete ---")
print("Final Results DataFrame:")
print(total_final_results.head())

# Note: The plotting function from your notebook is designed for a 4-year dataset.
# It will still run on this shorter test period but the yearly plots might look sparse.
print("\n--- Generating Revenue Plots ---")
# plot_market_revenue(total_final_results, BESS_Power)
# plt.show() # Add this to display the plots when running locally