"""Клиент для работы с Xray API"""
import httpx
import json
import subprocess
from typing import Dict, Any, Optional
from config.settings import settings
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_result,
    RetryCallState,
)

logger = logging.getLogger(__name__)


class XrayClient:
    """Клиент для взаимодействия с Xray API"""

    def __init__(self):
        self.base_url = f"http://{settings.xray_api_host}:{settings.xray_api_port}"
        self.timeout = 10.0
        self._is_available = None  # Кэш статуса доступности

    async def check_health(self) -> bool:
        """
        Проверка доступности Xray API

        Использует statsquery команду для проверки доступности API,
        так как это самый надежный способ проверить работу Xray API

        Returns:
            True если API доступен, False в противном случае
        """
        try:
            # Используем statsquery для проверки доступности API
            # Это более надежно, чем HTTP запросы, так как использует тот же механизм,
            # что и реальные операции
            server = f"{settings.xray_api_host}:{settings.xray_api_port}"
            cmd = ["/usr/local/bin/xray", "api", "statsquery", f"--server={server}"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                self._is_available = True
                logger.debug(f"✅ Xray API is available at {self.base_url}")
                return True
            else:
                self._is_available = False
                logger.warning(
                    f"⚠️  Xray API health check failed: "
                    f"statsquery returned code {result.returncode}, stderr: {result.stderr}"
                )
                return False

        except subprocess.TimeoutExpired:
            self._is_available = False
            logger.warning(
                f"⚠️  Xray API is not available: Timeout connecting to {self.base_url} "
                f"(timeout: 5s)"
            )
            return False
        except FileNotFoundError:
            self._is_available = False
            logger.warning(
                f"⚠️  Xray API health check failed: Xray binary not found at /usr/local/bin/xray"
            )
            return False
        except Exception as e:
            self._is_available = False
            logger.warning(f"⚠️  Xray API health check failed: {type(e).__name__}: {e}")
            return False

    def is_available(self) -> Optional[bool]:
        """
        Возвращает кэшированный статус доступности API

        Returns:
            True/False если проверка была выполнена, None если еще не проверяли
        """
        return self._is_available

    async def _add_user_internal(
        self, uuid: str, email: str, flow: str = "none"
    ) -> bool:
        """
        Внутренний метод добавления пользователя в Xray через API (без retry)
        Использует CLI команду xray api adu

        Args:
            uuid: UUID пользователя
            email: Email/идентификатор пользователя
            flow: Flow для VLESS (none или xtls-rprx-vision)

        Returns:
            True если успешно, False в противном случае
        """
        import tempfile
        import os

        # Создаем временный JSON файл с конфигурацией пользователя
        # Формат должен соответствовать структуре inbound из Xray
        user_config = {
            "inbounds": [
                {
                    "tag": "vless-reality",
                    "protocol": "vless",
                    "port": 443,
                    "settings": {
                        "clients": [
                            {
                                "id": uuid,
                                "flow": flow,
                                "email": email
                            }
                        ],
                        "decryption": "none"
                    }
                }
            ]
        }

        try:
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as tmp_file:
                json.dump(user_config, tmp_file, indent=2)
                tmp_config_path = tmp_file.name

            try:
                # Выполняем CLI команду для добавления пользователя
                server = f"{settings.xray_api_host}:{settings.xray_api_port}"
                cmd = [
                    "/usr/local/bin/xray",
                    "api",
                    "adu",
                    f"--server={server}",
                    f"--timeout={int(self.timeout)}",
                    tmp_config_path
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )

                if result.returncode == 0:
                    logger.info(
                        f"✅ User {uuid[:8]}... (email: {email}) added successfully to Xray via API"
                    )
                    return True
                else:
                    error_msg = result.stderr or result.stdout or "Unknown error"
                    logger.error(
                        f"❌ Failed to add user {uuid[:8]}... via Xray API: {error_msg}"
                    )
                    raise Exception(f"Xray API error: {error_msg}")

            finally:
                # Удаляем временный файл
                if os.path.exists(tmp_config_path):
                    os.unlink(tmp_config_path)

        except subprocess.TimeoutExpired:
            logger.error(
                f"❌ Timeout adding user {uuid[:8]}... via Xray API (timeout: {self.timeout}s)"
            )
            raise
        except Exception as e:
            logger.error(f"❌ Error adding user {uuid[:8]}... via Xray API: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (subprocess.TimeoutExpired, FileNotFoundError)
        ),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            f"🔄 Retrying add_user (attempt {retry_state.attempt_number}/3) "
            f"for UUID {retry_state.args[0][:8] if retry_state.args and len(retry_state.args) > 0 else 'unknown'}... "
            f"after {retry_state.next_action.sleep if retry_state.next_action else 0} seconds"
        )
        if retry_state.attempt_number < 3
        else None,
    )
    async def add_user(self, uuid: str, email: str, flow: str = "none") -> bool:
        """
        Добавление пользователя в Xray через API с retry механизмом

        Args:
            uuid: UUID пользователя
            email: Email/идентификатор пользователя (используем UUID)
            flow: Flow для VLESS (none или xtls-rprx-vision)

        Returns:
            True если успешно, False в противном случае
        """
        # Проверяем доступность API перед операцией
        if not await self.check_health():
            logger.warning(
                f"⚠️  Cannot add user {uuid[:8]}... to Xray: API is not available. "
                f"User will be added to config file only and will be available after Xray restart."
            )
            return False

        try:
            return await self._add_user_internal(uuid, email, flow)
        except subprocess.TimeoutExpired:
            logger.error(
                f"❌ Timeout adding user {uuid[:8]}... to Xray API after retries. "
                f"Xray API did not respond within {self.timeout}s"
            )
            return False
        except FileNotFoundError:
            logger.error(
                f"❌ Xray binary not found at /usr/local/bin/xray. "
                f"Cannot add user {uuid[:8]}... via API"
            )
            return False
        except Exception as e:
            logger.error(
                f"❌ Error adding user {uuid[:8]}... to Xray API: {type(e).__name__}: {e}"
            )
            return False

    async def _remove_user_internal(self, email: str) -> bool:
        """
        Внутренний метод удаления пользователя из Xray через API (без retry)
        Использует CLI команду xray api rmu

        Args:
            email: Email/идентификатор пользователя

        Returns:
            True если успешно, False в противном случае
        """
        try:
            # Выполняем CLI команду для удаления пользователя
            server = f"{settings.xray_api_host}:{settings.xray_api_port}"
            cmd = [
                "/usr/local/bin/xray",
                "api",
                "rmu",
                f"--server={server}",
                f"--timeout={int(self.timeout)}",
                "--tag=vless-reality",
                email
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0:
                logger.info(f"✅ User {email} removed successfully from Xray via API")
                return True
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                # Если пользователь не найден, это не критичная ошибка
                if "not found" in error_msg.lower() or "no such" in error_msg.lower():
                    logger.warning(
                        f"⚠️  User {email} not found in Xray (may have been already removed)"
                    )
                    return True  # Возвращаем True, так как цель достигнута
                logger.error(
                    f"❌ Failed to remove user {email} via Xray API: {error_msg}"
                )
                raise Exception(f"Xray API error: {error_msg}")

        except subprocess.TimeoutExpired:
            logger.error(
                f"❌ Timeout removing user {email} via Xray API (timeout: {self.timeout}s)"
            )
            raise
        except Exception as e:
            logger.error(f"❌ Error removing user {email} via Xray API: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (subprocess.TimeoutExpired, FileNotFoundError)
        ),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            f"🔄 Retrying remove_user (attempt {retry_state.attempt_number}/3) "
            f"for email {retry_state.args[0] if retry_state.args and len(retry_state.args) > 0 else 'unknown'} "
            f"after {retry_state.next_action.sleep if retry_state.next_action else 0} seconds"
        )
        if retry_state.attempt_number < 3
        else None,
    )
    async def remove_user(self, email: str) -> bool:
        """
        Удаление пользователя из Xray через API с retry механизмом

        Args:
            email: Email/идентификатор пользователя

        Returns:
            True если успешно, False в противном случае
        """
        # Проверяем доступность API перед операцией
        if not await self.check_health():
            logger.warning(
                f"⚠️  Cannot remove user {email} from Xray: API is not available. "
                f"User will be removed from config file only."
            )
            return False

        try:
            return await self._remove_user_internal(email)
        except subprocess.TimeoutExpired:
            logger.error(
                f"❌ Timeout removing user {email} from Xray API after retries. "
                f"Xray API did not respond within {self.timeout}s"
            )
            return False
        except FileNotFoundError:
            logger.error(
                f"❌ Xray binary not found at /usr/local/bin/xray. "
                f"Cannot remove user {email} via API"
            )
            return False
        except Exception as e:
            logger.error(
                f"❌ Error removing user {email} from Xray API: {type(e).__name__}: {e}"
            )
            return False

    async def get_stats(self, email: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение статистики трафика из Xray через CLI команду

        Args:
            email: Email пользователя (опционально, если None - статистика всех пользователей)

        Returns:
            Словарь со статистикой
        """
        try:
            # Используем встроенную CLI команду Xray для получения статистики
            # Формат: xray api statsquery --server=127.0.0.1:10085 [--pattern="user>>>email>>>"]
            server = f"{settings.xray_api_host}:{settings.xray_api_port}"
            cmd = ["/usr/local/bin/xray", "api", "statsquery", f"--server={server}"]

            # Если указан email, фильтруем по паттерну
            if email:
                pattern = f"user>>>{email}>>>"
                cmd.extend(["--pattern", pattern])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0 and result.stdout.strip():
                try:
                    stats_data = json.loads(result.stdout)
                    return stats_data
                except json.JSONDecodeError:
                    # Если не JSON, возможно пустой ответ
                    logger.warning(f"Empty or invalid JSON response from Xray API")
                    return {"stat": []}
            else:
                logger.error(
                    f"Failed to get stats: returncode={result.returncode}, stderr={result.stderr}"
                )
                return {}

        except subprocess.TimeoutExpired:
            logger.error("Timeout getting stats from Xray")
            return {}
        except FileNotFoundError:
            logger.error("Xray binary not found at /usr/local/bin/xray")
            return {}
        except Exception as e:
            logger.error(f"Error getting stats from Xray: {e}")
            return {}

    async def get_user_stats(self, email: str) -> Dict[str, int]:
        """
        Получение статистики трафика для конкретного пользователя

        Args:
            email: Email/идентификатор пользователя

        Returns:
            Словарь с upload и download в байтах
        """
        stats = await self.get_stats(email)

        upload = 0
        download = 0

        # Xray возвращает статистику в формате:
        # {"stat": [{"name": "user>>>email>>>uplink", "value": 12345}, ...]}
        if "stat" in stats:
            for stat_item in stats["stat"]:
                name = stat_item.get("name", "")
                value = stat_item.get("value", 0)

                if f">>>{email}>>>" in name:
                    if "uplink" in name:
                        upload += value
                    elif "downlink" in name:
                        download += value

        return {"upload": upload, "download": download}
