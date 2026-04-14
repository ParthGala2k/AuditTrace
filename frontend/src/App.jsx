import { useState } from "react";
import UploadPanel from "./components/UploadPanel";
import TraceGraph from "./components/TraceGraph";
import ViolationsTable from "./components/ViolationsTable";

export default function App() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleAudit({ pdfFile, repoUrl }) {
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("pdf", pdfFile);
      form.append("repo_url", repoUrl);

      const res = await fetch("http://localhost:8000/audit", {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      setReport(await res.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <header className="mb-10">
        <h1 className="text-3xl font-bold text-indigo-400">AuditTrace</h1>
        <p className="text-gray-400 mt-1">
          Autonomous compliance auditing — from policy PDF to Fix-PR
        </p>
      </header>

      <UploadPanel onSubmit={handleAudit} loading={loading} />

      {error && (
        <div className="mt-6 p-4 bg-red-900/40 border border-red-500 rounded text-red-300">
          {error}
        </div>
      )}

      {report && (
        <>
          <section className="mt-10">
            <h2 className="text-xl font-semibold mb-4 text-indigo-300">
              Compliance Trace Graph
            </h2>
            <TraceGraph data={report.compliance_trace} />
          </section>

          <section className="mt-10">
            <h2 className="text-xl font-semibold mb-4 text-indigo-300">
              Violations &amp; Suggested Fixes
            </h2>
            <ViolationsTable violations={report.violations} summary={report.summary} />
          </section>
        </>
      )}
    </div>
  );
}
