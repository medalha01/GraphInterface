# graphics_editor/main.py
import sys
import os
import traceback
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QLocale
from PyQt5.QtGui import QIcon

# Define the base path for resources relative to this file's location
# This makes it work correctly whether run as a script or imported module
_RESOURCE_PATH = os.path.join(os.path.dirname(__file__), "resources")


def main():
    """Configura e executa a aplicação do editor gráfico."""
    # Enable high DPI scaling for better visuals on high-resolution displays
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Set the default locale for number formatting etc. to the system's locale
    QLocale.setDefault(QLocale.system())

    # Create the QApplication instance
    app = QApplication(sys.argv)

    # Set application icon (optional)
    # Ensure 'app_icon.png' exists in the 'resources/icons' directory
    icon_path = os.path.join(_RESOURCE_PATH, "icons", "app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"Warning: Application icon not found at {icon_path}")

    # --- Import the main window inside the try block ---
    # This helps catch import errors related to dependencies or structure
    editor_instance = None
    try:
        # Use relative import within the package structure
        from .editor import GraphicsEditor

        # Instantiate the main window
        editor_instance = GraphicsEditor()

    except ImportError as e:
        print("--- ERRO CRÍTICO DE IMPORTAÇÃO ---", file=sys.stderr)
        traceback.print_exc()  # Print full traceback to console
        print("---------------------------------", file=sys.stderr)
        # Show a user-friendly error message
        QMessageBox.critical(
            None,  # No parent window available yet
            "Erro de Importação",
            f"Falha ao importar componentes necessários da aplicação.\n\n"
            f"Erro: {e}\n\n"
            f"Verifique a instalação e a estrutura do projeto.\n"
            f"Consulte o console para detalhes técnicos.",
        )
        sys.exit(1)  # Exit if core components cannot be imported

    except Exception as e:
        # Catch any other unexpected errors during initialization
        print("--- ERRO CRÍTICO INESPERADO ---", file=sys.stderr)
        traceback.print_exc()
        print("-----------------------------", file=sys.stderr)
        QMessageBox.critical(
            None,
            "Erro Inesperado na Inicialização",
            f"Ocorreu um erro inesperado ao iniciar a aplicação:\n\n"
            f"{e}\n\n"
            f"Consulte o console para detalhes técnicos.",
        )
        sys.exit(1)

    # If initialization succeeded, show the window and start the event loop
    if editor_instance:
        editor_instance.show()
        sys.exit(app.exec_())
    else:
        # Should not happen if try/except is correct, but as a safeguard
        print("Erro: Instância do editor não foi criada.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Ensure the script runs the main function when executed directly
    main()
