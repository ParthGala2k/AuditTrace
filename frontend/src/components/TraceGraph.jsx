import { useEffect, useRef } from "react";
import { Network } from "vis-network";
import { DataSet } from "vis-data";

const CLAUSE_COLOR  = { background: "#ef4444", border: "#b91c1c", highlight: { background: "#f87171", border: "#b91c1c" } };
const CODE_COLOR    = { background: "#3b82f6", border: "#1d4ed8", highlight: { background: "#60a5fa", border: "#1d4ed8" } };

const NETWORK_OPTIONS = {
  nodes: {
    shape: "box",
    font: { color: "#f1f5f9", size: 12, face: "monospace" },
    borderWidth: 2,
    margin: 8,
  },
  edges: {
    arrows: { to: { enabled: true, scaleFactor: 0.8 } },
    color: { color: "#94a3b8", highlight: "#e2e8f0" },
    font: { color: "#94a3b8", size: 10, align: "middle" },
    smooth: { type: "curvedCW", roundness: 0.2 },
  },
  layout: { improvedLayout: true },
  physics: {
    enabled: true,
    barnesHut: { gravitationalConstant: -8000, springLength: 150 },
  },
  interaction: { hover: true, tooltipDelay: 100 },
};

export default function TraceGraph({ data }) {
  const containerRef = useRef(null);
  const networkRef = useRef(null);

  useEffect(() => {
    if (!data || !containerRef.current) return;

    const nodes = new DataSet(
      data.nodes.map((n) => ({
        id: n.id,
        label: n.label || n.id,
        color: n.type === "clause" ? CLAUSE_COLOR : CODE_COLOR,
        title: n.type === "clause" ? `Policy clause: ${n.id}` : `${n.file}:${n.line}`,
      }))
    );

    const edges = new DataSet(
      data.edges.map((e, i) => ({
        id: i,
        from: e.from,
        to: e.to,
        label: e.check_id || "violates",
        title: e.check_id,
      }))
    );

    if (networkRef.current) {
      networkRef.current.destroy();
    }

    networkRef.current = new Network(
      containerRef.current,
      { nodes, edges },
      NETWORK_OPTIONS
    );

    return () => {
      networkRef.current?.destroy();
    };
  }, [data]);

  if (!data) return null;

  const { nodes = [], edges = [] } = data;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-700 p-4">
      <div className="flex gap-6 mb-3 text-xs text-gray-400">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-red-500" /> Policy clause
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-blue-500" /> Code location
        </span>
        <span className="ml-auto">{nodes.length} nodes · {edges.length} violation edges</span>
      </div>
      <div
        ref={containerRef}
        style={{ height: "480px" }}
        className="w-full rounded bg-gray-800"
      />
    </div>
  );
}
