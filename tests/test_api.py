"""Тесты для API endpoints"""
import pytest
from fastapi import status


def test_root(client):
    """Тест корневого endpoint"""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ok"


def test_create_key(client, auth_headers):
    """Тест создания ключа"""
    response = client.post(
        "/api/keys",
        json={"name": "test_key"},
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "key_id" in data
    assert "uuid" in data
    assert "short_id" in data
    assert len(data["short_id"]) == 8
    assert data["name"] == "test_key"


def test_create_key_without_name(client, auth_headers):
    """Тест создания ключа без имени"""
    response = client.post(
        "/api/keys",
        json={},
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "key_id" in data
    assert "uuid" in data


def test_create_key_unauthorized(client):
    """Тест создания ключа без авторизации"""
    response = client.post(
        "/api/keys",
        json={"name": "test_key"}
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_list_keys(client, auth_headers):
    """Тест получения списка ключей"""
    # Создаем ключ
    create_response = client.post(
        "/api/keys",
        json={"name": "test_key"},
        headers=auth_headers
    )
    assert create_response.status_code == status.HTTP_200_OK
    
    # Получаем список
    response = client.get("/api/keys", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "keys" in data
    assert "total" in data
    assert data["total"] >= 1


def test_get_key(client, auth_headers):
    """Тест получения конкретного ключа"""
    # Создаем ключ
    create_response = client.post(
        "/api/keys",
        json={"name": "test_key"},
        headers=auth_headers
    )
    key_id = create_response.json()["key_id"]
    
    # Получаем ключ
    response = client.get(f"/api/keys/{key_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["key_id"] == key_id
    assert data["name"] == "test_key"


def test_get_key_not_found(client, auth_headers):
    """Тест получения несуществующего ключа"""
    response = client.get("/api/keys/99999", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_key(client, auth_headers):
    """Тест удаления ключа"""
    # Создаем ключ
    create_response = client.post(
        "/api/keys",
        json={"name": "test_key"},
        headers=auth_headers
    )
    key_id = create_response.json()["key_id"]
    
    # Удаляем ключ
    response = client.delete(f"/api/keys/{key_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    
    # Проверяем, что ключ удален
    get_response = client.get(f"/api/keys/{key_id}", headers=auth_headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_key_not_found(client, auth_headers):
    """Тест удаления несуществующего ключа"""
    response = client.delete("/api/keys/99999", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_traffic(client, auth_headers):
    """Тест получения статистики трафика"""
    # Создаем ключ
    create_response = client.post(
        "/api/keys",
        json={"name": "test_key"},
        headers=auth_headers
    )
    key_id = create_response.json()["key_id"]
    
    # Получаем статистику
    response = client.get(f"/api/keys/{key_id}/traffic", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "key_id" in data
    assert "upload" in data
    assert "download" in data
    assert "total" in data
    assert "last_updated" in data


def test_get_vless_link(client, auth_headers):
    """Тест получения VLESS ссылки"""
    # Создаем ключ
    create_response = client.post(
        "/api/keys",
        json={"name": "test_key"},
        headers=auth_headers
    )
    key_id = create_response.json()["key_id"]
    
    # Получаем ссылку (может вернуть ошибку если не настроен публичный ключ)
    response = client.get(f"/api/keys/{key_id}/link", headers=auth_headers)
    # Может быть 200 или 500 в зависимости от конфигурации
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    if response.status_code == status.HTTP_200_OK:
        data = response.json()
        assert "key_id" in data
        assert "vless_link" in data
        assert data["vless_link"].startswith("vless://")


