"""Очередь задач для последовательной обработки операций с конфигурацией Xray"""
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Типы задач для очереди"""

    ADD_USER = "add_user"
    REMOVE_USER = "remove_user"


@dataclass
class ConfigTask:
    """Задача для обработки конфигурации Xray"""

    task_type: TaskType
    uuid: str
    short_id: Optional[str] = None
    email: Optional[str] = None
    callback: Optional[Callable[[bool], None]] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class ConfigTaskQueue:
    """Очередь задач для последовательной обработки операций с конфигурацией Xray"""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._is_running = False
        self._pending_futures: dict[
            str, asyncio.Future
        ] = {}  # Словарь для ожидания результатов задач

    async def start(self):
        """Запуск воркера для обработки задач"""
        if self._is_running:
            logger.warning("Task queue worker is already running")
            return

        self._is_running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("✅ Config task queue worker started")

    async def stop(self):
        """Остановка воркера"""
        if not self._is_running:
            return

        self._is_running = False
        # Добавляем сигнал остановки
        await self._queue.put(None)

        if self._worker_task:
            await self._worker_task
            logger.info("✅ Config task queue worker stopped")

    async def add_task(
        self,
        task_type: TaskType,
        uuid: str,
        short_id: Optional[str] = None,
        email: Optional[str] = None,
        callback: Optional[Callable[[bool], None]] = None,
    ) -> ConfigTask:
        """
        Добавление задачи в очередь

        Args:
            task_type: Тип задачи
            uuid: UUID пользователя
            short_id: Short ID пользователя (опционально)
            email: Email пользователя (опционально)
            callback: Функция обратного вызова для уведомления о результате

        Returns:
            Созданная задача
        """
        task = ConfigTask(
            task_type=task_type,
            uuid=uuid,
            short_id=short_id,
            email=email,
            callback=callback,
        )

        await self._queue.put(task)
        logger.debug(
            f"📥 Task {task_type.value} for UUID {uuid[:8]}... added to queue "
            f"(queue size: {self._queue.qsize()})"
        )
        return task

    async def _worker(self):
        """Воркер для последовательной обработки задач"""
        logger.info("🔄 Config task queue worker started")

        while self._is_running:
            try:
                # Получаем задачу из очереди (блокирующий вызов)
                task = await self._queue.get()

                # None - сигнал остановки
                if task is None:
                    break

                # Обрабатываем задачу последовательно
                async with self._lock:
                    success = await self._process_task(task)

                    # Уведомляем ожидающие Future о результате
                    task_id = f"{task.task_type.value}_{task.uuid}"
                    if task_id in self._pending_futures:
                        future = self._pending_futures.pop(task_id)
                        if not future.done():
                            future.set_result(success)
                        logger.debug(f"✅ Notified waiting future for task {task_id}")

                    # Вызываем callback если он есть
                    if task.callback:
                        try:
                            if asyncio.iscoroutinefunction(task.callback):
                                await task.callback(success)
                            else:
                                task.callback(success)
                        except Exception as e:
                            logger.error(f"Error calling task callback: {e}")

                # Помечаем задачу как выполненную
                self._queue.task_done()

            except Exception as e:
                logger.error(f"❌ Error in task queue worker: {e}")
                # Уведомляем ожидающие Future об ошибке
                if task:
                    task_id = f"{task.task_type.value}_{task.uuid}"
                    if task_id in self._pending_futures:
                        future = self._pending_futures.pop(task_id)
                        if not future.done():
                            future.set_result(False)  # Устанавливаем False при ошибке
                        logger.debug(
                            f"❌ Notified waiting future about error for task {task_id}"
                        )
                    self._queue.task_done()

        logger.info("🔄 Config task queue worker stopped")

    async def _process_task(self, task: ConfigTask) -> bool:
        """
        Обработка задачи

        Args:
            task: Задача для обработки

        Returns:
            True если успешно, False в противном случае
        """
        from api.xray_config import XrayConfigManager

        config_manager = XrayConfigManager()

        try:
            logger.info(
                f"🔄 Processing task {task.task_type.value} for UUID {task.uuid[:8]}... "
                f"(queue size: {self._queue.qsize()})"
            )

            if task.task_type == TaskType.ADD_USER:
                if not task.short_id:
                    logger.error(f"Short ID is required for ADD_USER task")
                    return False

                success = config_manager.add_user_to_config(
                    uuid=task.uuid, short_id=task.short_id, email=task.email
                )

                if success:
                    logger.info(
                        f"✅ Successfully processed ADD_USER task for UUID {task.uuid[:8]}..."
                    )
                else:
                    logger.error(
                        f"❌ Failed to process ADD_USER task for UUID {task.uuid[:8]}..."
                    )

                return success

            elif task.task_type == TaskType.REMOVE_USER:
                if not task.short_id:
                    logger.error(f"Short ID is required for REMOVE_USER task")
                    return False

                success = config_manager.remove_user_from_config(
                    uuid=task.uuid, short_id=task.short_id
                )

                if success:
                    logger.info(
                        f"✅ Successfully processed REMOVE_USER task for UUID {task.uuid[:8]}..."
                    )
                else:
                    logger.error(
                        f"❌ Failed to process REMOVE_USER task for UUID {task.uuid[:8]}..."
                    )

                return success
            else:
                logger.error(f"Unknown task type: {task.task_type}")
                return False

        except Exception as e:
            logger.error(f"❌ Error processing task {task.task_type.value}: {e}")
            return False

    def get_queue_size(self) -> int:
        """Получить текущий размер очереди"""
        return self._queue.qsize()

    async def execute_task_and_wait(
        self,
        task_type: TaskType,
        uuid: str,
        short_id: Optional[str] = None,
        email: Optional[str] = None,
        timeout: float = 30.0,
    ) -> bool:
        """
        Выполнить задачу и дождаться результата

        Args:
            task_type: Тип задачи
            uuid: UUID пользователя
            short_id: Short ID пользователя (опционально)
            email: Email пользователя (опционально)
            timeout: Таймаут ожидания в секундах (по умолчанию 30)

        Returns:
            True если успешно, False в противном случае

        Raises:
            asyncio.TimeoutError: Если задача не выполнена за указанное время
        """
        # Проверяем, запущена ли очередь
        if not self._is_running:
            logger.warning(
                "⚠️  Task queue is not running, executing task synchronously as fallback"
            )
            # Если очередь не запущена, выполняем задачу напрямую
            from api.xray_config import XrayConfigManager

            config_manager = XrayConfigManager()
            if task_type == TaskType.ADD_USER:
                if not short_id:
                    logger.error("Short ID is required for ADD_USER task")
                    return False
                return config_manager.add_user_to_config(
                    uuid=uuid, short_id=short_id, email=email
                )
            elif task_type == TaskType.REMOVE_USER:
                if not short_id:
                    logger.error("Short ID is required for REMOVE_USER task")
                    return False
                return config_manager.remove_user_from_config(
                    uuid=uuid, short_id=short_id
                )
            else:
                logger.error(f"Unknown task type: {task_type}")
                return False

        # Создаем Future для ожидания результата
        task_id = f"{task_type.value}_{uuid}"
        future: asyncio.Future[bool] = asyncio.Future()
        self._pending_futures[task_id] = future

        try:
            # Добавляем задачу в очередь
            await self.add_task(
                task_type=task_type, uuid=uuid, short_id=short_id, email=email
            )

            # Ждем результата с таймаутом
            try:
                success = await asyncio.wait_for(future, timeout=timeout)
                logger.debug(
                    f"✅ Task {task_type.value} for UUID {uuid[:8]}... completed with result: {success}"
                )
                return success
            except asyncio.TimeoutError:
                # Удаляем Future из словаря при таймауте
                self._pending_futures.pop(task_id, None)
                logger.error(
                    f"❌ Timeout waiting for task {task_type.value} for UUID {uuid[:8]}... "
                    f"(timeout: {timeout}s)"
                )
                raise

        except Exception as e:
            # Удаляем Future из словаря при ошибке
            self._pending_futures.pop(task_id, None)
            logger.error(f"❌ Error executing task {task_type.value}: {e}")
            raise


# Глобальный экземпляр очереди задач
config_task_queue = ConfigTaskQueue()
