import { Navigate, Route, Routes } from "react-router-dom";
import Shell from "./components/Shell";
import { useAuth } from "./auth";
import Archive from "./pages/Archive";
import Configure from "./pages/Configure";
import EditQuestions from "./pages/EditQuestions";
import Login from "./pages/Login";
import Preview from "./pages/Preview";
import Upload from "./pages/Upload";

function Protected({ children }) {
  const { user, checking } = useAuth();
  if (checking) return <div className="boot">Loading your workspace…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <Protected>
            <Shell />
          </Protected>
        }
      >
        <Route path="/" element={<Navigate to="/upload" replace />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/configure" element={<Configure />} />
        <Route path="/papers/:paperId/edit" element={<EditQuestions />} />
        <Route path="/papers/:paperId/preview" element={<Preview />} />
        <Route path="/archive" element={<Archive />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
