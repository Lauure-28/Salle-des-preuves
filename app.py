import json
import os
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

DATA_FILE = "enquetes.json"


# Fonction pour lire les enquêtes enregistrées
def load_enquetes():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


# Fonction pour sauvegarder les enquêtes
def save_enquetes(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.route("/")
def home():
    return render_template("index.html")


# Route API : Récupérer toutes les enquêtes enregistrées
@app.route("/api/enquetes", methods=["GET"])
def get_enquetes():
    return jsonify(load_enquetes())


# Route API : Sauvegarder une nouvelle enquête depuis l'Atelier
@app.route("/api/enquetes", methods=["POST"])
def add_enquete():
    new_case = request.get_json()
    if not new_case:
        return jsonify({"error": "Données invalides"}), 400

    enquetes = load_enquetes()
    # Ajout ou mise à jour de l'enquête
    enquetes.append(new_case)
    save_enquetes(enquetes)

    return jsonify({"message": "Enquête enregistrée avec succès !"}), 201


if __name__ == "__main__":
    app.run(debug=True)