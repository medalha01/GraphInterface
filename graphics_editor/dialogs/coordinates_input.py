# graphics_editor/dialogs/coordinates_input.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QMessageBox, QCheckBox, QWidget, QColorDialog,
                             QScrollArea)
from PyQt5.QtGui import QColor, QPalette, QDoubleValidator, QIcon, QPixmap
from PyQt5.QtCore import Qt, QSize
from typing import List, Tuple, Optional, Union, Any
import os # Para construir caminho do ícone

class CoordinateInputDialog(QDialog):
    """
    Diálogo para permitir ao usuário inserir coordenadas (e cor) manualmente
    para criar Pontos, Linhas ou Polígonos.
    """

    def __init__(self, parent: Optional[QWidget] = None, mode: str = 'point'):
        """
        Inicializa o diálogo.
        Args:
            parent: O widget pai.
            mode: O tipo de forma a ser criada ('point', 'line' ou 'polygon').
        """
        super().__init__(parent)
        self.mode: str = mode.lower()
        if self.mode not in ['point', 'line', 'polygon']:
            raise ValueError(f"Modo inválido para CoordinateInputDialog: '{self.mode}'. Use 'point', 'line' ou 'polygon'.")

        self.setWindowTitle(f"Inserir Coordenadas - {self.mode.capitalize()}")
        # Lista para armazenar widgets de entrada de pontos (apenas para polígono)
        self.polygon_point_widgets: List[Tuple[QLineEdit, QLineEdit]] = []
        self._selected_color: QColor = QColor(Qt.black) # Cor padrão inicial
        # Validador para permitir números decimais nas entradas de coordenadas
        self._double_validator = QDoubleValidator(-99999.99, 99999.99, 2, self) # Aceita até 2 casas decimais

        # --- Caminho Base para Ícones ---
        self._icon_base_path = os.path.join(os.path.dirname(__file__), "..", "icons")

        self._setup_ui()
        self.setMinimumWidth(400) # Garante largura mínima para melhor visualização

    def set_initial_color(self, color: QColor) -> None:
        """Define a cor inicial que será exibida no botão de cor."""
        if color.isValid():
            self._selected_color = color
            self._update_color_button_preview() # Atualiza a cor do botão

    def _get_icon(self, name: str) -> QIcon:
        """Carrega um QIcon do diretório de ícones."""
        # Constrói o caminho relativo ao diretório atual do script
        icon_path = os.path.join(self._icon_base_path, name)
        if not os.path.exists(icon_path):
             print(f"Aviso: Ícone não encontrado em {icon_path}")
             return QIcon() # Retorna ícone vazio se não encontrado
        return QIcon(icon_path)

    def _setup_ui(self) -> None:
        """Configura os elementos da interface do usuário do diálogo."""
        main_layout = QVBoxLayout(self)

        # --- Campos de Entrada de Coordenadas (variam por modo) ---
        if self.mode == 'point':
            # Layout simples para X e Y
            self.x_input = self._create_coord_input(main_layout, "Coordenada X:")
            self.y_input = self._create_coord_input(main_layout, "Coordenada Y:")
        elif self.mode == 'line':
            # Layout para X1, Y1 (inicial) e X2, Y2 (final)
            self.x1_input = self._create_coord_input(main_layout, "X Inicial:")
            self.y1_input = self._create_coord_input(main_layout, "Y Inicial:")
            self.x2_input = self._create_coord_input(main_layout, "X Final:")
            self.y2_input = self._create_coord_input(main_layout, "Y Final:")
        elif self.mode == 'polygon':
            # Usa uma ScrollArea para lidar com muitos pontos
            scroll_area = QScrollArea(self)
            scroll_area.setWidgetResizable(True) # Permite que o widget interno redimensione
            scroll_content_widget = QWidget() # Widget que conterá o layout dos pontos
            # Layout vertical dentro do widget de conteúdo da scroll area
            self.polygon_input_layout = QVBoxLayout(scroll_content_widget)
            self.polygon_input_layout.setContentsMargins(5, 5, 5, 5)
            self.polygon_input_layout.setSpacing(6)
            scroll_area.setWidget(scroll_content_widget) # Define o widget da scroll area
            main_layout.addWidget(scroll_area, 1) # Adiciona a scroll area ao layout principal

            # Controles abaixo da lista de pontos (checkbox, botão adicionar)
            controls_layout = QHBoxLayout()
            self.open_polygon_checkbox = QCheckBox("Polígono Aberto (Polilinha)")
            controls_layout.addWidget(self.open_polygon_checkbox)
            controls_layout.addStretch()
            # Botão para adicionar mais campos de ponto dinamicamente
            add_point_btn = QPushButton(self._get_icon("add.png"), " Ponto")
            add_point_btn.setIconSize(QSize(16, 16))
            add_point_btn.setToolTip("Adicionar campos para mais um ponto do polígono")
            add_point_btn.clicked.connect(self._add_polygon_point_inputs)
            controls_layout.addWidget(add_point_btn)
            main_layout.addLayout(controls_layout)

            # Adiciona os primeiros 3 conjuntos de campos de ponto por padrão
            for _ in range(3):
                self._add_polygon_point_inputs()

        # --- Seleção de Cor (Comum a todos os modos) ---
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Cor do Objeto:"))
        self.color_button = QPushButton() # Botão que mostrará a cor
        self.color_button.setToolTip("Clique para selecionar a cor do objeto")
        self.color_button.setFixedSize(QSize(40, 24)) # Tamanho fixo para o preview da cor
        self.color_button.setFlat(True) # Aparência mais "plana"
        self.color_button.setAutoFillBackground(True) # Necessário para stylesheet funcionar bem
        self.color_button.clicked.connect(self._choose_color) # Abre QColorDialog ao clicar
        self._update_color_button_preview() # Define a cor inicial no botão
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        main_layout.addLayout(color_layout)

        # --- Botões OK/Cancelar (Comum a todos os modos) ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch() # Empurra botões para a direita
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancelar")
        ok_btn.clicked.connect(self._on_accept) # Valida e aceita
        cancel_btn.clicked.connect(self.reject) # Fecha sem aceitar
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

    def _create_coord_input(self, parent_layout: QVBoxLayout, label_text: str) -> QLineEdit:
        """
        Cria um par de QLabel e QLineEdit para entrada de uma coordenada (X ou Y).
        Args:
            parent_layout: O layout onde adicionar este par de widgets.
            label_text: O texto para o QLabel.
        Returns:
            O QLineEdit criado (para referência posterior).
        """
        coord_layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(70) # Largura fixa para alinhar os campos
        input_field = QLineEdit()
        input_field.setValidator(self._double_validator) # Aplica o validador de números
        input_field.setPlaceholderText("ex: 10.5") # Texto de ajuda
        coord_layout.addWidget(label)
        coord_layout.addWidget(input_field)
        parent_layout.addLayout(coord_layout) # Adiciona o layout horizontal ao layout principal
        return input_field

    def _add_polygon_point_inputs(self) -> None:
        """Adiciona um novo conjunto de campos (X, Y) para um vértice de polígono."""
        if self.mode != 'polygon': return # Só faz sentido no modo polígono

        point_index = len(self.polygon_point_widgets) + 1
        point_layout = QHBoxLayout() # Layout para os campos deste ponto
        point_layout.setContentsMargins(0, 0, 0, 0) # Sem margens extras

        x_input = QLineEdit()
        y_input = QLineEdit()
        x_input.setValidator(self._double_validator)
        y_input.setValidator(self._double_validator)
        x_input.setPlaceholderText("X")
        y_input.setPlaceholderText("Y")
        # Largura fixa para melhor alinhamento vertical
        x_input.setFixedWidth(100)
        y_input.setFixedWidth(100)

        point_layout.addWidget(QLabel(f"{point_index}:")) # Label "1:", "2:", etc.
        point_layout.addWidget(x_input)
        point_layout.addWidget(y_input)
        point_layout.addStretch() # Empurra para a esquerda

        # Adiciona o layout do ponto ao layout principal dentro da scroll area
        self.polygon_input_layout.addLayout(point_layout)
        # Guarda a referência aos QLineEdits criados
        self.polygon_point_widgets.append((x_input, y_input))

    def _choose_color(self) -> None:
        """Abre o QColorDialog para o usuário escolher uma cor."""
        color = QColorDialog.getColor(self._selected_color, self, "Selecionar Cor do Objeto")
        if color.isValid(): # Se o usuário selecionou uma cor e clicou OK
            self._selected_color = color
            self._update_color_button_preview() # Atualiza o botão

    def _update_color_button_preview(self) -> None:
        """Atualiza a cor de fundo do botão de cor."""
        # Usa stylesheet para definir a cor de fundo e uma borda
        self.color_button.setStyleSheet(f"background-color: {self._selected_color.name()}; border: 1px solid gray;")

    def _on_accept(self) -> None:
        """Chamado quando o botão OK é clicado. Valida os dados antes de aceitar."""
        # Chama get_coordinates que faz a validação e mostra QMessageBox se falhar
        if self.get_coordinates() is not None:
            self.accept() # Fecha o diálogo com status Accepted se a validação passar

    def get_coordinates(self) -> Optional[Union[Tuple[List[Tuple[float, float]], QColor],
                                                Tuple[List[Tuple[float, float]], bool, QColor]]]:
        """
        Valida as entradas e retorna os dados formatados ou None se inválido.
        Retorna:
            - Point: Tuple[List[Tuple[float, float]], QColor] (lista com 1 ponto)
            - Line: Tuple[List[Tuple[float, float]], QColor] (lista com 2 pontos)
            - Polygon: Tuple[List[Tuple[float, float]], bool, QColor] (lista com N pontos, is_open)
            - None: Se a validação falhar.
        """
        coords: List[Tuple[float, float]] = []
        raw_texts: List[Tuple[Optional[str], Optional[str]]] = [] # Armazena textos antes da conversão

        try:
            # 1. Coleta os textos das caixas de entrada apropriadas
            if self.mode == 'point':
                raw_texts = [(self.x_input.text(), self.y_input.text())]
                if not raw_texts[0][0] or not raw_texts[0][1]:
                     raise ValueError("Coordenadas X e Y são obrigatórias para o ponto.")
            elif self.mode == 'line':
                raw_texts = [
                    (self.x1_input.text(), self.y1_input.text()),
                    (self.x2_input.text(), self.y2_input.text())
                ]
                if not all(raw_texts[0]) or not all(raw_texts[1]):
                     raise ValueError("Todas as 4 coordenadas (X1, Y1, X2, Y2) são obrigatórias para a linha.")
            elif self.mode == 'polygon':
                # Coleta apenas dos campos que foram preenchidos (ambos X e Y)
                for i, (x_input, y_input) in enumerate(self.polygon_point_widgets):
                     x_text = x_input.text().strip()
                     y_text = y_input.text().strip()
                     if x_text and y_text: # Se ambos estão preenchidos
                          raw_texts.append((x_text, y_text))
                     elif x_text or y_text: # Se apenas um está preenchido
                          raise ValueError(f"Ponto {i + 1}: Ambas as coordenadas X e Y devem ser preenchidas ou ambas deixadas em branco.")
                # Valida número mínimo de pontos preenchidos
                min_points = 2 if self.open_polygon_checkbox.isChecked() else 3
                if len(raw_texts) < min_points:
                    type_str = "aberto (polilinha)" if self.open_polygon_checkbox.isChecked() else "fechado"
                    raise ValueError(f"Polígono {type_str} requer pelo menos {min_points} pontos com coordenadas X e Y preenchidas (foram inseridos {len(raw_texts)}).")

            # 2. Converte os textos coletados para float
            for i, (x_text, y_text) in enumerate(raw_texts):
                # Garante que x_text e y_text não sejam None (embora a lógica acima deva prevenir isso)
                if x_text is None or y_text is None: continue # Segurança

                try:
                    # Substitui vírgula por ponto para aceitar ambos como separador decimal
                    x = float(x_text.strip().replace(',', '.'))
                    y = float(y_text.strip().replace(',', '.'))
                    coords.append((x, y))
                except ValueError:
                     # Define uma descrição do ponto para a mensagem de erro
                     point_desc = ""
                     if self.mode == 'point': point_desc = "Ponto"
                     elif self.mode == 'line': point_desc = "Ponto Inicial" if i == 0 else "Ponto Final"
                     elif self.mode == 'polygon': point_desc = f"Ponto {i + 1}"
                     raise ValueError(f"{point_desc}: Coordenadas '{x_text}', '{y_text}' inválidas. Use números (ex: 10.5 ou -20).")

            # 3. Retorna os dados no formato correto para cada modo
            if self.mode in ['point', 'line']:
                return coords, self._selected_color # Retorna lista de coords e cor
            elif self.mode == 'polygon':
                is_open = self.open_polygon_checkbox.isChecked()
                return coords, is_open, self._selected_color # Retorna coords, flag e cor

            # Se chegou aqui, algo deu errado (não deveria)
            return None

        except ValueError as e:
            # Exibe a mensagem de erro da validação para o usuário
            QMessageBox.warning(self, "Entrada Inválida", str(e))
            return None # Retorna None indicando falha na validação
