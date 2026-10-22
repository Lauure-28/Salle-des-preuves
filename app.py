import json
import os
import uuid
from flask import Flask, jsonify, render_template, request, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "enquetes.json")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 Mo par requête


# Fonction pour lire les enquêtes enregistrées
def load_enquetes():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    # Les anciennes enquêtes n'avaient pas d'identifiant : on leur en donne un
    changed = False
    for enquete in data:
        if not enquete.get("__backendId"):
            enquete["__backendId"] = uuid.uuid4().hex
            changed = True
    if changed:
        save_enquetes(data)
    return data


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


# Route API : Créer une nouvelle enquête depuis l'Atelier
@app.route("/api/enquetes", methods=["POST"])
def add_enquete():
    new_case = request.get_json(silent=True)
    if not isinstance(new_case, dict):
        return jsonify({"error": "Données invalides"}), 400

    enquetes = load_enquetes()
    new_case["__backendId"] = uuid.uuid4().hex
    enquetes.append(new_case)
    save_enquetes(enquetes)

    return jsonify(new_case), 201


# Route API : Mettre à jour une enquête existante
@app.route("/api/enquetes/<case_id>", methods=["PUT"])
def update_enquete(case_id):
    changes = request.get_json(silent=True)
    if not isinstance(changes, dict):
        return jsonify({"error": "Données invalides"}), 400

    enquetes = load_enquetes()
    for i, enquete in enumerate(enquetes):
        if enquete.get("__backendId") == case_id:
            changes["__backendId"] = case_id
            enquetes[i] = changes
            save_enquetes(enquetes)
            return jsonify(changes)

    return jsonify({"error": "Enquête introuvable"}), 404


# Route API : Supprimer une enquête
@app.route("/api/enquetes/<case_id>", methods=["DELETE"])
def delete_enquete(case_id):
    enquetes = load_enquetes()
    remaining = [e for e in enquetes if e.get("__backendId") != case_id]
    if len(remaining) == len(enquetes):
        return jsonify({"error": "Enquête introuvable"}), 404
    save_enquetes(remaining)
    return jsonify({"message": "Enquête supprimée"})


# Route API : Envoyer une image (portrait de personnage, photo de décor)
@app.route("/api/images", methods=["POST"])
def upload_image():
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"error": "Aucune image reçue"}), 400

    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in IMAGE_EXTENSIONS:
        return jsonify({"error": "Format accepté : png, jpg, gif ou webp"}), 400

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = uuid.uuid4().hex[:12] + "-" + secure_filename(file.filename)
    file.save(os.path.join(UPLOAD_DIR, name))

    return jsonify({"url": url_for("static", filename="uploads/" + name)}), 201


if __name__ == "__main__":
    app.run(debug=True)
