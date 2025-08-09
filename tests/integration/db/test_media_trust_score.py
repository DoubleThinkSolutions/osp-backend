import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.db.session import SessionLocal
from app.db.models import Media, User
from app.services.media.service import update_media_trust_score, TrustScoreUpdateError

# Helper to create timezone-aware datetime
def dt(*args):
    return datetime(*args, tzinfo=timezone.utc)

@pytest.fixture(scope="function")
def db_session():
    """Provide a transactional database session for tests."""
    session = SessionLocal()
    try:
        # Begin a transaction
        session.begin()
        yield session
    finally:
        # Rollback any changes after test
        session.rollback()
        session.close()

@pytest.fixture(scope="function")
def test_user(db_session: Session):
    user = User(
        username="testuser",
        email="testuser@example.com",
        hashed_password="fakehash",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def test_media(db_session: Session, test_user: User):
    media = Media(
        capture_time=dt(2023, 1, 1, 12, 0, 0),
        lat=37.7749,
        lng=-122.4194,
        orientation=0.0,
        file_path="/media/test.jpg",
        user_id=test_user.id,
        trust_score=0.0
    )
    db_session.add(media)
    db_session.commit()
    db_session.refresh(media)
    return media

class TestUpdateMediaTrustScore:
    def test_valid_update_successfully_calculates_and_persists_score(self, db_session: Session, test_media: Media):
        # Given
        capture_time = dt(2023, 1, 1, 12, 0, 0)
        upload_time = dt(2023, 1, 1, 12, 5, 0)  # 5 minutes after

        # When
        success = update_media_trust_score(db_session, test_media.id, capture_time, upload_time)

        # Then
        assert success is True
        updated_media = db_session.query(Media).filter(Media.id == test_media.id).first()
        assert updated_media is not None
        assert updated_media.trust_score == 95.0

        # Verify log message contains the success info (requires capture_logs fixture or inspection)
        # We'll rely on the service logging being tested via caplog in unit context.
        # In integration we check behavior rather than logs.

    def test_large_delay_yields_zero_score(self, db_session: Session, test_media: Media):
        # Given
        capture_time = dt(2023, 1, 1, 12, 0, 0)
        upload_time = dt(2023, 1, 1, 15, 20, 0)  # 200 minutes later

        # When
        success = update_media_trust_score(db_session, test_media.id, capture_time, upload_time)

        # Then
        assert success is True
        updated_media = db_session.query(Media).filter(Media.id == test_media.id).first()
        assert updated_media.trust_score == 0.0

    def test_equal_timestamps_yields_max_score(self, db_session: Session, test_media: Media):
        # Given
        capture_time = dt(2023, 1, 1, 12, 0, 0)
        upload_time = dt(2023, 1, 1, 12, 0, 0)

        # When
        success = update_media_trust_score(db_session, test_media.id, capture_time, upload_time)

        # Then
        assert success is True
        updated_media = db_session.query(Media).filter(Media.id == test_media.id).first()
        assert updated_media.trust_score == 100.0

    def test_none_timestamps_sets_score_to_zero_with_warning_log(self, db_session: Session, test_media: Media, caplog):
        # Given: Simulate missing capture time
        capture_time = None
        upload_time = dt(2023, 1, 1, 12, 0, 0)

        # When
        with caplog.at_level("WARNING"):
            success = update_media_trust_score(db_session, test_media.id, capture_time, upload_time)

        # Then
        assert success is True
        updated_media = db_session.query(Media).filter(Media.id == test_media.id).first()
        assert updated_media.trust_score == 0.0
        assert "Missing timestamp(s)" in caplog.text

    def test_database_error_handled_gracefully(self, db_session: Session, test_media: Media):
        # Given
        capture_time = dt(2023, 1, 1, 12, 0, 0)
        upload_time = dt(2023, 1, 1, 12, 5, 0)

        # Mock db.query to raise an exception
        with patch.object(db_session, "query", side_effect=Exception("DB connection lost")):
            # When
            success = update_media_trust_score(db_session, test_media.id, capture_time, upload_time)

            # Then
            assert success is False

    def test_media_record_not_found_returns_false(self, db_session: Session):
        # Given
        non_existent_id = 99999
        capture_time = dt(2023, 1, 1, 12, 0, 0)
        upload_time = dt(2023, 1, 1, 12, 5, 0)

        # When
        with patch("app.services.media.service.logger") as mock_logger:
            success = update_media_trust_score(db_session, non_existent_id, capture_time, upload_time)

        # Then
        assert success is False
        mock_logger.error.assert_called_with(f"Media record not found for id: {non_existent_id}")

    def test_unexpected_exception_rolls_back_and_returns_false(self, db_session: Session, test_media: Media):
        # Given
        capture_time = dt(2023, 1, 1, 12, 0, 0)
        upload_time = dt(2023, 1, 1, 12, 5, 0)

        # Patch within Media instance query to force failure after retrieval
        with patch.object(db_session.__class__, "commit", side_effect=Exception("Disk full")):
            with patch("app.services.media.service.logger") as mock_logger:
                # When
                success = update_media_trust_score(db_session, test_media.id, capture_time, upload_time)

                # Then
                assert success is False
                mock_logger.critical.assert_called()
                # Verify rollback occurred conceptually (we can't directly check SQL state)
                db_session.rollback.assert_called()

    def test_integrity_error_rolls_back_and_returns_false(self, db_session: Session, test_media: Media):
        # Given
        from sqlalchemy.exc import IntegrityError
        capture_time = dt(2023, 1, 1, 12, 0, 0)
        upload_time = dt(2023, 1, 1, 12, 5, 0)

        # Simulate IntegrityError on commit
        with patch.object(db_session.__class__, "commit", side_effect=IntegrityError(None, None, None)):
            with patch("app.services.media.service.logger") as mock_logger:
                # When
                success = update_media_trust_score(db_session, test_media.id, capture_time, upload_time)

                # Then
                assert success is False
                mock_logger.error.assert_called_with(
                    f"IntegrityError when updating trust score for media {test_media.id}: (builtins.NoneType) None"
                )
                db_session.rollback.assert_called()
        
    def test_data_error_rolls_back_and_returns_false(self, db_session: Session, test_media: Media):
        # Given
        from sqlalchemy.exc import DataError
        capture_time = dt(2023, 1, 1, 12, 0, 0)
        upload_time = dt(2023, 1, 1, 12, 5, 0)

        # Simulate DataError on commit
        with patch.object(db_session.__class__, "commit", side_effect=DataError(None, None, None)):
            with patch("app.services.media.service.logger") as mock_logger:
                # When
                success = update_media_trust_score(db_session, test_media.id, capture_time, upload_time)

                # Then
                assert success is False
                mock_logger.error.assert_called_with(
                    f"DataError when updating trust score for media {test_media.id}: (builtins.NoneType) None"
                )
                db_session.rollback.assert_called()
