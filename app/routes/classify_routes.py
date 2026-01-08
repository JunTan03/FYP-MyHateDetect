from flask import Blueprint, request, jsonify
from app.stage_predict import predict_toxic_and_hate_type

classify_bp = Blueprint("classify", __name__)

@classify_bp.route("/classify", methods=["POST"])
def classify():
    data = request.json or {}
    # Accept a single "text" field; ignore if empty
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    # predict_toxic_and_hate_type expects a list of strings
    results = predict_toxic_and_hate_type([text])
    # Return the first (and only) result as JSON
    return jsonify(results[0])
