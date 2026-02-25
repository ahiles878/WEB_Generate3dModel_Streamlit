"""
ComfyUI API Client Module
=========================

This module provides the ComfyUIClient class for interacting with the ComfyUI API
to generate images and 3D models using workflows.
"""

import streamlit as st
import requests
import json
import time
import os
import gdown
import re
import subprocess
import trimesh
import tempfile
import os

# Configuration settings loaded from secrets.toml
COMFYUI_URL = st.secrets["COMFYUI_URL"]
FOLDER_ID = st.secrets["FOLDER_ID"]

class ComfyUIClient:
    """Класс для работы с ComfyUI"""
    
    def __init__(self, base_url=None, timeout_generation: int = 180, timeout_3d: int = 760):
        #Инициализация класса ComfyUI.
        
        # Если передан base_url, используем его, иначе берем из secrets
        self.url_comfy = base_url if base_url is not None else COMFYUI_URL
        self.timeout_generation = timeout_generation
        self.timeout_3d = timeout_3d
        self.folder_id = FOLDER_ID
        self.current_prompt_id = None
        self.current_history = None
        
    def check_connection(self) -> bool:
        #Проверяет подключение к серверу ComfyUI.
        
        try:
            response = requests.get(f"{self.url_comfy}/history", timeout=10)
            if response.status_code == 200:
                # st.success(f"✅ Подключение к ComfyUI установлено: {self.url_comfy}")
                return True
            else:
                st.warning(f"⚠️ ComfyUI отвечает с кодом {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            st.error(f"❌ Не могу подключиться к ComfyUI по адресу {self.url_comfy}. Проверьте URL и соединение.")
            return False
        except requests.exceptions.Timeout:
            st.error(f"❌ Таймаут подключения к ComfyUI: {self.url_comfy}")
            return False
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Ошибка подключения к ComfyUI: {str(e)}")
            return False
        except Exception as e:
            st.error(f"❌ Неизвестная ошибка при подключении к ComfyUI: {str(e)}")
            return False
    
    def load_workflow(self, file_path: str) -> dict:
        #Загружает workflow из JSON файла и возврацает его в виде словаря
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                workflow = json.load(f)
                # st.success(f"✅ Workflow загружен из {file_path}")
                return workflow
        except FileNotFoundError:
            st.error(f"❌ Файл workflow не найден: {file_path}")
            return {}
        except json.JSONDecodeError as e:
            st.error(f"❌ Ошибка в формате JSON файла {file_path}: {str(e)}")
            return {}
        except Exception as e:
            st.error(f"❌ Не могу загрузить workflow {file_path}: {str(e)}")
            return {}
    
    def upload_image(self, image_path: str) -> str:
        #Загружает изображение в ComfyUI и возвращает имя файла.
        
        try:
            with open(image_path, 'rb') as f:
                files = {'image': f}
                response = requests.post(
                    f"{self.url_comfy}/upload/image",
                    files=files,
                    timeout=30
                )
            
            if response.status_code == 200:
                result = response.json()
                filename = result.get('name', '')
                #if filename:
                    # st.success(f"✅ Изображение загружено: {filename}")
                return filename
            else:
                st.error(f"❌ Ошибка загрузки изображения в ComfyUI: {response.text}")
                return ''
                
        except requests.exceptions.ConnectionError:
            st.error(f"❌ Не могу подключиться к ComfyUI по адресу {self.url_comfy} для загрузки изображения")
            return ''
        except requests.exceptions.Timeout:
            st.error(f"❌ Таймаут подключения к ComfyUI: {self.url_comfy}")
            return ''
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Ошибка подключения к ComfyUI: {str(e)}")
            return ''
        except Exception as e:
            st.error(f"❌ Ошибка при загрузке изображения: {str(e)}")
            return ''
    
    def run_workflow(self, workflow: dict, is_3d: bool = False) -> str:
        #Отправляет workflow в ComfyUI и возвращает id ответа

        try:
            # Проверяем, что workflow не пустой
            if not workflow:
                st.error("❌ Workflow пустой!")
                return ''
            
            timeout = self.timeout_3d if is_3d else self.timeout_generation
            
            response = requests.post(
                f"{self.url_comfy}/prompt",
                json={"prompt": workflow},
                timeout=30  # Таймаут на отправку запроса
            )
            
            if response.status_code == 200:
                data = response.json()
                prompt_id = data.get('prompt_id', '')
                if prompt_id:
                    self.current_prompt_id = prompt_id
                    task_type = "3D-модели" if is_3d else "изображений"
                    # st.info(f"🔄 Запущена генерация {task_type}. ID: {prompt_id[:8]}...")
                return prompt_id
            else:
                st.error(f"❌ Ошибка ComfyUI при запуске workflow: {response.text}")
                return ''
                
        except requests.exceptions.ConnectionError:
            st.error(f"❌ Не могу подключиться к ComfyUI по адресу {self.url_comfy}")
            st.info("📡 Убедись, что ComfyUI запущен и доступен по этому адресу.")
            return ''
        except requests.exceptions.Timeout:
            st.error(f"❌ Таймаут подключения к ComfyUI: {self.url_comfy}")
            return ''
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Ошибка подключения к ComfyUI: {str(e)}")
            return ''
        except Exception as e:
            st.error(f"❌ Ошибка при запуске workflow: {str(e)}")
            return ''
    
    def wait_for_completion_image(self, prompt_id: str = None, chat_messages=None) -> dict:
        #Ожидает завершения генерации и возвращает результат в виде словаря
        
        if prompt_id is None:
            if self.current_prompt_id:
                prompt_id = self.current_prompt_id
            else:
                st.error("❌ Не указан prompt_id и нет текущего промпта")
                return {}
        
        timeout = self.timeout_generation
        check_interval = 5  # Интервал проверки статуса
        start_time = time.time()
        
        task_type = "изображений"
        
        # Проверяем статус задания
        for attempt in range(int(timeout / check_interval)):
            try:
                # 1. ЗАПРАШИВАЕМ ИСТОРИЮ
                history_url = f"{self.url_comfy}/history/{prompt_id}"
                response = requests.get(history_url, timeout=10)
                
                if response.status_code != 200:
                    time.sleep(check_interval)
                    continue
                
                history_data = response.json()
                
                if prompt_id not in history_data:
                    time.sleep(check_interval)
                    continue
                
                task_data = history_data[prompt_id]
                status_info = task_data.get("status", {})
                status_str = status_info.get("status_str", "unknown")
                
                # 2. АНАЛИЗИРУЕМ СТАТУС
                with st.spinner(f"Проверка... Статус: {status_str}"):
                    
                    # СЛУЧАЙ 1: УСПЕШНО ВЫПОЛНЕНО
                    if status_str == "success" and status_info.get("completed", False):
                        # Для генерации изображений проверяем outputs как обычно
                        # 2A. Проверяем стандартные outputs для изображений
                        outputs = task_data.get("outputs", {})
                        if outputs:
                            # Ищем данные в outputs
                            for node_id, node_data in outputs.items():
                                if "images" in node_data and node_data["images"]:
                                    self.current_history = history_data
                                    # st.success(f"✅ Генерация {task_type} завершена!")
                                    return task_data
                                
                                if "files" in node_data and node_data["files"]:
                                    self.current_history = history_data
                                    st.success(f"✅ Генерация {task_type} завершена!")
                                    return task_data
                                
                                if 'images' in node_data and len(node_data['images']) > 0:
                                    for img_info in node_data['images']:
                                        if img_info.get('format') == 'stl' or img_info['filename'].lower().endswith('.stl'):
                                            self.current_history = history_data
                                            st.success(f"✅ Генерация {task_type} завершена!")
                                            return task_data
                        
                        # Если outputs пустые для изображений
                        st.info("Изображение сгенерировано, но данных в outputs нет.")
                        result_dict = {"status": "completed"}
                        return result_dict
                    
                    # СЛУЧАЙ 2: ВЫПОЛНЯЕТСЯ
                    elif status_str == "executing":
                        progress = status_info.get("progress", 0)
                        # st.progress(progress)
                        # st.info(f"🔄 Генерация... {progress*100:.1f}%")
                        
                        # Обновляем прогресс в чате
                        if chat_messages is not None:
                            # Обновляем последнее сообщение с прогрессом
                            if chat_messages:
                                last_msg_idx = len(chat_messages) - 1
                                if chat_messages[last_msg_idx]["role"] == "assistant":
                                    # Проверяем, содержит ли сообщение информацию о генерации изображения
                                    if "Генерация изображения..." in chat_messages[last_msg_idx]["content"]:
                                        chat_messages[last_msg_idx]["content"] = f"🔄 Генерация изображения... {progress*100:.1f}%"
                        
                        # Обновляем прогресс-бар в интерфейсе
                        st.progress(progress)
                    
                    # СЛУЧАЙ 3: В ОЧЕРЕДИ
                    elif status_str == "queued":
                        st.info("⏳ Задача в очереди...")
                    
                    # СЛУЧАЙ 4: ОШИБКА
                    elif status_str == "error":
                        error_msg = status_info.get("error", {}).get("message", "Неизвестная ошибка")
                        st.error(f"❌ Генерация {task_type} завершена с ошибкой: {error_msg}")
                        break
                    
                    # СЛУЧАЙ 5: ДРУГОЙ СТАТУС
                    else:
                        st.info(f"Статус: {status_str}")
                        break
                
                # 3. ЕСЛИ ЕЩЁ НЕ ГОТОВО - ЖДЁМ
                if status_str not in ["success", "error"]:
                    time.sleep(check_interval)
                    continue
                
            except requests.exceptions.ConnectionError:
                st.warning(f"⚠️ Нет подключения к ComfyUI: {self.url_comfy}. Повторяю попытку...")
                time.sleep(check_interval)
            except requests.exceptions.Timeout:
                st.warning(f"⚠️ Таймаут подключения к ComfyUI: {self.url_comfy}. Повторяю попытку...")
                time.sleep(check_interval)
            except requests.exceptions.RequestException as e:
                st.warning(f"⚠️ Проблема с подключением: {str(e)}. Повторяю попытку...")
                time.sleep(check_interval)
            except Exception as e:
                st.warning(f"⚠️ Неожиданная ошибка: {str(e)}. Продолжаю ожидание...")
                time.sleep(check_interval)
        
        # Таймаут
        st.warning(f"⏱️ Время ожидания генерации {task_type} истекло")
        return {}

    def wait_for_completion_model(self, prompt_id: str = None, chat_messages=None) -> dict:
        #Ожидает завершения генерации и возвращает результат в виде словаря
        
        if prompt_id is None:
            if self.current_prompt_id:
                prompt_id = self.current_prompt_id
            else:
                st.error("❌ Не указан prompt_id и нет текущего промпта")
                return {}
        
        timeout = self.timeout_3d
        check_interval = 5  # Интервал проверки статуса
        start_time = time.time()
        
        task_type = "3D моделей"
        
        # Проверяем статус задания
        for attempt in range(int(timeout / check_interval)):
            try:
                # 1. ЗАПРАШИВАЕМ ИСТОРИЮ
                history_url = f"{self.url_comfy}/history/{prompt_id}"
                response = requests.get(history_url, timeout=10)
                
                if response.status_code != 200:
                    time.sleep(check_interval)
                    continue
                
                history_data = response.json()
                
                if prompt_id not in history_data:
                    time.sleep(check_interval)
                    continue
                
                task_data = history_data[prompt_id]
                status_info = task_data.get("status", {})
                status_str = status_info.get("status_str", "unknown")
                
                # 2. АНАЛИЗИРУЕМ СТАТУС
                with st.spinner(f"Проверка... Статус: {status_str}"):
                    
                    # СЛУЧАЙ 1: УСПЕШНО ВЫПОЛНЕНО
                    if status_str == "success" and status_info.get("completed", False):
                        # Для 3D моделей сначала проверяем outputs, а затем вызываем скачивание модели из GDrive
                        self.current_history = history_data
                        # st.success(f"✅ Генерация {task_type} завершена!")
                        
                        # Если в outputs не найдена 3D модель, вызываем скачивание последней модели из Google Drive
                        # Модель будет скачиваться в функции generate_3d_from_image, поэтому здесь просто отмечаем статус
                        
                        result_dict = {"status": "completed"}
                        return result_dict
                    
                    # СЛУЧАЙ 2: ВЫПОЛНЯЕТСЯ
                    elif status_str == "executing":
                        progress = status_info.get("progress", 0)
                        # st.progress(progress)
                        # st.info(f"🔄 Генерация... {progress*100:.1f}%")
                        
                        # Обновляем прогресс в чате
                        if chat_messages is not None:
                            # Обновляем последнее сообщение с прогрессом
                            if chat_messages:
                                last_msg_idx = len(chat_messages) - 1
                                if chat_messages[last_msg_idx]["role"] == "assistant":
                                    # Проверяем, содержит ли сообщение информацию о генерации 3D модели
                                    if "Генерация 3D модели..." in chat_messages[last_msg_idx]["content"]:
                                        chat_messages[last_msg_idx]["content"] = f"🔄 Генерация 3D модели... {progress*100:.1f}%"
                        
                        # Обновляем прогресс-бар в интерфейсе
                        st.progress(progress)
                    
                    # СЛУЧАЙ 3: В ОЧЕРЕДИ
                    #elif status_str == "queued":
                        # st.info("⏳ Задача в очереди...")
                    
                    # СЛУЧАЙ 4: ОШИБКА
                    elif status_str == "error":
                        error_msg = status_info.get("error", {}).get("message", "Неизвестная ошибка")
                        st.error(f"❌ Генерация {task_type} завершена с ошибкой: {error_msg}")
                        return {"status": "error", "error_message": error_msg}
                    
                    # СЛУЧАЙ 5: ДРУГОЙ СТАТУС
                    else:
                        st.info(f"Статус: {status_str}")
                
                # 3. ЕСЛИ ЕЩЁ НЕ ГОТОВО - ЖДЁМ
                if status_str not in ["success", "error"]:
                    time.sleep(check_interval)
                    continue
                
            except requests.exceptions.ConnectionError:
                st.warning(f"⚠️ Нет подключения к ComfyUI: {self.url_comfy}. Повторяю попытку...")
                time.sleep(check_interval)
            except requests.exceptions.Timeout:
                st.warning(f"⚠️ Таймаут подключения к ComfyUI: {self.url_comfy}. Повторяю попытку...")
                time.sleep(check_interval)
            except requests.exceptions.RequestException as e:
                st.warning(f"⚠️ Проблема с подключением: {str(e)}. Повторяю попытку...")
                time.sleep(check_interval)
            except Exception as e:
                st.warning(f"⚠️ Неожиданная ошибка: {str(e)}. Продолжаю ожидание...")
                time.sleep(check_interval)
        
        # Таймаут
        st.warning(f"⏱️ Время ожидания генерации {task_type} истекло")
        return {"status": "timeout"}

    def get_image_urls(self, history_data: dict = None, prompt_id: str = None, max_images: int = 4) -> list:
        #Извлекает URL сгенерированных изображений из истории и возвращает их в виде списка.
        
        if history_data is None:
            if self.current_history:
                history_data = self.current_history
            else:
                st.warning("⚠️ Нет данных истории выполнения")
                return []
        
        if prompt_id is None:
            if self.current_prompt_id:
                prompt_id = self.current_prompt_id
            else:
                st.warning("⚠️ Не указан prompt_id")
                return []
        
        if prompt_id not in history_data:
            st.warning(f"⚠️ Prompt ID {prompt_id} не найден в истории")
            return []
        
        outputs = history_data[prompt_id].get('outputs', {})
        image_urls = []
        
        for node_id, node_data in outputs.items():
            if 'images' in node_data:
                for img in node_data['images']:
                    filename = img['filename']
                    # Формируем URL для доступа к изображению
                    image_url = f"{self.url_comfy}/view?filename={filename}&type=output"
                    image_urls.append(image_url)
                    
                    if len(image_urls) >= max_images:
                        break
        
        if image_urls:
            st.success(f"✅ Изображения готовы")
        else:
            st.warning("⚠️ Не удалось найти изображения в результатах")
            # Проверим, были ли какие-либо изображения в outputs, чтобы понять, что произошло
            if history_data and prompt_id in history_data:
                outputs = history_data[prompt_id].get('outputs', {})
                if outputs:
                    # Проверим, есть ли какие-либо изображения в outputs
                    has_any_images = False
                    for node_id, node_data in outputs.items():
                        if 'images' in node_data:
                            has_any_images = True
                            break
                    
                    if has_any_images:
                        st.info("ℹ️ Изображения обнаружены в результатах, но не удалось сформировать URL")
                    else:
                        st.info("ℹ️ В результатах не обнаружено изображений")
                    
                    st.info(f"ℹ️ Доступные ноды в результатах: {list(outputs.keys())}")
                else:
                    st.info("ℹ️ Ноды вывода отсутствуют в результатах")
        
        return image_urls[:max_images]
    
    def modify_workflow_prompt(self, workflow: dict, node_id: str, prompt_text: str) -> dict:
        #Модифицирует текст промпта в workflow.

        try:
            if node_id in workflow:
                workflow[node_id]["inputs"]["text"] = prompt_text
                # st.success(f"✅ Промпт в ноде {node_id} обновлён")
            else:
                st.warning(f"⚠️ Нода {node_id} не найдена в workflow")
            
            return workflow
        except Exception as e:
            st.error(f"❌ Ошибка при модификации workflow: {str(e)}")
            return workflow
    
    def modify_workflow_image_output(self, workflow: dict, node_id: str, image_filename: str) -> dict:
        #Модифицирует изображение в workflow для ноды Load Image (from Outputs).
        
        try:
            if node_id in workflow:
                # Для LoadImageOutput передаем имя файла в формате "filename [output]"
                output_filename = f"{image_filename} [output]"
                workflow[node_id]["inputs"]["image"] = output_filename
                # st.success(f"✅ Изображение в ноде {node_id} обновлено: {output_filename}")
            else:
                st.warning(f"⚠️ Нода {node_id} не найдена в workflow")
            
            return workflow
        except Exception as e:
            st.error(f"❌ Ошибка при модификации workflow изображением: {str(e)}")
            return workflow
        
    def clear_gdrive_folder(self, folder_id=None, file_extension=None):
        """Очищает папку Google Drive, удаляя файлы с указанным расширением или все файлы"""
        if folder_id is None:
            folder_id = self.folder_id
        
        try:
            import pickle
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            
            creds = None
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    st.error("❌ Не удалось получить доступ к Google Drive - токен авторизации недействителен")
                    return False
            
            service = build('drive', 'v3', credentials=creds)
            
            # Получаем список файлов в папке
            query = f"'{folder_id}' in parents"
            if file_extension:
                # Добавляем фильтр по расширению файла
                if file_extension.startswith('.'):
                    file_extension = file_extension[1:]
                query += f" and name contains '.{file_extension}'"
            
            results = service.files().list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name)"
            ).execute()
            items = results.get('files', [])
            
            if not items:
                st.info("📁 Папка Google Drive пуста или файлы не найдены")
                return True
            
            deleted_count = 0
            for file_item in items:
                try:
                    service.files().delete(fileId=file_item['id']).execute()
                    st.info(f"🗑️ Удален файл: {file_item['name']}")
                    deleted_count += 1
                except Exception as e:
                    st.warning(f"⚠️ Не удалось удалить файл {file_item['name']}: {str(e)}")
            
            st.success(f"✅ Удалено {deleted_count} файлов из папки Google Drive")
            return True
            
        except ImportError:
            st.error("❌ Для очистки папки Google Drive необходимо установить библиотеки Google API: pip install google-api-python-client google-auth-oauthlib google-auth")
            return False
        except Exception as e:
            st.error(f"❌ Ошибка при очистке папки Google Drive: {str(e)}")
            return False
    
    def _get_files_from_folder(self, folder_id, file_extension=""):
        """Получает список файлов из папки Google Drive с возможностью фильтрации по расширению"""
        # Используем Google Drive API для получения файлов
        # Для этого нам нужно получить токен доступа
        try:
            import pickle
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            
            creds = None
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # Если токены недоступны, возвращаем None - это нормально для резервного метода
                    return self._get_files_fallback(folder_id, file_extension)
            
            service = build('drive', 'v3', credentials=creds)
            
            # Поиск файлов в папке
            query = f"'{folder_id}' in parents"
            if file_extension:
                # Добавляем фильтр по расширению файла
                if file_extension.startswith('.'):
                    file_extension = file_extension[1:]
                query += f" and name contains '.{file_extension}'"
            
            results = service.files().list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)"
            ).execute()
            items = results.get('files', [])
            
            # Сортируем файлы по времени модификации (новые первыми)
            items.sort(key=lambda x: x.get('modifiedTime', ''), reverse=True)
            return items
            
        except ImportError:
            # Если модули Google API не установлены, используем резервный метод
            return self._get_files_fallback(folder_id, file_extension)
        except Exception as e:
            st.warning(f"⚠️ Ошибка при доступе к Google Drive API: {str(e)}. Использую резервный метод...")
            return self._get_files_fallback(folder_id, file_extension)
    
    def _get_files_fallback(self, folder_id, file_extension=""):
        """Резервный метод получения файлов из папки Google Drive через веб-скрапинг"""
        try:
            url = f"https://drive.google.com/drive/folders/{folder_id}"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            
            if response.status_code != 200:
                st.error("❌ Не удалось получить доступ к папке Google Drive")
                return []
            
            # Ищем информацию о файлах в HTML
            import re
            # Паттерн для поиска файлов в папке
            file_patterns = [
                r'<div[^>]*data-id="([a-zA-Z0-9_-]{25,})"[^>]*>.*?<a[^>]*>(.*?)</a>',
                r'"title":"([^"]+)".*?"id":"([a-zA-Z0-9_-]{25,})"',
                r'/file/d/([a-zA-Z0-9_-]+)/.*?">(.*?)</'
            ]
            
            files = []
            for pattern in file_patterns:
                matches = re.findall(pattern, response.text)
                for match in matches:
                    if len(match) == 2:
                        file_id, file_name = match
                    else:
                        file_name, file_id = match[1], match[0]
                    
                    # Фильтруем по расширению, если указано
                    if file_extension:
                        if not file_name.lower().endswith(file_extension.lower()):
                            continue
                    
                    files.append({'id': file_id, 'name': file_name})
                
                if files:
                    break
            
            # Убираем дубликаты и возвращаем
            unique_files = []
            seen_ids = set()
            for file in files:
                if file['id'] not in seen_ids:
                    unique_files.append(file)
                    seen_ids.add(file['id'])
            
            return unique_files
            
        except Exception as e:
            st.error(f"❌ Ошибка при получении файлов из Google Drive: {str(e)}")
            return []
    
    def get_latest_file_id(self, folder_id):
        """Извлекает ID последнего файла из папки Google Drive"""
        folder_id = self.folder_id
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code != 200:
            st.error("❌ Не удалось получить доступ к папке Google Drive")
            return None
        
        # Ищем все ID файлов в HTML
        file_ids = re.findall(r'data-id="([a-zA-Z0-9_-]{25,})"', response.text)
        
        if not file_ids:
            # Альтернативный паттерн
            file_ids = re.findall(r'"/file/d/([a-zA-Z0-9_-]+)/view"', response.text)
        
        if not file_ids:
            st.error("❌ Не найдено файлов в папке Google Drive")
            return None
        
        # Берем первый найденный (часто это последний)
        latest_id = file_ids[-1]
        # st.info(f"📄 Найден файл с ID: {latest_id}")
        return latest_id

    def download_latest_model_from_gdrive(self):
        """Скачивает последнюю модель из Google Drive в папку my_models"""
        # st.info("🔍 Ищу последний файл в папке Google Drive...")
        time.sleep(25)
        file_id = self.get_latest_file_id(FOLDER_ID)
        
        if file_id:
            # Создаем путь для сохранения
            download_path = "./3D_models"
            os.makedirs(download_path, exist_ok=True)

            # Формируем URL для скачивания
            file_url = f"https://drive.google.com/uc?id={file_id}"

            # Используем фиксированное имя файла
            filename = "model.glb"
            
            output_path = os.path.join(download_path, filename)
            
            # Удаляем старый файл, если он существует
            if os.path.exists(output_path):
                os.remove(output_path)
                
            self.ouput_path = output_path
            
            # st.info(f"⬇️  Скачиваю: {filename}")
            try:
                gdown.download(file_url, output_path, quiet=False)
                
                if os.path.exists(output_path):
                    size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    # st.success(f"✅ Скачан: {filename} ({size_mb:.1f} MB)")
                    return output_path
                else:
                    st.error(f"❌ Файл не был скачан: {output_path}")
                    return None
            except Exception as e:
                st.error(f"❌ Ошибка при скачивании файла: {str(e)}")
                return None
        else:
            st.error("❌ Не найден ID файла для скачивания")
            return None

    def convert_glb_to_stl(self, glb_path):
        """Конвертирует бинарные данные GLB в бинарные данные STL."""

        with open(glb_path, "rb") as f:
            glb_data_bytes = f.read()
        
        # Создаем временный файл для GLB данных
        with tempfile.NamedTemporaryFile(delete=False, suffix='.glb') as tmp_glb:
            tmp_glb.write(glb_data_bytes)
            tmp_glb_path = tmp_glb.name

        try:
            # Загружаем и экспортируем
            mesh = trimesh.load(tmp_glb_path)
            
            # Изменяем размер модели до 50 мм
            current_size = mesh.extents.max()  # максимальная сторона bounding box
            # задаем фиксированный размер модели 50 мм
            scale_factor = 50 / current_size
            mesh.apply_scale(scale_factor)
            
            # Сохраняем в STL
            stl_path = '3D_models/model.stl'
            
            # Удаляем старый файл, если он существует
            if os.path.exists(stl_path):
                os.remove(stl_path)
            
            mesh.export(stl_path)
            
        except Exception as e:
            st.error(f"Ошибка при конвертации GLB в STL: {str(e)}")
            return None
        finally:
            # Удаляем временный файл
            if os.path.exists(tmp_glb_path):
                os.unlink(tmp_glb_path)

        return stl_path

    def clear_gdrive_folder(self, folder_id=None, file_extension=None):
        """Очищает папку Google Drive, удаляя файлы с указанным расширением или все файлы"""
        if folder_id is None:
            folder_id = self.folder_id
        
        try:
            import pickle
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            
            creds = None
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    st.error("❌ Не удалось получить доступ к Google Drive - токен авторизации недействителен")
                    return False
            
            service = build('drive', 'v3', credentials=creds)
            
            # Получаем список файлов в папке
            query = f"'{folder_id}' in parents"
            if file_extension:
                # Добавляем фильтр по расширению файла
                if file_extension.startswith('.'):
                    file_extension = file_extension[1:]
                query += f" and name contains '.{file_extension}'"
            
            results = service.files().list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name)"
            ).execute()
            items = results.get('files', [])
            
            if not items:
                st.info("📁 Папка Google Drive пуста или файлы не найдены")
                return True
            
            deleted_count = 0
            for file_item in items:
                try:
                    service.files().delete(fileId=file_item['id']).execute()
                    st.info(f"🗑️ Удален файл: {file_item['name']}")
                    deleted_count += 1
                except Exception as e:
                    st.warning(f"⚠️ Не удалось удалить файл {file_item['name']}: {str(e)}")
            
            st.success(f"✅ Удалено {deleted_count} файлов из папки Google Drive")
            return True
            
        except ImportError:
            st.error("❌ Для очистки папки Google Drive необходимо установить библиотеки Google API: pip install google-api-python-client google-auth-oauthlib google-auth")
            return False
        except Exception as e:
            st.error(f"❌ Ошибка при очистке папки Google Drive: {str(e)}")
            return False
    
    def clear_images_gdrive_folder(self, folder_id=None):
        """Очищает папку Google Drive, удаляя только изображения (jpg, jpeg, png, webp)"""
        if folder_id is None:
            folder_id = self.folder_id
        
        # Удаляем файлы по каждому расширению изображений
        extensions = ['.jpg', '.jpeg', '.png', '.webp']
        total_deleted = 0
        
        for ext in extensions:
            try:
                import pickle
                from google.auth.transport.requests import Request
                from google_auth_oauthlib.flow import InstalledAppFlow
                from googleapiclient.discovery import build
                
                creds = None
                if os.path.exists('token.pickle'):
                    with open('token.pickle', 'rb') as token:
                        creds = pickle.load(token)
                
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        st.error("❌ Не удалось получить доступ к Google Drive - токен авторизации недействителен")
                        return False
                
                service = build('drive', 'v3', credentials=creds)
                
                # Получаем список файлов в папке с конкретным расширением
                query = f"'{folder_id}' in parents and name contains '{ext}'"
                
                results = service.files().list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name)"
                ).execute()
                items = results.get('files', [])
                
                for file_item in items:
                    try:
                        service.files().delete(fileId=file_item['id']).execute()
                        st.info(f"🗑️ Удалено изображение: {file_item['name']}")
                        total_deleted += 1
                    except Exception as e:
                        st.warning(f"⚠️ Не удалось удалить изображение {file_item['name']}: {str(e)}")
                        
            except ImportError:
                st.error("❌ Для очистки папки Google Drive необходимо установить библиотеки Google API: pip install google-api-python-client google-auth-oauthlib google-auth")
                return False
            except Exception as e:
                st.error(f"❌ Ошибка при очистке изображений из Google Drive: {str(e)}")
                return False
        
        st.success(f"✅ Удалено {total_deleted} изображений из папки Google Drive")
        return True
    
    def clear_models_gdrive_folder(self, folder_id=None):
        """Очищает папку Google Drive, удаляя только 3D модели (glb, stl, obj, fbx)"""
        if folder_id is None:
            folder_id = self.folder_id
        
        # Удаляем файлы по каждому расширению 3D моделей
        extensions = ['.glb', '.stl', '.obj', '.fbx', '.gltf']
        total_deleted = 0
        
        for ext in extensions:
            try:
                import pickle
                from google.auth.transport.requests import Request
                from google_auth_oauthlib.flow import InstalledAppFlow
                from googleapiclient.discovery import build
                
                creds = None
                if os.path.exists('token.pickle'):
                    with open('token.pickle', 'rb') as token:
                        creds = pickle.load(token)
                
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        st.error("❌ Не удалось получить доступ к Google Drive - токен авторизации недействителен")
                        return False
                
                service = build('drive', 'v3', credentials=creds)
                
                # Получаем список файлов в папке с конкретным расширением
                query = f"'{folder_id}' in parents and name contains '{ext}'"
                
                results = service.files().list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name)"
                ).execute()
                items = results.get('files', [])
                
                for file_item in items:
                    try:
                        service.files().delete(fileId=file_item['id']).execute()
                        st.info(f"🗑️ Удалена 3D модель: {file_item['name']}")
                        total_deleted += 1
                    except Exception as e:
                        st.warning(f"⚠️ Не удалось удалить 3D модель {file_item['name']}: {str(e)}")
                        
            except ImportError:
                st.error("❌ Для очистки папки Google Drive необходимо установить библиотеки Google API: pip install google-api-python-client google-auth-oauthlib google-auth")
                return False
            except Exception as e:
                st.error(f"❌ Ошибка при очистке 3D моделей из Google Drive: {str(e)}")
                return False
        
        st.success(f"✅ Удалено {total_deleted} 3D моделей из папки Google Drive")
        return True
        
    def clear_current_state(self):
        """Очищает текущее состояние клиента"""
        self.current_prompt_id = None
        self.current_history = None
        # st.info("🔄 Состояние клиента ComfyUI очищено")