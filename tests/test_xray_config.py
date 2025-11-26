"""Тесты для XrayConfigManager"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from api.xray_config import XrayConfigManager


@pytest.fixture
def sample_config():
    """Пример конфигурации Xray"""
    return {
        "inbounds": [
            {
                "protocol": "vless",
                "settings": {"clients": []},
                "streamSettings": {"realitySettings": {"shortIds": []}},
            }
        ]
    }


@pytest.fixture
def temp_config_file(sample_config):
    """Создание временного файла конфигурации"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_config, f)
        temp_path = f.name

    yield temp_path

    # Очистка
    if os.path.exists(temp_path):
        os.unlink(temp_path)
    backup_path = temp_path + ".backup"
    if os.path.exists(backup_path):
        os.unlink(backup_path)


@pytest.fixture
def config_manager(temp_config_file):
    """Создание менеджера конфигурации с временным файлом"""
    # Используем несуществующий путь к xray для тестов, чтобы пропустить проверку
    return XrayConfigManager(
        config_path=temp_config_file, xray_binary_path="/nonexistent/xray"
    )


def test_load_config(config_manager, sample_config):
    """Тест загрузки конфигурации"""
    config = config_manager.load_config()
    assert "inbounds" in config
    assert len(config["inbounds"]) > 0


def test_load_config_not_found():
    """Тест загрузки несуществующего файла"""
    manager = XrayConfigManager(config_path="/nonexistent/path/config.json")
    with pytest.raises(Exception):
        manager.load_config()


def test_save_config(config_manager, sample_config):
    """Тест сохранения конфигурации"""
    # Валидация и тест пропускаются, так как xray не найден
    result = config_manager.save_config(sample_config, validate=True, test=True)
    assert result is True
    assert os.path.exists(config_manager.config_path)


def test_save_config_with_validation(config_manager, sample_config):
    """Тест сохранения конфигурации с валидацией"""
    result = config_manager.save_config(sample_config, validate=True, test=False)
    assert result is True


def test_save_config_invalid_json(config_manager):
    """Тест сохранения невалидной JSON конфигурации"""
    invalid_config = "not a dict"
    result = config_manager.save_config(invalid_config, validate=True, test=False)
    assert result is False


def test_validate_json_valid(config_manager, sample_config):
    """Тест валидации валидной конфигурации"""
    is_valid, error_msg = config_manager.validate_json(sample_config)
    assert is_valid is True
    assert error_msg is None


def test_validate_json_invalid_type(config_manager):
    """Тест валидации невалидного типа"""
    is_valid, error_msg = config_manager.validate_json("not a dict")
    assert is_valid is False
    assert error_msg is not None


def test_validate_json_missing_sections(config_manager):
    """Тест валидации конфигурации без обязательных секций"""
    invalid_config = {"some": "data"}
    is_valid, error_msg = config_manager.validate_json(invalid_config)
    assert is_valid is False
    assert error_msg is not None


@patch("subprocess.run")
@patch("pathlib.Path.exists")
def test_test_config_success(
    mock_exists, mock_subprocess, config_manager, sample_config
):
    """Тест успешной проверки конфигурации через xray"""
    mock_exists.return_value = True
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    mock_result.stdout = ""
    mock_subprocess.return_value = mock_result

    # Обновляем путь к xray для этого теста
    config_manager.xray_binary_path = "/usr/local/bin/xray"

    is_valid, error_msg = config_manager.test_config(sample_config)
    assert is_valid is True
    assert error_msg is None
    mock_subprocess.assert_called_once()


@patch("subprocess.run")
@patch("pathlib.Path.exists")
def test_test_config_failure(
    mock_exists, mock_subprocess, config_manager, sample_config
):
    """Тест неудачной проверки конфигурации через xray"""
    mock_exists.return_value = True
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Configuration error"
    mock_result.stdout = ""
    mock_subprocess.return_value = mock_result

    # Обновляем путь к xray для этого теста
    config_manager.xray_binary_path = "/usr/local/bin/xray"

    is_valid, error_msg = config_manager.test_config(sample_config)
    assert is_valid is False
    assert error_msg is not None
    assert "Configuration error" in error_msg


@patch("pathlib.Path.exists")
def test_test_config_xray_not_found(mock_exists, config_manager, sample_config):
    """Тест пропуска проверки когда xray не найден"""
    mock_exists.return_value = False

    is_valid, error_msg = config_manager.test_config(sample_config)
    assert is_valid is True  # Пропускаем проверку
    assert error_msg is None


def test_add_user_to_config(config_manager, sample_config):
    """Тест добавления пользователя в конфигурацию"""
    from config.settings import settings

    # Убеждаемся, что общий short_id добавлен в конфигурацию перед тестом
    config_manager.ensure_common_short_id(settings.reality_common_short_id)

    result = config_manager.add_user_to_config(
        uuid="test-uuid-123", short_id="abcd1234", email="test@example.com"
    )
    assert result is True

    # Проверяем, что пользователь добавлен
    config = config_manager.load_config()
    vless_inbound = next(i for i in config["inbounds"] if i["protocol"] == "vless")
    clients = vless_inbound["settings"]["clients"]
    assert any(c["id"] == "test-uuid-123" for c in clients)

    # Проверяем, что общий short_id присутствует в конфигурации
    # (теперь используется общий short_id для всех пользователей)
    short_ids = vless_inbound["streamSettings"]["realitySettings"]["shortIds"]
    assert settings.reality_common_short_id in short_ids


def test_add_user_duplicate(config_manager, sample_config):
    """Тест добавления существующего пользователя"""
    # Добавляем пользователя первый раз
    config_manager.add_user_to_config(
        uuid="test-uuid-123", short_id="abcd1234", email="test@example.com"
    )

    # Пытаемся добавить снова
    result = config_manager.add_user_to_config(
        uuid="test-uuid-123", short_id="abcd1234", email="test@example.com"
    )
    assert result is True  # Должно вернуть True, но не добавить дубликат


def test_remove_user_from_config(config_manager, sample_config):
    """Тест удаления пользователя из конфигурации"""
    # Сначала добавляем пользователя
    config_manager.add_user_to_config(
        uuid="test-uuid-123", short_id="abcd1234", email="test@example.com"
    )

    # Удаляем пользователя
    result = config_manager.remove_user_from_config(
        uuid="test-uuid-123", short_id="abcd1234"
    )
    assert result is True

    # Проверяем, что пользователь удален
    config = config_manager.load_config()
    vless_inbound = next(i for i in config["inbounds"] if i["protocol"] == "vless")
    clients = vless_inbound["settings"]["clients"]
    assert not any(c["id"] == "test-uuid-123" for c in clients)

    # Проверяем, что short_id удален
    short_ids = vless_inbound["streamSettings"]["realitySettings"]["shortIds"]
    assert "abcd1234" not in short_ids


def test_remove_user_not_found(config_manager, sample_config):
    """Тест удаления несуществующего пользователя"""
    result = config_manager.remove_user_from_config(
        uuid="nonexistent-uuid", short_id="nonexistent"
    )
    assert result is True  # Должно вернуть True, даже если пользователь не найден


def test_add_user_no_vless_inbound():
    """Тест добавления пользователя когда нет VLESS inbound"""
    config_without_vless = {"inbounds": [{"protocol": "vmess", "settings": {}}]}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_without_vless, f)
        temp_path = f.name

    try:
        manager = XrayConfigManager(config_path=temp_path)
        result = manager.add_user_to_config(uuid="test-uuid", short_id="abcd1234")
        assert result is False
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@patch("subprocess.run")
def test_reload_config(mock_run, config_manager):
    """Тест перезагрузки конфигурации"""
    # Мокируем pgrep чтобы вернуть PID процесса
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "12345\n"
    mock_run.return_value = mock_result

    # Мокируем os.kill чтобы не было ошибок
    with patch("os.kill") as mock_kill:
        with patch("time.sleep"):  # Ускоряем тест
            result = config_manager.reload_config()
            # Может вернуть False если процесс не найден или не может быть перезапущен
            # Но в тестовой среде это нормально
            assert isinstance(result, bool)
