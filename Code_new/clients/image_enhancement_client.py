import streamlit as st
import requests
import json

# Configuration settings loaded from secrets.toml
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
OPENROUTER_MODEL = st.secrets.get("OPENROUTER_MODEL", "amazon/nova-2-lite-v1:free")
OPENROUTER_URL = st.secrets["OPENROUTER_URL"]

class ImageEnhancementClient:
    # класс генерации prompt на основе картинки пользователя
    
    def __init__(self):
        """Инициализация клиента с API ключом из настроек"""
        self.api_key = OPENROUTER_API_KEY
        self.model = OPENROUTER_MODEL
        self.base_url = OPENROUTER_URL
        
        # Загружаем системный промпт для улучшения изображений
        try:
            with open("editing_sysprompt.md", "r") as f:
                self.sys_prompt = f.read()
        except FileNotFoundError:
            # Если файл не найден, используем стандартный промпт для улучшения
            self.sys_prompt = (
                "You are a 3D modeling and printing expert. You should change the image "
                "according to the user's request, but you should not generate it from scratch, "
                "change only what the user asks for. You get an image that needs to be changed "
                "to match the user's new request and the initial prompt. Respond ONLY with the "
                "improved prompt, no explanations ON ENGLISH./no-think"
            )
        
        if not self.api_key:
            st.warning("⚠️ OpenRouter API ключ не найден в secrets.toml")
    
    def enhance_image_with_request(self, image_url: str, original_prompt: str, enhancement_request: str) -> str:
        """
        Улучшает изображение на основе запроса пользователя.
        Возвращает улучшенный промпт или оригинальный при ошибке.
        """
        if not self.api_key:
            st.warning("OpenRouter API ключ не настроен. Использую оригинальный запрос.")
            return original_prompt
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Формируем сообщение с описанием задачи улучшения
            user_message = (
                f"Initial prompt: '{original_prompt}'\n"
                f"Enhancement request: '{enhancement_request}'\n"
                f"Image URL: {image_url}\n"
            )
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.sys_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
                "max_tokens": 200
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
                return enhanced if enhanced else original_prompt
            else:
                st.warning(f"OpenRouter ошибка: {response.status_code}. Использую оригинальный запрос.")
                return original_prompt
                
        except Exception as e:
            st.warning(f"Ошибка связи с OpenRouter: {e}. Использую оригинальный запрос.")
            return original_prompt