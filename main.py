from app import app

if __name__ == "__main__":
    # Just run the Flask app - FastAPI runs in a separate workflow
    app.run(host="0.0.0.0", port=5001, debug=True)
