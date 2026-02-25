
## Обзор

В этом проекте реализована возможность сохранения изображения пользователя и дальнейшей его отправки в OpenRouter к VLM (визуально-языковой модели) для генерации промпта на основе пользовательского запроса и картинки. Этот промпт затем используется для генерации нового изображения.

## Архитектура

### 1. Модуль обработки изображений (`utils/image_utils.py`)
- `save_uploaded_image(uploaded_file)`: Сохраняет загруженное пользователем изображение во временный файл
- `encode_image_to_base64(image_path)`: Кодирует изображение в формат base64 для отправки в API
- `cleanup_temp_file(temp_path)`: Удаляет временный файл
- `validate_image(uploaded_file)`: Проверяет, является ли загруженный файл допустимым изображением

### 2. Клиент OpenRouter (`clients/openrouter_client.py`)
- `generate_prompt_from_image(user_request, image_path, task_type="editing")`: Генерирует промпт на основе пользовательского запроса и изображения
- `encode_image_to_base64(image_path)`: Кодирует изображение в формат base64
- Обновленный `enhance_prompt()` с поддержкой изображений
- Использует `prompts/editing_image.md` для задач изменения изображений и `prompts/system_prompt.md` для стандартных задач

### 3. Функции генерации (`utils/generation_functions.py`)
- Обновленная `generate_images_from_text()` с поддержкой обработки изображений через VLM
- Новая `generate_images_from_image()` для генерации изображений на основе загруженного изображения и текстового описания
- Функция `has_editing_request()` для определения типа задачи (изменение изображения или генерация нового)

## Использование

### Базовое использование

```python
from clients.openrouter_client import OpenRouterClient
from utils.image_utils import save_uploaded_image, cleanup_temp_file
from utils.generation_functions import generate_images_from_image

# Создаем клиента
client = OpenRouterClient()

# Сохраняем загруженное изображение
temp_path = save_uploaded_image(uploaded_file)
try:
    # Генерируем промпт на основе изображения и текста
    enhanced_prompt = client.generate_prompt_from_image(
        user_request="Изменить цвет объекта на синий", 
        image_path=temp_path, 
        task_type="editing"
    )
    
    # Используем промпт для генерации нового изображения
    # (через ComfyUI или другую систему генерации)
finally:
    # Очищаем временный файл
    cleanup_temp_file(temp_path)
```

### Использование с ComfyUI

```python
from clients.comfyui_client import ComfyUIClient
from utils.generation_functions import generate_images_from_image

# Создаем клиент ComfyUI
comfy_client = ComfyUIClient()

# Генерируем изображения на основе загруженного изображения и текстового описания
image_urls = generate_images_from_image(
    uploaded_file=uploaded_file,
    text_prompt="Добавить улыбку на лицо",
    client=comfy_client,
    num_images=1
)
```

## Интеграция с UI

Для демонстрации функциональности созданы два скрипта:

1. `test_image_integration.py` - простой тест интеграции
2. `image_processing_demo.py` - полнофункциональная демонстрация с UI

## Технические детали

### Форматы изображений
Поддерживаются следующие форматы:
- PNG
- JPG/JPEG
- BMP
- WEBP

### Работа с VLM
1. Изображение кодируется в base64
2. Base64 строка отправляется вместе с текстовым запросом в VLM через OpenRouter API
3. Система определяет тип задачи:
   - Если в текстовом запросе есть ключевые слова, указывающие на изменение (например, "увеличь", "измени", "сделай", "add", "change"), используется промпт `prompts/editing_image.md`
   - Если запрос не содержит указаний на изменение, используется стандартный промпт `prompts/system_prompt.md`
4. VLM анализирует как изображение, так и текстовый запрос с учетом выбранного промпта
5. Генерируется улучшенный промпт, учитывающий оба элемента
6. Этот промпт используется для генерации нового изображения

### Безопасность и очистка
- Все загруженные изображения сохраняются во временные файлы
- Временные файлы автоматически удаляются после обработки
- Проверяется валидность загружаемых изображений

## Ошибки и обработка исключений

Система обрабатывает следующие типы ошибок:
- Неподдерживаемые форматы изображений
- Ошибки при кодировании изображений
- Ошибки при работе с OpenRouter API
- Ошибки при генерации изображений
- Ошибки при очистке временных файлов