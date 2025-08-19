# optimization_engine.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import seaborn as sns

def DA_Dispatch(price, battery_params):
    """
    Optimizes battery dispatch in the Day-Ahead market.

    Args:
        price (pd.DataFrame): DataFrame containing price data with 'DA[GBP/MWh]' column.
        battery_params (dict): Dictionary containing battery parameters.
    Returns:
        pd.DataFrame: DataFrame with optimization results including charge, discharge, SoC, SoH, and revenue.
    """

    model = pyo.ConcreteModel(name="DayAheadBatteryOptimization")

    # ADD NOISE TO MODEL FORECASTING ERROR
    np.random.seed(42)
    # Add Gaussian noise: mean = 0, std = 0.1 (10%)
    noise = np.random.normal(loc=0, scale=battery_params['DA_noise_[%]'], size=len(price))
    noisy_price = pd.DataFrame()
    noisy_price['DA[GBP/MWh]'] = price['DA[GBP/MWh]'] * (1 + noise)

    if battery_params['DA_noise_[%]'] > 0:
    # Keeping hourly price for DA
        for i in range(0, len(noisy_price), 2):
            mean_val = noisy_price['DA[GBP/MWh]'].iloc[i:i+2].mean()
            noisy_price.iloc[i, noisy_price.columns.get_loc('DA[GBP/MWh]')] = mean_val
            noisy_price.iloc[i+1, noisy_price.columns.get_loc('DA[GBP/MWh]')] = mean_val

    # SETS
    model.T = pyo.Set(initialize=range(len(price))) # Time periods

    # PARAMETERS
    prices_DA = noisy_price['DA[GBP/MWh]'].values
    model.Num_Periods = pyo.Param(initialize=len(model.T)) # Number of time periods
    model.Price_DA = pyo.Param(model.T, initialize=lambda model, t: prices_DA[t])
    model.Capacity = pyo.Param(initialize=battery_params['capacity_mwh'])
    model.MaxPower = pyo.Param(initialize=battery_params['max_power_mw'])
    model.InitialSoC = pyo.Param(initialize=battery_params['initial_soc_[%]'] * battery_params['capacity_mwh'])
    model.SOC_min = pyo.Param(initialize=battery_params['soc_min_[%]'] * battery_params['capacity_mwh'])
    model.SOC_max = pyo.Param(initialize=battery_params['soc_max_[%]'] * battery_params['capacity_mwh'])
    model.initial_SoH = pyo.Param(initialize=battery_params['soh_initial_mwh'])  # Initial State of Health in MWh
    model.ChargeEff = pyo.Param(initialize=battery_params['charge_efficiency'])
    model.DischargeEff = pyo.Param(initialize=battery_params['discharge_efficiency'])
    model.DegradationFactor = pyo.Param(initialize=battery_params['degradation_per_mwh_discharged'])
    model.Cycles_per_day = pyo.Param(initialize=battery_params['max_cycles_per_day'])
    model.delta_t = pyo.Param(initialize=0.5)  # 30 minutes in hours

    # VARIABLES
    model.Charge = pyo.Var(model.T, within=pyo.NonNegativeReals, bounds=(0, model.MaxPower)) # MW charged
    model.Discharge = pyo.Var(model.T, within=pyo.NonNegativeReals, bounds=(0, model.MaxPower)) # MW discharged
    model.SoC = pyo.Var(model.T, within=pyo.NonNegativeReals, bounds=(0, model.Capacity)) # State of Charge in MWh
    model.SoH = pyo.Var(model.T, within=pyo.NonNegativeReals, bounds=(0, model.initial_SoH)) # State of Health
    model.IsCharging = pyo.Var(model.T, within=pyo.Binary) # Indicator if charging
    model.IsDischarging = pyo.Var(model.T, within=pyo.Binary) # Indicator if discharging

    # OBJECTIVE FUNCTION
    # Maximize profit from the Day-Ahead market

    def objective_rule(model):
        return sum(model.Discharge[t] * model.Price_DA[t] - model.Charge[t] * model.Price_DA[t] for t in model.T)
    model.Objective = pyo.Objective(rule=objective_rule, sense=pyo.maximize)

    # CONSTRAINTS
    # Charge/Discharge Constraints
    @model.Constraint(model.T)
    def charge_discharge_rule(model, t):
        return model.Charge[t] <= model.MaxPower * model.IsCharging[t]

    @model.Constraint(model.T)
    def discharge_charge_rule(model, t):
        return model.Discharge[t] <= model.MaxPower * model.IsDischarging[t]

    # no_simultaneous_charge_discharge_rule
    @model.Constraint(model.T)
    def no_simultaneous_charge_discharge_rule(model, t):
        return model.IsCharging[t] + model.IsDischarging[t] <= 1

    # SoC Balance
    @model.Constraint(model.T)
    def soc_balance_rule(model, t):
        if t == 0:
            return model.SoC[t] == model.InitialSoC + model.Charge[t] * model.delta_t * model.ChargeEff - model.Discharge[t] * model.delta_t / model.DischargeEff
        return model.SoC[t] == model.SoC[t-1] + model.Charge[t] * model.delta_t * model.ChargeEff - model.Discharge[t] * model.delta_t / model.DischargeEff

    @model.Constraint(model.T)
    def soc_min_rule(model, t):
        return model.SoC[t] >= model.SOC_min

    @model.Constraint(model.T)
    def soc_max_rule(model, t):
        return model.SoC[t] <= model.SOC_max

    # SoH Degradation
    @model.Constraint(model.T)
    def soh_degradation_rule(model, t):
        if t == 0:
            return model.SoH[t] == model.initial_SoH
        return model.SoH[t] == model.SoH[t-1] - (model.DegradationFactor * model.Discharge[t] * model.delta_t * 2)

    # Degradation impact on SoC
    @model.Constraint(model.T)
    def degradation_impact_rule(model, t):
        return model.SoC[t] <= model.SoH[t]

    # max_cycles_per_day_rule
    @model.Constraint()
    def max_cycles_per_day_rule(model):
        sum_throughput =  sum((model.Discharge[t]) for t in model.T) *(model.delta_t)
        return sum_throughput <= model.Cycles_per_day * model.Capacity

    # Hourly Dispatch Rule
    @model.Constraint(model.T)
    def dispatch_equality_rule_1(model, t):
        if t % 2 == 1:  # Only for the second in each pair
            return model.Charge[t] == model.Charge[t-1]
        return pyo.Constraint.Skip

    # Hourly Dispatch Rule
    @model.Constraint(model.T)
    def dispatch_equality_rule_2(model, t):
        if t % 2 == 1:  # Only for the second in each pair
            return model.Discharge[t] == model.Discharge[t-1]
        return pyo.Constraint.Skip

    # Solve
    # solver = SolverFactory('scip')
    solver = SolverFactory('glpk')
    results = solver.solve(model, tee=False)

    # Extract results from the model
    results_df = pd.DataFrame(index=price.index)
    if results.solver.termination_condition == pyo.TerminationCondition.optimal or \
        results.solver.termination_condition == pyo.TerminationCondition.feasible:
        print("DA Optimization successful.")

        results_df['DA_Charge_MW'] = [pyo.value(model.Charge[t]) for t in model.T]
        results_df['DA_Discharge_MW'] = [pyo.value(model.Discharge[t]) for t in model.T]
        results_df['DA_Charge_MWh'] = [pyo.value(model.Charge[t]) * model.delta_t for t in model.T]
        results_df['DA_Discharge_MWh'] = [pyo.value(model.Discharge[t]) * model.delta_t for t in model.T]
        results_df['DA_SoC_MWh'] = [pyo.value(model.SoC[t]) for t in model.T]
        results_df['DA_SoH_MWh'] = [pyo.value(model.SoH[t]) for t in model.T]
        results_df['DA_IsCharging'] = [pyo.value(model.IsCharging[t]) for t in model.T]
        results_df['DA_IsDischarging'] = [pyo.value(model.IsDischarging[t]) for t in model.T]
        results_df['DA_Revenue_GBP'] = (results_df['DA_Discharge_MWh'] * price['DA[GBP/MWh]'].values - \
                                        results_df['DA_Charge_MWh'] * price['DA[GBP/MWh]'].values)
        results_df['Forecasted_Price_DA'] = noisy_price['DA[GBP/MWh]']

    return results_df

def ID_Dispatch(price, battery_params, final_DA_results_df):

    """
    Optimizes battery dispatch in the Intraday market.

    Args:
        price (pd.DataFrame): DataFrame containing price data with 'DA[GBP/MWh]' column.
        battery_params (dict): Dictionary containing battery parameters.
    Returns:
        pd.DataFrame: DataFrame with optimization results including charge, discharge, SoC, SoH, and revenue.
    """

    model = pyo.ConcreteModel(name="IntraDayTimeBatteryOptimization")

    # ADD NOISE TO MODEL FORECASTING ERROR
    np.random.seed(42)
    # Add Gaussian noise: mean = 0, std = 0.1 (10%)
    noise = np.random.normal(loc=0, scale=battery_params['ID_noise_[%]'], size=len(price))
    noisy_price = pd.DataFrame()
    noisy_price['ID[GBP/MWh]'] = price['ID[GBP/MWh]'] * (1 + noise)

    # SETS
    model.T = pyo.Set(initialize=range(len(price))) # Time periods

    # PARAMETERS
    # prices_DA = price['DA[GBP/MWh]'].values
    prices_ID = noisy_price['ID[GBP/MWh]'].values
    model.Num_Periods = pyo.Param(initialize=len(model.T)) # Number of time periods
    model.Price_ID = pyo.Param(model.T, initialize=lambda model, t: prices_ID[t])
    model.Capacity = pyo.Param(initialize=battery_params['capacity_mwh'])
    model.MaxPower = pyo.Param(initialize=battery_params['max_power_mw'])
    model.InitialSoC = pyo.Param(initialize=battery_params['initial_soc_[%]'] * battery_params['capacity_mwh'])
    model.SOC_min = pyo.Param(initialize=battery_params['soc_min_[%]'] * battery_params['capacity_mwh'])
    model.SOC_max = pyo.Param(initialize=battery_params['soc_max_[%]'] * battery_params['capacity_mwh'])
    model.initial_SoH = pyo.Param(initialize=battery_params['soh_initial_mwh'])  # Initial State of Health in MWh
    model.ChargeEff = pyo.Param(initialize=battery_params['charge_efficiency'])
    model.DischargeEff = pyo.Param(initialize=battery_params['discharge_efficiency'])
    model.DegradationFactor = pyo.Param(initialize=battery_params['degradation_per_mwh_discharged'])
    model.Cycles_per_day = pyo.Param(initialize=battery_params['max_cycles_per_day'])
    model.delta_t = pyo.Param(initialize=0.5)  # 30 minutes in hours

    model.DA_Charge_MW = pyo.Param(model.T, initialize=lambda model, t: final_DA_results_df['DA_Charge_MW'].iloc[t])
    model.DA_Discharge_MW = pyo.Param(model.T, initialize=lambda model, t: final_DA_results_df['DA_Discharge_MW'].iloc[t])

    # VARIABLES
    model.Charge_ID = pyo.Var(model.T, within=pyo.NonNegativeReals, bounds=(0, model.MaxPower)) # MW charged
    model.Discharge_ID = pyo.Var(model.T, within=pyo.NonNegativeReals, bounds=(0, model.MaxPower)) # MW discharged
    model.SoC = pyo.Var(model.T, within=pyo.NonNegativeReals, bounds=(0, model.Capacity)) # State of Charge in MWh
    model.SoH = pyo.Var(model.T, within=pyo.NonNegativeReals, bounds=(0, model.initial_SoH)) # State of Health
    model.IsCharging_ID = pyo.Var(model.T, within=pyo.Binary) # Indicator if charging
    model.IsDischarging_ID = pyo.Var(model.T, within=pyo.Binary) # Indicator if discharging

    # OBJECTIVE FUNCTION
    # Maximize profit from the Day-Ahead market

    def objective_rule(model):
        return sum(model.Discharge_ID[t] * model.Price_ID[t] - model.Charge_ID[t] * model.Price_ID[t] for t in model.T)
    model.Objective = pyo.Objective(rule=objective_rule, sense=pyo.maximize)

    # CONSTRAINTS
    # Charge/Discharge Constraints
    @model.Constraint(model.T)
    def charge_discharge_rule(model, t):
        return model.Charge_ID[t] <= model.MaxPower - model.DA_Charge_MW[t] + model.DA_Discharge_MW[t]

    @model.Constraint(model.T)
    def discharge_charge_rule(model, t):
        return model.Discharge_ID[t] <= model.MaxPower - model.DA_Discharge_MW[t] + model.DA_Charge_MW[t]

    @model.Constraint(model.T)
    def charge_discharge_rule_additional(model, t):
        return model.Charge_ID[t] <= model.MaxPower * model.IsCharging_ID[t]

    @model.Constraint(model.T)
    def discharge_charge_rule_additional(model, t):
        return model.Discharge_ID[t] <= model.MaxPower * model.IsDischarging_ID[t]

    # no_simultaneous_charge_discharge_rule
    @model.Constraint(model.T)
    def no_simultaneous_charge_discharge_rule(model, t):
        return model.IsCharging_ID[t] + model.IsDischarging_ID[t] <= 1

    # SoC Balance
    @model.Constraint(model.T)
    def soc_balance_rule(model, t):
        if t == 0:
            return model.SoC[t] == model.InitialSoC + (model.Charge_ID[t] +  model.DA_Charge_MW[t]) * model.delta_t * model.ChargeEff - (model.Discharge_ID[t] +  model.DA_Discharge_MW[t]) * model.delta_t / model.DischargeEff
        return model.SoC[t] == model.SoC[t-1] +(model.Charge_ID[t] +  model.DA_Charge_MW[t]) * model.delta_t * model.ChargeEff - (model.Discharge_ID[t] +  model.DA_Discharge_MW[t]) * model.delta_t / model.DischargeEff

    @model.Constraint(model.T)
    def soc_min_rule(model, t):
        return model.SoC[t] >= model.SOC_min

    @model.Constraint(model.T)
    def soc_max_rule(model, t):
        return model.SoC[t] <= model.SOC_max

    # SoH Degradation
    @model.Constraint(model.T)
    def soh_degradation_rule(model, t):
        if t == 0:
            return model.SoH[t] == model.initial_SoH
        return model.SoH[t] == model.SoH[t-1] - (model.DegradationFactor * (model.Discharge_ID[t] +  model.DA_Discharge_MW[t]) * model.delta_t)

    # Degradation impact on SoC
    @model.Constraint(model.T)
    def degradation_impact_rule(model, t):
        return model.SoC[t] <= model.SoH[t]

    # max_cycles_per_day_rule
    @model.Constraint()
    def max_cycles_per_day_rule(model):
        sum_throughput = sum((model.Discharge_ID[t] + model.DA_Discharge_MW[t]) for t in model.T) *(model.delta_t)
        return sum_throughput <= model.Cycles_per_day * model.Capacity

    # solver = SolverFactory('scip')
    solver = SolverFactory('glpk')
    results = solver.solve(model, tee=False)

    # Extract results from the model
    results_df = pd.DataFrame(index=price.index)
    if results.solver.termination_condition == pyo.TerminationCondition.optimal:
        print("ID Optimization successful.")
        results_df['ID_Charge_MW'] = [pyo.value(model.Charge_ID[t]) for t in model.T]
        results_df['ID_Discharge_MW'] = [pyo.value(model.Discharge_ID[t]) for t in model.T]
        results_df['ID_Charge_MWh'] = [pyo.value(model.Charge_ID[t]) * model.delta_t for t in model.T]
        results_df['ID_Discharge_MWh'] = [pyo.value(model.Discharge_ID[t]) * model.delta_t for t in model.T]
        results_df['SoC_Final_MWh'] = [pyo.value(model.SoC[t]) for t in model.T]
        results_df['SoH_Final_MWh'] = [pyo.value(model.SoH[t]) for t in model.T]
        results_df['ID_IsCharging'] = [pyo.value(model.IsCharging_ID[t]) for t in model.T]
        results_df['ID_IsDischarging'] = [pyo.value(model.IsDischarging_ID[t]) for t in model.T]
        results_df['ID_Revenue_GBP'] = (results_df['ID_Discharge_MWh'] * price['ID[GBP/MWh]'].values - \
                                        results_df['ID_Charge_MWh'] * price['ID[GBP/MWh]'].values)
        results_df['Forecasted_Price_ID'] = noisy_price['ID[GBP/MWh]']


    return results_df

def plot_market_revenue(total_final_ID_DA_results_df, BESS_Power):
    """
    Plots the average monthly and total yearly revenue for DA and ID markets.

    Args:
        total_final_ID_DA_results_df: DataFrame with columns 'DA_Revenue_GBP' and 'ID_Revenue_GBP',
            indexed by datetime.
        BESS_Power: The BESS power in MW, used for normalization.
    """
    # This function returns a figure object, which can be displayed in Streamlit
    revenue = total_final_ID_DA_results_df[['DA_Revenue_GBP', 'ID_Revenue_GBP']].copy()
    bess_power_MW = BESS_Power

    month_names_map = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    }
    month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # plotting style
    plt.style.use('seaborn-v0_8-whitegrid')

    # Calculate total monthly revenue for each month for all years

    monthly_sums_per_year = revenue.resample('ME').agg(
        DA_Monthly_Sum=('DA_Revenue_GBP', 'sum'),
        ID_Monthly_Sum=('ID_Revenue_GBP', 'sum')
    ).reset_index()

    # Extract month number and map to month name
    monthly_sums_per_year['Month'] = monthly_sums_per_year['index'].dt.month
    monthly_sums_per_year['Month_Name'] = monthly_sums_per_year['Month'].map(month_names_map)

    # Group by month name and sum  monthly totals across all years
    overall_monthly_total_revenue = monthly_sums_per_year.groupby('Month_Name')[['DA_Monthly_Sum', 'ID_Monthly_Sum']].sum().reindex(month_order).reset_index()
    num_years = 4

    overall_monthly_avg_revenue_df = pd.DataFrame({
        'Month_Name': overall_monthly_total_revenue['Month_Name'],
        'DA_Avg': (overall_monthly_total_revenue['DA_Monthly_Sum'] / num_years) / bess_power_MW,
        'ID_Avg': (overall_monthly_total_revenue['ID_Monthly_Sum'] / num_years) / bess_power_MW
    })


    fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))

    sns.barplot(x='Month_Name', y='DA_Avg', data=overall_monthly_avg_revenue_df, order=month_order, color='deepskyblue', ax=ax1)
    ax1.set_title('Overall Average Monthly DA Revenue (Summed and Averaged by Year)')
    ax1.set_xlabel('Month')
    ax1.set_ylabel('Average Revenue [GBP/MW/Month]')
    ax1.tick_params(axis='x', rotation=45)
    ax1.grid(axis='y', linestyle='--', linewidth=0.7)
    for index, row in overall_monthly_avg_revenue_df.iterrows():
        y_val = row['DA_Avg']
        max_val = overall_monthly_avg_revenue_df['DA_Avg'].max()
        ax1.text(index, y_val + (max_val * 0.01), f"{y_val:.0f}", color='black', ha="center")

    sns.barplot(x='Month_Name', y='ID_Avg', data=overall_monthly_avg_revenue_df, order=month_order, color='salmon', ax=ax2)
    ax2.set_title('Overall Average Monthly ID Revenue (Summed and Averaged by Year)')
    ax2.set_xlabel('Month')
    ax2.set_ylabel('Average Revenue [GBP/MW/Month]')
    ax2.tick_params(axis='x', rotation=45)
    ax2.grid(axis='y', linestyle='--', linewidth=0.7)
    for index, row in overall_monthly_avg_revenue_df.iterrows():
        y_val = row['ID_Avg']
        max_val = overall_monthly_avg_revenue_df['ID_Avg'].max()
        ax2.text(index, y_val + (max_val * 0.01), f"{y_val:.0f}", color='black', ha="center")

    fig1.suptitle('Overall Average Monthly Market Revenue', fontsize=16)
    fig1.tight_layout(rect=[0, 0, 1, 0.95])


    # --- Plotting Total Yearly Revenue ---

    yearly_total_revenue = revenue.groupby(revenue.index.year)[['DA_Revenue_GBP', 'ID_Revenue_GBP']].sum().reset_index()

    yearly_total_revenue.columns = ['Year', 'DA_Total_Revenue', 'ID_Total_Revenue']

    # data for DA plotting
    plot_data_DA_revenue = yearly_total_revenue[['Year', 'DA_Total_Revenue']].copy()
    plot_data_DA_revenue['Total Revenue'] = plot_data_DA_revenue['DA_Total_Revenue'] / bess_power_MW
    plot_data_DA_revenue.columns = ['Period', 'DA_Total_Revenue_Original', 'Total Revenue']
    plot_data_DA_revenue = plot_data_DA_revenue[['Period', 'Total Revenue']]
    # data for ID plotting
    plot_data_ID_revenue = yearly_total_revenue[['Year', 'ID_Total_Revenue']].copy()
    plot_data_ID_revenue['Total Revenue'] = plot_data_ID_revenue['ID_Total_Revenue'] / bess_power_MW
    plot_data_ID_revenue.columns = ['Period', 'ID_Total_Revenue_Original', 'Total Revenue']
    plot_data_ID_revenue = plot_data_ID_revenue[['Period', 'Total Revenue']]


    fig2, (ax3, ax4) = plt.subplots(1, 2, figsize=(15, 7))

    sns.barplot(x='Period', y='Total Revenue', data=plot_data_DA_revenue, palette='viridis', ax=ax3)
    ax3.set_title('Total Yearly DA Revenue')
    ax3.set_xlabel('Year')
    ax3.set_ylabel('Total Revenue (DA) [GBP/MW/Year]')
    ax3.tick_params(axis='x', rotation=45)
    ax3.grid(axis='y', linestyle='--', linewidth=0.7)
    for index, row in plot_data_DA_revenue.iterrows():
        y_val = row['Total Revenue']
        max_val = plot_data_DA_revenue['Total Revenue'].max()
        ax3.text(index, y_val + (max_val * 0.01), f"{y_val:.0f}", color='black', ha="center")

    sns.barplot(x='Period', y='Total Revenue', data=plot_data_ID_revenue, palette='magma', ax=ax4)
    ax4.set_title('Total Yearly ID Revenue')
    ax4.set_xlabel('Year')
    ax4.set_ylabel('Total Revenue (ID) [GBP/MW/Year]')
    ax4.tick_params(axis='x', rotation=45)
    ax4.grid(axis='y', linestyle='--', linewidth=0.7)
    for index, row in plot_data_ID_revenue.iterrows():
        y_val = row['Total Revenue']
        max_val = plot_data_ID_revenue['Total Revenue'].max()
        ax4.text(index, y_val + (max_val * 0.01), f"{y_val:.0f}", color='black', ha="center")

    fig2.suptitle('Comparison of Total Yearly Market Revenue', fontsize=16)
    fig2.tight_layout(rect=[0, 0, 1, 0.95])

    return fig1, fig2
