import matplotlib.pyplot as plt
import pandas as pd

def plot_simulation_results(results_df, output_path="outputs/simulation_plot.png"):
    fig, ax1 = plt.subplots(figsize=(14, 8))

    # Plot Price on left y-axis
    color = 'tab:blue'
    ax1.set_xlabel('Time Step')
    ax1.set_ylabel('Price (INR/kWh)', color=color)
    ax1.plot(results_df.index, results_df['Price'], color=color, label='Price')
    ax1.tick_params(axis='y', labelcolor=color)

    # Create a second y-axis for Power and SOC
    ax2 = ax1.twinx()  
    color = 'tab:red'
    ax2.set_ylabel('Power (kW) / SOC (kWh)', color=color)  
    
    # Plot SOC
    ax2.plot(results_df.index, results_df['SOC'], color='tab:green', label='SOC', linestyle='--')
    
    # Plot Battery Power (Dispatch)
    # Positive is Discharging (selling), Negative is Charging (buying)
    ax2.plot(results_df.index, results_df['Battery_Power'], color='tab:red', label='Battery Power', alpha=0.6)
    
    ax2.tick_params(axis='y', labelcolor=color)

    # Combine legends
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    plt.title('Battery Simulation: Price, Power Dispatch, and SOC')
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Plot saved to {output_path}")
