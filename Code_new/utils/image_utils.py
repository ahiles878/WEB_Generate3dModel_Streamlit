import streamlit as st
import tempfile
import os
from pathlib import Path
import base64
from typing import Optional, Union
from PIL import Image
import io


def save_uploaded_image(uploaded_file) -> Optional[str]:
    #Сохраняет загруженное пользователем изображение во временный файл и возвращает путь к файлу
    
    if not uploaded_file:
        return None
    
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=f'.{Path(uploaded_file.name).suffix[1:]}' or 'png'
        ) as tmp:
            # Записываем содержимое загруженного файла в временный файл
            tmp.write(uploaded_file.getvalue())
            temp_path = tmp.name
            
        st.success(f"🖼️ Изображение сохранено во временный файл: {os.path.basename(temp_path)}")
        return temp_path
    except Exception as e:
        st.error(f"❌ Ошибка при сохранении изображения: {e}")
        return None

def encode_image_to_base64(image_path: str) -> Optional[str]:
    #Кодирует изображение в формат base64 для отправки в API
    
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        st.error(f"❌ Ошибка при кодировании изображения в base64: {e}")
        return None


def cleanup_temp_file(temp_path: str) -> bool:
    #Удаляет временный файл
    
    try:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
            return True
        return False
    except Exception as e:
        st.error(f"❌ Ошибка при удалении временного файла: {e}")
        return False

def validate_image(uploaded_file) -> bool:
    #Проверяет, является ли загруженный файл допустимым изображением
    
    if not uploaded_file:
        return False
    
    # Проверяем расширение файла
    valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
    file_ext = Path(uploaded_file.name).suffix.lower()
    
    if file_ext not in valid_extensions:
        st.error(f"❌ Недопустимый формат изображения: {file_ext}. Поддерживаются: {', '.join(valid_extensions)}")
        return False
    
    # Пытаемся открыть изображение с помощью PIL для проверки целостности
    try:
        image = Image.open(io.BytesIO(uploaded_file.getvalue()))
        # Проверяем, что изображение открывается без ошибок
        image.verify()
        return True
    except Exception as e:
        st.error(f"❌ Ошибка при проверке изображения: {e}")
        return False