"""
Simple test mock API - returns basic mock answers with Hebrew text.
Used for unit testing evaluators with controlled responses that include Hebrew content.
Runs on port 5001 and provides predictable test responses.
"""

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/get_answer", methods=["POST"])
def get_answer():
    """Return a deterministic mock answer payload for endpoint tests."""
    data = request.get_json()
    question = data.get("question", "")

    # Provide better mock responses with Hebrew text
    if "Shema" in question:
        mock_response = "The Shema is Judaism's central declaration of faith. שמע ישראל"
    else:
        mock_response = f"This is a mock answer to: '{question[:50]}...' תורה"

    return jsonify({"answer": mock_response})


if __name__ == "__main__":
    app.run(port=5001)
