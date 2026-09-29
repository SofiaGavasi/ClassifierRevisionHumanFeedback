// Omega picker: one toggle per variable. Clicking flips T/F. Only the letter changes; the box stays neutral so nothing implies a "correct" state.
export function OmegaPicker({
  vars, omega, onChange,
}: {
  vars: string[];
  omega: Record<string, boolean>;
  onChange: (next: Record<string, boolean>) => void;
}) {
  const toggle = (v: string) => onChange({ ...omega, [v]: !omega[v] });
  return (
    <div className="omega-toggle-row">
      {vars.map(v => (
        <div key={v} className="omega-toggle" onClick={() => toggle(v)} role="button">
          <span>{v}</span>
          <span className="mono" style={{ color: omega[v] ? 'var(--ok)' : 'var(--danger)' }}>
            {omega[v] ? 'T' : 'F'}
          </span>
        </div>
      ))}
    </div>
  );
}