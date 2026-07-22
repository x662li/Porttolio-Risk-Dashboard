"""Application entry point: run pipeline once, then start Dash."""

from dash import Dash

from dashboard.callbacks import register_callbacks
from dashboard.layout import create_layout
from risk_platform.pipeline import run_pipeline


def main() -> None:
    result = run_pipeline()
    app = Dash(__name__)
    app.layout = create_layout(result)
    register_callbacks(app, result)
    app.run(debug=True)


if __name__ == "__main__":
    main()
