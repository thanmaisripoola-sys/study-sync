# pytest configuration file
import os
from unittest.mock import MagicMock, patch

import pytest

# Set dummy GCP environment variables for local testing
os.environ["GOOGLE_CLOUD_PROJECT"] = "dummy-project"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"


@pytest.fixture(autouse=True)
def mock_gcp_services(monkeypatch):
    """Auto-mock all GCP services so tests never hit real APIs."""
    mock_logger = MagicMock()
    mock_logging_client = MagicMock()
    mock_logging_client.logger.return_value = mock_logger

    monkeypatch.setattr(
        "app.agent_runtime_app.google_cloud_logging.Client",
        lambda *args, **kwargs: mock_logging_client,
    )
    monkeypatch.setattr(
        "app.agent_runtime_app.vertexai.init",
        lambda *args, **kwargs: None,
    )
    yield
