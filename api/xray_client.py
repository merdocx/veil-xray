"""Клиент для работы с Xray API"""
import httpx
import json
import subprocess
from typing import Dict, Any, Optional
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class XrayClient:
    """Клиент для взаимодействия с Xray API"""
    
    def __init__(self):
        self.base_url = f"http://{settings.xray_api_host}:{settings.xray_api_port}"
        self.timeout = 10.0
    
    async def add_user(self, uuid: str, email: str, flow: str = "none") -> bool:
        """
        Добавление пользователя в Xray через API
        
        Args:
            uuid: UUID пользователя
            email: Email/идентификатор пользователя (используем UUID)
            flow: Flow для VLESS (none или xtls-rprx-vision)
        
        Returns:
            True если успешно, False в противном случае
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "email": email,
                    "uuid": uuid,
                    "flow": flow
                }
                
                response = await client.post(
                    f"{self.base_url}/api/v1/users/add",
                    json=payload
                )
                
                if response.status_code == 200:
                    logger.info(f"User {uuid} added successfully to Xray")
                    return True
                else:
                    logger.error(f"Failed to add user {uuid}: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error adding user {uuid} to Xray: {e}")
            return False
    
    async def remove_user(self, email: str) -> bool:
        """
        Удаление пользователя из Xray через API
        
        Args:
            email: Email/идентификатор пользователя
        
        Returns:
            True если успешно, False в противном случае
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/users/remove",
                    json={"email": email}
                )
                
                if response.status_code == 200:
                    logger.info(f"User {email} removed successfully from Xray")
                    return True
                else:
                    logger.error(f"Failed to remove user {email}: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error removing user {email} from Xray: {e}")
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
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    stats_data = json.loads(result.stdout)
                    return stats_data
                except json.JSONDecodeError:
                    # Если не JSON, возможно пустой ответ
                    logger.warning(f"Empty or invalid JSON response from Xray API")
                    return {"stat": []}
            else:
                logger.error(f"Failed to get stats: returncode={result.returncode}, stderr={result.stderr}")
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
        
        return {
            "upload": upload,
            "download": download
        }


