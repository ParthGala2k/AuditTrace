import { useState } from "react";

const MODELS = [
  { id: "openai/gpt-4o",                    label: "GPT-4o (OpenAI)"              },
  { id: "openai/gpt-4o-mini",               label: "GPT-4o mini (OpenAI)"         },
  { id: "deepseek/deepseek-chat",           label: "DeepSeek V3 (Open-source)"    },
  { id: "meta-llama/llama-3.1-70b-instruct", label: "Llama 3.1 70B (Open-source)" },
];

export default function UploadPanel({ onSubmit, loading }) {
  const [pdfFile, setPdfFile] = useState(null);
  const [repoUrl, setRepoUrl] = useState("");
  const [model, setModel] = useState(MODELS[0].id);

  function handleSubmit(e) {
    e.preventDefault();
    if (!pdfFile || !repoUrl) return;
    onSubmit({ pdfFile, repoUrl, model });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-gray-900 rounded-xl p-6 border border-gray-700 max-w-xl"
    >
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Compliance PDF
        </label>
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setPdfFile(e.target.files[0])}
          className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4
                     file:rounded file:border-0 file:bg-indigo-600 file:text-white
                     hover:file:bg-indigo-700 cursor-pointer"
        />
        {pdfFile && (
          <p className="text-xs text-gray-500 mt-1">{pdfFile.name}</p>
        )}
      </div>

      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-300 mb-1">
          GitHub Repository URL
        </label>
        <input
          type="url"
          placeholder="https://github.com/bridgecrewio/terragoat"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2
                     text-gray-100 placeholder-gray-500 focus:outline-none
                     focus:border-indigo-500"
        />
      </div>

      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-300 mb-1">
          LLM Model
        </label>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2
                     text-gray-100 focus:outline-none focus:border-indigo-500"
        >
          {MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </div>

      <button
        type="submit"
        disabled={loading || !pdfFile || !repoUrl}
        className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50
                   text-white font-semibold py-2 px-4 rounded transition"
      >
        {loading ? "Running Audit…" : "Run Compliance Audit"}
      </button>
    </form>
  );
}
