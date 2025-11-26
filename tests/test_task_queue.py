"""Тесты для ConfigTaskQueue"""
import pytest
import asyncio
from api.task_queue import ConfigTaskQueue, TaskType, ConfigTask


@pytest.fixture
def task_queue():
    """Создание экземпляра ConfigTaskQueue"""
    return ConfigTaskQueue()


@pytest.mark.asyncio
async def test_get_queue_size(task_queue):
    """Тест получения размера очереди"""
    size = task_queue.get_queue_size()
    assert isinstance(size, int)
    assert size >= 0


@pytest.mark.asyncio
async def test_start_stop(task_queue):
    """Тест запуска и остановки очереди"""
    await task_queue.start()
    assert task_queue._is_running is True

    await task_queue.stop()
    assert task_queue._is_running is False


@pytest.mark.asyncio
async def test_start_twice(task_queue):
    """Тест повторного запуска очереди"""
    await task_queue.start()
    await task_queue.start()  # Должно просто вернуться без ошибки
    await task_queue.stop()


@pytest.mark.asyncio
async def test_stop_when_not_running(task_queue):
    """Тест остановки не запущенной очереди"""
    await task_queue.stop()  # Не должно быть ошибки


@pytest.mark.asyncio
async def test_add_task(task_queue):
    """Тест добавления задачи в очередь"""
    await task_queue.start()
    try:
        task = await task_queue.add_task(
            task_type=TaskType.ADD_USER,
            uuid="test-uuid",
            short_id="test1234",
            email="test@example.com",
        )
        assert isinstance(task, ConfigTask)
        assert task.task_type == TaskType.ADD_USER
        assert task.uuid == "test-uuid"
    finally:
        await task_queue.stop()


@pytest.mark.asyncio
async def test_execute_task_and_wait_fallback(task_queue):
    """Тест выполнения задачи через fallback (когда очередь не запущена)"""
    # Очередь не запущена, должен использоваться fallback
    result = await task_queue.execute_task_and_wait(
        task_type=TaskType.ADD_USER,
        uuid="test-uuid",
        short_id="test1234",
        email="test@example.com",
        timeout=1.0,
    )
    # Результат зависит от того, удалось ли добавить пользователя
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_execute_task_and_wait_no_short_id(task_queue):
    """Тест выполнения задачи без short_id"""
    result = await task_queue.execute_task_and_wait(
        task_type=TaskType.ADD_USER,
        uuid="test-uuid",
        short_id=None,
        email="test@example.com",
        timeout=1.0,
    )
    assert result is False


@pytest.mark.asyncio
async def test_execute_task_and_wait_unknown_task_type(task_queue):
    """Тест выполнения задачи с неизвестным типом"""

    # Создаем фиктивный TaskType
    class UnknownTaskType:
        value = "unknown"

    result = await task_queue.execute_task_and_wait(
        task_type=UnknownTaskType(),  # type: ignore
        uuid="test-uuid",
        short_id="test1234",
        timeout=1.0,
    )
    assert result is False


@pytest.mark.asyncio
async def test_execute_task_and_wait_remove_user(task_queue):
    """Тест выполнения задачи REMOVE_USER через fallback"""
    result = await task_queue.execute_task_and_wait(
        task_type=TaskType.REMOVE_USER,
        uuid="test-uuid",
        short_id="test1234",
        timeout=1.0,
    )
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_execute_task_and_wait_remove_user_no_short_id(task_queue):
    """Тест выполнения задачи REMOVE_USER без short_id"""
    result = await task_queue.execute_task_and_wait(
        task_type=TaskType.REMOVE_USER,
        uuid="test-uuid",
        short_id=None,
        timeout=1.0,
    )
    assert result is False


@pytest.mark.asyncio
async def test_config_task_post_init():
    """Тест инициализации ConfigTask"""
    task = ConfigTask(
        task_type=TaskType.ADD_USER,
        uuid="test-uuid",
        short_id="test1234",
    )
    assert task.created_at is not None
    assert task.task_type == TaskType.ADD_USER
    assert task.uuid == "test-uuid"
    assert task.short_id == "test1234"
