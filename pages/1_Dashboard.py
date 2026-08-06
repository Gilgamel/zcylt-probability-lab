"""Dashboard page."""

from dashboard_view import render_dashboard
from ui import configure_page, page_guard

configure_page("仪表盘")
page_guard(render_dashboard)
