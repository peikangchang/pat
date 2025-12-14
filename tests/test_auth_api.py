"""Test authentication API endpoints.

Covers:
- POST /api/v1/auth/register
- POST /api/v1/auth/login

Status codes tested:
- 200 OK
- 401 Unauthorized
- 422 Unprocessable Entity
"""
import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.integration
class TestAuthRegister:
    """Test user registration endpoint."""

    async def test_register_200_success(self, client: AsyncClient):
        """Test successful user registration returns 200."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "SecurePass123!"
            }
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        data = response.json()["data"]
        assert "id" in data
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"

    async def test_register_422_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "user",
                "email": "invalid-email",
                "password": "password123"
            }
        )
        assert response.status_code == 422

    async def test_register_422_duplicate_username(
        self, client: AsyncClient, user_a: User
    ):
        """Test registration with duplicate username returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "user_a",  # Already exists
                "email": "different@example.com",
                "password": "password123"
            }
        )
        assert response.status_code == 422
        assert response.json()["error"] == "Validation"

    async def test_register_422_duplicate_email(
        self, client: AsyncClient, user_a: User
    ):
        """Test registration with duplicate email returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "different_user",
                "email": "user_a@example.com",  # Already exists
                "password": "password123"
            }
        )
        assert response.status_code == 422
        assert response.json()["error"] == "Validation"

    async def test_register_422_password_too_short(self, client: AsyncClient):
        """Test registration with short password returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "short"  # Less than 8 characters
            }
        )
        assert response.status_code == 422

    async def test_register_422_missing_username(self, client: AsyncClient):
        """Test registration without username returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "password123"
            }
        )
        assert response.status_code == 422

    async def test_register_422_missing_email(self, client: AsyncClient):
        """Test registration without email returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "password": "password123"
            }
        )
        assert response.status_code == 422

    async def test_register_422_missing_password(self, client: AsyncClient):
        """Test registration without password returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com"
            }
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestAuthLogin:
    """Test user login endpoint."""

    async def test_login_200_success(
        self, client: AsyncClient, user_a: User
    ):
        """Test successful login returns 200 with JWT token."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "user_a",
                "password": "password123"
            }
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    async def test_login_401_invalid_credentials(
        self, client: AsyncClient, user_a: User
    ):
        """Test login with wrong password returns 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "user_a",
                "password": "wrong_password"
            }
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_login_401_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent user returns 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "password123"
            }
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_login_422_missing_username(self, client: AsyncClient):
        """Test login without username returns 422."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "password": "password123"
            }
        )
        assert response.status_code == 422

    async def test_login_422_missing_password(self, client: AsyncClient):
        """Test login without password returns 422."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "user_a"
            }
        )
        assert response.status_code == 422
