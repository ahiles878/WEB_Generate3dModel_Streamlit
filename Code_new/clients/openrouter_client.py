import streamlit as st
import requests
import json
import base64
from typing import Optional
import os
from openai import OpenAI

# путь к файлу с sys_prompt и editind_prompt
path_sys = "prompts/system_prompt.md"
path_edit = "prompts/editing_image.md"

# Configuration settings loaded from secrets.toml

OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = st.secrets.get("OPENROUTER_MODEL")
OLLAMA_MODEL = st.secrets.get("OLLAMA_MODEL")

class OpenRouterClient:
    """Client for working with OpenRouter API"""
    
    def __init__(self):
        #Инициализация класса с API ключом из настроек
        
        self.api_key = OPENROUTER_API_KEY
        self.model = OPENROUTER_MODEL
        self.ollama_model = OLLAMA_MODEL
        self.base_url = "https://openrouter.ai/api/v1" # "http://localhost:11434"
        
        # Настройка клиента для Ollama
        self.ollama_client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

        # загрузка system и editing prompts
        with open(path_sys, "r") as f:
            self.sys_prompt = f.read()
            
        with open(path_edit, "r") as f:
            self.editing_sys_prompt = f.read()
    
    def enhance_prompt(self, user_prompt: str, image_url: str = None, task_type: str = "standard") -> str:
        #улучшает pormpt пользователя, чтобы создать изображение пригодное для печати. Работет как с текстом, так и с изображением
        
        if not self.api_key:
            st.warning("OpenRouter API ключ не настроен. Использую локальную модель Ollama.")
            return self.enhance_prompt_with_ollama(user_prompt, image_url, task_type)
        
        # Выбираем системный промпт в зависимости от типа задачи
        sys_prompt = self.editing_sys_prompt if task_type == "editing" else self.sys_prompt
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Подготовка сообщений для API
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Если есть изображение и модель поддерживает работу с изображениями(модели из-за лимитов меняются в secrets)
            if image_url:
                # Для моделей с поддержкой изображений формируем специальное сообщение
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ]
            elif image_url:
                # Если модель не поддерживает изображения, добавляем информацию о наличии изображения в текст
                enhanced_prompt = f"{user_prompt}. {self.sys_prompt}"
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": enhanced_prompt}
                ]
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                enhanced = result["choices"][0]["message"]["content"].strip()
                
                # Проверяем, является ли ответ JSON-строкой, содержащей поле message
                try:
                    # Пытаемся распарсить как JSON
                    parsed_result = json.loads(enhanced)
                    # Если успешно, извлекаем текст из поля message
                    if isinstance(parsed_result, dict) and "choices" in parsed_result:
                        message_content = parsed_result["choices"][0]["message"]
                        if isinstance(message_content, dict) and "message" in message_content:
                            enhanced = message_content["message"]
                        elif isinstance(message_content, str):
                            enhanced = message_content
                    elif isinstance(parsed_result, dict) and "message" in parsed_result:
                        enhanced = parsed_result["message"]
                except json.JSONDecodeError:
                    # Если это не JSON, используем как есть
                    pass
                
                return enhanced
            else:
                st.warning(f"OpenRouter ошибка: {response.status_code}. Использую локальную модель Ollama.")
                return self.enhance_prompt_with_ollama(user_prompt, image_url, task_type)
                
        except Exception as e:
            st.warning(f"Ошибка связи с OpenRouter: {e}. Использую локальную модель Ollama.")
            return self.enhance_prompt_with_ollama(user_prompt, image_url, task_type)

    def generate_prompt_from_image(self, user_request: str, image_path: str = None, task_type: str = "editing", image_bytes=None) -> str:
        """
        Генерирует промпт на основе пользовательского запроса и изображения
        
        Args:
            user_request: Текстовый запрос пользователя
            image_path: Путь к изображению (опционально, если используется image_bytes)
            task_type: Тип задачи (editing или standard)
            image_bytes: Байты изображения (опционально, если используется image_path)
        
        Returns:
            str: Сгенерированный промпт
        """
        st.info(f"DEBUG generate_prompt_from_image: user_request = '{user_request}', image_path = {image_path}, image_bytes = {type(image_bytes)}, task_type = {task_type}")
        
        if not self.api_key:
            st.warning("OpenRouter API ключ не настроен. Использую локальную модель Ollama.")
            return self.generate_prompt_from_image_with_ollama(user_request, image_path, task_type, image_bytes)
        
        # Кодируем изображение в base64
        base64_image = None
        if image_bytes is not None:
            base64_image = self.encode_image_stream_to_base64(image_bytes)
        elif image_path is not None:
            base64_image = self.encode_image_to_base64(image_path)
        
        if not base64_image:
            st.error("Не удалось закодировать изображение в base64. Использую локальную модель Ollama.")
            return self.generate_prompt_from_image_with_ollama(user_request, image_path, task_type, image_bytes)
        
        # Выбираем системный промпт в зависимости от типа задачи
        sys_prompt = self.editing_sys_prompt if task_type == "editing" else self.sys_prompt
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Подготовка сообщений для API с изображением в base64 формате
            messages = [
                {"role": "system", "content": sys_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_request},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500  # Увеличиваем лимит токенов для более подробных промптов
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_prompt = result["choices"][0]["message"]["content"].strip()
                
                # Проверяем, является ли ответ JSON-строкой
                try:
                    parsed_result = json.loads(generated_prompt)
                    if isinstance(parsed_result, dict) and "choices" in parsed_result:
                        message_content = parsed_result["choices"][0]["message"]
                        if isinstance(message_content, dict) and "message" in message_content:
                            generated_prompt = message_content["message"]
                        elif isinstance(message_content, str):
                            generated_prompt = message_content
                    elif isinstance(parsed_result, dict) and "message" in parsed_result:
                        generated_prompt = parsed_result["message"]
                except json.JSONDecodeError:
                    # Если это не JSON, используем как есть
                    pass
                
                return generated_prompt
            else:
                st.warning(f"OpenRouter ошибка: {response.status_code}. Использую локальную модель Ollama.")
                return self.generate_prompt_from_image_with_ollama(user_request, image_path, task_type, image_bytes)
                
        except Exception as e:
            st.warning(f"Ошибка связи с OpenRouter: {e}. Использую локальную модель Ollama.")
            return self.generate_prompt_from_image_with_ollama(user_request, image_path, task_type, image_bytes)

    def encode_image_stream_to_base64(self, image_stream) -> Optional[str]:
        """
        Кодирует поток изображения в формат base64
        
        Args:
            image_stream: Поток изображения (например, uploaded_file.getvalue())
            
        Returns:
            str: Base64 строка или None в случае ошибки
        """
        try:
            return base64.b64encode(image_stream).decode('utf-8')
        except Exception as e:
            st.error(f"❌ Ошибка при кодировании изображения в base64: {e}")
            return None

    def enhance_prompt_with_ollama(self, user_prompt: str, image_url: str = None, task_type: str = "standard") -> str:
        """
        Улучшает промпт с использованием локальной модели Ollama
        """
        # Выбираем системный промпт в зависимости от типа задачи
        sys_prompt = self.editing_sys_prompt if task_type == "editing" else self.sys_prompt
        
        st.info(f"DEBUG enhance_prompt_with_ollama: user_prompt = {user_prompt}")
        st.info(f"DEBUG enhance_prompt_with_ollama: image_url = {image_url}")
        st.info(f"DEBUG enhance_prompt_with_ollama: task_type = {task_type}")

        try:
            # Подготовка сообщений для Ollama
            # Если есть изображение, формируем мультимодальное сообщение
            if image_url:
                # Для локальной модели Ollama используем подход с передачей URL или пути к изображению
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ]
            else:
                # Если изображения нет, используем только текст
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ]

            # Вызов локальной модели Ollama
            response = self.ollama_client.chat.completions.create(
                model=self.ollama_model,  # используем указанную в задании модель
                messages=messages,
                temperature=0.7
            )

            enhanced = response.choices[0].message.content
            st.write(response.choices[0].message)
            return enhanced

        except Exception as e:
            st.warning(f"Ошибка при вызове локальной модели Ollama: {e}. Использую оригинальный запрос.")
            return user_prompt

    def generate_prompt_from_image_with_ollama(self, user_request: str, image_path: str = None, task_type: str = "editing", image_bytes=None) -> str:
        """
        Генерирует промпт на основе пользовательского запроса и изображения с использованием локальной модели Ollama
        """
        # Выбираем системный промпт в зависимости от типа задачи
        sys_prompt = self.editing_sys_prompt if task_type == "editing" else self.sys_prompt
        
        st.info(f"DEBUG: user_request = {user_request}")
        st.info(f"DEBUG: image_path = {image_path}")
        st.info(f"DEBUG: image_bytes type = {type(image_bytes)}")
        if image_bytes is not None:
            st.info(f"DEBUG: image_bytes length = {len(image_bytes) if image_bytes else 0}")

        try:
            # Кодируем изображение в base64
            base64_image = None
            if image_bytes is not None:
                base64_image = self.encode_image_stream_to_base64(image_bytes)
            elif image_path is not None:
                # Предполагаем, что есть метод encode_image_to_base64
                with open(image_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')

            if not base64_image:
                st.error("Не удалось закодировать изображение в base64 для локальной модели Ollama.")
                return user_request
                
            st.info(f"DEBUG: base64_image length = {len(base64_image) if base64_image else 0}")

            # Подготовка сообщений для Ollama с изображением в base64 формате
            # Изменяем формат для лучшей совместимости с qwen3-vl:4B
            messages = [
                {"role": "system", "content": sys_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_request},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"  # Изменили на png для лучшей совместимости
                            }
                        }
                    ]
                }
            ]
            
            st.info(f"DEBUG: messages structure prepared for Ollama")

            # Вызов локальной модели Ollama
            response = self.ollama_client.chat.completions.create(
                model=self.ollama_model,  # используем указанную в задании модель
                messages=messages,
                temperature=0.7,
                max_tokens=300
            )

            generated_prompt = response.choices[0].message.content.strip()
            st.info(f"DEBUG: response received, content length = {len(generated_prompt) if generated_prompt else 0}")
            
            # Проверяем, что ответ не пустой
            if not generated_prompt:
                st.warning("Получен пустой ответ от локальной модели Ollama. Использую оригинальный запрос.")
                return user_request
            return generated_prompt

        except Exception as e:
            st.warning(f"Ошибка при вызове локальной модели Ollama: {e}. Использую оригинальный запрос.")
            # Добавим дополнительное логирование для отладки
            st.error(f"Детали ошибки: {str(e)}")
            return user_request

    def encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """
        Кодирует изображение в формат base64

        Args:
            image_path: Путь к изображению

        Returns:
            str: Base64 строка или None в случае ошибки
        """
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            st.error(f"❌ Ошибка при кодировании изображения в base64: {e}")
            return None
    
    # Пример использования
    # orc = OpenRouterClient()
    # response = orc.enhance_prompt("кот")
    # print(response)