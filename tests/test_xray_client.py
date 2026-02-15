"""Тесты для XrayClient"""
import subprocess
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
    with patch("api.xray_client.subprocess.run") as mock_run:
        # Мокируем check_health чтобы вернуть True
        with patch.object(xray_client, "check_health", return_value=True):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stderr = ""
            mock_result.stdout = ""
            mock_run.return_value = mock_result

            result = await xray_client.add_user("test-uuid", "test@example.com")
            assert result is True


@pytest.mark.asyncio
async def test_add_user_failure(xray_client):
    """Тест неудачного добавления пользователя"""
    with patch("api.xray_client.subprocess.run") as mock_run:
        # Мокируем check_health чтобы вернуть True
        with patch.object(xray_client, "check_health", return_value=True):
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Error adding user"
            mock_result.stdout = ""
            mock_run.return_value = mock_result

            result = await xray_client.add_user("test-uuid", "test@example.com")
            assert result is False


@pytest.mark.asyncio
async def test_add_user_exception(xray_client):
    """Тест обработки исключения при добавлении пользователя"""
    with patch("api.xray_client.subprocess.run") as mock_run:
        # Мокируем check_health чтобы вернуть True
        with patch.object(xray_client, "check_health", return_value=True):
            import subprocess

            mock_run.side_effect = subprocess.TimeoutExpired("xray", 10)

            result = await xray_client.add_user("test-uuid", "test@example.com")
            assert result is False


@pytest.mark.asyncio
async def test_remove_user_success(xray_client):
    """Тест успешного удаления пользователя"""
    with patch("api.xray_client.subprocess.run") as mock_run:
        # Мокируем check_health чтобы вернуть True
        with patch.object(xray_client, "check_health", return_value=True):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stderr = ""
            mock_result.stdout = ""
            mock_run.return_value = mock_result

            result = await xray_client.remove_user("test@example.com")
            assert result is True


@pytest.mark.asyncio
async def test_remove_user_failure(xray_client):
    """Тест неудачного удаления пользователя"""
    with patch("api.xray_client.subprocess.run") as mock_run:
        # Мокируем check_health чтобы вернуть True
        with patch.object(xray_client, "check_health", return_value=True):
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Error removing user"
            mock_result.stdout = ""
            mock_run.return_value = mock_result

            result = await xray_client.remove_user("test@example.com")
            # Если пользователь не найден, возвращается True (это нормально)
            # Но если другая ошибка, то False
            assert result is False


@pytest.mark.asyncio
async def test_get_stats_success(xray_client):
    """Тест успешного получения статистики"""
    with patch("api.xray_client.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            '{"stat": [{"name": "user>>>test>>>uplink", "value": 1000}]}'
        )
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = await xray_client.get_stats("test@example.com")
        assert "stat" in result


@pytest.mark.asyncio
async def test_get_stats_no_email(xray_client):
    """Тест получения статистики без email"""
    with patch("api.xray_client.subprocess.run") as mock_run:
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
    with patch("api.xray_client.subprocess.run") as mock_run:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("xray", 5)

        result = await xray_client.get_stats()
        assert result == {}


@pytest.mark.asyncio
async def test_get_stats_file_not_found(xray_client):
    """Тест обработки отсутствия бинарника Xray"""
    with patch("api.xray_client.subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()

        result = await xray_client.get_stats()
        assert result == {}


@pytest.mark.asyncio
async def test_get_stats_invalid_json(xray_client):
    """Тест обработки невалидного JSON"""
    with patch("api.xray_client.subprocess.run") as mock_run:
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
    with patch.object(xray_client, "get_stats") as mock_get_stats:
        mock_get_stats.return_value = {
            "stat": [
                {"name": "user>>>test@example.com>>>uplink", "value": 1000},
                {"name": "user>>>test@example.com>>>downlink", "value": 2000},
            ]
        }

        result = await xray_client.get_user_stats("test@example.com")
        assert result["upload"] == 1000
        assert result["download"] == 2000


@pytest.mark.asyncio
async def test_get_user_stats_empty(xray_client):
    """Тест получения статистики для пользователя без данных"""
    with patch.object(xray_client, "get_stats") as mock_get_stats:
        mock_get_stats.return_value = {"stat": []}

        result = await xray_client.get_user_stats("test@example.com")
        assert result["upload"] == 0
        assert result["download"] == 0


@pytest.mark.asyncio
async def test_reset_user_stats_success(xray_client):
    """Тест сброса статистики пользователя в Xray (statsquery -reset=true)"""
    with patch("api.xray_client.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        result = await xray_client.reset_user_stats("user_1_abc12345")
        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "statsquery" in call_args
        assert "-reset=true" in call_args
        assert "user>>>user_1_abc12345>>>" in call_args


@pytest.mark.asyncio
async def test_reset_user_stats_failure(xray_client):
    """Тест сброса статистики при ошибке Xray"""
    with patch("api.xray_client.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        result = await xray_client.reset_user_stats("user_1_abc12345")
        assert result is False
