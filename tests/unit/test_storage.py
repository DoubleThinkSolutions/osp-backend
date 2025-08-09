import os
import uuid
import pytest
from unittest.mock import patch, mock_open, MagicMock
import logging

# Import the storage module
from app.services.storage import save_file, delete_file

# Test constants
TEST_JPEG_DATA = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
TEST_MP4_DATA = b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41'
TEST_TXT_DATA = b'This is a test text file.\n'
LARGE_FILE_DATA = b'\x00' * (102 * 1024 * 1024)  # 102MB (>100MB limit)

class TestSaveFile:
    @patch("app.services.storage.uuid.uuid4")
    @patch("app.services.storage.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_valid_jpeg_file(self, mock_file, mock_makedirs, mock_uuid):
        # Arrange
        mock_uuid.return_value = "12345678-1234-4123-8234-123456789abc"
        expected_filename = "12345678-1234-4123-8234-123456789abc.jpg"
        expected_filepath = os.path.join("storage", expected_filename)

        # Act
        result = save_file(TEST_JPEG_DATA, "image/jpeg", len(TEST_JPEG_DATA))

        # Assert
        assert result == expected_filename
        mock_makedirs.assert_called_once_with("storage", exist_ok=True)
        mock_file.assert_called_once_with(expected_filepath, "wb")
        mock_file().write.assert_called_once_with(TEST_JPEG_DATA)
        # Verify logger.info was called with expected message
        with patch("app.services.storage.logger.info") as mock_log:
            result = save_file(TEST_JPEG_DATA, "image/jpeg", len(TEST_JPEG_DATA))
            mock_log.assert_called_once()

    @patch("app.services.storage.uuid.uuid4")
    @patch("app.services.storage.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_valid_mp4_file(self, mock_file, mock_makedirs, mock_uuid):
        # Arrange
        mock_uuid.return_value = "abcdef12-3456-4321-b456-abcdef123456"
        expected_filename = "abcdef12-3456-4321-b456-abcdef123456.mp4"
        expected_filepath = os.path.join("storage", expected_filename)

        # Act
        result = save_file(TEST_MP4_DATA, "video/mp4", len(TEST_MP4_DATA))

        # Assert
        assert result == expected_filename
        mock_makedirs.assert_called_once_with("storage", exist_ok=True)
        mock_file.assert_called_once_with(expected_filepath, "wb")
        mock_file().write.assert_called_once_with(TEST_MP4_DATA)
        # Verify logger.info was called
        with patch("app.services.storage.logger.info") as mock_log:
            result = save_file(TEST_MP4_DATA, "video/mp4", len(TEST_MP4_DATA))
            mock_log.assert_called_once()

    @patch("app.services.storage.logger.error")
    def test_save_unsupported_content_type(self, mock_log_error):
        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported content type: text/plain"):
            save_file(TEST_TXT_DATA, "text/plain", len(TEST_TXT_DATA))
        
        # Verify error was logged
        mock_log_error.assert_called_once_with(
            "Unsupported content type: text/plain. Allowed types: ['image/jpeg', 'video/mp4']"
        )

    @patch("app.services.storage.logger.error")
    def test_save_file_size_exceeded(self, mock_log_error):
        # Act & Assert
        with pytest.raises(ValueError, match=r"File size \d+ bytes exceeds maximum limit of 104857600 bytes"):
            save_file(LARGE_FILE_DATA, "image/jpeg", len(LARGE_FILE_DATA))
        
        # Verify error was logged
        mock_log_error.assert_called_once()

    @patch("app.services.storage.os.makedirs")
    @patch("builtins.open", side_effect=OSError("Permission denied"))
    @patch("app.services.storage.logger.error")
    def test_save_file_os_error(self, mock_log_error, mock_open_file, mock_makedirs):
        # Act & Assert
        with pytest.raises(OSError, match="Failed to write file to disk: Permission denied"):
            save_file(TEST_JPEG_DATA, "image/jpeg", len(TEST_JPEG_DATA))
        
        # Verify error was logged
        mock_log_error.assert_called_once_with("Failed to write file to disk: Permission denied")

    @patch("app.services.storage.os.makedirs")
    @patch("builtins.open", side_effect=Exception("Unexpected error"))
    @patch("app.services.storage.logger.error")
    def test_save_file_unexpected_exception(self, mock_log_error, mock_open_file, mock_makedirs):
        # Act & Assert
        with pytest.raises(Exception, match="Unexpected error while saving file: Unexpected error"):
            save_file(TEST_JPEG_DATA, "image/jpeg", len(TEST_JPEG_DATA))
        
        # Verify error was logged
        mock_log_error.assert_called_once_with("Unexpected error while saving file: Unexpected error")

class TestDeleteFile:
    @patch("app.services.storage.os.path.exists")
    @patch("app.services.storage.os.remove")
    @patch("app.services.storage.logger.info")
    @patch("app.services.storage.logger.warning")
    def test_delete_existing_file(self, mock_log_warning, mock_log_info, mock_remove, mock_exists):
        # Arrange
        mock_exists.return_value = True

        # Act
        result = delete_file("test.jpg")

        # Assert
        assert result is True
        mock_exists.assert_called_once_with(os.path.join("storage", "test.jpg"))
        mock_remove.assert_called_once_with(os.path.join("storage", "test.jpg"))
        mock_log_info.assert_called_once_with("Successfully deleted file: test.jpg")
        mock_log_warning.assert_not_called()

    @patch("app.services.storage.os.path.exists")
    @patch("app.services.storage.os.remove")
    @patch("app.services.storage.logger.warning")
    def test_delete_nonexistent_file(self, mock_log_warning, mock_remove, mock_exists):
        # Arrange
        mock_exists.return_value = False

        # Act
        result = delete_file("nonexistent.jpg")

        # Assert
        assert result is True
        mock_exists.assert_called_once_with(os.path.join("storage", "nonexistent.jpg"))
        mock_remove.assert_not_called()
        mock_log_warning.assert_called_once_with("Attempted to delete non-existent file: nonexistent.jpg")

    @patch("app.services.storage.os.path.exists")
    @patch("app.services.storage.os.remove", side_effect=OSError("Permission denied"))
    @patch("app.services.storage.logger.error")
    @patch("app.services.storage.logger.warning")
    def test_delete_file_os_error(self, mock_log_warning, mock_log_error, mock_remove, mock_exists):
        # Arrange
        mock_exists.return_value = True

        # Act
        result = delete_file("test.jpg")

        # Assert
        assert result is False
        mock_exists.assert_called_once_with(os.path.join("storage", "test.jpg"))
        mock_remove.assert_called_once_with(os.path.join("storage", "test.jpg"))
        mock_log_error.assert_called_once_with("Failed to delete file test.jpg: Permission denied")
        mock_log_warning.assert_not_called()

    @patch("app.services.storage.os.path.exists")
    @patch("app.services.storage.os.remove", side_effect=Exception("Unexpected error"))
    @patch("app.services.storage.logger.error")
    @patch("app.services.storage.logger.warning")
    def test_delete_unexpected_exception(self, mock_log_warning, mock_log_error, mock_remove, mock_exists):
        # Arrange
        mock_exists.return_value = True

        # Act
        result = delete_file("test.jpg")

        # Assert
        assert result is False
        mock_exists.assert_called_once_with(os.path.join("storage", "test.jpg"))
        mock_remove.assert_called_once_with(os.path.join("storage", "test.jpg"))
        mock_log_error.assert_called_once_with("Unexpected error while deleting file test.jpg: Unexpected error")
        mock_log_warning.assert_not_called()
