from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta, datetime
import logging

# ================= APP SETUP =================
app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb+srv://lokesh2914:lokesh2914@greens-fs.kujgi3k.mongodb.net/greens_db?retryWrites=true&w=majority"
app.config["JWT_SECRET_KEY"] = "super-secret-key"  # Dev only
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)

# CORS setup: allow your frontend to talk to backend
CORS(
    app,
    resources={r"/api/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}},
    supports_credentials=True,
)


# Initialize MongoDB and JWT
mongo = PyMongo(app)
jwt = JWTManager(app)

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    mongo.cx.admin.command("ping")
    logger.info("✅ Successfully connected to MongoDB Atlas!")
except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {e}")

users = mongo.db.users

# ================= SIGNUP =================
@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    if users.find_one({"email": email}):
        return jsonify({"error": "Email already exists"}), 400

    # Hash the password
    hashed_password = generate_password_hash(password)

    # Initialize empty topic files
    FRONTEND_TOPICS = ["html", "css", "javascript", "react"]
    BACKEND_TOPICS = ["nodejs", "express", "mongodb", "flask", "jwt", "docker"]
    DATABASE_TOPICS = ["sql", "nosql", "normalization", "acid", "indexing", "transactions", "cloud"]

    def init_user_files():
        return {
            "frontendFiles": {topic: [] for topic in FRONTEND_TOPICS},
            "backendFiles": {topic: [] for topic in BACKEND_TOPICS},
            "databaseFiles": {topic: [] for topic in DATABASE_TOPICS},
        }

    user_data = {
        "username": username,
        "email": email,
        "password": hashed_password,
        "createdAt": datetime.utcnow(),
        **init_user_files()  # Initialize empty topics
    }

    users.insert_one(user_data)

    access_token = create_access_token(identity=email)
    return jsonify({"message": "Signup successful", "token": access_token, "username": username}), 201


# ================= LOGIN =================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = users.find_one({"email": email})
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = create_access_token(identity=email)
    return jsonify({"message": "Login successful", "token": access_token, "username": user["username"]})

# ================= DASHBOARD =================
@app.route("/api/dashboard", methods=["GET"])
@jwt_required()
def dashboard():
    current_user = get_jwt_identity()
    user = users.find_one({"email": current_user})

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "message": "Welcome to dashboard",
        "username": user["username"],
        "email": user["email"]
    })

# ================= RUN APP =================
if __name__ == "__main__":
    app.run(port=5000, debug=True)
