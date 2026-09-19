import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { readError } from "../api";

const LABELS = ["A", "B", "C", "D", "E", "F"];

export default function Preview() {
  const { paperId } = useParams();
  const navigate = useNavigate();
  const [paper, setPaper] = useState(null);
  const [showKey, setShowKey] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    api.get(`/papers/${paperId}`).then((r) => setPaper(r.data)).catch((e) => setError(readError(e)));
  }, [paperId]);

  async function download(fmt) {
    setBusy(fmt);
    setError("");
    try {
      const res = await api.get(`/papers/${paperId}/export/${fmt}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = fmt === "pdf" ? `paper_${paperId}.pdf` : `paper_${paperId}${fmt === "key" ? "_key" : ""}.docx`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(readError(e, "The export didn't complete."));
    } finally {
      setBusy("");
    }
  }

  async function publish() {
    const { data } = await api.post(`/papers/${paperId}/publish`);
    setPaper({ ...paper, status: data.status });
  }

  if (error && !paper) return <p className="form-error">{error}</p>;
  if (!paper) return <p className="empty">Loading the paper…</p>;

  return (
    <div className="panel">
      <header className="panel-head">
        <h1>Preview</h1>
        <p>This is exactly how the paper will look once exported.</p>
      </header>

      <div className="preview-toggle">
        <button className={!showKey ? "active" : ""} onClick={() => setShowKey(false)}>Question paper</button>
        <button className={showKey ? "active" : ""} onClick={() => setShowKey(true)}>Answer key</button>
      </div>

      <article className="paper-sheet">
        <h2>{paper.institution}</h2>
        <p className="sheet-sub">{paper.title}</p>
        <div className="paper-meta-row">
          <span>{paper.subject}{paper.semester ? ` · ${paper.semester}` : ""}</span>
          <span>Time: {paper.duration_minutes} min</span>
          <span>Max marks: {paper.total_marks}</span>
        </div>
        {paper.instructions && <p className="paper-instructions">{paper.instructions}</p>}

        {paper.sections.map((section) => (
          <div key={section.id}>
            <p className="paper-section-title">{section.title}</p>
            {section.instruction && <p className="paper-instructions">{section.instruction}</p>}
            {section.questions.map((q, i) => (
              <div className="paper-q" key={q.id}>
                <span className="qnum">{i + 1}.</span>
                <span className="qbody">
                  {q.text}
                  {q.qtype === "mcq" && (
                    <span className="paper-options">
                      {q.options.map((o, oi) => (
                        <span key={oi} className={showKey && o === q.answer_key ? "correct" : ""}>
                          ({LABELS[oi]}) {o}
                        </span>
                      ))}
                    </span>
                  )}
                  {showKey && q.qtype !== "mcq" && (
                    <span className="key-text">{q.answer_key || "Open-ended — grade on rubric."}</span>
                  )}
                </span>
                <span className="qmarks">[{q.marks}]</span>
              </div>
            ))}
          </div>
        ))}
      </article>

      {error && <p className="form-error">{error}</p>}

      <div className="panel-actions right">
        <button className="btn btn-outline" onClick={() => navigate(`/papers/${paperId}/edit`)}>Back to edit</button>
        <button className="btn btn-outline" onClick={() => download("key")} disabled={busy === "key"}>
          {busy === "key" ? "Preparing…" : "Answer key"}
        </button>
        <button className="btn btn-pen" onClick={() => download("docx")} disabled={busy === "docx"}>
          {busy === "docx" ? "Preparing…" : "Download DOCX"}
        </button>
        <button className="btn" onClick={() => download("pdf")} disabled={busy === "pdf"}>
          {busy === "pdf" ? "Preparing…" : "Download PDF"}
        </button>
        {paper.status !== "published" && (
          <button className="btn btn-outline" onClick={publish}>Publish to students</button>
        )}
      </div>
    </div>
  );
}
