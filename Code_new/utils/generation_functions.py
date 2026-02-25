import streamlit as st
from pathlib import Path

from clients.comfyui_client import ComfyUIClient
from clients.openrouter_client import OpenRouterClient
from utils.image_utils import save_uploaded_image, cleanup_temp_file
from streamlit_stl import stl_from_file

# Пути к файлам workflow
WORKFLOW_IMAGES = "workflows/OnlyGenImage.json"
WORKFLOW_3D = "workflows/OnlyGenModel.json"


def generate_images_from_text(prompt: str, client: ComfyUIClient, num_images: int = 4, uploaded_image_path: str = None):
    # генерация изображений по тексту, возвращает ссылки на изображения
    
    openrouter_client = OpenRouterClient()
    # st.info("🎨 Улучшаю запрос...")
    
    try:
        # Если есть загруженое изображение, используем его для генерации промпта через VLM
        if uploaded_image_path:
            # Любой запрос пользователя является запросом на изменения
            task_type = "editing"
            
            # st.info("🖼️ Обрабатываю изображение и текстовый запрос с помощью VLM...")
            enhanced_prompt = openrouter_client.generate_prompt_from_image(prompt, image_path=uploaded_image_path, task_type=task_type)
            st.success("✅ Промпт сгенерирован на основе изображения и текста")
            
            # Отображаем сгенерированный промпт
            with st.expander("📝 Промпт, сгенерированный на основе изображения"):
                st.write(enhanced_prompt)
        else:
            enhanced_prompt = openrouter_client.enhance_prompt(prompt, task_type="standard")
            
            if enhanced_prompt != prompt:
                with st.expander("📝 Улучшенный запрос"):
                    st.write(enhanced_prompt)
    except Exception as e:
        error_msg = f"❌ Ошибка при улучшении промпта: {str(e)}"
        st.error(error_msg)
        # Добавляем сообщение об ошибке в историю чата
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        
        # Устанавливаем состояние ошибки для отображения в интерфейсе
        if 'error_message' not in st.session_state:
            st.session_state.error_message = error_msg
        return []
    
    # Загружаем workflow для генерации изображений
    try:
        workflow = client.load_workflow(WORKFLOW_IMAGES)
        if not workflow:
            error_msg = "❌ Не удалось загрузить workflow для генерации изображений"
            st.error(error_msg)
            # Добавляем сообщение об ошибке в историю чата
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            
            # Устанавливаем состояние ошибки для отображения в интерфейсе
            if 'error_message' not in st.session_state:
                st.session_state.error_message = error_msg
            return []
            
        workflow["761"]["inputs"]["text"] = enhanced_prompt

    except Exception as e:
        error_msg = f"❌ Ошибка при подготовке workflow: {str(e)}"
        st.error(error_msg)
        # Добавляем сообщение об ошибке в историю чата
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        
        # Устанавливаем состояние ошибки для отображения в интерфейсе
        if 'error_message' not in st.session_state:
            st.session_state.error_message = error_msg
        return []

    # Если предоставлено загруженное изображение, генерируем только одно изображение
    if uploaded_image_path:
        # Для простоты в текущей реализации будем считать, что мы генерируем одно изображение
        # В реальности может потребоваться использование специальных нод для обработки изображений
        # st.info("🖼️ Генерирую изображение на основе загруженного изображения и описания...")
        
        try:
            # Запускаем workflow
            prompt_id = client.run_workflow(workflow)
            
            if not prompt_id:
                error_msg = "❌ Не удалось запустить workflow"
                st.error(error_msg)
                # Добавляем сообщение об ошибке в историю чата
                if 'messages' not in st.session_state:
                    st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # Устанавливаем состояние ошибки для отображения в интерфейсе
                if 'error_message' not in st.session_state:
                    st.session_state.error_message = error_msg
                return []
            
            # Ждем завершения генерации изображений
            result = client.wait_for_completion_image(prompt_id, st.session_state.messages if 'messages' in st.session_state else None)

            # Проверяем, есть ли результат
            if not result:
                error_msg = "❌ Не удалось дождаться завершения генерации изображения"
                st.error(error_msg)
                # Добавляем сообщение об ошибке в историю чата
                if 'messages' not in st.session_state:
                    st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # Устанавливаем состояние ошибки для отображения в интерфейсе
                if 'error_message' not in st.session_state:
                    st.session_state.error_message = error_msg
                return []
            
            # Извлекаем изображения
            image_urls = get_images_from_history(client, prompt_id, 1)
            
            if not image_urls:
                error_msg = "❌ Не удалось получить URL изображения после генерации"
                st.error(error_msg)
                # Добавляем сообщение об ошибке в историю чата
                if 'messages' not in st.session_state:
                    st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # Устанавливаем состояние ошибки для отображения в интерфейсе
                if 'error_message' not in st.session_state:
                    st.session_state.error_message = error_msg
                return []
            
            return image_urls
        except Exception as e:
            error_msg = f"❌ Ошибка при генерации изображения: {str(e)}"
            st.error(error_msg)
            # Добавляем сообщение об ошибке в историю чата
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            
            # Устанавливаем состояние ошибки для отображения в интерфейсе
            if 'error_message' not in st.session_state:
                st.session_state.error_message = error_msg
            return []
    else:
        # Генерируем несколько изображений за один запуск workflow
        all_image_urls = []
        # st.info(f"🖼️ Генерирую {num_images} варианта(ов) изображений...")
        
        try:
            # Модифицируем batch_size в workflow, чтобы соответствовал количеству изображений
            if "759" in workflow:
                workflow["759"]["inputs"]["batch_size"] = num_images
                # st.info(f"📊 Установлен batch_size в {num_images}")
            
            # Запускаем workflow только один раз
            prompt_id = client.run_workflow(workflow)
            if not prompt_id:
                error_msg = f"❌ Не удалось запустить workflow для генерации изображений"
                st.error(error_msg)
                # Добавляем сообщение об ошибке в историю чата
                if 'messages' not in st.session_state:
                    st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # Устанавливаем состояние ошибки для отображения в интерфейсе
                if 'error_message' not in st.session_state:
                    st.session_state.error_message = error_msg
                return []
            
            # Ждем завершения генерации изображений
            result = client.wait_for_completion_image(prompt_id, st.session_state.messages if 'messages' in st.session_state else None)

            # Проверяем, есть ли результат
            if not result:
                error_msg = f"❌ Не удалось дождаться завершения генерации изображений"
                st.error(error_msg)
                # Добавляем сообщение об ошибке в историю чата
                if 'messages' not in st.session_state:
                    st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # Устанавливаем состояние ошибки для отображения в интерфейсе
                if 'error_message' not in st.session_state:
                    st.session_state.error_message = error_msg
                return []
            
            # Извлекаем все изображения (num_images штук) за один раз
            image_urls = get_images_from_history(client, prompt_id, num_images)
            
            if not image_urls:
                error_msg = f"❌ Не удалось получить URL изображений после генерации"
                st.error(error_msg)
                # Добавляем сообщение об ошибке в историю чата
                if 'messages' not in st.session_state:
                    st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # Устанавливаем состояние ошибки для отображения в интерфейсе
                if 'error_message' not in st.session_state:
                    st.session_state.error_message = error_msg
                return []
            
            # Проверяем, что получили ожидаемое количество изображений
            #if len(image_urls) < num_images:
                # st.warning(f"⚠️ Получено {len(image_urls)} изображений вместо {num_images}, возвращаем доступные")
            
            return image_urls
        
        except Exception as e:
            error_msg = f"❌ Ошибка при генерации изображений: {str(e)}"
            st.error(error_msg)
            # Добавляем сообщение об ошибке в историю чата
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            
            # Устанавливаем состояние ошибки для отображения в интерфейсе
            if 'error_message' not in st.session_state:
                st.session_state.error_message = error_msg
            return []

def generate_images_from_image(uploaded_file, text_prompt: str, client: ComfyUIClient, num_images: int = 1, pregenerated_prompt: str = None):
    """
    Генерирует изображения на основе загруженного изображения и текстового описания
    
    Args:
        uploaded_file: Загруженный файл изображения
        text_prompt: Текстовое описание/запрос
        client: Экземпляр ComfyUIClient
        num_images: Количество изображений для генерации
        pregenerated_prompt: Уже сгенерированный промпт (если есть)
    
    Returns:
        list: Список URL сгенерированных изображений
    """
    # Сохраняем загруженное изображение во временный файл
    temp_image_path = save_uploaded_image(uploaded_file)
    if not temp_image_path:
        st.error("❌ Не удалось сохранить загруженное изображение")
        return []
    
    try:
        # Создаем экземпляр OpenRouterClient
        openrouter_client = OpenRouterClient()
        
        if pregenerated_prompt is not None:
            # Если промпт уже сгенерирован, используем его
            enhanced_prompt = pregenerated_prompt
            #st.success("✅ Использую предварительно сгенерированный промпт")
        else:
            # Любой запрос пользователя является запросом на изменения
            task_type = "editing"
            
            # Генерируем улучшенный промпт на основе изображения и текста
            # st.info("🖼️ Обрабатываю изображение и текстовый запрос с помощью VLM...")
            enhanced_prompt = openrouter_client.generate_prompt_from_image(text_prompt, image_path=temp_image_path, task_type=task_type)
            #st.success("✅ Промпт сгенерирован на основе изображения и текста")
            
            # Отображаем сгенерированный промпт
            with st.expander("📝 Промпт, сгенерированный на основе изображения"):
                st.write(enhanced_prompt)
        
        # Загружаем workflow для генерации изображений
        workflow = client.load_workflow(WORKFLOW_IMAGES)
        if not workflow:
            error_msg = "❌ Не удалось загрузить workflow для генерации изображений"
            st.error(error_msg)
            # Добавляем сообщение об ошибке в историю чата
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            
            # Устанавливаем состояние ошибки для отображения в интерфейсе
            if 'error_message' not in st.session_state:
                st.session_state.error_message = error_msg
            return []
        
        # Обновляем промпт в workflow
        workflow["761"]["inputs"]["text"] = enhanced_prompt
        workflow["759"]["inputs"]["batch_size"] = 1

        # Генерируем изображения
        # st.info(f"🖼️ Генерирую {num_images} изображение(ий) на основе вашего запроса...")
        
        # Запускаем workflow
        prompt_id = client.run_workflow(workflow)
        if not prompt_id:
            error_msg = "❌ Не удалось запустить workflow для генерации изображений"
            st.error(error_msg)
            # Добавляем сообщение об ошибке в историю чата
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            
            # Устанавливаем состояние ошибки для отображения в интерфейсе
            if 'error_message' not in st.session_state:
                st.session_state.error_message = error_msg
            return []
        
        # Ждем завершения генерации изображений
        result = client.wait_for_completion_image(prompt_id, st.session_state.messages if 'messages' in st.session_state else None)

        # Проверяем, есть ли результат
        if not result:
            error_msg = "❌ Не удалось дождаться завершения генерации изображений"
            st.error(error_msg)
            # Добавляем сообщение об ошибке в историю чата
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            
            # Устанавливаем состояние ошибки для отображения в интерфейсе
            if 'error_message' not in st.session_state:
                st.session_state.error_message = error_msg
            return []
        
        # Извлекаем изображения
        image_urls = get_images_from_history(client, prompt_id, num_images)
        
        if not image_urls:
            error_msg = "❌ Не удалось получить URL изображений после генерации"
            st.error(error_msg)
            # Добавляем сообщение об ошибке в историю чата
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            
            # Устанавливаем состояние ошибки для отображения в интерфейсе
            if 'error_message' not in st.session_state:
                st.session_state.error_message = error_msg
            return []
        
        # Убедимся, что возвращаемое количество изображений соответствует ожидаемому
        #if len(image_urls) < num_images:
            # st.warning(f"⚠️ Получено {len(image_urls)} изображений вместо {num_images}, возвращаем доступные")
        
        return image_urls
        
    finally:
        # Удаляем временный файл
        cleanup_temp_file(temp_image_path)

def get_images_from_history(client, prompt_id, num_images=1):
    """
    Извлечение информации о сгенерированных изображениях из истории выполнения
    """
    # Используем встроенный метод клиента ComfyUI для получения URL изображений
    try:
        # Получаем изображения с помощью клиента
        image_urls = client.get_image_urls(history_data=None, prompt_id=prompt_id, max_images=num_images)
        
        if image_urls:
            st.success(f"✅ Изображения готовы")
        else:
            st.warning("⚠️ Не удалось найти изображения в результатах")
        
        # Возвращаем URL изображений, которые могут быть использованы напрямую в 3D-генерации
        return image_urls
    except Exception as e:
        st.error(f"❌ Ошибка при извлечении изображений из истории: {e}")
        return []


def generate_3d_from_image(client: ComfyUIClient, image_filename: str = None, gdrive_url: str = None, file_id: str = None):
    """
    Generates a 3D model from an image using the new Load Image (from Outputs) node.
    Accepts the filename of an image that already exists in ComfyUI's output folder or a Google Drive URL.
    Returns the 3D model URL.
    """
    st.info("Создаю 3D-модель")
    
    # Если указан URL модели из Google Drive, скачиваем её
    if gdrive_url or file_id:
        # Создаем путь для сохранения модели
        import os
        from pathlib import Path
        
        # Определяем имя файла из URL или используем временное имя
        if file_id:
            # Если указан file_id, используем фиксированное имя файла
            output_path = f"3D_models/model.glb"
        elif gdrive_url and '/d/' in gdrive_url:
            # Извлекаем ID файла из URL
            import re
            match = re.search(r'/d/([^/]+)', gdrive_url)
            file_id_from_url = match.group(1) if match else "unknown"
            output_path = f"3D_models/model.glb"
        else:
            # Используем фиксированное имя файла
            output_path = f"3D_models/model.glb"
        
        # Создаем директорию, если она не существует
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Скачиваем модель из Google Drive
        download_success = client.download_model_from_gdrive(gdrive_url=gdrive_url, output_path=output_path, file_id=file_id)
        if download_success:
            # st.success(f"✅ Модель скачана")
            # Возвращаем путь к скачанной модели
            return output_path
        else:
            st.error("❌ Не удалось скачать модель из Google Drive")
            return ""
    elif not image_filename:
        # Если не указано ни изображение, ни Google Drive URL, возвращаем ошибку
        st.error("Не предоставлено имя файла изображения для генерации 3D-модели")
        return ""
    else:
        # Загружаем workflow для 3D
        workflow = client.load_workflow(WORKFLOW_3D)
        if not workflow:
            return ""
        
        # Если передан полный URL изображения, извлекаем из него имя файла
        if image_filename.startswith('http'):
            import urllib.parse
            parsed_url = urllib.parse.urlparse(image_filename)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            extracted_filename = query_params.get('filename', [None])[0]
            if extracted_filename:
                image_filename = extracted_filename  # Сохраняем полное имя файла с расширением
        
        # Убираем '[output]' из имени файла, если оно там есть, чтобы избежать дублирования
        if '[output]' in image_filename:
            clean_filename = image_filename.replace(' [output]', '')
        else:
            clean_filename = image_filename
        
        # Убираем концевые пробелы из имени файла
        clean_filename = clean_filename.strip()
        
        # Убираем символ подчеркивания в конце, если он есть
        if clean_filename.endswith('_'):
            clean_filename = clean_filename[:-1]
        
        # Подставляем имя файла в ноду LoadImageOutput (ID "19")
        output_filename = f"{clean_filename} [output]"
        
        # Обновляем ноду LoadImageOutput в workflow
        if "19" in workflow:
            workflow["19"]["inputs"]["image"] = output_filename
            # st.success(f"✅ Изображение в ноде 19 обновлено: {output_filename}")
        else:
            st.error("❌ Нода LoadImageOutput (ID 19) не найдена в workflow")
            return ""

        # Запускаем генерацию 3D
        prompt_id = client.run_workflow(workflow, True)
        if not prompt_id:
            return ""

        # Ждем завершения (3D-генерация дольше)
        result = client.wait_for_completion_model(prompt_id, st.session_state.messages if 'messages' in st.session_state else None)

        if result.get("status") == "error":
            st.error(f"❌ Ошибка 3D-модели: {result.get('error_message', 'Неизвестная ошибка')}")
            return ""
        elif result.get("status") == "timeout":
            st.error("❌ Время ожидания генерации 3D-модели истекло")
            return ""
        else:
            # Извлекаем 3D-модель
            # Проверяем, была ли модель уже скачана в процессе ожидания завершения
            if hasattr(client, 'ouput_path') and client.ouput_path:
                downloaded_model_path = client.ouput_path
            else:
                downloaded_model_path = client.download_latest_model_from_gdrive()
            
            if downloaded_model_path:
                # Если скачанная модель в формате GLB, конвертируем в STL
                if downloaded_model_path.endswith('.glb'):
                    try:
                        # Конвертируем в STL
                        stl_path = client.convert_glb_to_stl(downloaded_model_path)
                        if stl_path:
                            result = stl_path
                        else:
                            st.error("❌ Не удалось конвертировать GLB в STL")
                            result = downloaded_model_path
                    except Exception as e:
                        st.error(f"❌ Ошибка при конвертации модели: {str(e)}")
                        result = downloaded_model_path
                else:
                    # Если модель не в формате GLB, возвращаем путь к скачанному файлу
                    result = downloaded_model_path
            else:
                # st.warning("Проблема с установкой модели")
                result = ""
            
            # После завершения генерации 3D модели, очищаем папку с изображениями на GDrive
            try:
                client.clear_images_gdrive_folder()
            except Exception as e:
                st.warning(f"⚠️ Не удалось очистить папку с изображениями на GDrive: {str(e)}")
            
            return result