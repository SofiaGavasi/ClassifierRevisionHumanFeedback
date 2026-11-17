// Framework entry point, with independent unary and batch workspaces.
import { useState } from 'react';
import { UnaryWorkspace } from './UnaryWorkspace';
import { BatchWorkspace } from './BatchWorkspace';

export default function App() {
  const [framework, setFramework] = useState<'unary' | 'batch' | null>(null);
  return <main className="app">
    <header className="workbench-header"><div className="eyebrow">Boolean classifier revision</div>
      <h1></h1>
      <p className="subtitle"></p>
    </header>
    <nav className="framework-picker" aria-label="Revision framework">
      <button className={`framework-card ${framework === 'unary' ? 'selected' : ''}`} aria-pressed={framework === 'unary'} onClick={() => setFramework('unary')}>
        <span className="framework-icon">1</span><span><strong>Unary revision</strong><small>One instance, one positive correction.<br /></small></span><span aria-hidden="true">→</span>
      </button>
      <button className={`framework-card ${framework === 'batch' ? 'selected' : ''}`} aria-pressed={framework === 'batch'} onClick={() => setFramework('batch')}>
        <span className="framework-icon">1+</span><span><strong>Batch revision</strong><small>Positive and negative feedback together.<br /></small></span><span aria-hidden="true">→</span>
      </button>
    </nav>
    {!framework && <div className="welcome-note"></div>}
    {framework === 'unary' && <UnaryWorkspace />}
    {framework === 'batch' && <BatchWorkspace />}
    
  </main>;
}
