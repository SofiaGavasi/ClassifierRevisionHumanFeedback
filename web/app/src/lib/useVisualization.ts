// Load exact original PI overlays for a committed classifier and suppress stale responses.
import { useEffect, useState } from 'react';
import { api, Classifier } from './api';
import { MapVisualization } from './mapGeometry';

export function useVisualization(classifier: Classifier | null) {
  const [visualization, setVisualization] = useState<MapVisualization | undefined>();
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true; setVisualization(undefined); setError('');
    if (classifier && classifier.nvars <= 6) api.visualization(classifier).then(value => { if (active) setVisualization(value); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [classifier]);
  return { visualization, error };
}
