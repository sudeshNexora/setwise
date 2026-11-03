import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { readError } from "../api";

const BLANK_SECTION = { title: "", instruction: "", qtype: "short", count: 5, marks_each: 2 };

export default function Configure() {
  const navigate = useNavigate();
  const [uploads, setUploads] = useState([]);
  const [selected, setSelected] = useState([]);
  const [meta, setMeta] = useState({
    title: "", institution: "", subject: "", semester: "",
    duration_minutes: 90, instructions: "Answer all questions in Section A.",
  });
  const [sections, setSections] = useState([
    { title: "Section A — Short answer", instruction: "Answer all questions.", qtype: "short", count: 8, marks_each: 2 },
    { title: "Section B — Long answer", instruction: "Attempt any three.", qtype: "long", count: 4, marks_each: 8 },
  ]);
  const [mix, setMix] = useState({ easy: 35, medium: 45, hard: 20 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/uploads").then((r) => {
      setUploads(r.data);
      if (r.data[0]) {
        setSelected([r.data[0].id]);
        setMeta((m) => ({ ...m, subject: m.subject || r.data[0].subject }));
      }
    });
  }, []);

  const planned = sections.reduce((sum, s) => sum + s.count * s.marks_each, 0);

  const setMetaField = (key) => (e) => setMeta({ ...meta, [key]: e.target.value });

  function updateSection(i, key, value) {
    const next = [...sections];
    next[i] = { ...next[i], [key]: key === "count" || key === "marks_each" ? Number(value) : value };
    setSections(next);
  }

  async function generate() {
    setError("");
    if (selected.length === 0) return setError("Pick at least one uploaded file.");
    if (!meta.title.trim()) return setError("Give the paper a title.");
    setBusy(true);
    try {
      const { data } = await api.post("/papers/generate", {
        ...meta,
        duration_minutes: Number(meta.duration_minutes),
        upload_ids: selected,
        sections,
        difficulty_mix: mix,
      });
      navigate(`/papers/${data.id}/edit`);
    } catch (err) {
      setError(readError(err, "Generation failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <header className="panel-head">
        <h1>Configure the paper</h1>
        <p>Set the shape of the paper — sections, question types, and how marks are split.</p>
      </header>

      <label className="field-label">Generate from</label>
      <div className="source-list">
        {uploads.map((u) => (
          <label className="source-item" key={u.id}>
            <input
              type="checkbox"
              checked={selected.includes(u.id)}
              onChange={(e) =>
                setSelected(e.target.checked ? [...selected, u.id] : selected.filter((id) => id !== u.id))
              }
            />
            <span>{u.filename}</span>
            <span className="muted">{u.subject}{u.unit ? ` · ${u.unit}` : ""}</span>
          </label>
        ))}
        {uploads.length === 0 && <p className="empty">Upload material first.</p>}
      </div>

      <div className="form-grid">
        <div>
          <label className="field-label" htmlFor="ptitle">Paper title</label>
          <input id="ptitle" className="text-input" value={meta.title} onChange={setMetaField("title")} placeholder="End Semester Examination" />
        </div>
        <div>
          <label className="field-label" htmlFor="inst">Institution</label>
          <input id="inst" className="text-input" value={meta.institution} onChange={setMetaField("institution")} />
        </div>
        <div>
          <label className="field-label" htmlFor="subj">Subject</label>
          <input id="subj" className="text-input" value={meta.subject} onChange={setMetaField("subject")} />
        </div>
        <div>
          <label className="field-label" htmlFor="sem">Semester</label>
          <input id="sem" className="text-input" value={meta.semester} onChange={setMetaField("semester")} placeholder="Semester III" />
        </div>
        <div>
          <label className="field-label" htmlFor="dur">Duration (minutes)</label>
          <input id="dur" type="number" className="text-input" value={meta.duration_minutes} onChange={setMetaField("duration_minutes")} />
        </div>
        <div>
          <label className="field-label" htmlFor="instr">Instructions to candidates</label>
          <input id="instr" className="text-input" value={meta.instructions} onChange={setMetaField("instructions")} />
        </div>
      </div>

      <label className="field-label">Sections</label>
      {sections.map((s, i) => (
        <div className="section-row" key={i}>
          <input className="text-input" value={s.title} onChange={(e) => updateSection(i, "title", e.target.value)} />
          <select className="text-input" value={s.qtype} onChange={(e) => updateSection(i, "qtype", e.target.value)}>
            <option value="short">Short answer</option>
            <option value="long">Long answer</option>
            <option value="mcq">MCQ</option>
            <option value="fill">Fill in the blank</option>
          </select>
          <input className="text-input" type="number" min="1" value={s.count} onChange={(e) => updateSection(i, "count", e.target.value)} />
          <input className="text-input" type="number" min="1" value={s.marks_each} onChange={(e) => updateSection(i, "marks_each", e.target.value)} />
          <button className="icon-btn" title="Remove section" onClick={() => setSections(sections.filter((_, x) => x !== i))}>✕</button>
        </div>
      ))}
      <button className="btn btn-outline small" onClick={() => setSections([...sections, { ...BLANK_SECTION }])}>
        Add section
      </button>

      <label className="field-label spaced">Difficulty mix</label>
      <div className="mix-row">
        {["easy", "medium", "hard"].map((level) => (
          <div className="mix-item" key={level}>
            <label htmlFor={level}><span>{level}</span><span>{mix[level]}%</span></label>
            <input
              id={level} type="range" min="0" max="100" value={mix[level]}
              onChange={(e) => setMix({ ...mix, [level]: Number(e.target.value) })}
            />
          </div>
        ))}
      </div>

      {error && <p className="form-error">{error}</p>}

      <div className="panel-actions spread">
        <span className="tally">Planned total: <strong>{planned} marks</strong></span>
        <button className="btn" onClick={generate} disabled={busy}>
          {busy ? "Generating…" : "Generate questions"}
        </button>
      </div>
    </div>
  );
}
