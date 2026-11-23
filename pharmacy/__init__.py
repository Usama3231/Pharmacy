import logging
from typing import Type

from flask import Flask

from config import Config

from .routes.batches import bp as batches_bp
from .routes.reports import bp as reports_bp
from .routes.sales import bp as sales_bp
from .routes.stock import bp as stock_bp
from .security import init_security


def create_app(config_class: Type[Config] = Config) -> Flask:
    app = Flask(__name__, template_folder="../templates")
    app.config.from_object(config_class)

    if not app.config["TESTING"]:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        app.logger.setLevel(logging.INFO)

    init_security(app)
    app.register_blueprint(stock_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(batches_bp)
    return app
