import os
import datetime
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# -------------------------
# Config
# -------------------------
STORAGE_ACCOUNT_URL = os.getenv("STORAGE_ACCOUNT_URL")
IMAGES_CONTAINER = os.getenv("IMAGES_CONTAINER", "lanternfly-images")
AZURE_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIMES = ["image/png", "image/jpeg", "image/jpg", "image/gif"]

# -------------------------
# Flask App
# -------------------------
app = Flask(__name__)

# -------------------------
# Azure Blob Service Setup
# -------------------------
bsc = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
cc = bsc.get_container_client(IMAGES_CONTAINER)
# Create container if it doesn't exist
try:
    cc.create_container(public_access="container")
except Exception:
    pass  # already exists

# -------------------------
# Helpers
# -------------------------
def allowed_file(file):
    return file.mimetype in ALLOWED_MIMES

def timestamped_filename(filename):
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    safe_name = secure_filename(filename)
    return f"{ts}-{safe_name}"

# -------------------------
# Routes
# -------------------------
@app.get("/")
def index():
    return render_template("index.html")

@app.get("/health")
def health():
    return "OK", 200

@app.post("/api/v1/upload")
def upload():
    if "file" not in request.files:
        return jsonify(ok=False, error="No file provided"), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify(ok=False, error="Empty filename"), 400
    if not allowed_file(f):
        return jsonify(ok=False, error="Invalid file type"), 400
    if f.content_length and f.content_length > MAX_FILE_SIZE:
        return jsonify(ok=False, error="File too large"), 413

    try:
        blob_name = timestamped_filename(f.filename)
        content_settings = ContentSettings(content_type=f.mimetype)
        cc.upload_blob(name=blob_name, data=f, overwrite=True, content_settings=content_settings)
        url = f"{STORAGE_ACCOUNT_URL}/{IMAGES_CONTAINER}/{blob_name}"
        print(f"Uploaded {blob_name}")
        return jsonify(ok=True, url=url)
    except Exception as e:
        print("Upload error:", e)
        return jsonify(ok=False, error=str(e)), 500

@app.get("/api/v1/gallery")
def gallery():
    try:
        blobs = cc.list_blobs()
        urls = [f"{STORAGE_ACCOUNT_URL}/{IMAGES_CONTAINER}/{b.name}" for b in blobs]
        return jsonify(ok=True, gallery=urls)
    except Exception as e:
        print("Gallery error:", e)
        return jsonify(ok=False, error=str(e)), 500

if __name__ == "__main__":
    app.run(debug=True)
