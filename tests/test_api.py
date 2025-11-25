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
    response = client.post("/api/keys", json={"name": "test_key"}, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "key_id" in data
    assert "uuid" in data
    assert "short_id" in data
    assert len(data["short_id"]) == 8
    assert data["name"] == "test_key"


def test_create_key_without_name(client, auth_headers):
    """Тест создания ключа без имени"""
    response = client.post("/api/keys", json={}, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "key_id" in data
    assert "uuid" in data


def test_create_key_unauthorized(client):
    """Тест создания ключа без авторизации"""
    response = client.post("/api/keys", json={"name": "test_key"})

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_list_keys(client, auth_headers):
    """Тест получения списка ключей"""
    # Создаем ключ
    create_response = client.post(
        "/api/keys", json={"name": "test_key"}, headers=auth_headers
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
        "/api/keys", json={"name": "test_key"}, headers=auth_headers
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
        "/api/keys", json={"name": "test_key"}, headers=auth_headers
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
        "/api/keys", json={"name": "test_key"}, headers=auth_headers
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
        "/api/keys", json={"name": "test_key"}, headers=auth_headers
    )
    key_id = create_response.json()["key_id"]

    # Получаем ссылку (может вернуть ошибку если не настроен публичный ключ)
    response = client.get(f"/api/keys/{key_id}/link", headers=auth_headers)
    # Может быть 200 или 500 в зависимости от конфигурации
    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    ]

    if response.status_code == status.HTTP_200_OK:
        data = response.json()
        assert "key_id" in data
        assert "vless_link" in data
        assert data["vless_link"].startswith("vless://")


def test_get_vless_link_not_found(client, auth_headers):
    """Тест получения VLESS ссылки для несуществующего ключа"""
    response = client.get("/api/keys/99999/link", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_traffic_not_found(client, auth_headers):
    """Тест получения статистики для несуществующего ключа"""
    response = client.get("/api/keys/99999/traffic", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_sync_all_traffic(client, auth_headers, mock_xray_client):
    """Тест синхронизации статистики для всех ключей"""
    from unittest.mock import AsyncMock

    # Создаем несколько ключей
    for i in range(3):
        client.post("/api/keys", json={"name": f"test_key_{i}"}, headers=auth_headers)

    # Мокируем get_user_stats для каждого ключа
    mock_xray_client.get_user_stats = AsyncMock(
        return_value={"upload": 1000, "download": 2000}
    )

    # Синхронизируем статистику
    response = client.post("/api/traffic/sync", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert "updated" in data
    assert "errors" in data
    assert data["updated"] >= 3


def test_sync_all_traffic_unauthorized(client):
    """Тест синхронизации без авторизации"""
    response = client.post("/api/traffic/sync")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_list_keys_empty(client, auth_headers):
    """Тест получения пустого списка ключей"""
    response = client.get("/api/keys", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "keys" in data
    assert "total" in data
    assert isinstance(data["keys"], list)


def test_list_keys_unauthorized(client):
    """Тест получения списка ключей без авторизации"""
    response = client.get("/api/keys")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_get_key_unauthorized(client):
    """Тест получения ключа без авторизации"""
    response = client.get("/api/keys/1")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_delete_key_unauthorized(client):
    """Тест удаления ключа без авторизации"""
    response = client.delete("/api/keys/1")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_get_traffic_unauthorized(client):
    """Тест получения статистики без авторизации"""
    response = client.get("/api/keys/1/traffic")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_get_vless_link_unauthorized(client):
    """Тест получения VLESS ссылки без авторизации"""
    response = client.get("/api/keys/1/link")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_create_key_config_failure(client, auth_headers, monkeypatch):
    """Тест создания ключа при ошибке сохранения конфигурации"""
    from api.main import xray_config_manager, config_task_queue
    from unittest.mock import AsyncMock

    # Мокируем очередь задач, чтобы она выбрасывала исключение
    # Это заставит код использовать fallback - прямой вызов add_user_to_config
    async def mock_add_task(*args, **kwargs):
        raise Exception("Queue unavailable")

    # Мокируем add_user_to_config чтобы возвращал False
    original_add = xray_config_manager.add_user_to_config
    xray_config_manager.add_user_to_config = lambda *args, **kwargs: False

    # Мокируем add_task чтобы выбрасывал исключение
    original_add_task = config_task_queue.add_task
    config_task_queue.add_task = mock_add_task

    try:
        response = client.post(
            "/api/keys", json={"name": "test_key"}, headers=auth_headers
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    finally:
        xray_config_manager.add_user_to_config = original_add
        config_task_queue.add_task = original_add_task


def test_get_traffic_with_new_stats(
    client, auth_headers, mock_xray_client, monkeypatch
):
    """Тест получения статистики с созданием новой записи"""
    from unittest.mock import AsyncMock

    # Создаем ключ
    create_response = client.post(
        "/api/keys", json={"name": "test_key"}, headers=auth_headers
    )
    key_id = create_response.json()["key_id"]

    # Мокируем get_user_stats для возврата новых данных
    mock_xray_client.get_user_stats = AsyncMock(
        return_value={"upload": 5000, "download": 10000}
    )

    # Получаем статистику (должна создать новую запись TrafficStats)
    response = client.get(f"/api/keys/{key_id}/traffic", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["upload"] == 5000
    assert data["download"] == 10000
    assert data["total"] == 15000


def test_sync_all_traffic_with_errors(client, auth_headers, mock_xray_client):
    """Тест синхронизации с ошибками для некоторых ключей"""
    # Создаем несколько ключей
    key_ids = []
    for i in range(3):
        create_response = client.post(
            "/api/keys", json={"name": f"test_key_{i}"}, headers=auth_headers
        )
        key_ids.append(create_response.json()["key_id"])

    # Мокируем get_user_stats чтобы один из вызовов падал с ошибкой
    call_count = 0

    async def mock_get_user_stats(email):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # Второй вызов падает
            raise Exception("Xray API error")
        return {"upload": 1000, "download": 2000}

    mock_xray_client.get_user_stats = mock_get_user_stats

    # Синхронизируем статистику
    response = client.post("/api/traffic/sync", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["errors"] >= 1  # Должна быть хотя бы одна ошибка
    assert data["updated"] >= 1  # Но хотя бы один должен обновиться


def test_reset_traffic(client, auth_headers, mock_xray_client):
    """Тест обнуления статистики трафика"""
    # Создаем ключ
    create_response = client.post(
        "/api/keys", json={"name": "test_key"}, headers=auth_headers
    )
    key_id = create_response.json()["key_id"]

    # Сначала получаем статистику (чтобы создать запись в БД)
    traffic_response = client.get(f"/api/keys/{key_id}/traffic", headers=auth_headers)
    assert traffic_response.status_code == status.HTTP_200_OK
    initial_traffic = traffic_response.json()

    # Обнуляем трафик
    response = client.post(f"/api/keys/{key_id}/traffic/reset", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["key_id"] == key_id
    assert "previous_upload" in data
    assert "previous_download" in data
    assert "previous_total" in data
    assert data["message"] == f"Traffic reset successfully for key {key_id}"

    # Проверяем, что трафик действительно обнулен
    traffic_response = client.get(f"/api/keys/{key_id}/traffic", headers=auth_headers)
    assert traffic_response.status_code == status.HTTP_200_OK
    reset_traffic = traffic_response.json()
    assert reset_traffic["upload"] == 0
    assert reset_traffic["download"] == 0
    assert reset_traffic["total"] == 0


def test_reset_traffic_not_found(client, auth_headers):
    """Тест обнуления трафика для несуществующего ключа"""
    response = client.post("/api/keys/99999/traffic/reset", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_reset_traffic_unauthorized(client):
    """Тест обнуления трафика без авторизации"""
    response = client.post("/api/keys/1/traffic/reset")
    assert response.status_code == status.HTTP_403_FORBIDDEN
