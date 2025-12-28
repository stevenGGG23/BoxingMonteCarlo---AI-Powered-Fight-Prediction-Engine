from flask import Flask, jsonify

app = Flask(__name__)

@app.get("/")
def home():
    return jsonify({"message": "Hello from Flask on Vercel!"})

# Vercel needs this
def handler(request, *args, **kwargs):
    return app(request, *args, **kwargs)
