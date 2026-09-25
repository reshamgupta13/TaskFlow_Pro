import React, { useMemo } from 'react';
import { X, Network, Flame } from 'lucide-react';
import type { Dependency, Task } from '../types';

interface DAGVisualizerModalProps {
  tasks: Task[];
  dependencies: Dependency[];
  criticalPath: string[];
  onClose: () => void;
  onSelectTask: (task: Task) => void;
}

export const DAGVisualizerModal: React.FC<DAGVisualizerModalProps> = ({
  tasks,
  dependencies,
  criticalPath,
  onClose,
  onSelectTask,
}) => {
  // Compute topological layers for clean horizontal SVG layout
  const { nodePositions, width, height, edges } = useMemo(() => {
    // Build adjacency
    const prereqMap: Record<string, string[]> = {};
    const taskMap: Record<string, Task> = {};
    tasks.forEach((t) => {
      prereqMap[t.id] = t.prerequisites;
      taskMap[t.id] = t;
    });

    // Compute layer (longest path from roots)
    const layerMap: Record<string, number> = {};
    const getLayer = (id: string, visited: Set<string>): number => {
      if (layerMap[id] !== undefined) return layerMap[id];
      if (visited.has(id)) return 0;
      visited.add(id);

      const prereqs = prereqMap[id] || [];
      if (prereqs.length === 0) {
        layerMap[id] = 0;
        return 0;
      }
      let maxP = 0;
      prereqs.forEach((p) => {
        maxP = Math.max(maxP, getLayer(p, new Set(visited)) + 1);
      });
      layerMap[id] = maxP;
      return maxP;
    };

    tasks.forEach((t) => getLayer(t.id, new Set()));

    // Group tasks by layer
    const layers: Record<number, string[]> = {};
    Object.entries(layerMap).forEach(([id, l]) => {
      if (!layers[l]) layers[l] = [];
      layers[l].push(id);
    });

    const maxLayer = Math.max(0, ...Object.keys(layers).map(Number));
    const layerSpacingX = 220;
    const nodeSpacingY = 100;
    const paddingX = 70;
    const paddingY = 60;

    let maxNodesInLayer = 1;
    const positions: Record<string, { x: number; y: number; task: Task }> = {};

    Object.entries(layers).forEach(([layerStr, ids]) => {
      const l = Number(layerStr);
      maxNodesInLayer = Math.max(maxNodesInLayer, ids.length);
      ids.forEach((id, idx) => {
        positions[id] = {
          x: paddingX + l * layerSpacingX,
          y: paddingY + idx * nodeSpacingY,
          task: taskMap[id],
        };
      });
    });

    const calculatedWidth = Math.max(800, paddingX * 2 + (maxLayer + 1) * layerSpacingX);
    const calculatedHeight = Math.max(500, paddingY * 2 + maxNodesInLayer * nodeSpacingY);

    // Build edges with coordinates
    const edgeLines = dependencies
      .filter((d) => positions[d.task_id] && positions[d.prerequisite_id])
      .map((d) => {
        const from = positions[d.prerequisite_id];
        const to = positions[d.task_id];
        const isCritical =
          criticalPath.includes(d.task_id) && criticalPath.includes(d.prerequisite_id);
        return {
          id: `${d.prerequisite_id}->${d.task_id}`,
          from,
          to,
          isCritical,
        };
      });

    return {
      nodePositions: positions,
      width: calculatedWidth,
      height: calculatedHeight,
      edges: edgeLines,
    };
  }, [tasks, dependencies, criticalPath]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        style={{ maxWidth: '95vw', width: '1200px', height: '85vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Network size={20} style={{ color: '#818cf8' }} />
            <div>
              <h3 className="modal-title">Interactive DAG Graph Visualizer</h3>
              <p style={{ fontSize: '0.74rem', color: 'var(--text-subtle)' }}>
                Topological levels left-to-right. Critical Path highlighted in luminous gold.
              </p>
            </div>
          </div>
          <button className="card-icon-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', background: '#070a11', padding: '20px' }}>
          <svg
            width={width}
            height={height}
            style={{ minWidth: '100%', minHeight: '100%' }}
          >
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 9 5 L 0 9 z" fill="#64748b" />
              </marker>
              <marker
                id="arrow-critical"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 9 5 L 0 9 z" fill="#f59e0b" />
              </marker>
            </defs>

            {/* Directed Edge lines */}
            {edges.map((e) => {
              const startX = e.from.x + 80;
              const startY = e.from.y;
              const endX = e.to.x - 80;
              const endY = e.to.y;
              const midX = (startX + endX) / 2;

              const pathData = `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`;

              return (
                <path
                  key={e.id}
                  d={pathData}
                  fill="none"
                  stroke={e.isCritical ? '#f59e0b' : '#334155'}
                  strokeWidth={e.isCritical ? 3 : 1.5}
                  strokeDasharray={e.isCritical ? 'none' : '4,2'}
                  markerEnd={e.isCritical ? 'url(#arrow-critical)' : 'url(#arrow)'}
                />
              );
            })}

            {/* Nodes */}
            {Object.entries(nodePositions).map(([id, pos]) => {
              const t = pos.task;
              const isCrit = criticalPath.includes(id);

              return (
                <g
                  key={id}
                  transform={`translate(${pos.x}, ${pos.y})`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => {
                    onSelectTask(t);
                    onClose();
                  }}
                >
                  <rect
                    x={-75}
                    y={-30}
                    width={150}
                    height={60}
                    rx={8}
                    fill={isCrit ? 'rgba(245, 158, 11, 0.15)' : '#1e293b'}
                    stroke={isCrit ? '#f59e0b' : t.is_blocked ? '#f43f5e' : '#10b981'}
                    strokeWidth={isCrit ? 2.5 : 1.5}
                  />

                  {/* ID */}
                  <text
                    x={-68}
                    y={-14}
                    fill="#94a3b8"
                    fontSize="9px"
                    fontFamily="monospace"
                  >
                    {t.id}
                  </text>

                  {/* Status Indicator */}
                  <circle
                    cx={60}
                    cy={-16}
                    r={4}
                    fill={t.is_blocked ? '#f43f5e' : '#10b981'}
                  />

                  {/* Title */}
                  <text
                    x={-68}
                    y={6}
                    fill="#f8fafc"
                    fontSize="11px"
                    fontWeight="600"
                  >
                    {t.title.length > 18 ? `${t.title.substring(0, 16)}...` : t.title}
                  </text>

                  {/* Duration & Column */}
                  <text
                    x={-68}
                    y={21}
                    fill="#64748b"
                    fontSize="9px"
                  >
                    {t.duration_days}d • {t.column}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        <div className="modal-footer" style={{ justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }} />
              Ready
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#f43f5e' }} />
              Blocked
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Flame size={14} style={{ color: '#f59e0b' }} />
              Critical Path
            </span>
          </div>

          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
