import React from 'react';
import './AlgorithmToolbar.css';

const ALGORITHM_OPTIONS = [
  { value: 'peer_review', label: 'Peer Review' },
  { value: 'consensus_only', label: 'Consensus Only' },
  { value: 'chairman_only', label: 'Chairman Only' },
  { value: 'red_team', label: 'Red Team' },
  { value: 'audience_split', label: 'Audience Split' },
  { value: 'claim_evidence', label: 'Claim / Evidence' },
];

const ALGORITHM_HINTS = {
  peer_review: 'Full 3-stage deliberation with anonymized peer review',
  consensus_only: 'Stage 1 + Chairman synthesis, skip peer review',
  chairman_only: 'Chairman answers directly, fastest option',
  red_team: 'Peer review focused on failure modes and risks',
  audience_split: 'Evaluates answers for exec, security, and product audiences',
  claim_evidence: 'Grades evidentiary quality of claims',
};

function AlgorithmToolbar({ algorithm, onChange }) {
  return (
    <div className="algorithm-toolbar">
      <label className="algorithm-label">Algorithm:</label>
      <select
        className="algorithm-select"
        value={algorithm}
        onChange={(e) => onChange(e.target.value)}
      >
        {ALGORITHM_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <span className="algorithm-hint">{ALGORITHM_HINTS[algorithm]}</span>
    </div>
  );
}

export default AlgorithmToolbar;
