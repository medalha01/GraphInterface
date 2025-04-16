# graphics_editor/main.py
import sys
import os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QLocale  # Import QLocale
from PyQt5.QtGui import QIcon, QPixmap, QPainter


def main():
    """Configura e executa a aplicação do editor gráfico."""

    # Configuração da Aplicação Qt
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Define o Locale para PT-BR para consistência (pode afetar validadores, etc.)
    # QLocale.setDefault(QLocale(QLocale.Portuguese, QLocale.Brazil))
    # Usar o do sistema pode ser mais flexível, mas esteja ciente das diferenças (ex: vírgula vs ponto)
    QLocale.setDefault(QLocale.system())

    app = QApplication(sys.argv)

    # Define um ícone para a aplicação (opcional)
    # app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons", "app_icon.png")))

    # Importa a janela principal *depois* de configurar QApplication
    try:
        # Tentativa de import relativo padrão
        from graphics_editor.editor import GraphicsEditor
    except ImportError as e1:
        try:
            # Tentativa de import relativo ao diretório pai (útil se executado de dentro da pasta)
            sys.path.insert(
                0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            )
            from graphics_editor.editor import GraphicsEditor

            print("INFO: Importado GraphicsEditor do diretório pai.")
        except ImportError as e2:
            print(f"ERRO CRÍTICO: Não foi possível importar GraphicsEditor.")
            print(f"Erro original: {e1}")
            print(f"Erro fallback: {e2}")
            print(
                "Verifique se o pacote 'graphics_editor' está acessível (PYTHONPATH)."
            )
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Erro de Importação")
            msg_box.setText("Não foi possível iniciar o editor.")
            msg_box.setInformativeText(
                "Falha ao importar o componente principal 'GraphicsEditor'.\nVerifique a instalação e a estrutura do projeto."
            )
            msg_box.exec_()
            sys.exit(1)
    except Exception as e:
        print(f"ERRO CRÍTICO: Erro inesperado ao importar GraphicsEditor: {e}")
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Erro Inesperado")
            msg_box.setText("Ocorreu um erro inesperado ao iniciar.")
            msg_box.setInformativeText(str(e))
            msg_box.exec_()
        except Exception:
            pass  # Ignora erro ao mostrar o erro
        sys.exit(1)

    # Cria e exibe a janela do editor
    editor = GraphicsEditor()
    editor.show()

    # Inicia o loop de eventos da aplicação Qt
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
