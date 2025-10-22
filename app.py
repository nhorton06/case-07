from flask import Flask, request, jsonify, render_template
from azure.storage.blob import BlobServiceClient
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import datetime
import logging

# --- Load environment variables ---
load_dotenv()

# --- Configuration ---
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_BLOB_CONTAINER", "kbr8eycase07")
MAX_FILE_SIZE_MB = 10
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}

# --- Initialize Flask app ---
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_MB * 1024 * 1024  # 10 MB max

# --- Setup logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- Create Blob Service Client ---
bsc = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

# --- Ensure container exists ---
try:
    cc = bsc.get_container_client(CONTAINER_NAME)
    cc.get_container_properties()
    logging.info(f"✅ Connected to existing container: {CONTAINER_NAME}")
except Exception:
    logging.info(f"Container '{CONTAINER_NAME}' does not exist. Creating...")
    cc = bsc.create_container(CONTAINER_NAME, public_access="blob")
    logging.info(f"✅ Created container '{CONTAINER_NAME}' with public read access")

# --- Helper functions ---
def allowed_file_type(file):
    """Ensure the uploaded file is an image."""
    return file.content_type.lower() in ALLOWED_MIME_TYPES

def generate_filename(original):
    """Sanitize and prepend timestamp to the filename."""
    safe_name = secure_filename(original)
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    return f"{timestamp}-{safe_name}"

# --- Upload Endpoint ---
@app.post("/api/v1/upload")
def upload():
    if "file" not in request.files:
        return jsonify(ok=False, error="No file provided"), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify(ok=False, error="Empty filename"), 400
    if not allowed_file_type(f):
        return jsonify(ok=False, error=f"Unsupported file type: {f.content_type}"), 400

    try:
        blob_name = generate_filename(f.filename)
        blob_client = cc.get_blob_client(blob_name)
        blob_client.upload_blob(f, overwrite=True)

        blob_url = f"{cc.url}/{blob_name}"
        logging.info(f"Uploaded {blob_name} → {blob_url}")
        return jsonify(ok=True, url=blob_url)
    except Exception as e:
        logging.error(f"Upload failed: {e}")
        return jsonify(ok=False, error=str(e)), 500

# --- Gallery Endpoint ---
@app.get("/api/v1/gallery")
def gallery():
    try:
        blob_list = cc.list_blobs()
        urls = [f"{cc.url}/{b.name}" for b in blob_list]
        return jsonify(ok=True, gallery=urls)
    except Exception as e:
        logging.error(f"Failed to list gallery: {e}")
        return jsonify(ok=False, error=str(e)), 500

# --- Health Endpoint ---
@app.get("/api/v1/health")
def health():
    return jsonify(ok=True), 200

# --- Frontend Endpoint ---
@app.get("/")
def index():
    return render_template("index.html")

# --- Main Entry Point ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
