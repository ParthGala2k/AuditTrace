/**
 * TraceGraph
 * Renders the compliance trace as an interactive graph using vis-network.
 * Nodes = policy clauses (red) or code locations (blue).
 * Edges = "violates" relationships.
 *
 * TODO: replace placeholder div with actual vis-network or D3 render.
 */
import { useEffect, useRef } from "react";

export default function TraceGraph({ data }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!data || !containerRef.current) return;
    // TODO: initialize vis.Network with data.nodes and data.edges
    // import { Network } from "vis-network";
    // const network = new Network(containerRef.current, data, options);
  }, [data]);

  if (!data) return null;

  const { nodes = [], edges = [] } = data;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-700 p-4">
      {/* Placeholder stats until vis-network is wired in */}
      <div className="flex gap-6 mb-4 text-sm text-gray-400">
        <span>{nodes.length} nodes</span>
        <span>{edges.length} violation edges</span>
      </div>

      {/* Graph canvas — vis-network will mount here */}
      <div
        ref={containerRef}
        className="w-full h-96 rounded bg-gray-800 flex items-center justify-center text-gray-500"
      >
        Graph visualization coming soon (vis-network)
      </div>
    </div>
  );
}
