import { Tex, TexInline } from '../lib/latex';
import { TraceStep } from '../lib/api';
import { MuBlock } from './MuBlock';

export function StepView({ step, onPickReason, dOriginalDot }: {
  step: TraceStep;
  onPickReason?: (assignment: Record<string, boolean>) => void;
  dOriginalDot?: string;
}) {
  return (
    <div className="step">
      <h3>{prettyName(step.name)}</h3>
      <p className="muted"><TexInline text={step.description} /></p>
      <StepBody step={step} onPickReason={onPickReason} dOriginalDot={dOriginalDot} />
    </div>
  );
}

function prettyName(n: string): string {
  return ({
    input: 'Input',
    accepted: 'Already accepted',
    distance: 'Distance to the nearest accepted instance',
    nearest_models: 'Nearest models',
    per_model_enumeration: 'Enumerate reasons for each nearest model',
    reasons: 'Minimal sufficient reasons',
  } as Record<string, string>)[n] ?? n;
}

function StepBody({ step, onPickReason, dOriginalDot }: {
  step: TraceStep;
  onPickReason?: (assignment: Record<string, boolean>) => void;
  dOriginalDot?: string;
}) {
  const d = step.data;
  switch (step.name) {
    case 'input':
      return (
        <div className="kv">
          <span className="k">classifier</span>
          <span><Tex src={d.clauses_latex} /></span>
          <span className="k">ω</span>
          <span><Tex src={d.omega_latex} /></span>
          <span className="k">accepted?</span>
          <span className={d.rejected ? 'err' : 'ok'}>{d.rejected ? 'no -> needs revision' : 'yes'}</span>
        </div>
      );

    case 'accepted': return null;

    case 'distance':
      return <div className="kv"><span className="k"><Tex src="d^\star" /></span><span>{d.d_star}</span></div>;

    case 'nearest_models':
      return (
        <>
          <div className="muted">{d.count} model{d.count === 1 ? '' : 's'}.</div>
          {d.models.map((m: any, i: number) => (
            <div key={i} style={{ marginTop: 4 }}>
              <span className="mono">μ<sub>{i}</sub></span>{' = '}<Tex src={m.latex} />
            </div>
          ))}
        </>
      );

    case 'per_model_enumeration':
      return <>{d.per_model.map((b: any, i: number) => (
        <MuBlock key={i} idx={i} block={b} dOriginalDotFallback={dOriginalDot} /> // we call each mu block
      ))}</>;

    case 'reasons':
      return (
        <>
          {d.reasons.length === 0 && <p className="err">No reasons produced.</p>}
          {d.reasons.map((r: any) => (
            <div key={r.index} className="reason-card">
              <div><Tex src={r.latex} /></div>
              {onPickReason && (
                <button className="small" onClick={() => onPickReason(r.assignment)}>choose this reason</button>
              )}
            </div>
          ))}
        </>
      );

    default: return <pre className="mono">{JSON.stringify(d, null, 2)}</pre>;
  }
}