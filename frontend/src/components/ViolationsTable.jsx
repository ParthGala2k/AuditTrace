const SEVERITY_COLOR = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-blue-400",
};

export default function ViolationsTable({ violations = [], summary = {} }) {
  return (
    <div>
      {/* Summary bar */}
      <div className="flex gap-6 mb-4 text-sm">
        <span className="text-gray-400">
          Clauses checked:{" "}
          <strong className="text-gray-100">{summary.clauses_checked ?? "—"}</strong>
        </span>
        <span className="text-gray-400">
          Failing:{" "}
          <strong className="text-red-400">{summary.clauses_failing ?? "—"}</strong>
        </span>
        <span className="text-gray-400">
          Total violations:{" "}
          <strong className="text-orange-400">{summary.total_violations ?? "—"}</strong>
        </span>
      </div>

      {violations.length === 0 ? (
        <p className="text-green-400">No violations found.</p>
      ) : (
        <div className="space-y-4">
          {violations.map((v, i) => (
            <div
              key={i}
              className="bg-gray-900 border border-gray-700 rounded-xl p-4"
            >
              <div className="flex items-center gap-3 mb-2">
                <span className="font-mono text-xs bg-gray-800 px-2 py-0.5 rounded text-indigo-300">
                  {v.clause_id}
                </span>
                <span
                  className={`text-xs font-semibold uppercase ${
                    SEVERITY_COLOR[v.severity] ?? "text-gray-400"
                  }`}
                >
                  {v.severity}
                </span>
              </div>

              <p className="text-sm text-gray-300 mb-2">{v.clause_text}</p>

              <p className="text-xs text-gray-500 mb-3">
                {v.file}:{v.line?.[0]}
              </p>

              {v.suggested_fix && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-sm text-indigo-400 hover:text-indigo-300">
                    View suggested fix (diff)
                  </summary>
                  <pre className="mt-2 text-xs bg-gray-800 rounded p-3 overflow-x-auto text-green-300 whitespace-pre-wrap">
                    {v.suggested_fix}
                  </pre>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
