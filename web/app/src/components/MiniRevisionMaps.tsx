// Shared original-to-revised compact PI maps for every unary reason and batch plan choice.
import { MapVisualization } from '../lib/mapGeometry';
import { EditableKmap } from './EditableKmap';

export function MiniRevisionMaps({ original, revised, positive = [], negative = [], omega, label = 'Revision choice' }: {
  original?: MapVisualization; revised?: MapVisualization; positive?: string[]; negative?: string[]; omega?: string; label?: string;
}) {
  if (!original || !revised) return null;
  if (!original.available || !revised.available) return <p className="muted">Map previews support 1 to 6 variables. The selected revision still has its truth-table and formula views.</p>;
  return <div className="mini-map-comparison" aria-label={`${label} map comparison`}>
    <div><strong className="mini-map-title">Original</strong><EditableKmap vars={original.vars} accepted={original.accepted} reasons={original.reasons} positive={positive} negative={negative} omega={omega} compact label={`${label} original map`} /></div>
    <span className="map-transition" aria-hidden="true">→</span>
    <div><strong className="mini-map-title">Revised</strong><EditableKmap vars={revised.vars} accepted={original.accepted} revised={revised.accepted} reasons={revised.reasons} positive={positive} negative={negative} omega={omega} compact label={`${label} revised map`} /></div>
  </div>;
}
