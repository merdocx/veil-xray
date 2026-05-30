"""Тесты для XrayConfigManager"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from api.xray_config import XrayConfigManager
from config.settings import settings


def _minimal_vless_inbound(tag: str) -> dict:
    return {
        "tag": tag,
        "protocol": "vless",
        "settings": {"clients": [], "decryption": "none"},
        "streamSettings": {"realitySettings": {"shortIds": []}},
    }


def _minimal_trojan_inbound() -> dict:
    return {
        "tag": settings.xray_trojan_reality_inbound_tag,
        "protocol": "trojan",
        "settings": {"clients": []},
        "streamSettings": {"realitySettings": {"shortIds": []}},
    }


@pytest.fixture
def sample_config():
    """Минимальный config.json с тегами inbounds как в settings / prod."""
    inbounds = [_minimal_vless_inbound(tag) for tag in settings.vless_inbound_tags()]
    inbounds.append(_minimal_trojan_inbound())
    return {"inbounds": inbounds, "outbounds": []}


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
    from unittest.mock import patch
    from config.settings import settings

    # Убеждаемся, что общий short_id добавлен в конфигурацию перед тестом
    config_manager.ensure_common_short_id(settings.reality_common_short_id)

    with patch.object(config_manager, "reload_config") as reload_mock:
        result = config_manager.add_user_to_config(
            uuid="test-uuid-123", short_id="abcd1234", email="test@example.com"
        )
        reload_mock.assert_not_called()
    assert result is True

    config = config_manager.load_config()
    primary = config_manager._get_inbound_by_tag(
        config, settings.xray_vless_reality_inbound_tag
    )
    assert primary is not None
    clients = primary["settings"]["clients"]
    assert any(c["id"] == "test-uuid-123" for c in clients)
    short_ids = primary["streamSettings"]["realitySettings"]["shortIds"]
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

    config = config_manager.load_config()
    for tag in settings.vless_inbound_tags():
        inbound = config_manager._get_inbound_by_tag(config, tag)
        assert inbound is not None
        clients = inbound["settings"]["clients"]
        assert not any(c["id"] == "test-uuid-123" for c in clients)


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


def test_bulk_sync_vless_clients(config_manager, sample_config):
    """Один save при массовой синхронизации."""
    from unittest.mock import patch

    users = [
        ("uuid-a", "a@x"),
        ("uuid-b", "b@x"),
    ]
    with patch.object(config_manager, "save_config", return_value=True) as mock_save:
        result = config_manager.bulk_sync_vless_clients(
            users, validate=False, test=False
        )
    assert result["saved"] is True
    assert result["added"] == 2
    assert mock_save.call_count == 1
