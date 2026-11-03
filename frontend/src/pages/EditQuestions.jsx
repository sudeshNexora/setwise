import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { readError } from "../api";

const LABELS = ["A", "B", "C", "D", "E", "F"];

export default function EditQuestions() {
  const { paperId } = useParams();
  const navigate = useNavigate();
  const [paper, setPaper] = useState(null);
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState(null);

  useEffect(() => { load(); }, [paperId]);

  function load() {
    api.get(`/papers/${paperId}`).then((r) => setPaper(r.data)).catch((e) => setError(readError(e)));
  }

  function patchLocal(questionId, changes) {
    setPaper((p) => ({
      ...p,
      sections: p.sections.map((s) => ({
        ...s,
        questions: s.questions.map((q) => (q.id === questionId ? { ...q, ...changes } : q)),
      })),
    }));
  }

  async function save(question, changes) {
    patchLocal(question.id, changes);
    setSavingId(question.id);
    try {
      await api.patch(`/papers/questions/${question.id}`, changes);
    } catch (e) {
      setError(readError(e, "That edit didn't save."));
    } finally {
      setSavingId(null);
    }
  }

  async function regenerate(question) {
    setSavingId(question.id);
    try {
      const { data } = await api.post(`/papers/questions/${question.id}/regenerate`);
      patchLocal(question.id, data);
    } catch (e) {
      setError(readError(e, "Couldn't swap that question."));
    } finally {
      setSavingId(null);
    }
  }

  async function remove(question) {
    await api.delete(`/papers/questions/${question.id}`);
    load();
  }

  async function addManual(sectionId) {
    const { data } = await api.post("/papers/questions", {
      section_id: sectionId, text: "New question — type it here.", qtype: "short", marks: 2,
    });
    setPaper((p) => ({
      ...p,
      sections: p.sections.map((s) => (s.id === sectionId ? { ...s, questions: [...s.questions, data] } : s)),
    }));
  }

  if (error && !paper) return <p className="form-error">{error}</p>;
  if (!paper) return <p className="empty">Loading the paper…</p>;

  const total = paper.sections.reduce((sum, s) => sum + s.questions.reduce((a, q) => a + q.marks, 0), 0);

  return (
    <div className="panel">
      <header className="panel-head">
        <h1>Edit the set</h1>
        <p>Everything here is editable. Rewrite a question, swap it for another, or add one of your own.</p>
      </header>

      {error && <p className="form-error">{error}</p>}

      {paper.sections.map((section) => (
        <section key={section.id} className="edit-section">
          <h2 className="edit-section-title">{section.title}</h2>
          {section.questions.map((q, i) => (
            <article className="q-card" key={q.id}>
              <div className="q-card-top">
                <div className="q-meta">
                  <span className="q-index">Q{i + 1}</span>
                  <span className="q-type-tag">{q.qtype}</span>
                  <span className="q-type-tag">{q.difficulty}</span>
                  {savingId === q.id && <span className="muted">saving…</span>}
                </div>
                <div className="q-actions">
                  <button className="icon-btn" title="Swap for another question" onClick={() => regenerate(q)}>↻</button>
                  <button className="icon-btn" title="Delete question" onClick={() => remove(q)}>✕</button>
                </div>
              </div>

              <textarea
                className="q-text"
                value={q.text}
                rows={2}
                onChange={(e) => patchLocal(q.id, { text: e.target.value })}
                onBlur={(e) => save(q, { text: e.target.value })}
              />

              {q.qtype === "mcq" && (
                <div className="q-options">
                  {q.options.map((opt, oi) => (
                    <label className="q-option" key={oi}>
                      <input
                        type="radio" name={`q${q.id}`}
                        checked={opt === q.answer_key}
                        onChange={() => save(q, { answer_key: opt })}
                      />
                      <span className="opt-label">{LABELS[oi]}</span>
                      <input
                        className="opt-input"
                        value={opt}
                        onChange={(e) => {
                          const options = [...q.options];
                          options[oi] = e.target.value;
                          patchLocal(q.id, { options });
                        }}
                        onBlur={() => save(q, { options: q.options })}
                      />
                    </label>
                  ))}
                </div>
              )}

              <div className="q-foot">
                <label className="field-label inline" htmlFor={`m${q.id}`}>Marks</label>
                <input
                  id={`m${q.id}`} className="marks-input" type="number" min="1" value={q.marks}
                  onChange={(e) => patchLocal(q.id, { marks: Number(e.target.value) })}
                  onBlur={(e) => save(q, { marks: Number(e.target.value) })}
                />
              </div>
            </article>
          ))}
          <button className="btn btn-outline small" onClick={() => addManual(section.id)}>
            Add question manually
          </button>
        </section>
      ))}

      <div className="panel-actions spread bordered">
        <span className="tally">Total: <strong>{total} marks</strong></span>
        <button className="btn" onClick={() => navigate(`/papers/${paperId}/preview`)}>Continue to preview</button>
      </div>
    </div>
  );
}
