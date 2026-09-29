// SDD renderer: takes a Graphviz DOT string and renders it inline using d3-graphviz. The full DAG view is the default; a simplified summary is provided as a toggle
import { useEffect, useRef, useState } from 'react';
// @ts-ignore  d3-graphviz has no bundled types
import { graphviz } from 'd3-graphviz';

export function SDDView({ dot, sizeHint }: { dot: string; sizeHint?: number }) {
  const [mode, setMode] = useState<'full' | 'summary'>('full');
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (mode !== 'full' || !container.current) return;
    container.current.innerHTML = '';
    try {
      graphviz(container.current)
        .zoom(true)
        .fit(true)
        .renderDot(dot);
    } catch (e) {
      if (container.current) container.current.textContent = String(e);
    }
  }, [dot, mode]);

  return (
    <div>
      <div className="row" style={{ marginBottom: 6 }}>
        <div className="tabs">
          <button
            className={'tab ' + (mode === 'full' ? 'active' : '')}
            onClick={() => setMode('full')}
          >
            full DAG
          </button>
          <button
            className={'tab ' + (mode === 'summary' ? 'active' : '')}
            onClick={() => setMode('summary')}
          >
            summary
          </button>
        </div>
      </div>
      {mode === 'full' ? (
        <div className="sdd-wrap" ref={container} />
      ) : (
        <div className="panel">
          <div className="kv">
            <span className="k">nodes (size)</span>
            <span>{sizeHint ?? '—'}</span>
            <span className="k">note</span>
            <span className="muted">
              The full DAG is the faithful view.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
