# graphics_editor/main.py
import sys
import os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QLocale
from PyQt5.QtGui import QIcon
import traceback


def main():
    """Configura e executa a aplicação do editor gráfico."""
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QLocale.setDefault(QLocale.system())
    app = QApplication(sys.argv)

    # app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons", "app_icon.png")))

    try:
        # Adjust import path if necessary, but should work if run correctly
        from graphics_editor.editor import GraphicsEditor  # Import the main window
    except ImportError as e:
        print("--- ERRO CRÍTICO DE IMPORTAÇÃO ---", file=sys.stderr)
        traceback.print_exc()  # Print the full stack trace to standard error
        print("---------------------------------", file=sys.stderr)
        QMessageBox.critical(
            None,
            "Erro de Importação",
            f"Falha ao importar componentes necessários.\n\nErro: {e}\n\nVeja o console para detalhes.",
        )
        sys.exit(1)
    except Exception as e:
        print(f"ERRO CRÍTICO: Erro inesperado ao importar: {e}")
        traceback.print_exc()
        QMessageBox.critical(
            None, "Erro Inesperado", f"Ocorreu um erro inesperado ao iniciar:\n{e}"
        )
        sys.exit(1)

    editor = GraphicsEditor()
    editor.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
