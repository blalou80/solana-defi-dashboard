"""Trade Template manager for saving and reusing trade configurations."""

import os
from typing import Dict, List, Optional

import yaml

from ..models.trade_request import TradeRequest
from ..utils.error_handling import DeFiAnalyticsError

TEMPLATE_FILE = os.path.expanduser("~/.defi_tool/trade_templates.yaml")


class TradeTemplateManager:
    """Manages saved trade templates."""

    def __init__(self, template_file: str = TEMPLATE_FILE):
        self.template_file = template_file
        self._ensure_template_file_exists()

    def _ensure_template_file_exists(self):
        """Create the template file and directory if they don't exist."""
        directory = os.path.dirname(self.template_file)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        if not os.path.exists(self.template_file):
            with open(self.template_file, 'w') as f:
                yaml.dump({}, f)

    def _load_templates(self) -> Dict[str, Dict]:
        """Load all templates from the YAML file."""
        try:
            with open(self.template_file, 'r') as f:
                data = yaml.safe_load(f)
                return data if data is not None else {}
        except Exception as e:
            raise DeFiAnalyticsError(f"Failed to load trade templates: {e}") from e

    def _save_templates(self, templates: Dict[str, Dict]) -> None:
        """Save all templates to the YAML file."""
        try:
            with open(self.template_file, 'w') as f:
                yaml.dump(templates, f, default_flow_style=False)
        except Exception as e:
            raise DeFiAnalyticsError(f"Failed to save trade templates: {e}") from e

    def save_template(self, name: str, trade_request: TradeRequest) -> None:
        """Save a trade request as a template.

        Args:
            name: The name to save the template under.
            trade_request: The TradeRequest to save.
        """
        templates = self._load_templates()
        # Convert TradeRequest to a dict for storage
        template_data = {
            'input_text': trade_request.input_text,
            'token_in': trade_request.token_in,
            'token_out': trade_request.token_out,
            'amount_in': trade_request.amount_in,
            'amount_out_min': trade_request.amount_out_min,
            'intent': trade_request.intent,
        }
        templates[name] = template_data
        self._save_templates(templates)

    def get_template(self, name: str) -> Optional[TradeRequest]:
        """Get a template by name.

        Args:
            name: The name of the template.

        Returns:
            TradeRequest if found, None otherwise.
        """
        templates = self._load_templates()
        template_data = templates.get(name)
        if not template_data:
            return None
        # Convert dict back to TradeRequest
        return TradeRequest(
            input_text=template_data.get('input_text', ''),
            token_in=template_data.get('token_in', ''),
            token_out=template_data.get('token_out', ''),
            amount_in=template_data.get('amount_in', 0.0),
            amount_out_min=template_data.get('amount_out_min', 0.0),
            intent=template_data.get('intent', ''),
            # Note: id and timestamp will be generated when creating a new TradeRequest
            # from the template. We don't store them in the template.
        )

    def list_templates(self) -> List[str]:
        """List all template names.

        Returns:
            A list of template names.
        """
        templates = self._load_templates()
        return list(templates.keys())

    def delete_template(self, name: str) -> bool:
        """Delete a template by name.

        Args:
            name: The name of the template to delete.

        Returns:
            True if the template was deleted, False if it didn't exist.
        """
        templates = self._load_templates()
        if name in templates:
            del templates[name]
            self._save_templates(templates)
            return True
        return False

    def update_template(self, name: str, trade_request: TradeRequest) -> bool:
        """Update an existing template.

        Args:
            name: The name of the template to update.
            trade_request: The new TradeRequest.

        Returns:
            True if the template was updated, False if it didn't exist.
        """
        templates = self._load_templates()
        if name not in templates:
            return False
        template_data = {
            'input_text': trade_request.input_text,
            'token_in': trade_request.token_in,
            'token_out': trade_request.token_out,
            'amount_in': trade_request.amount_in,
            'amount_out_min': trade_request.amount_out_min,
            'intent': trade_request.intent,
        }
        templates[name] = template_data
        self._save_templates(templates)
        return True


# Example usage
if __name__ == "__main__":
    # This is just for demonstration.
    manager = TradeTemplateManager()
    print("TradeTemplateManager initialized.")
    print(f"Templates file: {manager.template_file}")
