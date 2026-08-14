"""Plotly-only visualization factory tests."""

import pandas as pd

from charts.plotly_chart import apply_theme, bar, box, heatmap, line, scatter


def test_all_required_plotly_chart_types_render() -> None:
    frame = pd.DataFrame({"x": [1, 2, 3], "y": [2, 1, 3], "group": ["a", "a", "b"]})
    figures = [
        line(frame, "x", "y", "line", "group"),
        bar(frame, "x", "y", "bar", "group"),
        scatter(frame, "x", "y", "scatter", "group"),
        box(frame, "group", "y", "box", "group"),
        heatmap([[1, 2], [3, 4]], ["a", "b"], ["c", "d"], "heatmap"),
    ]
    assert all(figure.data for figure in figures)
    assert apply_theme(figures[0], "dark").layout.template.layout.paper_bgcolor
