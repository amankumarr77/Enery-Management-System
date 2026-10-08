from src.data_loader import load_price_data
from src.forecast import train_forecast_model
from src.plotting import plot_simulation_results
from src.simulation import simulate_operation
from src.metrics import compute_all_metrics
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("emsjb_cli")


def main():
    if not os.path.exists("outputs"):
        os.makedirs("outputs")

    logger.info("Loading data...")
    df = load_price_data("data/iex_dam_hourly_2024_25.csv")

    logger.info("Training forecast model...")
    model, residuals, accuracy, train_end = train_forecast_model(df)
    logger.info(f"Model trained. Test accuracy: MAE={accuracy['mae']}, RMSE={accuracy['rmse']}, MAPE={accuracy['mape']}%")

    limit = 500
    logger.info(f"Starting simulation ({limit} steps)...")
    results_df = simulate_operation(df.head(limit + 48), model, residuals)
    results_df = results_df.head(limit)

    output_path = "outputs/simulation_results.csv"
    results_df.to_csv(output_path, index=False)
    logger.info(f"Results saved to {output_path}")

    metrics = compute_all_metrics(results_df)
    logger.info("── Performance Metrics ──")
    for k, v in metrics.items():
        logger.info(f"  {k}: {v}")

    logger.info("Generating plot...")
    plot_simulation_results(results_df, "outputs/simulation_plot.png")


if __name__ == "__main__":
    main()