import streamlit as st
import requests
import tempfile
import os
import urllib.parse
from pathlib import Path

from clients.openrouter_client import OpenRouterClient
from clients.comfyui_client import ComfyUIClient
from streamlit_stl import stl_from_file

from utils.generation_functions import generate_images_from_text, generate_3d_from_image, generate_images_from_image

# Configuration settings loaded from secrets.toml
COMFYUI_URL = st.secrets["COMFYUI_URL"]
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
OPENROUTER_MODEL = st.secrets.get("OPENROUTER_MODEL")

# ============================================================================
# STREAMLIT INTERFACE
# ============================================================================

def main():
    # Настройка страницы
    st.set_page_config(
        page_title="3D Model Generator",
        page_icon="🖨️",
        layout="wide"
    )
    
    # Инициализация состояния сессии
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'current_step' not in st.session_state:
        st.session_state.current_step = "start"  # start, image_generation, image_selection, model_generation, model_ready
    if 'user_prompt' not in st.session_state:
        st.session_state.user_prompt = ""
    if 'uploaded_image' not in st.session_state:
        st.session_state.uploaded_image = None
    if 'generated_images' not in st.session_state:
        st.session_state.generated_images = []
    if 'selected_image' not in st.session_state:
        st.session_state.selected_image = None
    if 'generated_model' not in st.session_state:
        st.session_state.generated_model = None
    if 'image_generation_count' not in st.session_state:
        st.session_state.image_generation_count = 0
    if 'downloaded_model_path' not in st.session_state:
        st.session_state.downloaded_model_path = None
    if 'generated_model_stl' not in st.session_state:
        st.session_state.generated_model_stl = None
    if 'downloaded_model_path_stl' not in st.session_state:
        st.session_state.downloaded_model_path_stl = None
    
    # Заголовок
    st.title("🖨️ Генератор 3D-моделей")
    st.markdown("---")
    
    # Отображение истории сообщений (в обычном(или обратном reverset()) порядке - последние сообщения сверху)
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "image" in message:
                st.image(message["image"], caption=message.get("caption", ""))
            if "model_url" in message:
                # Отображаем 3D-модель вместо ссылки
                model_path = message["model_url"]
                if model_path and os.path.exists(model_path):
                    if model_path.endswith('.stl'):
                        with open(model_path, 'rb') as f:
                            stl_data = f.read()
                        stl_from_file(
                            file_path=stl_data,
                            color="#8605F0EA",
                            material='material',
                            auto_rotate=True,
                            opacity=1,
                            height=400,
                        )
                    elif model_path.endswith('.glb'):
                        # Для GLB файлов отображаем как 3D модель
                        stl_from_file(
                            file_path=model_path,
                            color="#8605F0EA",
                            material='material',
                            auto_rotate=True,
                            opacity=1,
                            height=400,
                        )
                    else:
                        st.markdown(f"[Скачать 3D-модель]({message['model_url']})")
                else:
                    st.markdown(f"[Скачать 3D-модель]({message['model_url']})")

    # Отображение ошибки, если она есть в состоянии сессии
    if 'error_message' in st.session_state and st.session_state.error_message:
        with st.chat_message("assistant"):
            st.error(st.session_state.error_message)
        # Очищаем сообщение об ошибке после отображения
        st.session_state.error_message = None
    
    # Основная логика приложения
    if st.session_state.current_step == "start":
        handle_start_step()
    elif st.session_state.current_step == "image_generation":
        handle_image_generation_step()
    elif st.session_state.current_step == "image_selection":
        handle_image_selection_step()
    elif st.session_state.current_step == "model_generation":
        handle_model_generation_step()
    elif st.session_state.current_step == "model_ready":
        handle_model_ready_step()

def handle_start_step():
    """Обработка начального шага - приветствие и ввод пользователя"""
    with st.chat_message("assistant"):
        st.markdown("Привет! Я могу помочь вам создать 3D-модель. Вы можете:")
        st.markdown("- Загрузить изображение и описать, что на нем")
        st.markdown("- Только описать объект, который хотите создать")
    
    # Поле ввода для пользователя (перемещено вниз)
    with st.chat_message("user"):
        col1, col2 = st.columns([4, 1])
        with col1:
            user_input = st.text_area("Введите описание или загрузите изображение:", height=150, key="user_input_start")
        with col2:
            uploaded_file = st.file_uploader("Загрузить изображение", type=['png', 'jpg', 'jpeg', 'webp'], key="image_upload_start")
        
        if st.button("Отправить", key="send_start"):
            process_user_input(user_input, uploaded_file)

    # Кнопки навигации (перемещены в самый низ)
    if any([
        st.session_state.user_prompt,
        st.session_state.uploaded_image,
        st.session_state.generated_images,
        st.session_state.selected_image,
        st.session_state.generated_model
    ]):
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Начать новый диалог", key="new_dialog_btn_start"):
                reset_session()
                st.rerun()
        with col2:
            # В зависимости от текущего состояния, предлагаем продолжить с последнего шага
            if st.session_state.generated_model:
                step_name = "просмотра готовой модели"
                target_step = "model_ready"
            elif st.session_state.selected_image:
                step_name = "генерации 3D-модели"
                target_step = "model_generation"
            elif st.session_state.generated_images:
                step_name = "выбора изображения"
                target_step = "image_selection"
            elif st.session_state.user_prompt or st.session_state.uploaded_image:
                step_name = "генерации изображений"
                target_step = "image_generation"
            else:
                step_name = "начала"
                target_step = "start"
            
            if st.button(f"⏩ Продолжить с {step_name}", key="continue_from_btn_start"):
                st.session_state.current_step = target_step
                st.rerun()
    

def handle_image_generation_step():
    """Обработка шага генерации изображений"""
    with st.chat_message("assistant"):
        # Определяем, было ли загружено изображение
        if st.session_state.uploaded_image:
            # Было загружено изображение - мы не генерируем промежуточное изображение, а сразу переходим к 3D модели
            # Согласно логике: "улучшенный запрос вставляется в ноду положительного запроса в OnlyGenImage.json и этот workflow отправляется в ComfyUI"
            # и "после генерации изображения оно скачивается и вставляется в ноду загрузки изображений в OnlyGenModel.json"
            # То есть, даже если у нас есть изображение от пользователя, мы всё равно генерируем промежуточное изображение с помощью VLM + ComfyUI
            
            # st.markdown("Генерирую изображение на основе загруженного изображения и описания...")
            with st.spinner("Генерация изображения..."):
                comfy_client = ComfyUIClient(COMFYUI_URL)
                
                # Используем новую функцию для генерации изображений на основе загруженного изображения и текста
                image_urls = generate_images_from_image(
                    uploaded_file=st.session_state.uploaded_image,
                    text_prompt="",  # текст уже учтен в user_prompt
                    client=comfy_client,
                    num_images=1,
                    pregenerated_prompt=st.session_state.user_prompt
                )
        else:
            # Только текст - генерируем 4 изображения
            # st.markdown("Генерирую несколько вариантов изображений на основе вашего описания...")
            with st.spinner("Генерация изображений..."):
                comfy_client = ComfyUIClient(COMFYUI_URL)
                image_urls = generate_images_from_text(st.session_state.user_prompt, comfy_client, num_images=4, uploaded_image_path=None)
        if image_urls:
            st.session_state.generated_images = image_urls
            st.session_state.current_step = "image_selection"
            # Удаляем сообщение о прогрессе генерации изображений, если оно есть
            if st.session_state.messages and "Генерация изображения..." in st.session_state.messages[-1]["content"]:
                st.session_state.messages.pop()
            st.rerun()
        else:
            # Проверяем, есть ли сообщение об ошибке в состоянии сессии
            if 'error_message' not in st.session_state or not st.session_state.error_message:
                st.error("Не удалось сгенерировать изображения. Попробуйте еще раз.")
            # Вместо перехода к старту, лучше остаться на текущем шаге или вернуться к вводу
            st.session_state.current_step = "start"
            st.rerun()


    # Кнопки навигации (перемещены в самый низ)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔙 Вернуться к началу", key="back_to_start_img_gen"):
            reset_session()
            st.rerun()
    with col2:
        if st.button("↩️ Назад к описанию", key="back_to_desc_img_gen"):
            # Возвращаемся к начальному шагу, сохраняя введенные данные
            st.session_state.current_step = "start"
            st.rerun()

def handle_image_selection_step():
    """Обработка шага выбора изображения"""
    with st.chat_message("assistant"):
        # Проверяем, было ли загружено изображение пользователем и у нас одно сгенерированное изображение
        # Это означает, что мы сгенерировали одно изображение на основе загруженного пользователем
        if st.session_state.uploaded_image and len(st.session_state.generated_images) == 1:
            # Случай, когда пользователь загрузил изображение и мы сгенерировали одно подходящее изображение для 3D моделирования
            st.markdown("Сгенерированное изображение для 3D моделирования:")
            st.image(st.session_state.generated_images[0], caption="Подготовленное изображение", width=500)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Использовать это изображение для 3D модели", key="select_single"):
                    st.session_state.selected_image = st.session_state.generated_images[0]
                    st.session_state.current_step = "model_generation"
                    st.rerun()
            with col2:
                # Кнопка перегенерации изображения на основе загруженного пользователем
                if st.button("🔄 Сгенерировать другое изображение", key="regenerate_image_from_upload"):
                    st.session_state.current_step = "image_generation"
                    st.session_state.image_generation_count += 1
                    st.rerun()
        elif len(st.session_state.generated_images) == 1:
            # Один вариант - возможна перегенерация
            st.markdown("Сгенерированное изображение для 3D моделирования:")
            st.image(st.session_state.generated_images[0], caption="Подготовленное изображение", width=500)
            
            if st.button("Использовать это изображение для 3D модели", key="select_single_img_1"):
                st.session_state.selected_image = st.session_state.generated_images[0]
                st.session_state.current_step = "model_generation"
                st.rerun()
            
            # Кнопка перегенерации изображений
            if st.button("🔄 Сгенерировать другие варианты", key="regenerate_images_single"):
                st.session_state.current_step = "image_generation"
                st.session_state.image_generation_count += 1
                st.rerun()
        else:
            # Несколько вариантов - пользователь ввел текст и мы сгенерировали несколько изображений
            st.markdown("Выберите подходящее изображение для генерации 3D-модели:")
            
            # Отображаем 4 изображения
            cols = st.columns(4)
            for idx, col in enumerate(cols):
                with col:
                    if idx < len(st.session_state.generated_images):
                        st.image(
                            st.session_state.generated_images[idx],
                            caption=f"Вариант {idx+1}",
                            width=500
                        )
                        if st.button(f"✅ Выбрать #{idx+1}", key=f"select_{idx}"):
                            st.session_state.selected_image = st.session_state.generated_images[idx]
                            st.session_state.current_step = "model_generation"
                            st.rerun()
            
            # Кнопка перегенерации изображений
            if st.button("🔄 Сгенерировать другие варианты", key="regenerate_images_1"):
                st.session_state.current_step = "image_generation"
                st.session_state.image_generation_count += 1
                st.rerun()

    # Кнопки навигации (перемещены в самый низ)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔙 Вернуться к началу", key="back_to_start_img_sel"):
            reset_session()
            st.rerun()
    with col2:
        if st.button("↩️ Назад к генерации", key="back_to_gen_img_sel"):
            st.session_state.current_step = "image_generation"
            st.rerun()

def handle_model_generation_step():
    """Обработка шага генерации 3D-модели"""
    with st.chat_message("assistant"):
        # st.markdown("Создаю 3D-модель из выбранного изображения...")
        with st.spinner("Создаю 3D-модель..."):
            try:
                comfy_client = ComfyUIClient(COMFYUI_URL)
                # Используем изображение напрямую из предыдущего workflow без скачивания
                model_path = generate_3d_from_image(comfy_client, image_filename=st.session_state.selected_image)
                # Убираем вывод URL изображения, чтобы не засорять интерфейс
                # st.warning(st.session_state.selected_image)
                if model_path:
                    # Результат - путь STL-файла
                    st.session_state.generated_model_stl = model_path
                    # Устанавливаем путь к STL модели для проверки в handle_model_ready_step
                    # Сохраняем байты STL в переменной состояния, а не строку
                    st.session_state.downloaded_model_path_stl = model_path

                    st.session_state.current_step = "model_ready"
                    st.rerun()
                    
                else:
                    # В случае ошибки при генерации 3D-модели, просто выводим сообщение об ошибке
                    error_msg = "❌ Не удалось создать 3D-модель."
                    st.error(error_msg)
                    
                    # Добавляем сообщение об ошибке в историю чата
                    if 'messages' not in st.session_state:
                        st.session_state.messages = []
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
                    
                    # Остаемся на текущем шаге, не возвращаемся к выбору изображения
                    st.rerun()
            except Exception as e:
                # При критической ошибке показываем её и останавливаем выполнение
                error_msg = f"❌ КРИТИЧЕСКАЯ ОШИБКА при генерации 3D-модели: {str(e)}"
                st.error(error_msg)
                
                # Добавляем сообщение об ошибке в историю чата
                if 'messages' not in st.session_state:
                    st.session_state.messages = []
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg
                })
                
                # Добавляем сообщение об ошибке в состояние сессии для отображения
                if 'error_message' not in st.session_state:
                    st.session_state.error_message = error_msg
                
                # Останавливаем выполнение и не возвращаемся к выбору изображения
                # Пользователь может решить, хочет ли он продолжить
                st.rerun()

    # Кнопки навигации (перемещены в самый низ)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔙 Вернуться к началу", key="back_to_start_mod_gen"):
            reset_session()
            st.rerun()
    with col2:
        if st.button("↩️ Назад к выбору изображения", key="back_to_img_sel_mod_gen"):
            st.session_state.current_step = "image_selection"
            st.rerun()

def handle_model_ready_step():
    """Обработка шага готовой модели"""
    with st.chat_message("assistant"):
        st.markdown("Ваша 3D-модель готова!")
        # Добавляем кнопку для скачивания файла модели
        # Проверяем, есть ли скачанная модель
        if st.session_state.generated_model_stl:
            # Если у нас есть STL модель (успешно конвертированная из GLB)
            stl_path = st.session_state.generated_model_stl
                
            if stl_path and os.path.exists(stl_path):
                with open(stl_path, "rb") as f:
                    stl_data = f.read()
                # Отображаем модель с настройками
                stl_from_file(
                    file_path=stl_path,  # Передаем байты файла, а не путь
                    color="#FF9900",          # Цвет модели
                    material='material',       # Стиль: 'material', 'flat', 'wireframe'
                    auto_rotate=True,          # Включить авто-вращение
                    opacity=1,                 # Прозрачность (0 - прозрачно, 1 - непрозрачно)
                    height=500,                # Высота окна просмотра
                )
                # Предоставляем возможность скачать STL-файл
                st.download_button(
                    label="📥 Скачать STL-модель",
                    data=stl_data,  # Передаем байты файла, а не путь
                    file_name="model.stl",
                    mime="model/stl"
                )
            else:
                st.error("❌ Не удалось найти конвертированную STL модель")
        elif st.session_state.downloaded_model_path:
            # Если есть только оригинальный GLB файл
            glb_path = st.session_state.downloaded_model_path
            if glb_path and os.path.exists(glb_path):
                # Отображаем GLB модель
                with open(glb_path, 'rb') as f:
                    glb_data = f.read()
                
                stl_from_file(
                    file_path=glb_path,  # Передаем путь к GLB файлу
                    color="#FF9900",          # Цвет модели
                    material='material',       # Стиль: 'material', 'flat', 'wireframe'
                    auto_rotate=True,          # Включить авто-вращение
                    opacity=1,                 # Прозрачность (0 - прозрачно, 1 - непрозрачно)
                    height=500,                # Высота окна просмотра
                )
                # Предоставляем возможность скачать GLB-файл
                with open(glb_path, "rb") as f:
                    st.download_button(
                        label="📥 Скачать GLB-модель",
                        data=f,
                        file_name=os.path.basename(glb_path),
                        mime="model/gltf-binary"
                    )
            else:
                st.error("❌ Не удалось найти скачанную GLB модель")
        else:
            st.warning("Произошла ошибка: не найден путь к модели")

    # Кнопки навигации (перемещены в самый низ)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Начать новый диалог", key="new_dialog_btn_mod_ready"):
            reset_session()
            st.rerun()
    with col2:
        # Кнопка для возврата к началу текущего диалога (сохраняя историю)
        if st.button("🔙 К началу диалога", key="back_to_start_mod_ready"):
            st.session_state.current_step = "start"
            st.rerun()

def process_user_input(user_input, uploaded_file):
    """Обработка пользовательского ввода (текст или изображение)"""
    # Добавляем сообщение пользователя в историю
    user_message = {"role": "user", "content": user_input or "Загрузка изображения"}
    if uploaded_file:
        user_message["image"] = uploaded_file
        user_message["caption"] = "Загруженное изображение"
    st.session_state.messages.append(user_message)
    
    # Обработка ввода
    if uploaded_file and (user_input or True):  # Если есть изображение (с текстом или без)
        # Пользователь загрузил изображение (с текстом или без текста)
        # Используем VLM для создания промпта для генерации изображения, пригодного для 3D моделирования
        openrouter_client = OpenRouterClient()
        
        if user_input:
            # Если есть и изображение и текст
            user_request = user_input
        else:
            # Если есть только изображение
            user_request = "Create a 3D printable model based on this image"
        
        # Используем новую функцию для генерации промпта на основе изображения и текста
        # Передаем байты изображения напрямую, избегая сохранения во временный файл
        st.info(f"DEBUG process_user_input: user_request = {user_request}")
        st.info(f"DEBUG process_user_input: uploaded_file type = {type(uploaded_file)}")
        st.info(f"DEBUG process_user_input: uploaded_file size = {len(uploaded_file.getvalue()) if uploaded_file else 0}")
        
        enhanced_prompt = openrouter_client.generate_prompt_from_image(user_request, image_bytes=uploaded_file.getvalue(), task_type="editing")
        st.session_state.user_prompt = enhanced_prompt
        st.success("✅ Промпт сгенерирован на основе изображения и текста")
        
        # Устанавливаем шаг генерации изображения
        st.session_state.uploaded_image = uploaded_file
        st.session_state.current_step = "image_generation"
        
        # Добавляем сообщение ассистента в историю
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Создаю 3D-модель"
        })
        
    elif user_input:
        # Пользователь ввел только текст
        st.session_state.user_prompt = user_input
        
        # Устанавливаем шаг генерации изображений
        st.session_state.current_step = "image_generation"
        
        # Добавляем сообщение ассистента в историю
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Создаю 3D-модель"
        })
    
    st.rerun()

def reset_session():
    """Сброс состояния сессии для начала нового диалога"""
    st.session_state.current_step = "start"
    st.session_state.user_prompt = ""
    st.session_state.uploaded_image = None
    st.session_state.generated_images = []
    st.session_state.selected_image = None
    st.session_state.generated_model = None
    st.session_state.image_generation_count = 0
    st.session_state.downloaded_model_path = None
    st.session_state.generated_model_stl = None
    st.session_state.downloaded_model_path_stl = None
    # Также сбрасываем историю сообщений при полном перезапуске
    st.session_state.messages = []

# ============================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================================================

if __name__ == "__main__":
    main()