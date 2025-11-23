# my_app/final_app.py
from flask import Flask, request, jsonify
from neighborhood_recommender import recommend_from_answers

app = Flask(__name__)

@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    data = request.get_json(force=True) or {}
    # Acceptem o bé {"answers": {...}} o bé directament {...}
    answers = data.get("answers", data)

    # Cridem el model
    top_df = recommend_from_answers(answers, top_n=5)

    # Convertim a JSON simple
    results = top_df.to_dict(orient="records")

    return jsonify({"results": results})

if __name__ == "__main__":
    app.run(debug=True)
