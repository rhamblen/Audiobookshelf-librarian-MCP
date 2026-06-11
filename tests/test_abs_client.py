"""Mocked ABS API client tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from abs_librarian.abs_client import ABSClient

BASE = "http://abs.local"
TOKEN = "test-token"


@pytest.fixture()
def client():
    return ABSClient(BASE, TOKEN)


@pytest.mark.asyncio
async def test_get_libraries(client):
    mock_resp = {"libraries": [{"id": "lib1", "name": "Audiobooks"}]}
    mock_response = MagicMock()
    mock_response.json.return_value = mock_resp
    mock_response.raise_for_status = lambda: None
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await client.get_libraries()
    assert result == [{"id": "lib1", "name": "Audiobooks"}]


@pytest.mark.asyncio
async def test_batch_update_chunks(client):
    """batch_update must split into chunks of 100."""
    items = [{"id": str(i)} for i in range(250)]
    call_bodies = []

    async def fake_post(url, headers, json):
        call_bodies.append(json)
        r = AsyncMock()
        r.json.return_value = json  # echo back
        r.content = b"[]"
        r.raise_for_status = lambda: None
        return r

    with patch("httpx.AsyncClient.post", side_effect=fake_post):
        await client.batch_update(items)

    assert len(call_bodies) == 3  # 100 + 100 + 50


@pytest.mark.asyncio
async def test_set_cover_url(client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"success": True}
    mock_response.content = b'{"success":true}'
    mock_response.raise_for_status = lambda: None
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await client.set_cover_url("item1", "http://example.com/cover.jpg")
    assert result == {"success": True}
