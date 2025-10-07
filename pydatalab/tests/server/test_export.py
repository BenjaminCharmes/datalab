import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

from pydatalab.models.export_task import ExportStatus, ExportTask


@pytest.fixture
def sample_collection(database):
    """Create a test collection with some items."""
    collection_data = {
        "_id": ObjectId(),
        "collection_id": "test_export_collection",
        "title": "Test Export Collection",
        "description": "Collection for testing export functionality",
    }

    database.collections.insert_one(collection_data)

    yield collection_data

    database.collections.delete_one({"collection_id": collection_data["collection_id"]})


@pytest.fixture
def mock_scheduler():
    """Mock the APScheduler to run jobs synchronously for testing."""

    with patch("pydatalab.routes.v0_1.export.export_scheduler") as mock_scheduler:
        mock_scheduler.add_job = MagicMock()

        def mock_add_job(func, args, job_id=None):
            return None

        mock_scheduler.add_job.side_effect = mock_add_job

        yield mock_scheduler


@pytest.fixture
def mock_current_user():
    """Mock the current user for testing."""
    with patch("pydatalab.routes.v0_1.export.current_user") as mock_user:
        mock_person = MagicMock()
        mock_person.immutable_id = "test_user_id"
        mock_user.person = mock_person
        mock_user.is_authenticated = True
        yield mock_user


class TestExportRoutes:
    def test_start_collection_export_success(
        self, client, sample_collection, mock_scheduler, mock_current_user
    ):
        """Test starting a collection export successfully."""
        collection_id = sample_collection["collection_id"]

        response = client.post(f"/collections/{collection_id}/export")

        if response.status_code == 500:
            print(f"Error response: {response.data}")

        assert response.status_code == 202

        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "task_id" in data
        assert "status_url" in data
        assert data["status_url"] == f"/exports/{data['task_id']}/status"

        assert mock_scheduler.add_job.called

    def test_start_collection_export_not_found(self, client, mock_scheduler):
        """Test starting export for non-existent collection."""
        response = client.post("/collections/nonexistent/export")
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    def test_get_export_status_pending(self, client, database):
        """Test getting status of pending export task."""
        task_id = "test-task-pending"
        task = ExportTask(
            task_id=task_id,
            collection_id="test_collection",
            creator_id="000000000000000000000000",
            status=ExportStatus.PENDING,
        )
        database.export_tasks.insert_one(task.dict())

        response = client.get(f"/exports/{task_id}/status")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "pending"
        assert "created_at" in data

        database.export_tasks.delete_one({"task_id": task_id})

    def test_get_export_status_ready(self, client, database, tmp_path):
        """Test getting status of completed export task."""
        task_id = "test-task-ready"
        file_path = tmp_path / f"{task_id}.eln"
        file_path.write_text("test content")

        task = ExportTask(
            task_id=task_id,
            collection_id="test_collection",
            creator_id="000000000000000000000000",
            status=ExportStatus.READY,
            file_path=str(file_path),
            completed_at=datetime.now(tz=timezone.utc),
        )
        database.export_tasks.insert_one(task.dict())

        response = client.get(f"/exports/{task_id}/status")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "ready"
        assert data["download_url"] == f"/exports/{task_id}/download"
        assert "completed_at" in data

        database.export_tasks.delete_one({"task_id": task_id})

    def test_get_export_status_error(self, client, database):
        """Test getting status of failed export task."""
        task_id = "test-task-error"
        error_message = "Export failed due to test error"

        task = ExportTask(
            task_id=task_id,
            collection_id="test_collection",
            creator_id="000000000000000000000000",
            status=ExportStatus.ERROR,
            error_message=error_message,
            completed_at=datetime.now(tz=timezone.utc),
        )
        database.export_tasks.insert_one(task.dict())

        response = client.get(f"/exports/{task_id}/status")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["status"] == "error"
        assert data["error_message"] == error_message
        assert "completed_at" in data

        database.export_tasks.delete_one({"task_id": task_id})

    def test_get_export_status_not_found(self, client):
        """Test getting status of non-existent export task."""
        response = client.get("/exports/nonexistent-task/status")
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    def test_download_export_success(self, client, database, tmp_path):
        """Test downloading completed export file."""
        task_id = "test-download-task"
        collection_id = "test_collection"
        file_path = tmp_path / f"{task_id}.eln"
        file_path.write_bytes(b"test export content")

        task = ExportTask(
            task_id=task_id,
            collection_id=collection_id,
            creator_id="000000000000000000000000",
            status=ExportStatus.READY,
            file_path=str(file_path),
        )
        database.export_tasks.insert_one(task.dict())

        response = client.get(f"/exports/{task_id}/download")
        assert response.status_code == 200
        assert response.data == b"test export content"
        assert f"filename={collection_id}.eln" in response.headers.get("Content-Disposition", "")

        database.export_tasks.delete_one({"task_id": task_id})

    def test_download_export_not_ready(self, client, database):
        """Test downloading export that's not ready."""
        task_id = "test-not-ready-task"

        task = ExportTask(
            task_id=task_id,
            collection_id="test_collection",
            creator_id="000000000000000000000000",
            status=ExportStatus.PROCESSING,
        )
        database.export_tasks.insert_one(task.dict())

        response = client.get(f"/exports/{task_id}/download")
        assert response.status_code == 400

        data = json.loads(response.data)
        assert "not ready" in data["message"].lower()

        database.export_tasks.delete_one({"task_id": task_id})

    def test_download_export_file_missing(self, client, database):
        """Test downloading export when file is missing."""
        task_id = "test-missing-file-task"

        task = ExportTask(
            task_id=task_id,
            collection_id="test_collection",
            creator_id="000000000000000000000000",
            status=ExportStatus.READY,
            file_path="/nonexistent/path.eln",
        )
        database.export_tasks.insert_one(task.dict())

        response = client.get(f"/exports/{task_id}/download")
        assert response.status_code == 404

        data = json.loads(response.data)
        assert "file not found" in data["message"].lower()

        database.export_tasks.delete_one({"task_id": task_id})
