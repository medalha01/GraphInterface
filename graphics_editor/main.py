# graphics_editor/main.py
import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# --- Dummy Icon Creation (Moved here from editor.py) ---
def create_dummy_icons():
    """Creates placeholder icon files if they don't exist."""
    icon_dir = "icons"
    if not os.path.isabs(icon_dir): # Handle running from different directories
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_dir = os.path.join(script_dir, icon_dir)

    os.makedirs(icon_dir, exist_ok=True)
    dummy_icons = [
        "select.png", "pan.png", "point.png", "line.png", "polygon.png",
        "coords.png", "transform.png", "add.png", "clear.png",
        "open.png", "save.png", "exit.png",
    ]
    for icon_name in dummy_icons:
        icon_path = os.path.join(icon_dir, icon_name)
        if not os.path.exists(icon_path):
            try:
                from PIL import Image, ImageDraw # Optional dependency

                img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.rectangle([(2, 2), (21, 21)], outline="gray", width=1)
                draw.text((4, 4), icon_name[:2], fill="black")
                img.save(icon_path)
                # print(f"Criado ícone dummy: {icon_path}")
            except ImportError:
                # print(f"Pillow não instalado, criando arquivo vazio para: {icon_path}")
                open(icon_path, "w").close() # Create empty file as fallback
            except Exception as e:
                print(f"Erro ao criar ícone dummy {icon_path}: {e}")
                open(icon_path, "w").close() # Create empty file as fallback


def main():
    """Sets up and runs the graphics editor application."""
    # Create icons if missing (especially useful for first run)
    create_dummy_icons()

    # Configure Qt application attributes
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # Import the editor window class *after* QApplication is initialized
    # and potential dependencies (like icons) are handled.
    try:
        from graphics_editor.editor import GraphicsEditor
    except ImportError as e:
        print(f"Erro ao importar GraphicsEditor: {e}")
        print("Certifique-se de que o pacote está instalado ou o PYTHONPATH está configurado.")
        sys.exit(1)

    editor = GraphicsEditor()
    editor.show() # Show the editor window
    sys.exit(app.exec_()) # Start the Qt event loop


if __name__ == "__main__":
    main()
