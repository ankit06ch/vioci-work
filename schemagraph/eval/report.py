"""HTML report rendering for the eval harness."""

from __future__ import annotations

from jinja2 import Template

from schemagraph.eval.harness import EvalReport


_TEMPLATE = Template(
    """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>schemagraph eval report</title>
<style>
  body { font: 14px/1.45 -apple-system, system-ui, sans-serif; margin: 2em; color: #222; }
  h1 { margin-bottom: 0; }
  .meta { color: #777; margin-top: 0.3em; }
  table { border-collapse: collapse; margin-top: 1em; }
  th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: right; }
  th { background: #f7f7f7; text-align: left; }
  td.text, th.text { text-align: left; }
  .bar { background: #4caf50; height: 10px; border-radius: 2px; }
  .bar.warn { background: #ff9800; }
  .bar.bad  { background: #e53935; }
  .pct { display: inline-block; min-width: 5em; }
  details summary { cursor: pointer; }
  pre { background: #fafafa; padding: 8px; border-radius: 4px; overflow: auto; }
</style>
</head>
<body>
<h1>schemagraph eval report</h1>
<p class="meta">Provider: <b>{{ summary.provider }}</b>
   &middot; Fixtures: <b>{{ summary.n_fixtures }}</b></p>

<h2>Aggregate metrics</h2>
<table>
  <tr>
    <th class="text">Metric</th>
    <th>Score</th>
    <th>Bar</th>
  </tr>
  {% for name, val in [
      ("Node F1", summary.node_f1),
      ("Node precision", summary.node_precision),
      ("Node recall", summary.node_recall),
      ("Edge F1", summary.edge_f1),
      ("Label accuracy", summary.label_accuracy),
      ("Value accuracy", summary.value_accuracy),
  ] %}
  <tr>
    <td class="text">{{ name }}</td>
    <td>{{ "%.3f"|format(val) }}</td>
    <td style="width: 240px">
      <div class="bar {{ 'bad' if val < 0.5 else ('warn' if val < 0.8 else '') }}"
           style="width: {{ (val * 100)|round(1) }}%"></div>
    </td>
  </tr>
  {% endfor %}
</table>

<h2>Per-fixture results</h2>
<table>
  <tr>
    <th class="text">Fixture</th>
    <th>Nodes (pred / gold / match)</th>
    <th>Edges (pred / gold / match)</th>
    <th>Node F1</th>
    <th>Edge F1</th>
    <th>Label acc.</th>
    <th>Value acc.</th>
  </tr>
  {% for f in fixtures %}
  <tr>
    <td class="text">{{ f.name }}</td>
    <td>{{ f.metrics.nodes_pred }} / {{ f.metrics.nodes_gold }} / {{ f.metrics.nodes_matched }}</td>
    <td>{{ f.metrics.edges_pred }} / {{ f.metrics.edges_gold }} / {{ f.metrics.edges_matched }}</td>
    <td>{{ "%.3f"|format(f.metrics.node_f1) }}</td>
    <td>{{ "%.3f"|format(f.metrics.edge_f1) }}</td>
    <td>{{ "%.3f"|format(f.metrics.label_accuracy) }}</td>
    <td>{{ "%.3f"|format(f.metrics.value_accuracy) }}</td>
  </tr>
  {% if f.notes %}
  <tr><td class="text" colspan="7"><pre>{{ f.notes|join("\\n") }}</pre></td></tr>
  {% endif %}
  {% endfor %}
</table>

</body>
</html>
"""
)


def render_html(report: EvalReport) -> str:
    return _TEMPLATE.render(summary=report.summary(), fixtures=report.fixtures)
