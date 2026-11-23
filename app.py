from pharmacy import create_app
from pharmacy.db import init_db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=app.config["DEBUG"])
