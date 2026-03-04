import './ExportButton.css';

export default function ExportButton({ message, query }) {
  if (!message) return null;

  function handleExport() {
    const now = new Date();
    const pad = (n, len = 2) => String(n).padStart(len, '0');
    const timestamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}`;
    const filenameTimestamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;

    const { stage1, stage2, stage3, metadata } = message;
    const lines = [];

    lines.push(`# Council Run — ${timestamp}`);
    lines.push('');
    lines.push(`**Query:** ${query}`);
    lines.push('');
    if (metadata && metadata.algorithm) {
      lines.push(`**Algorithm:** ${metadata.algorithm}`);
      lines.push('');
    }
    lines.push('---');
    lines.push('');

    // Stage 1
    if (stage1 && stage1.length > 0) {
      lines.push('## Stage 1: Individual Responses');
      lines.push('');
      for (const resp of stage1) {
        const modelName = resp.model.split('/')[1] || resp.model;
        lines.push(`### ${modelName}`);
        lines.push('');
        lines.push(resp.response);
        lines.push('');
      }
      lines.push('---');
      lines.push('');
    }

    // Stage 2
    if (stage2 && stage2.length > 0) {
      const aggregateRankings = metadata && metadata.aggregate_rankings ? metadata.aggregate_rankings : null;

      lines.push('## Stage 2: Peer Evaluations');
      lines.push('');
      for (const rank of stage2) {
        const modelName = rank.model.split('/')[1] || rank.model;
        lines.push(`### Evaluator: ${modelName}`);
        lines.push('');
        lines.push(rank.ranking);
        lines.push('');
        if (rank.parsed_ranking && rank.parsed_ranking.length > 0) {
          const rankingStr = rank.parsed_ranking.join(' > ');
          lines.push(`**Extracted ranking:** ${rankingStr}`);
          lines.push('');
        }
      }

      if (aggregateRankings && aggregateRankings.length > 0) {
        lines.push('### Aggregate Rankings');
        lines.push('');
        lines.push('| Rank | Model | Score | Votes |');
        lines.push('|------|-------|-------|-------|');
        aggregateRankings.forEach((agg, index) => {
          const modelName = agg.model.split('/')[1] || agg.model;
          let score = 'N/A';
          if (typeof agg.average_rank === 'number') {
            score = `Avg: ${agg.average_rank.toFixed(2)}`;
          } else if (typeof agg.borda_points === 'number') {
            score = `Borda: ${agg.borda_points}`;
          }
          lines.push(`| ${index + 1} | ${modelName} | ${score} | ${agg.rankings_count} |`);
        });
        lines.push('');
      }

      lines.push('---');
      lines.push('');
    }

    // Stage 3
    if (stage3) {
      lines.push('## Stage 3: Final Answer');
      lines.push('');
      const chairmanName = stage3.model.split('/')[1] || stage3.model;
      lines.push(`**Chairman:** ${chairmanName}`);
      lines.push('');
      lines.push(stage3.response);
      lines.push('');
    }

    const markdown = lines.join('\n');
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `council-run-${filenameTimestamp}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <button className="export-button" onClick={handleExport}>
      &#8615; Export .md
    </button>
  );
}
