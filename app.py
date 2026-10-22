import json
import os
import uuid
from flask import Flask, Response, abort, jsonify, render_template, request, url_for
from sqlalchemy import Column, LargeBinary, MetaData, String, Table, Text, create_engine, delete, insert, select, update
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OLD_DATA_FILE = os.path.join(BASE_DIR, "enquetes.json")
IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 Mo par requête


# ==========================================
# BASE DE DONNÉES
# ==========================================
# En local (votre PC), aucune variable DATABASE_URL n'est définie : on utilise
# le fichier SQLite salle_des_preuves.db. En ligne (Render), la variable
# DATABASE_URL (fournie par Neon) prend le relais : enquêtes et images
# survivent alors aux redémarrages et redéploiements du service.
database_url = os.environ.get("DATABASE_URL", "").strip()
if database_url.startswith("postgres://"):
    # SQLAlchemy 2.x ne reconnaît plus l'ancien préfixe "postgres://"
    database_url = database_url.replace("postgres://", "postgresql://", 1)
if not database_url:
    database_url = "sqlite:///" + os.path.join(BASE_DIR, "salle_des_preuves.db")

# pool_pre_ping : le serveur Postgres coupe les connexions inactives, on les
# teste avant usage et on les renouvelle toutes les 5 minutes.
engine = create_engine(database_url, pool_pre_ping=True, pool_recycle=300)

metadata = MetaData()
enquetes_table = Table(
    "enquetes", metadata,
    Column("id", String(40), primary_key=True),
    Column("data", Text, nullable=False),  # l'enquête complète, en JSON
)
images_table = Table(
    "images", metadata,
    Column("id", String(40), primary_key=True),
    Column("filename", String(255), nullable=False),
    Column("mimetype", String(50), nullable=False),
    Column("data", LargeBinary, nullable=False),
)
metadata.create_all(engine)


# Reprise des anciennes enquêtes : si un enquetes.json existe encore et que la
# base est vide, on les importe une fois dans la base.
def import_old_file():
    if not os.path.exists(OLD_DATA_FILE):
        return
    with engine.begin() as conn:
        if conn.execute(select(enquetes_table.c.id).limit(1)).first():
            return
        with open(OLD_DATA_FILE, "r", encoding="utf-8") as f:
            try:
                old = json.load(f)
            except json.JSONDecodeError:
                return
        for enquete in old:
            enquete["__backendId"] = enquete.get("__backendId") or uuid.uuid4().hex
            conn.execute(insert(enquetes_table).values(id=enquete["__backendId"], data=json.dumps(enquete, ensure_ascii=False)))


import_old_file()


@app.route("/")
def home():
    return render_template("index.html")


# Route API : Récupérer toutes les enquêtes enregistrées
@app.route("/api/enquetes", methods=["GET"])
def get_enquetes():
    with engine.connect() as conn:
        rows = conn.execute(select(enquetes_table.c.data)).scalars().all()
    return jsonify([json.loads(row) for row in rows])


# Route API : Créer une nouvelle enquête depuis l'Atelier
@app.route("/api/enquetes", methods=["POST"])
def add_enquete():
    new_case = request.get_json(silent=True)
    if not isinstance(new_case, dict):
        return jsonify({"error": "Données invalides"}), 400

    new_case["__backendId"] = uuid.uuid4().hex
    with engine.begin() as conn:
        conn.execute(insert(enquetes_table).values(id=new_case["__backendId"], data=json.dumps(new_case, ensure_ascii=False)))

    return jsonify(new_case), 201


# Route API : Mettre à jour une enquête existante
@app.route("/api/enquetes/<case_id>", methods=["PUT"])
def update_enquete(case_id):
    changes = request.get_json(silent=True)
    if not isinstance(changes, dict):
        return jsonify({"error": "Données invalides"}), 400

    changes["__backendId"] = case_id
    with engine.begin() as conn:
        result = conn.execute(update(enquetes_table).where(enquetes_table.c.id == case_id).values(data=json.dumps(changes, ensure_ascii=False)))
    if result.rowcount == 0:
        return jsonify({"error": "Enquête introuvable"}), 404
    return jsonify(changes)


# Route API : Supprimer une enquête
@app.route("/api/enquetes/<case_id>", methods=["DELETE"])
def delete_enquete(case_id):
    with engine.begin() as conn:
        result = conn.execute(delete(enquetes_table).where(enquetes_table.c.id == case_id))
    if result.rowcount == 0:
        return jsonify({"error": "Enquête introuvable"}), 404
    return jsonify({"message": "Enquête supprimée"})


# Route API : Envoyer une image (portrait de personnage, photo de décor).
# L'image est rangée dans la base, pas sur le disque du serveur : Render
# efface les fichiers du disque à chaque redéploiement.
@app.route("/api/images", methods=["POST"])
def upload_image():
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"error": "Aucune image reçue"}), 400

    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in IMAGE_TYPES:
        return jsonify({"error": "Format accepté : png, jpg, gif ou webp"}), 400

    image_id = uuid.uuid4().hex
    with engine.begin() as conn:
        conn.execute(insert(images_table).values(
            id=image_id,
            filename=secure_filename(file.filename) or "image." + extension,
            mimetype=IMAGE_TYPES[extension],
            data=file.read(),
        ))

    return jsonify({"url": url_for("get_image", image_id=image_id)}), 201


# Afficher une image enregistrée
@app.route("/images/<image_id>")
def get_image(image_id):
    with engine.connect() as conn:
        image = conn.execute(select(images_table).where(images_table.c.id == image_id)).first()
    if not image:
        abort(404)
    response = Response(image.data, mimetype=image.mimetype)
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


if __name__ == "__main__":
    app.run(debug=True)
