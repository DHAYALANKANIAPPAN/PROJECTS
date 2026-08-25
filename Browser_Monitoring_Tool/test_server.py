import os
import joblib
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
from functools import wraps
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import logging
from pymongo.errors import ConnectionFailure, DuplicateKeyError

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------
# Configuration
# ------------------------------
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS")

# ------------------------------
# MongoDB connection with error handling
# ------------------------------
client = None
db = None
records_col = None

try:
    if MONGO_URI:
        # Use the correct MongoDB connection format
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'), serverSelectionTimeoutMS=5000)
        client.admin.command('ping')  # Simple test command
        db = client["activity_db"]
        records_col = db["records"]
        logger.info("✅ MongoDB connected successfully")
    else:
        logger.warning("❌ MONGO_URI not set")
except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {e}")
    client = None
    db = None
    records_col = None

# Create indexes if connected
if records_col is not None:
    try:
        records_col.create_index([("timestamp", -1)])
        records_col.create_index([("lab_name", 1), ("system_name", 1)])
        records_col.create_index([("timestamp", 1)])  # Added for date filtering
        logger.info("✅ Database indexes created")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")

# ------------------------------
# ML Model Files
# ------------------------------
MODEL_FILE = "url_model.pkl"
VECT_FILE = "vectorizer.pkl"
CAT_MODEL_FILE = "cat_model.pkl"
CAT_VECT_FILE = "cat_vectorizer.pkl"

# Model cache
_model_cache = {}

# ------------------------------
# Admin Authentication
# ------------------------------
def check_auth(username, password):
    return username == ADMIN_USER and password == ADMIN_PASS

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                'Authentication required',
                401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            )
        return f(*args, **kwargs)
    return decorated

# ------------------------------
# ML Functions
# ------------------------------
def load_models():
    """Load models into cache"""
    try:
        if not _model_cache.get('flag_model') and os.path.exists(MODEL_FILE):
            _model_cache['flag_model'] = joblib.load(MODEL_FILE)
            _model_cache['flag_vectorizer'] = joblib.load(VECT_FILE)
            logger.info("✅ Flag prediction models loaded")
        
        if not _model_cache.get('cat_model') and os.path.exists(CAT_MODEL_FILE):
            _model_cache['cat_model'] = joblib.load(CAT_MODEL_FILE)
            _model_cache['cat_vectorizer'] = joblib.load(CAT_VECT_FILE)
            logger.info("✅ Category prediction models loaded")
    except Exception as e:
        logger.error(f"Error loading models: {e}")

def train_model():
    """Retrain models for flag prediction and category prediction."""
    if records_col is None:
        logger.warning("Cannot train model: No database connection")
        return
        
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        rows = list(records_col.find({
            "timestamp": {"$gte": cutoff_date.isoformat()},
            "url": {"$exists": True, "$ne": ""}
        }, {"url": 1, "flagged": 1, "category": 1, "_id": 0}).limit(10000))
        
        if len(rows) < 20:
            logger.info("Insufficient data for model training")
            return

        urls = [r["url"] for r in rows if r.get("url")]
        flags = np.array([r.get("flagged", 0) for r in rows])
        categories = [r.get("category", "Uncategorized") for r in rows]

        # Flag prediction model
        if len(set(flags)) > 1:
            vectorizer = TfidfVectorizer(max_features=1000, stop_words='english', ngram_range=(1, 2))
            X = vectorizer.fit_transform(urls)
            flag_model = LogisticRegression(max_iter=1000, class_weight='balanced')
            flag_model.fit(X, flags)
            
            joblib.dump(flag_model, MODEL_FILE)
            joblib.dump(vectorizer, VECT_FILE)
            logger.info(f"✅ Flag model trained on {len(urls)} samples")

        # Category prediction model
        unique_cats = set(categories)
        if len(unique_cats) > 1:
            cat_vectorizer = TfidfVectorizer(max_features=1500, stop_words='english')
            X_cat = cat_vectorizer.fit_transform(urls)
            cat_model = LogisticRegression(max_iter=1000)
            cat_model.fit(X_cat, categories)
            
            joblib.dump(cat_model, CAT_MODEL_FILE)
            joblib.dump(cat_vectorizer, CAT_VECT_FILE)
            logger.info(f"✅ Category model trained on {len(urls)} samples, {len(unique_cats)} categories")
        
        load_models()
        
    except Exception as e:
        logger.error(f"Model training failed: {e}")

def predict_flag(url):
    """Predict if URL should be flagged"""
    try:
        if not _model_cache.get('flag_model'):
            return 0
        
        X = _model_cache['flag_vectorizer'].transform([url])
        return int(_model_cache['flag_model'].predict(X)[0])
    except Exception as e:
        logger.error(f"Flag prediction error: {e}")
        return 0

def predict_category(url):
    """Predict URL category"""
    try:
        if not _model_cache.get('cat_model'):
            return "Uncategorized"
        
        X = _model_cache['cat_vectorizer'].transform([url])
        return str(_model_cache['cat_model'].predict(X)[0])
    except Exception as e:
        logger.error(f"Category prediction error: {e}")
        return "Uncategorized"

# ------------------------------
# MongoDB Helpers
# ------------------------------
def insert_records(records):
    """Safely insert multiple records into MongoDB with predictions."""
    if records_col is None:
        logger.error("No database connection")
        return 0
        
    if not records or not isinstance(records, list):
        return 0

    docs = []
    inserted_count = 0
    
    for r in records:
        try:
            url = r.get("url", "").strip()
            if not url or len(url) < 5:
                continue

            existing_category = r.get("category", "").strip()
            predicted_cat = existing_category if existing_category else predict_category(url)
            
            existing_flag = r.get("flagged", 0)
            predicted_flag = existing_flag if existing_flag in [0, 1] else predict_flag(url)
            
            doc = {
                "browser": r.get("browser", "Unknown")[:100],
                "url": url[:500],
                "title": r.get("title", "")[:500],
                "timestamp": r.get("timestamp") or datetime.utcnow().isoformat(),
                "system_name": r.get("system_name", "Unknown")[:100],
                "lab_name": r.get("lab_name", "Unknown")[:100],
                "category": predicted_cat[:50],
                "flagged": predicted_flag,
                "user_name": r.get("user_name", "Unknown")[:100],
                "created_at": datetime.utcnow()
            }
            docs.append(doc)
            
        except Exception as e:
            logger.error(f"Error processing record: {e}")
            continue

    if docs:
        try:
            result = records_col.insert_many(docs, ordered=False)
            inserted_count = len(result.inserted_ids)
            logger.info(f"✅ Inserted {inserted_count} records")
        except DuplicateKeyError:
            logger.warning("Duplicate records detected")
        except Exception as e:
            logger.error(f"Bulk insert error: {e}")
    
    return inserted_count

def fetch_records(date=None, limit=1000):
    """Fetch records with optional date filter"""
    if records_col is None:
        return []
        
    try:
        query = {}
        if date:
            # Use proper date range query instead of regex for better performance
            start_date = datetime.strptime(date, "%Y-%m-%d")
            end_date = start_date + timedelta(days=1)
            query["timestamp"] = {
                "$gte": start_date.isoformat(),
                "$lt": end_date.isoformat()
            }
        
        cursor = records_col.find(query).sort("timestamp", -1).limit(limit)
        rows = list(cursor)
        
        return [
            {
                "id": str(r["_id"]),
                "browser": r.get("browser", ""),
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "timestamp": r.get("timestamp", ""),
                "system_name": r.get("system_name", ""),
                "lab_name": r.get("lab_name", ""),
                "category": r.get("category", ""),
                "flagged": r.get("flagged", 0),
                "user_name": r.get("user_name", "Unknown")
            } for r in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching records: {e}")
        return []

def update_flag(record_id, flagged):
    """Update record flag status"""
    if records_col is None:
        return False
        
    try:
        result = records_col.update_one(
            {"_id": ObjectId(record_id)}, 
            {"$set": {"flagged": flagged, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating flag: {e}")
        return False

# ------------------------------
# Flask Routes
# ------------------------------
@app.route("/upload", methods=["POST"])
def upload():
    """Upload activity data to MongoDB."""
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        if not isinstance(data, list):
            return jsonify({"error": "Expected list of records"}), 400
        
        inserted_count = insert_records(data)
        
        if inserted_count > 0:
            if records_col is not None:
                total_count = records_col.count_documents({})
                if total_count % 1000 < inserted_count:
                    train_model()
        
        return jsonify({
            "status": "success", 
            "message": f"Processed {len(data)} records, inserted {inserted_count}",
            "inserted": inserted_count
        }), 200
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/labs", methods=["GET"])
@requires_auth
def get_labs():
    """Get lab and system overview - IMPROVED VERSION"""
    try:
        date_filter = request.args.get("date")
        logger.info(f"Labs endpoint called with date: {date_filter}")
        
        if records_col is None:
            logger.warning("No database connection in labs endpoint")
            return jsonify({})
        
        # Build query with date filter
        query = {}
        if date_filter:
            # Use proper date range query
            start_date = datetime.strptime(date_filter, "%Y-%m-%d")
            end_date = start_date + timedelta(days=1)
            query["timestamp"] = {
                "$gte": start_date.isoformat(),
                "$lt": end_date.isoformat()
            }
        
        # Use aggregation for better performance
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": {
                    "lab": "$lab_name",
                    "system": "$system_name",
                    "user": "$user_name"
                },
                "total_visits": {"$sum": 1},
                "flagged": {"$max": "$flagged"}
            }},
            {"$group": {
                "_id": {
                    "lab": "$_id.lab",
                    "system": "$_id.system"
                },
                "total_visits": {"$sum": "$total_visits"},
                "flagged": {"$max": "$flagged"},
                "users": {"$addToSet": "$_id.user"}
            }},
            {"$group": {
                "_id": "$_id.lab",
                "systems": {
                    "$push": {
                        "system_name": "$_id.system",
                        "total_visits": "$total_visits",
                        "flagged": "$flagged",
                        "users": "$users"
                    }
                }
            }}
        ]
        
        lab_data = list(records_col.aggregate(pipeline))
        
        # Convert to the expected format
        result = {}
        for lab in lab_data:
            lab_name = lab["_id"] or "Unknown Lab"
            result[lab_name] = lab["systems"]
        
        logger.info(f"Returning {len(result)} labs with systems")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Labs endpoint failed: {str(e)}", exc_info=True)
        return jsonify({"error": "Server error"}), 500

@app.route("/data", methods=["GET"])
@requires_auth
def get_data():
    """Get recent activity data"""
    try:
        date = request.args.get("date")
        limit = int(request.args.get("limit", 1000))
        records = fetch_records(date, limit=limit)
        return jsonify(records)
    except Exception as e:
        logger.error(f"Data endpoint error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/flag", methods=["POST"])
@requires_auth
def flag_entry():
    """Flag a specific entry"""
    try:
        data = request.get_json()
        if not data or "id" not in data:
            return jsonify({"error": "Missing record ID"}), 400
        
        success = update_flag(data["id"], 1)
        if success:
            train_model()
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Record not found"}), 404
            
    except Exception as e:
        logger.error(f"Flag endpoint error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/unflag", methods=["POST"])
@requires_auth
def unflag_entry():
    """Unflag a specific entry"""
    try:
        data = request.get_json()
        if not data or "id" not in data:
            return jsonify({"error": "Missing record ID"}), 400
        
        success = update_flag(data["id"], 0)
        if success:
            train_model()
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Record not found"}), 404
            
    except Exception as e:
        logger.error(f"Unflag endpoint error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    try:
        if client is not None:
            client.admin.command('ping')
            db_status = "connected"
            records_count = records_col.count_documents({}) if records_col is not None else 0
        else:
            db_status = "disconnected"
            records_count = 0
        
        stats = {
            "status": "healthy" if client is not None else "unhealthy",
            "database": db_status,
            "timestamp": datetime.utcnow().isoformat(),
            "records_count": records_count,
            "models_loaded": {
                "flag_model": bool(_model_cache.get('flag_model')),
                "category_model": bool(_model_cache.get('cat_model'))
            }
        }
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy", 
            "error": str(e),
            "database": "connection_failed"
        }), 500

@app.route('/')
@requires_auth  
def dashboard():
    """Serve the dashboard"""
    return send_from_directory(os.path.dirname(__file__), 'activity_monitor.html')

# ------------------------------
# Application Startup
# ------------------------------
def initialize_app():
    """Initialize application on startup"""
    logger.info("Initializing application...")
    load_models()
    if not _model_cache and client is not None:
        train_model()

# Print all routes for debugging
def print_routes():
    print("\n📋 ALL FLASK ROUTES:")
    print("-" * 50)
    for rule in app.url_map.iter_rules():
        if rule.endpoint != 'static':
            methods = ','.join(rule.methods)
            protected = "PROTECTED" if "requires_auth" in str(app.view_functions[rule.endpoint]) else "UNPROTECTED"
            print(f"{rule.endpoint:20} {methods:15} {rule.rule:30} [{protected}]")
    print("-" * 50)

# Initialize immediately
initialize_app()
print_routes()

# ------------------------------
# Run Flask
# ------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    debug = os.environ.get("FLASK_ENV") == "development"
    
    logger.info(f"Starting server on port {port} (debug: {debug})")
    app.run(debug=debug, host="0.0.0.0", port=port)
