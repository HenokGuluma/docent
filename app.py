"""
Docent — an AI reading-room attendant for your documents.

Upload a scan or PDF. Docent reads it, writes the catalog card
(title, summary, tags, type), and files it so you can find it again.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:5000
"""
import os
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash

from docent import storage, ocr, enrich

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

app = Flask(__name__)
app.secret_key = os.environ.get("DOCENT_SECRET", "docent-dev-key")
storage.init_db()


@app.route("/")
def library():
    query = request.args.get("q", "").strip()
    doc_type = request.args.get("type", "").strip()
    documents = storage.list_documents(query=query, doc_type=doc_type)
    doc_types = storage.list_doc_types()
    return render_template(
        "library.html",
        documents=documents,
        query=query,
        active_type=doc_type,
        doc_types=doc_types,
        total=storage.count_documents(),
    )


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Choose a file first — Docent can't read an empty hand.")
        return redirect(url_for("library"))

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        flash(f"Docent doesn't read {suffix or 'that'} files yet. Try a PDF or an image.")
        return redirect(url_for("library"))

    doc_id = storage.next_id()
    stored_name = f"{doc_id}{suffix}"
    stored_path = UPLOAD_DIR / stored_name
    file.save(stored_path)

    raw_text = ocr.extract_text(stored_path)
    card = enrich.catalog(raw_text, original_filename=file.filename)

    storage.insert_document(
        doc_id=doc_id,
        original_filename=file.filename,
        stored_filename=stored_name,
        raw_text=raw_text,
        title=card["title"],
        summary=card["summary"],
        tags=card["tags"],
        doc_type=card["doc_type"],
        source=card["source"],
    )
    return redirect(url_for("document_detail", doc_id=doc_id))


@app.route("/documents/<int:doc_id>")
def document_detail(doc_id):
    doc = storage.get_document(doc_id)
    if doc is None:
        flash("That catalog card doesn't exist (or was withdrawn).")
        return redirect(url_for("library"))
    return render_template("document.html", doc=doc)


@app.route("/documents/<int:doc_id>/retag", methods=["POST"])
def retag(doc_id):
    """Ask Docent to re-read a document and rewrite its catalog card."""
    doc = storage.get_document(doc_id)
    if doc is None:
        flash("That catalog card doesn't exist (or was withdrawn).")
        return redirect(url_for("library"))
    card = enrich.catalog(doc["raw_text"], original_filename=doc["original_filename"])
    storage.update_card(doc_id, card)
    return redirect(url_for("document_detail", doc_id=doc_id))


@app.route("/documents/<int:doc_id>/delete", methods=["POST"])
def delete(doc_id):
    doc = storage.get_document(doc_id)
    if doc:
        stored_path = UPLOAD_DIR / doc["stored_filename"]
        if stored_path.exists():
            stored_path.unlink()
        storage.delete_document(doc_id)
        flash(f'"{doc["title"]}" withdrawn from the catalog.')
    return redirect(url_for("library"))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
