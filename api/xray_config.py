"""Управление конфигурацией Xray"""
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
from config.settings import settings

logger = logging.getLogger(__name__)


class XrayConfigManager:
    """Менеджер для управления конфигурацией Xray"""

    def __init__(
        self, config_path: Optional[str] = None, xray_binary_path: Optional[str] = None
    ):
        self.config_path = config_path or settings.xray_config_path
        self.config_file = Path(self.config_path)
        self.xray_binary_path = xray_binary_path or "/usr/local/bin/xray"

    def load_config(self) -> dict:
        """Загрузка конфигурации Xray из файла"""
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading Xray config: {e}")
            raise

    def validate_json(self, config: dict) -> Tuple[bool, Optional[str]]:
        """
        Валидация JSON структуры конфигурации

        Args:
            config: Словарь с конфигурацией

        Returns:
            Кортеж (is_valid, error_message)
        """
        try:
            # Проверяем, что это словарь
            if not isinstance(config, dict):
                return False, "Configuration must be a dictionary"

            # Проверяем базовую структуру Xray конфигурации
            if "inbounds" not in config and "outbounds" not in config:
                return False, "Configuration must contain 'inbounds' or 'outbounds'"

            # Пытаемся сериализовать в JSON для проверки валидности
            json.dumps(config)

            return True, None
        except (TypeError, ValueError) as e:
            return False, f"Invalid JSON structure: {e}"
        except Exception as e:
            return False, f"Validation error: {e}"

    def test_config(self, config: dict) -> Tuple[bool, Optional[str]]:
        """
        Проверка конфигурации через xray -test -config

        Args:
            config: Словарь с конфигурацией для проверки

        Returns:
            Кортеж (is_valid, error_message)
        """
        # Проверяем наличие бинарника xray
        xray_binary = Path(self.xray_binary_path)
        if not xray_binary.exists():
            logger.warning(
                f"⚠️  Xray binary not found at {self.xray_binary_path}, skipping config test"
            )
            return True, None  # Пропускаем проверку, если xray не установлен

        try:
            # Создаем временный файл с конфигурацией
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as tmp_file:
                json.dump(config, tmp_file, indent=2, ensure_ascii=False)
                tmp_config_path = tmp_file.name

            try:
                # Запускаем xray -test -config
                result = subprocess.run(
                    [self.xray_binary_path, "-test", "-config", tmp_config_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    logger.debug("✅ Configuration test passed")
                    return True, None
                else:
                    error_msg = result.stderr or result.stdout or "Unknown error"
                    logger.error(f"❌ Configuration test failed: {error_msg}")
                    return False, error_msg
            finally:
                # Удаляем временный файл
                Path(tmp_config_path).unlink(missing_ok=True)

        except subprocess.TimeoutExpired:
            logger.error("❌ Configuration test timed out")
            return False, "Configuration test timed out"
        except FileNotFoundError:
            logger.warning(
                f"⚠️  Xray binary not found at {self.xray_binary_path}, skipping config test"
            )
            return True, None  # Пропускаем проверку, если xray не установлен
        except Exception as e:
            logger.error(f"❌ Error testing configuration: {e}")
            return False, str(e)

    def save_config(
        self, config: dict, validate: bool = True, test: bool = True
    ) -> bool:
        """
        Сохранение конфигурации Xray в файл с валидацией

        Args:
            config: Словарь с конфигурацией
            validate: Выполнять валидацию JSON перед сохранением
            test: Выполнять проверку через xray -test -config перед сохранением

        Returns:
            True если успешно, False в противном случае
        """
        try:
            # Валидация JSON структуры
            if validate:
                is_valid, error_msg = self.validate_json(config)
                if not is_valid:
                    logger.error(f"❌ JSON validation failed: {error_msg}")
                    return False
                logger.debug("✅ JSON validation passed")

            # Проверка конфигурации через xray -test -config
            if test:
                is_valid, error_msg = self.test_config(config)
                if not is_valid:
                    logger.error(f"❌ Configuration test failed: {error_msg}")
                    return False
                logger.debug("✅ Configuration test passed")

            # Создаем резервную копию
            backup_path = self.config_file.with_suffix(".json.backup")
            if self.config_file.exists():
                import shutil

                shutil.copy2(self.config_file, backup_path)
                logger.debug(f"Backup created: {backup_path}")

            # Сохраняем новую конфигурацию
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Xray config saved to {self.config_path}")
            return True
        except (TypeError, ValueError) as e:
            logger.error(f"❌ JSON encoding error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error saving Xray config: {e}")
            return False

    def ensure_common_short_id(self, common_short_id: str) -> bool:
        """
        Убедиться, что общий short_id присутствует в конфигурации Xray

        Args:
            common_short_id: Общий short_id для всех пользователей

        Returns:
            True если успешно, False в противном случае
        """
        try:
            config = self.load_config()

            # Находим VLESS inbound
            vless_inbound = None
            for inbound in config.get("inbounds", []):
                if inbound.get("protocol") == "vless":
                    vless_inbound = inbound
                    break

            if not vless_inbound:
                logger.error("VLESS inbound not found in Xray config")
                return False

            # Проверяем и обновляем shortIds в realitySettings
            stream_settings = vless_inbound.get("streamSettings", {})
            if "realitySettings" not in stream_settings:
                stream_settings["realitySettings"] = {}

            reality_settings = stream_settings["realitySettings"]
            short_ids = reality_settings.get("shortIds", [])

            if common_short_id not in short_ids:
                short_ids.append(common_short_id)
                reality_settings["shortIds"] = short_ids
                stream_settings["realitySettings"] = reality_settings
                vless_inbound["streamSettings"] = stream_settings
                logger.info(
                    f"✅ Added common short_id '{common_short_id}' to Xray config"
                )

                # Сохраняем конфигурацию
                if self.save_config(config):
                    logger.info(
                        f"✅ Common short_id '{common_short_id}' configured in Xray"
                    )
                    return True
                else:
                    logger.error("Failed to save Xray config with common short_id")
                    return False
            else:
                logger.debug(f"Common short_id '{common_short_id}' already in config")
                return True

        except Exception as e:
            logger.error(f"Error ensuring common short_id: {e}")
            return False

    def add_user_to_config(
        self, uuid: str, short_id: str, email: Optional[str] = None, reload: bool = True
    ) -> bool:
        """
        Добавление пользователя в конфигурацию Xray

        Args:
            uuid: UUID пользователя
            short_id: Short ID пользователя (не используется, оставлен для совместимости)
            email: Email/идентификатор пользователя (опционально)
            reload: Перезагрузить конфигурацию Xray после добавления (по умолчанию True, использует SIGHUP для graceful reload без прерывания соединений)

        Returns:
            True если успешно, False в противном случае
        """
        try:
            config = self.load_config()

            # Находим VLESS inbound
            vless_inbound = None
            for inbound in config.get("inbounds", []):
                if inbound.get("protocol") == "vless":
                    vless_inbound = inbound
                    break

            if not vless_inbound:
                logger.error("VLESS inbound not found in Xray config")
                return False

            # Убеждаемся, что общий short_id присутствует в конфигурации
            common_short_id = settings.reality_common_short_id
            self.ensure_common_short_id(common_short_id)

            # Проверяем, есть ли уже такой пользователь
            clients = vless_inbound["settings"].get("clients", [])
            if any(client.get("id") == uuid for client in clients):
                logger.info(f"User {uuid[:8]}... already exists in config")
            else:
                # Добавляем пользователя
                if not email:
                    email = f"user_{uuid[:8]}"

                new_client = {"id": uuid, "flow": "none", "email": email}
                clients.append(new_client)
                vless_inbound["settings"]["clients"] = clients
                logger.info(f"Added user {uuid[:8]}... to Xray config")

            # НЕ добавляем Short ID в realitySettings - используем общий short_id для всех
            # Общий short_id должен быть уже настроен в конфигурации Xray
            # Это позволяет избежать перезагрузки Xray при создании/удалении ключей
            logger.info(
                f"User {uuid[:8]}... added to Xray config (using common short_id)"
            )

            # Сохраняем конфигурацию (только для UUID, short_id не меняется)
            if self.save_config(config):
                logger.info(f"User {uuid[:8]}... added to Xray config")
                # UUID уже добавлен через Xray API 'adu' - работает сразу
                # Общий short_id уже настроен в конфигурации - не требует изменений
                # Перезагрузка НЕ нужна - ключ работает сразу!
                logger.info(
                    f"✅ Key is ready immediately (UUID via API, common short_id in config)"
                )
                return True
            else:
                logger.error("Failed to save Xray config")
                return False

        except Exception as e:
            logger.error(f"Error adding user to Xray config: {e}")
            return False

    def remove_user_from_config(
        self, uuid: str, short_id: str, reload: bool = True
    ) -> bool:
        """
        Удаление пользователя из конфигурации Xray

        Args:
            uuid: UUID пользователя
            short_id: Short ID пользователя (не используется, оставлен для совместимости)

        Returns:
            True если успешно, False в противном случае
        """
        try:
            config = self.load_config()

            # Находим VLESS inbound
            vless_inbound = None
            for inbound in config.get("inbounds", []):
                if inbound.get("protocol") == "vless":
                    vless_inbound = inbound
                    break

            if not vless_inbound:
                logger.error("VLESS inbound not found in Xray config")
                return False

            # Удаляем пользователя из clients
            clients = vless_inbound["settings"].get("clients", [])
            original_count = len(clients)
            clients = [c for c in clients if c.get("id") != uuid]
            vless_inbound["settings"]["clients"] = clients

            if len(clients) < original_count:
                logger.info(f"Removed user {uuid[:8]}... from Xray config")

            # НЕ удаляем Short ID из realitySettings - используем общий short_id для всех
            # Общий short_id остается в конфигурации для других пользователей
            # Это позволяет избежать перезагрузки Xray при удалении ключей
            logger.info(
                f"User {uuid[:8]}... removed from Xray config (common short_id preserved)"
            )

            # Сохраняем конфигурацию (только для UUID, short_id не меняется)
            if self.save_config(config):
                logger.info(f"User {uuid[:8]}... removed from Xray config")
                # UUID уже удален через Xray API 'rmu' - удален сразу
                # Общий short_id остается в конфигурации - не требует изменений
                # Перезагрузка НЕ нужна!
                logger.info(
                    f"✅ Key removed immediately (UUID via API, common short_id preserved)"
                )
                return True
            else:
                logger.error("Failed to save Xray config")
                return False

        except Exception as e:
            logger.error(f"Error removing user from Xray config: {e}")
            return False

    def reload_config(self) -> bool:
        """
        Graceful перезагрузка конфигурации Xray

        Использует комбинацию методов для гарантированного применения изменений:
        1. Сначала пробует SIGHUP (если поддерживается)
        2. Если не работает, использует graceful restart процесса

        Returns:
            True если успешно, False в противном случае
        """
        try:
            import signal
            import os
            import time

            # Ищем процесс Xray
            result = subprocess.run(
                ["pgrep", "-f", "/usr/local/bin/xray"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                pid = int(result.stdout.strip().split("\n")[0])
                logger.info(f"Found Xray process with PID: {pid}")

                # Метод 1: Пробуем SIGHUP (может не работать для всех типов изменений)
                try:
                    os.kill(pid, signal.SIGHUP)
                    logger.info(f"✅ Sent SIGHUP to Xray process {pid}")
                    time.sleep(2)  # Даем больше времени на применение изменений

                    # Проверяем, что процесс все еще работает
                    check_result = subprocess.run(
                        ["pgrep", "-f", "/usr/local/bin/xray"],
                        capture_output=True,
                        text=True,
                    )

                    if check_result.returncode == 0:
                        logger.info(f"✅ Xray process still running after SIGHUP")
                        # SIGHUP отправлен, но Xray может не применять изменения для shortIds
                        # Используем graceful restart для гарантированного применения
                        logger.info(
                            f"⚠️  Note: SIGHUP may not apply shortIds changes, using graceful restart for reliability"
                        )
                        return self._restart_xray()
                    else:
                        logger.warning(
                            f"⚠️  Xray process terminated after SIGHUP, restarting..."
                        )
                        # Процесс завершился, нужно перезапустить
                        return self._restart_xray()

                except ProcessLookupError:
                    logger.warning(f"Xray process {pid} not found, restarting...")
                    return self._restart_xray()
                except PermissionError:
                    logger.warning(f"No permission to send signal to process {pid}")
                    return False
            else:
                logger.warning("Xray process not found, starting...")
                return self._start_xray()

        except Exception as e:
            logger.error(f"Error reloading Xray config: {e}")
            return False

    def _restart_xray(self) -> bool:
        """Graceful restart Xray процесса"""
        try:
            import signal
            import os
            import time

            # Находим процесс
            result = subprocess.run(
                ["pgrep", "-f", "/usr/local/bin/xray"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                pid = int(result.stdout.strip().split("\n")[0])
                # Отправляем SIGTERM для graceful shutdown
                os.kill(pid, signal.SIGTERM)
                logger.info(
                    f"✅ Sent SIGTERM to Xray process {pid} for graceful shutdown"
                )

                # Ждем завершения процесса
                for i in range(10):
                    time.sleep(0.5)
                    check_result = subprocess.run(
                        ["pgrep", "-f", "/usr/local/bin/xray"],
                        capture_output=True,
                        text=True,
                    )
                    if check_result.returncode != 0:
                        break
                else:
                    # Процесс не завершился, принудительно
                    logger.warning(
                        f"⚠️  Xray process did not terminate, sending SIGKILL"
                    )
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

            # Запускаем заново
            return self._start_xray()

        except Exception as e:
            logger.error(f"Error restarting Xray: {e}")
            return False

    def _start_xray(self) -> bool:
        """Запуск Xray процесса"""
        try:
            import subprocess
            import os

            xray_binary = self.xray_binary_path
            config_path = self.config_path

            if not os.path.exists(xray_binary):
                logger.error(f"Xray binary not found at {xray_binary}")
                return False

            # Запускаем в фоне
            process = subprocess.Popen(
                [xray_binary, "-config", config_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            logger.info(f"✅ Started Xray process (PID: {process.pid})")
            return True

        except Exception as e:
            logger.error(f"Error starting Xray: {e}")
            return False
