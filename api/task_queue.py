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
                if task:
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


# Глобальный экземпляр очереди задач
config_task_queue = ConfigTaskQueue()
