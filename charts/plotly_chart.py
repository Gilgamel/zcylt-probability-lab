"""Reusable Plotly chart factories."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def empty_chart(message: str = "暂无数据") -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(text=message, showarrow=False, font={"size": 18})
    figure.update_layout(height=340, xaxis={"visible": False}, yaxis={"visible": False})
    return figure


def bar(frame: pd.DataFrame, x: str, y: str, title: str, color: str | None = None) -> go.Figure:
    if frame.empty:
        return empty_chart()
    return px.bar(frame, x=x, y=y, color=color, title=title, text_auto=".3s")


def line(frame: pd.DataFrame, x: str, y: str, title: str, color: str | None = None) -> go.Figure:
    if frame.empty:
        return empty_chart()
    return px.line(frame, x=x, y=y, color=color, title=title, markers=True)


def faceted_line(
    frame: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    facet: str,
) -> go.Figure:
    """Render one aligned panel per category so equal series cannot overlap."""
    if frame.empty:
        return empty_chart()
    figure = px.line(
        frame,
        x=x,
        y=y,
        facet_col=facet,
        facet_col_wrap=3,
        title=title,
        markers=True,
        labels={x: "日期", y: "累计尝试次数", facet: "分类"},
    )
    figure.for_each_annotation(
        lambda annotation: annotation.update(text=annotation.text.split("=")[-1])
    )
    figure.update_layout(showlegend=False, height=430)
    return figure


def histogram(values: object, title: str, x_label: str = "红色数量") -> go.Figure:
    return px.histogram(x=values, title=title, labels={"x": x_label, "y": "频数"})


def scatter(
    frame: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    color: str | None = None,
) -> go.Figure:
    """Create a scatter chart or a standard empty state."""
    if frame.empty:
        return empty_chart()
    return px.scatter(frame, x=x, y=y, color=color, title=title)


def box(
    frame: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    color: str | None = None,
) -> go.Figure:
    """Create a box plot or a standard empty state."""
    if frame.empty:
        return empty_chart()
    return px.box(frame, x=x, y=y, color=color, title=title, points="all")


def heatmap(
    values: object,
    x_labels: object,
    y_labels: object,
    title: str,
) -> go.Figure:
    """Create an annotated heatmap."""
    return px.imshow(
        values, x=x_labels, y=y_labels, text_auto=True, aspect="auto", title=title
    )


def apply_theme(figure: go.Figure, theme: str = "dark") -> go.Figure:
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    figure.update_layout(template=template, margin={"l": 20, "r": 20, "t": 55, "b": 20})
    return figure
