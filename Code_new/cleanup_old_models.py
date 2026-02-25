import os
import glob

def cleanup_old_models():
    """Удаляет старые GLB файлы с именами вида ComfyUI_XXXXX_.glb из папки 3D_models"""
    old_files = glob.glob("3D_models/ComfyUI_*.glb")
    old_files.extend(glob.glob("3D_models/downloaded_model_*.glb"))
    
    print(f"Найдено {len(old_files)} старых файлов для удаления:")
    for file in old_files:
        print(f"  - {file}")
    
    if old_files:
        for file in old_files:
            try:
                os.remove(file)
                print(f"Удален: {file}")
            except OSError as e:
                print(f"Ошибка при удалении {file}: {e}")
        print("Удаление завершено.")
    else:
        print("Старые файлы не найдены.")

if __name__ == "__main__":
    cleanup_old_models()