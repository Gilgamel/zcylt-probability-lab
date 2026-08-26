"""Plotly-only visualization factory tests."""

import pandas as pd

from charts.plotly_chart import apply_theme, bar, box, faceted_line, heatmap, line, scatter


def test_all_required_plotly_chart_types_render() -> None:
    frame = pd.DataFrame({"x": [1, 2, 3], "y": [2, 1, 3], "group": ["a", "a", "b"]})
    figures = [
        line(frame, "x", "y", "line", "group"),
        faceted_line(frame, "x", "y", "faceted", "group"),
        bar(frame, "x", "y", "bar", "group"),
        scatter(frame, "x", "y", "scatter", "group"),
        box(frame, "group", "y", "box", "group"),
        heatmap([[1, 2], [3, 4]], ["a", "b"], ["c", "d"], "heatmap"),
    ]
    assert all(figure.data for figure in figures)
    assert apply_theme(figures[0], "dark").layout.template.layout.paper_bgcolor


def test_faceted_line_keeps_equal_category_series_visible() -> None:
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2026-08-24", "2026-08-25"] * 2),
        "sample_growth": [40, 48, 40, 48],
        "category": ["灵禽院", "灵禽院", "马厩", "马厩"],
    })
    figure = faceted_line(
        frame, "date", "sample_growth", "各分类累计尝试次数", "category"
    )
    assert len(figure.data) == 2
    assert {annotation.text for annotation in figure.layout.annotations} == {
        "灵禽院", "马厩"
    }
