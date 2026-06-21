export interface HarnessSummaryProps {
  summary: Record<string, number>;
}

export function HarnessSummary({ summary }: HarnessSummaryProps) {
  if (!summary || Object.keys(summary).length === 0) {
    return null;
  }

  const supported = summary.supported || 0;
  const weak = summary.weak || 0;
  const unverified = summary.unverified || 0;
  const numericTraceMissing = summary.numeric_trace_missing || 0;
  const conflictDetected = summary.conflict_detected || 0;

  const total = supported + weak + unverified + numericTraceMissing + conflictDetected;

  return (
    <div className="border border-line rounded-lg p-4 bg-panel">
      <h2 className="text-lg font-semibold text-ink mb-4">
        Verification Summary ({total} claims)
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="text-center p-3 rounded-lg bg-green-50 border border-green-200">
          <div className="text-2xl font-bold text-green-600">{supported}</div>
          <div className="text-sm text-muted mt-1">Supported</div>
        </div>

        <div className="text-center p-3 rounded-lg bg-yellow-50 border border-yellow-200">
          <div className="text-2xl font-bold text-yellow-600">{weak}</div>
          <div className="text-sm text-muted mt-1">Weak</div>
        </div>

        <div className="text-center p-3 rounded-lg bg-gray-50 border border-gray-200">
          <div className="text-2xl font-bold text-gray-600">{unverified}</div>
          <div className="text-sm text-muted mt-1">Unverified</div>
        </div>

        <div className="text-center p-3 rounded-lg bg-orange-50 border border-orange-200">
          <div className="text-2xl font-bold text-orange-600">{numericTraceMissing}</div>
          <div className="text-sm text-muted mt-1">Numeric Missing</div>
        </div>

        <div className="text-center p-3 rounded-lg bg-red-50 border border-red-200">
          <div className="text-2xl font-bold text-red-600">{conflictDetected}</div>
          <div className="text-sm text-muted mt-1">Conflict</div>
        </div>
      </div>
    </div>
  );
}
