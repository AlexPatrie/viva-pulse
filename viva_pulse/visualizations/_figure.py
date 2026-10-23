"""Shared pieces for the study figures: palette tokens, run labels, HTML wrapper."""

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


def missing_runs(state, ports):
    """An error figure when a port has no runs or the ports disagree on the run count."""
    counts = {port: len(state.get(port) or []) for port in ports}
    if min(counts.values()) == 0 or len(set(counts.values())) > 1:
        return {"html": ('<p style="color:#991b1b">Missing or mismatched run data: '
                         f'{html.escape(json.dumps(counts))}. Check the readouts and inputs_map.</p>')}
    return None


def axis(title, **extra):
    return {"title": {"text": title, "font": {"color": TEXT_SECONDARY, "size": 12}},
            "gridcolor": GRID, "linecolor": AXIS, "zeroline": False,
            "tickfont": {"color": MUTED, "size": 11}, **extra}


def layout(title, caption, **extra):
    return {
        "title": {"text": html.escape(title), "font": {"size": 15, "color": TEXT}, "x": 0.01},
        "paper_bgcolor": SURFACE, "plot_bgcolor": SURFACE,
        "font": {"family": "system-ui, -apple-system, Segoe UI, sans-serif", "color": TEXT},
        "hovermode": "closest", "margin": {"l": 60, "r": 20, "t": 60, "b": 70},
        "annotations": [{"text": html.escape(caption), "xref": "paper", "yref": "paper",
                         "x": 0, "y": -0.12, "xanchor": "left", "yanchor": "top",
                         "showarrow": False, "font": {"size": 11, "color": TEXT_SECONDARY}}],
        **extra,
    }


def render(element_id, traces, figure_layout, height):
    return {"html": (
        f'<div id="{element_id}" style="height:{height}px"></div>'
        f'<script src="{PLOTLY_CDN}"></script>'
        f'<script>Plotly.newPlot("{element_id}",{json.dumps(traces)},'
        f'{json.dumps(figure_layout)},{{responsive:true,displaylogo:false}});</script>'
    )}
