"""Base interface for xyOps plugins."""
class XYOpsPlugin:
    def __init__(self):
        pass

    def on_load(self):
        """Called when plugin is loaded."""
        pass

    def on_unload(self):
        """Called when plugin is unloaded."""
        pass

    def get_scripts(self):
        """Return dictionary of script names to paths."""
        return {}

    def get_health_status(self):
        """Return plugin health status."""
        return {"status": "unknown"}
