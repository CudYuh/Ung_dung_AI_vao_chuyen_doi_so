import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

const NODE_COLORS = {
  root: "#60a5fa",
  group: "#94a3b8",
  document: "#a78bfa",
  topic: "#38bdf8",
  situation: "#34d399",
  missing: "#f87171",
};

const NODE_LABELS = {
  root: "Trung tâm",
  group: "Nhóm tri thức",
  document: "Văn bản pháp lý",
  topic: "Chủ đề nghiệp vụ",
  situation: "Tình huống",
  missing: "Thiếu file",
};

function getEdgeKey(source, target) {
  const a = String(source);
  const b = String(target);
  return [a, b].sort().join("__");
}

function dedupeEdges(edges) {
  const seen = new Set();
  const result = [];

  edges.forEach((edge) => {
    const key = getEdgeKey(edge.source, edge.target);

    if (seen.has(key)) return;

    seen.add(key);
    result.push(edge);
  });

  return result;
}

function ObsidianLegalGraph({ graph, height = 760 }) {
  const wrapperRef = useRef(null);
  const graphRef = useRef(null);

  const [width, setWidth] = useState(1100);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [onlyRelated, setOnlyRelated] = useState(false);

  const rawNodes = graph?.nodes || [];

  // Chỉ giữ 1 đường nối giữa 2 node, dù Obsidian có nhiều link trùng / link 2 chiều.
  const rawEdges = useMemo(() => {
    return dedupeEdges(graph?.edges || []);
  }, [graph]);

  const rootNode =
    rawNodes.find((node) => node.id === graph?.root_id) ||
    rawNodes.find((node) => node.type === "root") ||
    rawNodes[0];

  const selectedNode =
    rawNodes.find((node) => node.id === selectedNodeId) || rootNode;

  const getNode = (id) => rawNodes.find((node) => node.id === id);

  useEffect(() => {
    if (!selectedNodeId && rootNode?.id) {
      setSelectedNodeId(rootNode.id);
    }
  }, [rootNode, selectedNodeId]);

  useEffect(() => {
    if (!wrapperRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      const nextWidth = Math.floor(entry.contentRect.width);

      if (nextWidth > 400) {
        setWidth(nextWidth);
      }
    });

    resizeObserver.observe(wrapperRef.current);

    return () => resizeObserver.disconnect();
  }, []);

  const relatedNodeIds = useMemo(() => {
    const ids = new Set();

    if (!selectedNode) return ids;

    ids.add(selectedNode.id);

    rawEdges.forEach((edge) => {
      if (edge.source === selectedNode.id) {
        ids.add(edge.target);
      }

      if (edge.target === selectedNode.id) {
        ids.add(edge.source);
      }
    });

    return ids;
  }, [rawEdges, selectedNode]);

  const relatedEdges = useMemo(() => {
    if (!selectedNode) return [];

    const directEdges = rawEdges.filter(
      (edge) =>
        edge.source === selectedNode.id || edge.target === selectedNode.id,
    );

    return dedupeEdges(directEdges);
  }, [rawEdges, selectedNode]);

  const highlightedLinkKeys = useMemo(() => {
    const keys = new Set();

    relatedEdges.forEach((edge) => {
      keys.add(getEdgeKey(edge.source, edge.target));
    });

    return keys;
  }, [relatedEdges]);

  const graphData = useMemo(() => {
    let nodes = rawNodes;

    if (onlyRelated && selectedNode) {
      nodes = rawNodes.filter((node) => relatedNodeIds.has(node.id));
    }

    const visibleIds = new Set(nodes.map((node) => node.id));

    const links = rawEdges
      .filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
      .map((edge) => ({
        source: edge.source,
        target: edge.target,
        label: edge.label || "liên kết",
      }));

    return {
      nodes: nodes.map((node) => ({
        ...node,
        val:
          node.type === "root"
            ? 11
            : node.type === "group"
              ? 8
              : node.type === "document"
                ? 7
                : 6,
      })),
      links: dedupeEdges(links),
    };
  }, [rawNodes, rawEdges, onlyRelated, selectedNode, relatedNodeIds]);

  useEffect(() => {
    if (!graphRef.current) return;

    graphRef.current.d3Force("charge")?.strength(-260);
    graphRef.current.d3Force("link")?.distance(125);
    graphRef.current.d3Force("center")?.strength(0.08);
    graphRef.current.zoom(1.25, 600);
  }, [graphData]);

  const nodeRadius = (node) => {
    if (node.type === "root") return 9;
    if (node.type === "group") return 7.5;
    if (node.type === "document") return 7;
    if (node.type === "topic") return 6.5;
    if (node.type === "situation") return 6.5;
    return 6;
  };

  const isNodeHighlighted = (node) => {
    if (!selectedNode) return true;
    return relatedNodeIds.has(node.id);
  };

  const getLinkIds = (link) => {
    const sourceId =
      typeof link.source === "object" ? link.source.id : link.source;

    const targetId =
      typeof link.target === "object" ? link.target.id : link.target;

    return { sourceId, targetId };
  };

  const isLinkHighlighted = (link) => {
    const { sourceId, targetId } = getLinkIds(link);
    return highlightedLinkKeys.has(getEdgeKey(sourceId, targetId));
  };

  const handleNodeClick = (node) => {
    setSelectedNodeId(node.id);

    if (
      graphRef.current &&
      typeof node.x === "number" &&
      typeof node.y === "number"
    ) {
      graphRef.current.centerAt(node.x, node.y, 650);
      graphRef.current.zoom(2.1, 650);
    }
  };

  const formatNodeContent = (node) => {
    if (!node) return "Chưa chọn node.";

    return node.content || node.summary || "Node này chưa có nội dung.";
  };

  if (!graph) {
    return (
      <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 text-slate-400">
        Đang tải sơ đồ tri thức...
      </div>
    );
  }

  return (
    <div className="rounded-3xl border border-violet-500/20 bg-slate-900/80 overflow-hidden shadow-2xl shadow-violet-500/10">
      <div className="p-6 border-b border-slate-800">
        <h3 className="text-2xl font-bold text-white mb-2">
          Sơ đồ tri thức pháp lý
        </h3>

        <p className="text-slate-500 text-sm">
          Sơ đồ mô phỏng graph từ Obsidian. Mỗi file Markdown là một node, mỗi liên kết là một đường nối.
        </p>
      </div>

      <div className="p-6 space-y-5">
        <div className="flex flex-col xl:flex-row gap-3 xl:items-center justify-between">
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full border border-blue-500/20 bg-blue-500/10 px-3 py-1.5 text-xs text-blue-300">
              Trung tâm
            </span>

            <span className="rounded-full border border-slate-500/20 bg-slate-500/10 px-3 py-1.5 text-xs text-slate-300">
              Nhóm tri thức
            </span>

            <span className="rounded-full border border-violet-500/20 bg-violet-500/10 px-3 py-1.5 text-xs text-violet-300">
              Văn bản pháp lý
            </span>

            <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-300">
              Chủ đề nghiệp vụ
            </span>

            <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-300">
              Tình huống
            </span>
          </div>

          <button
            type="button"
            onClick={() => setOnlyRelated((current) => !current)}
            className={`rounded-xl px-4 py-2.5 text-sm font-bold border transition-colors ${
              onlyRelated
                ? "bg-violet-600 border-violet-500 text-white"
                : "bg-slate-950 border-slate-800 text-slate-300 hover:border-violet-500/50"
            }`}
          >
            {onlyRelated ? "Đang chỉ xem node liên quan" : "Chỉ xem node liên quan"}
          </button>
        </div>

        <div
          ref={wrapperRef}
          className="rounded-3xl border border-slate-800 bg-slate-950 overflow-hidden"
        >
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            width={width}
            height={height}
            backgroundColor="#020617"
            cooldownTicks={140}
            d3VelocityDecay={0.32}
            nodeRelSize={5}
            linkCurvature={0.03}
            linkDirectionalArrowLength={0}
            linkDirectionalArrowRelPos={1}
            linkColor={(link) =>
              isLinkHighlighted(link)
                ? "rgba(167,139,250,0.95)"
                : "rgba(148,163,184,0.22)"
            }
            linkWidth={(link) => (isLinkHighlighted(link) ? 2.2 : 0.7)}
            linkDirectionalParticles={0}
            nodeLabel={(node) =>
              `${node.label}\n${NODE_LABELS[node.type] || node.type}`
            }
            onNodeClick={handleNodeClick}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const highlighted = isNodeHighlighted(node);
              const selected = selectedNode?.id === node.id;
              const radius = nodeRadius(node);
              const color = NODE_COLORS[node.type] || "#94a3b8";

              ctx.save();

              ctx.globalAlpha = selectedNode ? (highlighted ? 1 : 0.22) : 1;

              if (selected) {
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius + 9, 0, 2 * Math.PI, false);
                ctx.fillStyle = "rgba(167,139,250,0.25)";
                ctx.fill();
              }

              ctx.beginPath();
              ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
              ctx.fillStyle = color;
              ctx.fill();

              ctx.lineWidth = selected ? 2.8 : 1.2;
              ctx.strokeStyle = selected ? "#ffffff" : "rgba(255,255,255,0.6)";
              ctx.stroke();

              const label = node.label || "";
              const fontSize = Math.max(8, selected ? 13 / globalScale : 11 / globalScale);

              ctx.font = `${selected ? 800 : 650} ${fontSize}px Sans-Serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillStyle = selected
                ? "#ffffff"
                : highlighted
                  ? "#e5e7eb"
                  : "#94a3b8";

              const maxLength = selected ? 36 : 27;
              const shortLabel =
                label.length > maxLength
                  ? `${label.slice(0, maxLength - 3)}...`
                  : label;

              ctx.fillText(shortLabel, node.x, node.y + radius + 5);

              ctx.restore();
            }}
          />
        </div>

        <div className="rounded-3xl border border-violet-500/20 bg-slate-950/70 overflow-hidden">
          <div className="p-5 border-b border-slate-800">
            <div className="text-xs uppercase tracking-wider text-violet-300 font-bold mb-2">
              Giải thích node đang chọn
            </div>

            <h4 className="text-2xl font-bold text-white">
              {selectedNode?.label || "Chưa chọn node"}
            </h4>

            {selectedNode && (
              <p className="text-sm text-slate-500 mt-1">
                {NODE_LABELS[selectedNode.type] || selectedNode.type}
                {selectedNode.file_name ? ` • ${selectedNode.file_name}` : ""}
              </p>
            )}
          </div>

          <div className="p-5 space-y-5">
            <div>
              <h5 className="text-emerald-300 font-bold mb-2">
                Nội dung đầy đủ
              </h5>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
                <pre className="whitespace-pre-wrap text-sm text-slate-300 leading-7 font-sans">
                  {formatNodeContent(selectedNode)}
                </pre>
              </div>
            </div>

            <div>
              <h5 className="text-blue-300 font-bold mb-3">
                Node liên kết trực tiếp
              </h5>

              {relatedEdges.length === 0 ? (
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 text-slate-500">
                  Node này chưa có liên kết trực tiếp.
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {relatedEdges.map((edge, index) => {
                    const source = getNode(edge.source);
                    const target = getNode(edge.target);

                    const otherNode =
                      edge.source === selectedNode?.id ? target : source;

                    return (
                      <button
                        key={`${edge.source}-${edge.target}-${index}`}
                        type="button"
                        onClick={() => otherNode && setSelectedNodeId(otherNode.id)}
                        className="rounded-full border border-slate-700 bg-slate-900 hover:bg-violet-500/10 hover:border-violet-500/40 px-3 py-2 text-sm text-slate-300 transition-colors"
                      >
                        {otherNode?.label || "Node liên quan"}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-amber-500/10 bg-amber-500/5 p-4 text-sm text-slate-400">
              Phần này chỉ thuộc module Kho tri thức pháp lý, không ảnh hưởng đến module Định giá.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ObsidianLegalGraph;