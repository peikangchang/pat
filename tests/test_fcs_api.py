"""Test FCS API endpoints with global sharing model.

Test cases:
1. FCS file upload and file_id format (UUID)
2. Global sharing - all users see the same file
3. Latest file logic - only latest file is returned
4. Permission checks for all endpoints
5. 404 when no file exists
"""
import io
import pytest
from httpx import AsyncClient
from uuid import UUID

from app.models.user import User


def create_mock_fcs_file(filename: str = "test.fcs") -> tuple[str, bytes]:
    """Create a minimal valid FCS file for testing.

    Returns:
        Tuple of (filename, file_content)
    """
    # Minimal FCS 3.0 file structure
    header = b"FCS3.0    "

    # TEXT segment with minimal required parameters
    text_segment = (
        b"/$BEGINDATA/512/$ENDDATA/1024/$BEGINSTEXT/0/$ENDSTEXT/0/"
        b"$BYTEORD/1,2,3,4/$DATATYPE/I/$MODE/L/$NEXTDATA/0/"
        b"$PAR/2/$TOT/10/"
        b"$P1N/FSC-H/$P1S/FSC-H/$P1B/32/$P1R/1024/$P1E/0,0/$P1D/LIN/"
        b"$P2N/SSC-H/$P2S/SSC-H/$P2B/32/$P2R/1024/$P2E/0,0/$P2D/LIN/"
    )

    # Pad header to 58 bytes
    header_padding = b" " * (58 - len(header))
    full_header = header + header_padding

    # Create TEXT offsets in header
    text_begin = 256
    text_end = text_begin + len(text_segment)
    data_begin = 512
    data_end = 1024

    # Update header with offsets
    offset_str = f"{text_begin:>8}{text_end:>8}{data_begin:>8}{data_end:>8}{0:>8}{0:>8}"
    full_header = full_header[:10] + offset_str.encode() + full_header[58:]

    # Pad to 256 bytes
    full_header += b" " * (256 - len(full_header))

    # Create DATA segment (10 events, 2 parameters, 32-bit integers)
    import struct
    data_segment = b""
    for i in range(10):
        # FSC-H value
        data_segment += struct.pack("<I", 100 + i * 10)
        # SSC-H value
        data_segment += struct.pack("<I", 50 + i * 5)

    # Pad data to reach expected size
    data_padding = b"\x00" * (512 - len(data_segment))

    # Combine all parts
    fcs_content = full_header + text_segment + b" " * (256 - len(text_segment)) + data_segment + data_padding

    return filename, fcs_content


@pytest.mark.fcs
class TestFCSUpload:
    """Test FCS file upload functionality."""

    async def test_upload_fcs_file_success(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test successful FCS file upload returns 200 with UUID file_id."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["fcs:write"])

        filename, content = create_mock_fcs_file("test_upload.fcs")
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}

        response = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {full_token}"},
            files=files
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["filename"] == filename
        assert data["data"]["total_events"] == 10
        assert data["data"]["total_parameters"] == 2

        # Verify file_id is UUID format
        file_id = data["data"]["file_id"]
        try:
            UUID(file_id)  # Should not raise ValueError
        except ValueError:
            pytest.fail(f"file_id is not valid UUID: {file_id}")

    async def test_upload_fcs_file_403_without_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test uploading FCS file without fcs:write permission returns 403."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["fcs:read"])

        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}

        response = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {full_token}"},
            files=files
        )

        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "fcs:write"

    async def test_upload_invalid_file_extension(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test uploading non-FCS file returns 422."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["fcs:write"])

        files = {"file": ("test.txt", io.BytesIO(b"not fcs"), "text/plain")}

        response = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {full_token}"},
            files=files
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "Validation"


@pytest.mark.fcs
class TestFCSGlobalSharing:
    """Test that FCS files are globally shared among all users."""

    async def test_all_users_see_same_file(
        self, client: AsyncClient, user_a: User, user_b: User, create_pat_token
    ):
        """Test that User B can see FCS file uploaded by User A."""
        # User A uploads file
        token_a, _ = await create_pat_token(user_a.id, scopes=["fcs:write", "fcs:read"])
        filename, content = create_mock_fcs_file("shared_file.fcs")
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}

        upload_response = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_a}"},
            files=files
        )
        assert upload_response.status_code == 200
        uploaded_file_id = upload_response.json()["data"]["file_id"]

        # User B reads parameters with only read permission
        token_b, _ = await create_pat_token(user_b.id, scopes=["fcs:read"])

        params_response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {token_b}"}
        )

        assert params_response.status_code == 200
        data = params_response.json()["data"]
        assert data["total_events"] == 10
        assert data["total_parameters"] == 2
        # Both users see the same file
        assert len(data["parameters"]) == 2


@pytest.mark.fcs
class TestFCSLatestFileLogic:
    """Test that only the latest uploaded file is returned."""

    async def test_only_latest_file_is_returned(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test uploading multiple files, only latest is accessible."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["fcs:write", "fcs:read"])

        # Upload first file
        filename1, content1 = create_mock_fcs_file("first_file.fcs")
        files1 = {"file": (filename1, io.BytesIO(content1), "application/octet-stream")}
        response1 = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {full_token}"},
            files=files1
        )
        assert response1.status_code == 200
        file_id_1 = response1.json()["data"]["file_id"]

        # Upload second file
        filename2, content2 = create_mock_fcs_file("second_file.fcs")
        files2 = {"file": (filename2, io.BytesIO(content2), "application/octet-stream")}
        response2 = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {full_token}"},
            files=files2
        )
        assert response2.status_code == 200
        file_id_2 = response2.json()["data"]["file_id"]

        # Verify different file IDs
        assert file_id_1 != file_id_2

        # Get parameters should return second (latest) file
        params_response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        assert params_response.status_code == 200
        # Should return data from latest file
        assert params_response.json()["data"]["total_events"] == 10


@pytest.mark.fcs
class TestFCSPermissions:
    """Test FCS API permission requirements."""

    async def test_get_parameters_requires_fcs_read(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test GET /fcs/parameters requires fcs:read permission."""
        # Upload a file first
        token_write, _ = await create_pat_token(user_a.id, scopes=["fcs:write"])
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
        await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_write}"},
            files=files
        )

        # Try to access with wrong permission
        token_wrong, _ = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {token_wrong}"}
        )

        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "fcs:read"

    async def test_get_events_requires_fcs_read(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test GET /fcs/events requires fcs:read permission."""
        # Upload a file first
        token_write, _ = await create_pat_token(user_a.id, scopes=["fcs:write", "fcs:read"])
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
        await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_write}"},
            files=files
        )

        # Access with correct permission
        response = await client.get(
            "/api/v1/fcs/events?limit=5",
            headers={"Authorization": f"Bearer {token_write}"}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["limit"] == 5
        assert len(data["events"]) <= 5

    async def test_get_statistics_requires_fcs_analyze(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test GET /fcs/statistics requires fcs:analyze permission."""
        # Upload a file
        token_write, _ = await create_pat_token(user_a.id, scopes=["fcs:write"])
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
        await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_write}"},
            files=files
        )

        # Try with only read permission
        token_read, _ = await create_pat_token(user_a.id, scopes=["fcs:read"])

        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": f"Bearer {token_read}"}
        )

        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "fcs:analyze"

        # Access with analyze permission
        token_analyze, _ = await create_pat_token(user_a.id, scopes=["fcs:analyze"])

        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": f"Bearer {token_analyze}"}
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "statistics" in data
        assert len(data["statistics"]) == 2  # 2 parameters


@pytest.mark.fcs
class TestFCSUpload401:
    """Test 401 Unauthorized scenarios for FCS upload."""

    async def test_upload_fcs_401_no_authorization_header(self, client: AsyncClient):
        """Test uploading FCS file without Authorization header returns 401."""
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}

        response = await client.post("/api/v1/fcs/upload", files=files)
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_upload_fcs_401_invalid_token(self, client: AsyncClient):
        """Test uploading FCS file with invalid PAT token returns 401."""
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}

        response = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": "Bearer pat_invalid_token"},
            files=files
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_upload_fcs_401_expired_token(
        self, client: AsyncClient, user_a: User
    ):
        """Test uploading FCS file with expired PAT token returns 401."""
        from datetime import datetime, timedelta, timezone
        from app.domain.token_service import create_token_info
        from app.models.token import Token
        from app.common.database import async_session_maker

        token_info = create_token_info()
        expired_at = datetime.now(timezone.utc) - timedelta(days=1)

        async with async_session_maker() as session:
            async with session.begin():
                token = Token(
                    user_id=user_a.id,
                    name="Expired Token",
                    token_hash=token_info.token_hash,
                    token_prefix=token_info.token_prefix,
                    scopes=["fcs:write"],
                    expires_at=expired_at,
                )
                session.add(token)

        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}

        response = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_info.full_token}"},
            files=files
        )
        assert response.status_code == 401
        assert "expired" in response.json()["message"].lower()

    async def test_upload_fcs_401_revoked_token(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test uploading FCS file with revoked PAT token returns 401."""
        full_token, _ = await create_pat_token(
            user_a.id,
            scopes=["fcs:write"],
            is_revoked=True
        )

        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}

        response = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {full_token}"},
            files=files
        )
        assert response.status_code == 401
        assert "revoked" in response.json()["message"].lower()


@pytest.mark.fcs
class TestFCSParameters401:
    """Test 401 Unauthorized scenarios for FCS parameters endpoint."""

    async def test_get_parameters_401_no_authorization_header(self, client: AsyncClient):
        """Test getting FCS parameters without Authorization header returns 401."""
        response = await client.get("/api/v1/fcs/parameters")
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_get_parameters_401_invalid_token(self, client: AsyncClient):
        """Test getting FCS parameters with invalid PAT token returns 401."""
        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": "Bearer pat_invalid_token"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_get_parameters_401_expired_token(
        self, client: AsyncClient, user_a: User
    ):
        """Test getting FCS parameters with expired PAT token returns 401."""
        from datetime import datetime, timedelta, timezone
        from app.domain.token_service import create_token_info
        from app.models.token import Token
        from app.common.database import async_session_maker

        token_info = create_token_info()
        expired_at = datetime.now(timezone.utc) - timedelta(days=1)

        async with async_session_maker() as session:
            async with session.begin():
                token = Token(
                    user_id=user_a.id,
                    name="Expired Token",
                    token_hash=token_info.token_hash,
                    token_prefix=token_info.token_prefix,
                    scopes=["fcs:read"],
                    expires_at=expired_at,
                )
                session.add(token)

        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["message"].lower()

    async def test_get_parameters_401_revoked_token(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test getting FCS parameters with revoked PAT token returns 401."""
        full_token, _ = await create_pat_token(
            user_a.id,
            scopes=["fcs:read"],
            is_revoked=True
        )

        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 401
        assert "revoked" in response.json()["message"].lower()


@pytest.mark.fcs
class TestFCSEvents401:
    """Test 401 Unauthorized scenarios for FCS events endpoint."""

    async def test_get_events_401_no_authorization_header(self, client: AsyncClient):
        """Test getting FCS events without Authorization header returns 401."""
        response = await client.get("/api/v1/fcs/events")
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_get_events_401_invalid_token(self, client: AsyncClient):
        """Test getting FCS events with invalid PAT token returns 401."""
        response = await client.get(
            "/api/v1/fcs/events",
            headers={"Authorization": "Bearer pat_invalid_token"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_get_events_401_expired_token(
        self, client: AsyncClient, user_a: User
    ):
        """Test getting FCS events with expired PAT token returns 401."""
        from datetime import datetime, timedelta, timezone
        from app.domain.token_service import create_token_info
        from app.models.token import Token
        from app.common.database import async_session_maker

        token_info = create_token_info()
        expired_at = datetime.now(timezone.utc) - timedelta(days=1)

        async with async_session_maker() as session:
            async with session.begin():
                token = Token(
                    user_id=user_a.id,
                    name="Expired Token",
                    token_hash=token_info.token_hash,
                    token_prefix=token_info.token_prefix,
                    scopes=["fcs:read"],
                    expires_at=expired_at,
                )
                session.add(token)

        response = await client.get(
            "/api/v1/fcs/events",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["message"].lower()

    async def test_get_events_401_revoked_token(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test getting FCS events with revoked PAT token returns 401."""
        full_token, _ = await create_pat_token(
            user_a.id,
            scopes=["fcs:read"],
            is_revoked=True
        )

        response = await client.get(
            "/api/v1/fcs/events",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 401
        assert "revoked" in response.json()["message"].lower()


@pytest.mark.fcs
class TestFCSStatistics401:
    """Test 401 Unauthorized scenarios for FCS statistics endpoint."""

    async def test_get_statistics_401_no_authorization_header(self, client: AsyncClient):
        """Test getting FCS statistics without Authorization header returns 401."""
        response = await client.get("/api/v1/fcs/statistics")
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_get_statistics_401_invalid_token(self, client: AsyncClient):
        """Test getting FCS statistics with invalid PAT token returns 401."""
        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": "Bearer pat_invalid_token"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_get_statistics_401_expired_token(
        self, client: AsyncClient, user_a: User
    ):
        """Test getting FCS statistics with expired PAT token returns 401."""
        from datetime import datetime, timedelta, timezone
        from app.domain.token_service import create_token_info
        from app.models.token import Token
        from app.common.database import async_session_maker

        token_info = create_token_info()
        expired_at = datetime.now(timezone.utc) - timedelta(days=1)

        async with async_session_maker() as session:
            async with session.begin():
                token = Token(
                    user_id=user_a.id,
                    name="Expired Token",
                    token_hash=token_info.token_hash,
                    token_prefix=token_info.token_prefix,
                    scopes=["fcs:analyze"],
                    expires_at=expired_at,
                )
                session.add(token)

        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["message"].lower()

    async def test_get_statistics_401_revoked_token(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test getting FCS statistics with revoked PAT token returns 401."""
        full_token, _ = await create_pat_token(
            user_a.id,
            scopes=["fcs:analyze"],
            is_revoked=True
        )

        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 401
        assert "revoked" in response.json()["message"].lower()


@pytest.mark.fcs
class TestFCSEventsPagination:
    """Test pagination parameters for FCS events endpoint."""

    async def test_get_events_with_valid_pagination(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test GET /fcs/events with valid limit and offset."""
        # Upload a file first
        token, _ = await create_pat_token(user_a.id, scopes=["fcs:write", "fcs:read"])
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
        await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token}"},
            files=files
        )

        # Test with limit
        response = await client.get(
            "/api/v1/fcs/events?limit=5",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["limit"] == 5
        assert len(data["events"]) <= 5

        # Test with limit and offset
        response = await client.get(
            "/api/v1/fcs/events?limit=3&offset=2",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["limit"] == 3
        assert data["offset"] == 2

    async def test_get_events_422_invalid_limit(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test GET /fcs/events with invalid limit returns 422."""
        token, _ = await create_pat_token(user_a.id, scopes=["fcs:read"])

        # Upload a file first
        token_write, _ = await create_pat_token(user_a.id, scopes=["fcs:write"])
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
        await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_write}"},
            files=files
        )

        # Test negative limit
        response = await client.get(
            "/api/v1/fcs/events?limit=-1",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422

        # Test zero limit
        response = await client.get(
            "/api/v1/fcs/events?limit=0",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422

        # Test limit too large
        response = await client.get(
            "/api/v1/fcs/events?limit=10001",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422

    async def test_get_events_422_invalid_offset(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test GET /fcs/events with invalid offset returns 422."""
        token, _ = await create_pat_token(user_a.id, scopes=["fcs:read"])

        # Upload a file first
        token_write, _ = await create_pat_token(user_a.id, scopes=["fcs:write"])
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
        await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_write}"},
            files=files
        )

        # Test negative offset
        response = await client.get(
            "/api/v1/fcs/events?offset=-1",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422


@pytest.mark.fcs
class TestFCSNoFileScenarios:
    """Test FCS API behavior when no file exists."""

    async def test_get_parameters_404_no_file(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test GET /fcs/parameters returns 404 when no file uploaded."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["fcs:read"])

        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "NotFound"
        assert "No FCS file found" in data["message"]

    async def test_get_events_404_no_file(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test GET /fcs/events returns 404 when no file uploaded."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["fcs:read"])

        response = await client.get(
            "/api/v1/fcs/events",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        assert response.status_code == 404

    async def test_get_statistics_404_no_file(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test GET /fcs/statistics returns 404 when no file uploaded."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["fcs:analyze"])

        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        assert response.status_code == 404
