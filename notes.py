from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from flask_cors import CORS
from pymongo.errors import PyMongoError
from datetime import datetime
import logging

# ================= APP SETUP =================
app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb+srv://lokesh2914:lokesh2914@greens-fs.kujgi3k.mongodb.net/greens_db?retryWrites=true&w=majority"
app.config["JWT_SECRET_KEY"] = "super-secret-key"

mongo = PyMongo(app)
jwt = JWTManager(app)

CORS(
    app,
    resources={r"/api/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}},
    supports_credentials=True,
)

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    mongo.cx.admin.command("ping")
    logger.info("✅ Successfully connected to MongoDB Atlas for notes!")
except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {e}")

users_collection = mongo.db.users

# ================= TOPICS =================
FRONTEND_TOPICS = ["html", "css", "javascript", "react"]
BACKEND_TOPICS = ["nodejs", "express", "mongodb", "flask", "jwt", "docker"]
DATABASE_TOPICS = ["sql", "nosql", "normalization", "acid", "indexing", "transactions", "cloud"]

# ================= HELPERS =================
def init_user_files():
    return {
        "frontendFiles": {topic: [] for topic in FRONTEND_TOPICS},
        "backendFiles": {topic: [] for topic in BACKEND_TOPICS},
        "databaseFiles": {topic: [] for topic in DATABASE_TOPICS},
    }

def sanitize_files(topic_list, incoming):
    safe_data = {}
    if not isinstance(incoming, dict):
        return safe_data
    for topic, files in incoming.items():
        if topic not in topic_list or not isinstance(files, list):
            continue
        cleaned = []
        for f in files:
            if isinstance(f, dict) and isinstance(f.get("name"), str) and isinstance(f.get("content"), str):
                cleaned.append({
                    "name": f["name"],
                    "content": f["content"],
                    "updatedAt": datetime.utcnow().isoformat()
                })
        safe_data[topic] = cleaned
    return safe_data

def update_topic_files(user, payload, topic_list, key_name):
    if key_name in payload:
        sanitized = sanitize_files(topic_list, payload[key_name])
        for topic in topic_list:
            existing_files = {f["name"]: f for f in user[key_name].get(topic, [])}
            if topic in sanitized:
                for f in sanitized[topic]:
                    existing_files[f["name"]] = f  # add or replace
            user[key_name][topic] = list(existing_files.values())  # ensures topic exists

# ================= GET NOTES =================
@app.route("/api/notes", methods=["GET"])
@jwt_required()
def get_notes():
    email = get_jwt_identity()
    try:
        user = users_collection.find_one({"email": email})

        if not user:
            # If user exists in auth but has no notes yet → create default files
            data = init_user_files()
            data["updatedAt"] = datetime.utcnow()
            users_collection.update_one(
                {"email": email},
                {"$set": data},
                upsert=True
            )
            user = users_collection.find_one({"email": email})

        # Ensure all topics exist to avoid frontend crashes
        user.setdefault("frontendFiles", {t: [] for t in FRONTEND_TOPICS})
        user.setdefault("backendFiles", {t: [] for t in BACKEND_TOPICS})
        user.setdefault("databaseFiles", {t: [] for t in DATABASE_TOPICS})

        user["_id"] = str(user["_id"])
        return jsonify({
            "_id": user["_id"],
            "frontendFiles": user["frontendFiles"],
            "backendFiles": user["backendFiles"],
            "databaseFiles": user["databaseFiles"]
        })

    except PyMongoError as e:
        logger.error(str(e))
        return jsonify({"error": "Database error"}), 500

# ================= SAVE NOTES =================
@app.route("/api/notes", methods=["POST"])
@jwt_required()
def save_notes():
    email = get_jwt_identity()
    payload = request.get_json() or {}

    try:
        user = users_collection.find_one({"email": email})

        if not user:
            # Create a proper user document if it doesn't exist
            user = {
                "email": email,
                **init_user_files(),
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow()
            }
            users_collection.insert_one(user)

        # Update files per topic
        update_topic_files(user, payload, FRONTEND_TOPICS, "frontendFiles")
        update_topic_files(user, payload, BACKEND_TOPICS, "backendFiles")
        update_topic_files(user, payload, DATABASE_TOPICS, "databaseFiles")

        # Save to DB
        users_collection.update_one(
            {"email": email},
            {
                "$set": {
                    "frontendFiles": user["frontendFiles"],
                    "backendFiles": user["backendFiles"],
                    "databaseFiles": user["databaseFiles"],
                    "updatedAt": datetime.utcnow()
                }
            },
            upsert=True
        )

        updated_user = users_collection.find_one({"email": email})
        updated_user["_id"] = str(updated_user["_id"])

        return jsonify({
            "_id": updated_user["_id"],
            "frontendFiles": updated_user["frontendFiles"],
            "backendFiles": updated_user["backendFiles"],
            "databaseFiles": updated_user["databaseFiles"]
        })

    except PyMongoError as e:
        logger.error(str(e))
        return jsonify({"error": "Database error"}), 500
    
 # ================delete field===========
@app.route("/api/notes/<string:key_name>/<string:topic>/<string:file_name>", methods=["DELETE"])
@jwt_required()
def delete_file(key_name, topic, file_name):
    email = get_jwt_identity()
    
    if key_name not in ["frontendFiles", "backendFiles", "databaseFiles"]:
        return jsonify({"error": "Invalid file category"}), 400
    
    try:
        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        if topic not in user[key_name]:
            return jsonify({"error": "Topic not found"}), 404
        
        # Filter out the file to delete
        updated_files = [f for f in user[key_name][topic] if f["name"] != file_name]
        user[key_name][topic] = updated_files
        
        users_collection.update_one(
            {"email": email},
            {"$set": {key_name: user[key_name], "updatedAt": datetime.utcnow()}}
        )
        
        return jsonify({"message": f"{file_name} deleted permanently", key_name: user[key_name]})
    
    except PyMongoError as e:
        logger.error(str(e))
        return jsonify({"error": "Database error"}), 500
    
# ================= RENAME FILE =================
@app.route("/api/notes/rename/<string:key_name>/<string:topic>", methods=["PUT"])
@jwt_required()
def rename_file(key_name, topic):
    email = get_jwt_identity()
    data = request.get_json() or {}
    old_name = data.get("oldName")
    new_name = data.get("newName")

    if key_name not in ["frontendFiles", "backendFiles", "databaseFiles"]:
        return jsonify({"error": "Invalid file category"}), 400
    if not old_name or not new_name:
        return jsonify({"error": "Missing oldName or newName"}), 400

    try:
        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found"}), 404

        if topic not in user[key_name]:
            return jsonify({"error": "Topic not found"}), 404

        # Check for duplicate new name
        if any(f["name"] == new_name for f in user[key_name][topic]):
            return jsonify({"error": "File with new name already exists"}), 400

        # Rename file
        renamed = False
        for f in user[key_name][topic]:
            if f["name"] == old_name:
                f["name"] = new_name
                f["updatedAt"] = datetime.utcnow().isoformat()
                renamed = True
                break

        if not renamed:
            return jsonify({"error": "File not found"}), 404

        users_collection.update_one(
            {"email": email},
            {"$set": {key_name: user[key_name], "updatedAt": datetime.utcnow()}}
        )

        return jsonify({"message": f"{old_name} renamed to {new_name}", key_name: user[key_name]})

    except PyMongoError as e:
        logger.error(str(e))
        return jsonify({"error": "Database error"}), 500

# ================= HEALTH CHECK =================
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "OK"}), 200

# ================= RUN APP =================
if __name__ == "__main__":
    app.run(port=5001, debug=True)
