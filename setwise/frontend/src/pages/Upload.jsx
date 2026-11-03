import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { readError } from "../api";

export default function Upload() {
  const navigate = useNavigate();
  const fileInput = useRef(null);
  const [uploads, setUploads] = useState([]);
  const [subject, setSubject] = useState("");
  const [unit, setUnit] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/uploads").then((r) => setUploads(r.data)).catch(() => {});
  }, []);

  async function send(file) {
    if (!subject.trim()) return setError("Add a subject before uploading.");
    setError("");
    setBusy(true);
    const body = new FormData();
    body.append("file", file);
    body.append("subject", subject);
    if (unit) body.append("unit", unit);
    try {
      const { data } = await api.post("/uploads", body);
      setUploads([data, ...uploads]);
    } catch (err) {
      setError(readError(err, "That file couldn't be read."));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    await api.delete(`/uploads/${id}`);
    setUploads(uploads.filter((u) => u.id !== id));
  }

  function onDrop(e) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) send(file);
  }

  return (
    <div className="panel">
      <header className="panel-head">
        <h1>Add this term's material</h1>
        <p>Drop in the syllabus or chapter notes. Setwise reads the text to find topics before it sets any questions.</p>
      </header>

      <div className="form-grid">
        <div>
          <label className="field-label" htmlFor="subject">Subject</label>
          <input id="subject" className="text-input" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Data Structures" />
        </div>
        <div>
          <label className="field-label" htmlFor="unit">Unit or chapter</label>
          <input id="unit" className="text-input" value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="Unit 2 — Linear Structures" />
        </div>
      </div>

      <div
        className="dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        onClick={() => fileInput.current.click()}
      >
        <p>{busy ? "Reading the file…" : "Drag a PDF or DOCX here"}</p>
        <p>or <span className="browse">browse your files</span></p>
        <input
          ref={fileInput} type="file" hidden accept=".pdf,.docx,.doc,.txt,.md"
          onChange={(e) => e.target.files[0] && send(e.target.files[0])}
        />
      </div>

      {error && <p className="form-error">{error}</p>}

      {uploads.length === 0 ? (
        <p className="empty">Nothing uploaded yet. Add a file to get started.</p>
      ) : (
        uploads.map((u) => (
          <div className="file-row" key={u.id}>
            <div className="file-row-top">
              <span className="file-name">{u.filename}</span>
              <span className="row-right">
                <span className="status-pill">{u.word_count} words</span>
                <button className="link-btn" onClick={() => remove(u.id)}>Remove</button>
              </span>
            </div>
            <div>
              {(u.topics || []).slice(0, 8).map((t) => (
                <span className="chip" key={t}>{t}</span>
              ))}
            </div>
          </div>
        ))
      )}

      <div className="panel-actions">
        <button className="btn" disabled={uploads.length === 0} onClick={() => navigate("/configure")}>
          Continue to configure
        </button>
      </div>
    </div>
  );
}
