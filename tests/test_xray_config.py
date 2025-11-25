"""Тесты для XrayConfigManager"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open
from api.xray_config import XrayConfigManager


@pytest.fixture
def sample_config():
    """Пример конфигурации Xray"""
    return {
        "inbounds": [
            {
                "protocol": "vless",
                "settings": {
                    "clients": []
                },
                "streamSettings": {
                    "realitySettings": {
                        "shortIds": []
                    }
                }
            }
        ]
    }


@pytest.fixture
def temp_config_file(sample_config):
    """Создание временного файла конфигурации"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_config, f)
        temp_path = f.name
    
    yield temp_path
    
    # Очистка
    if os.path.exists(temp_path):
        os.unlink(temp_path)
    backup_path = temp_path + '.backup'
    if os.path.exists(backup_path):
        os.unlink(backup_path)


@pytest.fixture
def config_manager(temp_config_file):
    """Создание менеджера конфигурации с временным файлом"""
    return XrayConfigManager(config_path=temp_config_file)


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
    result = config_manager.save_config(sample_config)
    assert result is True
    assert os.path.exists(config_manager.config_path)


def test_add_user_to_config(config_manager, sample_config):
    """Тест добавления пользователя в конфигурацию"""
    result = config_manager.add_user_to_config(
        uuid="test-uuid-123",
        short_id="abcd1234",
        email="test@example.com"
    )
    assert result is True
    
    # Проверяем, что пользователь добавлен
    config = config_manager.load_config()
    vless_inbound = next(i for i in config["inbounds"] if i["protocol"] == "vless")
    clients = vless_inbound["settings"]["clients"]
    assert any(c["id"] == "test-uuid-123" for c in clients)
    
    # Проверяем, что short_id добавлен
    short_ids = vless_inbound["streamSettings"]["realitySettings"]["shortIds"]
    assert "abcd1234" in short_ids


def test_add_user_duplicate(config_manager, sample_config):
    """Тест добавления существующего пользователя"""
    # Добавляем пользователя первый раз
    config_manager.add_user_to_config(
        uuid="test-uuid-123",
        short_id="abcd1234",
        email="test@example.com"
    )
    
    # Пытаемся добавить снова
    result = config_manager.add_user_to_config(
        uuid="test-uuid-123",
        short_id="abcd1234",
        email="test@example.com"
    )
    assert result is True  # Должно вернуть True, но не добавить дубликат


def test_remove_user_from_config(config_manager, sample_config):
    """Тест удаления пользователя из конфигурации"""
    # Сначала добавляем пользователя
    config_manager.add_user_to_config(
        uuid="test-uuid-123",
        short_id="abcd1234",
        email="test@example.com"
    )
    
    # Удаляем пользователя
    result = config_manager.remove_user_from_config(
        uuid="test-uuid-123",
        short_id="abcd1234"
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
        uuid="nonexistent-uuid",
        short_id="nonexistent"
    )
    assert result is True  # Должно вернуть True, даже если пользователь не найден


def test_add_user_no_vless_inbound():
    """Тест добавления пользователя когда нет VLESS inbound"""
    config_without_vless = {
        "inbounds": [
            {
                "protocol": "vmess",
                "settings": {}
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_without_vless, f)
        temp_path = f.name
    
    try:
        manager = XrayConfigManager(config_path=temp_path)
        result = manager.add_user_to_config(
            uuid="test-uuid",
            short_id="abcd1234"
        )
        assert result is False
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_reload_config(config_manager):
    """Тест перезагрузки конфигурации"""
    result = config_manager.reload_config()
    assert result is True

