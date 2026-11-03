import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

export default function Archive() {
  const navigate = useNavigate();
  const [papers, setPapers] = useState([]);
  const [filters, setFilters] = useState({ q: "", subject: "", semester: "" });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(true);
      const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
      api.get("/papers", { params })
        .then((r) => setPapers(r.data))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [filters]);

  const subjects = [...new Set(papers.map((p) => p.subject))];
  const set = (key) => (e) => setFilters({ ...filters, [key]: e.target.value });

  return (
    <div className="panel wide">
      <header className="panel-head">
        <h1>Past papers</h1>
        <p>Everything you've set, searchable by title, subject and semester.</p>
      </header>

      <div className="filter-row">
        <input className="text-input" placeholder="Search by title" value={filters.q} onChange={set("q")} />
        <select className="text-input" value={filters.subject} onChange={set("subject")}>
          <option value="">All subjects</option>
          {subjects.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <input className="text-input" placeholder="Semester" value={filters.semester} onChange={set("semester")} />
      </div>

      {loading ? (
        <p className="empty">Fetching papers…</p>
      ) : papers.length === 0 ? (
        <p className="empty">No papers match that. Set one from the upload step.</p>
      ) : (
        <table className="archive-table">
          <thead>
            <tr><th>Title</th><th>Subject</th><th>Semester</th><th>Set on</th><th>Marks</th><th>Status</th><th /></tr>
          </thead>
          <tbody>
            {papers.map((p) => (
              <tr key={p.id}>
                <td>{p.title}</td>
                <td>{p.subject}</td>
                <td>{p.semester || "—"}</td>
                <td>{new Date(p.created_at).toLocaleDateString()}</td>
                <td>{p.total_marks}</td>
                <td><span className="status-pill">{p.status}</span></td>
                <td>
                  <button className="link-btn" onClick={() => navigate(`/papers/${p.id}/preview`)}>View</button>
                  <button className="link-btn" onClick={() => navigate(`/papers/${p.id}/edit`)}>Edit</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
