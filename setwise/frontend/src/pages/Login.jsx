import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { readError } from "../api";
import { useAuth } from "../auth";

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("signin");
  const [role, setRole] = useState("faculty");
  const [form, setForm] = useState({ name: "", email: "", password: "", department: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "signin") await login(form.email, form.password);
      else await register({ ...form, role });
      navigate("/upload");
    } catch (err) {
      setError(readError(err, "Could not sign you in."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-screen">
      <section className="login-hero">
        <span className="wordmark">Set<span>wise</span></span>
        <div>
          <h1>From syllabus to sealed paper.</h1>
          <p>
            Upload what you're teaching, set the paper, and grade what comes back —
            Setwise handles the parts that eat your evening.
          </p>
        </div>
        <p className="hero-foot">
          Faculty sign in with an institutional email. Students use the code their teacher shares.
        </p>
      </section>

      <section className="login-form-side">
        <form className="login-form" onSubmit={submit}>
          <h2>{mode === "signin" ? "Sign in" : "Create an account"}</h2>
          <p className="sub">
            {mode === "signin" ? "Continue setting or grading a paper." : "Takes about a minute."}
          </p>

          {mode === "signup" && (
            <>
              <div className="role-toggle">
                <button type="button" className={role === "faculty" ? "active" : ""} onClick={() => setRole("faculty")}>Faculty</button>
                <button type="button" className={role === "student" ? "active" : ""} onClick={() => setRole("student")}>Student</button>
              </div>
              <div className="form-row">
                <label className="field-label" htmlFor="name">Full name</label>
                <input id="name" className="text-input" value={form.name} onChange={set("name")} required />
              </div>
              <div className="form-row">
                <label className="field-label" htmlFor="dept">Department</label>
                <input id="dept" className="text-input" value={form.department} onChange={set("department")} />
              </div>
            </>
          )}

          <div className="form-row">
            <label className="field-label" htmlFor="email">Institutional email</label>
            <input id="email" type="email" className="text-input" value={form.email} onChange={set("email")} required />
          </div>
          <div className="form-row">
            <label className="field-label" htmlFor="pw">Password</label>
            <input id="pw" type="password" className="text-input" value={form.password} onChange={set("password")} minLength={8} required />
          </div>

          {error && <p className="form-error">{error}</p>}

          <button className="btn full" disabled={busy}>
            {busy ? "Working…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>

          <p className="login-foot">
            {mode === "signin" ? "New here? " : "Already have an account? "}
            <button type="button" className="link-btn" onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); }}>
              {mode === "signin" ? "Create an account" : "Sign in"}
            </button>
          </p>
        </form>
      </section>
    </div>
  );
}
