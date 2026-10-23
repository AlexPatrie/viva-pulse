"""Shared pieces for the study figures: palette tokens, layout, HTML wrapper."""

import html
import json

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.27.0.min.js"

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
# Categorical slots 1-3 (validated all-pairs) and a 5-step ordinal blue ramp
# (steps 250-650, validated with --ordinal).
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a"]
ORDINAL_BLUE = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]


def _numeric(series):
    return bool(series) and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                for v in series)


def missing_runs(state, ports):
    """An error figure when a port has no runs, the ports disagree on the run count, or a
    run's series is not numbers. A mistyped nested path resolves to one None per tick."""
    counts = {port: len(state.get(port) or []) for port in ports}
    bad = sorted(port for port in ports if not all(_numeric(run) for run in state.get(port) or []))
    if min(counts.values()) == 0 or len(set(counts.values())) > 1 or bad:
        return {"html": ('<p style="color:#991b1b">Missing or non-numeric run data: '
                         f'{html.escape(json.dumps({"runs": counts, "non_numeric": bad}))}. '
                         'Check the readouts and inputs_map.</p>')}
    return None


def axis(title, **extra):
    return {"title": {"text": title, "font": {"color": TEXT_SECONDARY, "size": 12}},
            "gridcolor": GRID, "linecolor": AXIS, "zeroline": False,
            "tickfont": {"color": MUTED, "size": 11}, **extra}


def layout(title, **extra):
    return {
        "title": {"text": html.escape(title), "font": {"size": 15, "color": TEXT}, "x": 0.01},
        "paper_bgcolor": SURFACE, "plot_bgcolor": SURFACE,
        "font": {"family": "system-ui, -apple-system, Segoe UI, sans-serif", "color": TEXT},
        "hovermode": "closest", "margin": {"l": 60, "r": 20, "t": 60, "b": 60},
        **extra,
    }


def render(element_id, traces, figure_layout, height, caption):
    """The figure plus its caption as a paragraph below it (never overlapping the axes)."""
    return {"html": (
        f'<div id="{element_id}" style="height:{height}px"></div>'
        f'<p style="margin:6px 0 0 8px;font:12px system-ui,sans-serif;color:{TEXT_SECONDARY}">'
        f'{html.escape(caption)}</p>'
        f'<script src="{PLOTLY_CDN}"></script>'
        f'<script>Plotly.newPlot("{element_id}",{json.dumps(traces)},'
        f'{json.dumps(figure_layout)},{{responsive:true,displaylogo:false}});</script>'
    )}
