"""Health checking for xyOps plugin."""
import time

from .plugin_interface import XYOpsPlugin


class SolanaDeFiPlugin(XYOpsPlugin):
    def __init__(self):
        super().__init__()
        self._start_time = time.time()
        self._last_analytics_run = None
        self._last_trade_run = None
        self._error_count = 0

    def on_load(self):
        """Initialize plugin on load."""
        self._start_time = time.time()
        return {"status": "healthy", "message": "Plugin loaded"}

    def get_health_status(self):
        """Return current health status."""
        uptime = time.time() - self._start_time
        if self._error_count > 5:
            status = "unhealthy"
        elif self._error_count > 0:
            status = "degraded"
        else:
            status = "healthy"
        return {
            "status": status,
            "uptime_seconds": uptime,
            "last_analytics_run": self._last_analytics_run,
            "last_trade_run": self._last_trade_run,
            "error_count": self._error_count,
            "version": "1.0.0"
        }

    def analytics_completed(self):
        """Called when analytics task completes successfully."""
        import time
        self._last_analytics_run = time.time()

    def analytics_failed(self):
        """Called when analytics task fails."""
        import time
        self._error_count += 1
        self._last_analytics_run = time.time()

    def trade_completed(self):
        """Called when trade task completes successfully."""
        import time
        self._last_trade_run = time.time()

    def trade_failed(self):
        """Called when trade task fails."""
        import time
        self._error_count += 1
        self._last_trade_run = time.time()
