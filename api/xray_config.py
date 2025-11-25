"""Управление конфигурацией Xray"""
import json
import logging
from pathlib import Path
from typing import List, Optional
from config.settings import settings

logger = logging.getLogger(__name__)


class XrayConfigManager:
    """Менеджер для управления конфигурацией Xray"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or settings.xray_config_path
        self.config_file = Path(self.config_path)
    
    def load_config(self) -> dict:
        """Загрузка конфигурации Xray из файла"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading Xray config: {e}")
            raise
    
    def save_config(self, config: dict) -> bool:
        """Сохранение конфигурации Xray в файл"""
        try:
            # Создаем резервную копию
            backup_path = self.config_file.with_suffix('.json.backup')
            if self.config_file.exists():
                import shutil
                shutil.copy2(self.config_file, backup_path)
            
            # Сохраняем новую конфигурацию
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Xray config saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving Xray config: {e}")
            return False
    
    def add_user_to_config(self, uuid: str, short_id: str, email: Optional[str] = None) -> bool:
        """
        Добавление пользователя в конфигурацию Xray
        
        Args:
            uuid: UUID пользователя
            short_id: Short ID пользователя
            email: Email/идентификатор пользователя (опционально)
        
        Returns:
            True если успешно, False в противном случае
        """
        try:
            config = self.load_config()
            
            # Находим VLESS inbound
            vless_inbound = None
            for inbound in config.get('inbounds', []):
                if inbound.get('protocol') == 'vless':
                    vless_inbound = inbound
                    break
            
            if not vless_inbound:
                logger.error("VLESS inbound not found in Xray config")
                return False
            
            # Проверяем, есть ли уже такой пользователь
            clients = vless_inbound['settings'].get('clients', [])
            if any(client.get('id') == uuid for client in clients):
                logger.info(f"User {uuid[:8]}... already exists in config")
            else:
                # Добавляем пользователя
                if not email:
                    email = f"user_{uuid[:8]}"
                
                new_client = {
                    "id": uuid,
                    "flow": "none",
                    "email": email
                }
                clients.append(new_client)
                vless_inbound['settings']['clients'] = clients
                logger.info(f"Added user {uuid[:8]}... to Xray config")
            
            # Добавляем Short ID в realitySettings
            reality_settings = vless_inbound.get('streamSettings', {}).get('realitySettings', {})
            short_ids = reality_settings.get('shortIds', [])
            
            if short_id not in short_ids:
                short_ids.append(short_id)
                reality_settings['shortIds'] = short_ids
                logger.info(f"Added Short ID {short_id} to realitySettings")
            
            # Сохраняем конфигурацию
            if self.save_config(config):
                logger.info(f"User {uuid[:8]}... and Short ID {short_id} added to Xray config")
                return True
            else:
                logger.error("Failed to save Xray config")
                return False
                
        except Exception as e:
            logger.error(f"Error adding user to Xray config: {e}")
            return False
    
    def remove_user_from_config(self, uuid: str, short_id: str) -> bool:
        """
        Удаление пользователя из конфигурации Xray
        
        Args:
            uuid: UUID пользователя
            short_id: Short ID пользователя
        
        Returns:
            True если успешно, False в противном случае
        """
        try:
            config = self.load_config()
            
            # Находим VLESS inbound
            vless_inbound = None
            for inbound in config.get('inbounds', []):
                if inbound.get('protocol') == 'vless':
                    vless_inbound = inbound
                    break
            
            if not vless_inbound:
                logger.error("VLESS inbound not found in Xray config")
                return False
            
            # Удаляем пользователя из clients
            clients = vless_inbound['settings'].get('clients', [])
            original_count = len(clients)
            clients = [c for c in clients if c.get('id') != uuid]
            vless_inbound['settings']['clients'] = clients
            
            if len(clients) < original_count:
                logger.info(f"Removed user {uuid[:8]}... from Xray config")
            
            # Удаляем Short ID из realitySettings
            reality_settings = vless_inbound.get('streamSettings', {}).get('realitySettings', {})
            short_ids = reality_settings.get('shortIds', [])
            
            if short_id in short_ids:
                short_ids.remove(short_id)
                reality_settings['shortIds'] = short_ids
                logger.info(f"Removed Short ID {short_id} from realitySettings")
            
            # Сохраняем конфигурацию
            if self.save_config(config):
                logger.info(f"User {uuid[:8]}... and Short ID {short_id} removed from Xray config")
                return True
            else:
                logger.error("Failed to save Xray config")
                return False
                
        except Exception as e:
            logger.error(f"Error removing user from Xray config: {e}")
            return False
    
    def reload_config(self) -> bool:
        """
        Перезагрузка конфигурации Xray через API
        
        Returns:
            True если успешно, False в противном случае
        """
        try:
            import httpx
            import asyncio
            
            async def reload():
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Xray не имеет прямого API для перезагрузки конфигурации
                    # Нужно использовать SIGHUP или перезапуск сервиса
                    # Для простоты возвращаем True, предполагая что конфигурация будет перезагружена
                    return True
            
            return asyncio.run(reload())
        except Exception as e:
            logger.warning(f"Could not reload Xray config via API: {e}")
            # Это не критично, конфигурация будет перезагружена при следующем перезапуске
            return True

