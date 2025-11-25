"""Тесты для XrayClient"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from api.xray_client import XrayClient


@pytest.fixture
def xray_client():
    """Создание экземпляра XrayClient"""
    return XrayClient()


@pytest.mark.asyncio
async def test_add_user_success(xray_client):
    """Тест успешного добавления пользователя"""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client
        
        result = await xray_client.add_user("test-uuid", "test@example.com")
        assert result is True


@pytest.mark.asyncio
async def test_add_user_failure(xray_client):
    """Тест неудачного добавления пользователя"""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Error"
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client
        
        result = await xray_client.add_user("test-uuid", "test@example.com")
        assert result is False


@pytest.mark.asyncio
async def test_add_user_exception(xray_client):
    """Тест обработки исключения при добавлении пользователя"""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client
        
        result = await xray_client.add_user("test-uuid", "test@example.com")
        assert result is False


@pytest.mark.asyncio
async def test_remove_user_success(xray_client):
    """Тест успешного удаления пользователя"""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client
        
        result = await xray_client.remove_user("test@example.com")
        assert result is True


@pytest.mark.asyncio
async def test_remove_user_failure(xray_client):
    """Тест неудачного удаления пользователя"""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client
        
        result = await xray_client.remove_user("test@example.com")
        assert result is False


@pytest.mark.asyncio
async def test_get_stats_success(xray_client):
    """Тест успешного получения статистики"""
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"stat": [{"name": "user>>>test>>>uplink", "value": 1000}]}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = await xray_client.get_stats("test@example.com")
        assert "stat" in result


@pytest.mark.asyncio
async def test_get_stats_no_email(xray_client):
    """Тест получения статистики без email"""
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"stat": []}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = await xray_client.get_stats()
        assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_get_stats_timeout(xray_client):
    """Тест обработки таймаута при получении статистики"""
    with patch('subprocess.run') as mock_run:
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("xray", 5)
        
        result = await xray_client.get_stats()
        assert result == {}


@pytest.mark.asyncio
async def test_get_stats_file_not_found(xray_client):
    """Тест обработки отсутствия бинарника Xray"""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = FileNotFoundError()
        
        result = await xray_client.get_stats()
        assert result == {}


@pytest.mark.asyncio
async def test_get_stats_invalid_json(xray_client):
    """Тест обработки невалидного JSON"""
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = await xray_client.get_stats()
        assert result == {"stat": []}


@pytest.mark.asyncio
async def test_get_user_stats(xray_client):
    """Тест получения статистики пользователя"""
    with patch.object(xray_client, 'get_stats') as mock_get_stats:
        mock_get_stats.return_value = {
            "stat": [
                {"name": "user>>>test@example.com>>>uplink", "value": 1000},
                {"name": "user>>>test@example.com>>>downlink", "value": 2000}
            ]
        }
        
        result = await xray_client.get_user_stats("test@example.com")
        assert result["upload"] == 1000
        assert result["download"] == 2000


@pytest.mark.asyncio
async def test_get_user_stats_empty(xray_client):
    """Тест получения статистики для пользователя без данных"""
    with patch.object(xray_client, 'get_stats') as mock_get_stats:
        mock_get_stats.return_value = {"stat": []}
        
        result = await xray_client.get_user_stats("test@example.com")
        assert result["upload"] == 0
        assert result["download"] == 0

