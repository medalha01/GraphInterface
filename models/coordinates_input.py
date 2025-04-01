# models/coordinates_input.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QMessageBox, QCheckBox, QWidget, QColorDialog,
                             QScrollArea)
from PyQt5.QtGui import QColor, QPalette, QDoubleValidator, QIcon, QPixmap
from PyQt5.QtCore import Qt, QSize
from typing import List, Tuple, Optional, Union, Any

class CoordinateInputDialog(QDialog):
    """Diálogo para inserir coordenadas manualmente e cor para formas."""

    def __init__(self, parent: Optional[QWidget] = None, mode: str = 'point'):
        super().__init__(parent)
        self.mode: str = mode.lower()
        if self.mode not in ['point', 'line', 'polygon']:
            raise ValueError(f"Modo inválido para CoordinateInputDialog: {self.mode}")

        self.setWindowTitle(f"Inserir Coordenadas - {self.mode.capitalize()}")
        self.polygon_point_widgets: List[Tuple[QLineEdit, QLineEdit]] = []
        self._selected_color: QColor = QColor(Qt.black)
        self._double_validator = QDoubleValidator(-99999.99, 99999.99, 2, self)
        self._setup_ui()
        self.setMinimumWidth(400)

    def set_initial_color(self, color: QColor):
        """Define a cor inicial exibida no diálogo."""
        if color.isValid():
            self._selected_color = color
            self._update_color_button_preview()

    def _setup_ui(self) -> None:
        """Configura os elementos da interface do usuário para o diálogo."""
        main_layout = QVBoxLayout(self)

        if self.mode == 'point':
            self.x_input = self._create_coord_input(main_layout, "Coordenada X:")
            self.y_input = self._create_coord_input(main_layout, "Coordenada Y:")
        elif self.mode == 'line':
            self.x1_input = self._create_coord_input(main_layout, "X Inicial:")
            self.y1_input = self._create_coord_input(main_layout, "Y Inicial:")
            self.x2_input = self._create_coord_input(main_layout, "X Final:")
            self.y2_input = self._create_coord_input(main_layout, "Y Final:")
        elif self.mode == 'polygon':
            scroll_area = QScrollArea(self)
            scroll_area.setWidgetResizable(True)
            scroll_content_widget = QWidget()
            self.polygon_input_layout = QVBoxLayout(scroll_content_widget)
            self.polygon_input_layout.setContentsMargins(5, 5, 5, 5)
            self.polygon_input_layout.setSpacing(6)
            scroll_area.setWidget(scroll_content_widget)
            main_layout.addWidget(scroll_area, 1)

            controls_layout = QHBoxLayout()
            self.open_polygon_checkbox = QCheckBox("Polígono Aberto")
            controls_layout.addWidget(self.open_polygon_checkbox)
            controls_layout.addStretch()
            # Make sure 'icons/add.png' exists or is created by the main script
            add_point_btn = QPushButton(QIcon("icons/add.png"), "Adicionar Ponto")
            add_point_btn.setIconSize(QSize(16, 16))
            add_point_btn.setToolTip("Adicionar campos para mais um ponto")
            add_point_btn.clicked.connect(self._add_polygon_point_inputs)
            controls_layout.addWidget(add_point_btn)
            main_layout.addLayout(controls_layout)

            for _ in range(3):
                self._add_polygon_point_inputs()

        # --- Seleção de Cor ---
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Cor:"))
        self.color_button = QPushButton()
        self.color_button.setToolTip("Clique para selecionar a cor do objeto")
        self.color_button.setFixedSize(QSize(40, 24))
        self.color_button.setFlat(True)
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button_preview()
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        main_layout.addLayout(color_layout)

        # --- Botões OK/Cancelar ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancelar")
        ok_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)


    def _create_coord_input(self, layout: QVBoxLayout, label_text: str) -> QLineEdit:
        """Auxiliar para criar um rótulo e um line edit validado para uma coordenada."""
        coord_layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(70)
        input_field = QLineEdit()
        input_field.setValidator(self._double_validator)
        input_field.setPlaceholderText("ex: 10.5")
        coord_layout.addWidget(label)
        coord_layout.addWidget(input_field)
        layout.addLayout(coord_layout)
        return input_field

    def _add_polygon_point_inputs(self) -> None:
        """Adiciona campos de entrada X e Y para um vértice de polígono dentro do layout do polígono."""
        if self.mode != 'polygon': return

        point_index = len(self.polygon_point_widgets) + 1
        point_layout = QHBoxLayout()
        point_layout.setContentsMargins(0, 0, 0, 0)

        x_input = QLineEdit()
        y_input = QLineEdit()
        x_input.setValidator(self._double_validator)
        y_input.setValidator(self._double_validator)
        x_input.setPlaceholderText("X")
        y_input.setPlaceholderText("Y")
        x_input.setFixedWidth(80)
        y_input.setFixedWidth(80)

        point_layout.addWidget(QLabel(f"{point_index}:"))
        point_layout.addWidget(x_input)
        point_layout.addWidget(y_input)
        point_layout.addStretch()

        self.polygon_input_layout.addLayout(point_layout)
        self.polygon_point_widgets.append((x_input, y_input))


    def _choose_color(self):
        """Abre o diálogo de cores e atualiza a cor armazenada e a pré-visualização do botão."""
        color = QColorDialog.getColor(self._selected_color, self, "Selecionar Cor")
        if color.isValid():
            self._selected_color = color
            self._update_color_button_preview()

    def _update_color_button_preview(self):
        """Atualiza a aparência do botão de cor para mostrar a cor selecionada."""
        self.color_button.setStyleSheet(f"background-color: {self._selected_color.name()}; border: 1px solid gray;")

    def _on_accept(self):
        """Chamado quando OK é clicado. Realiza validação antes de aceitar."""
        if self.get_coordinates() is not None:
            self.accept()

    def get_coordinates(self) -> Optional[Union[Tuple[List[Tuple[float, float]], QColor],
                                                Tuple[List[Tuple[float, float]], bool, QColor]]]:
        """
        Analisa os campos de entrada, valida-os e retorna coordenadas
        e cor com base no modo. Retorna None se a validação falhar.
        Mostra um QMessageBox em caso de falha na validação.
        """
        coords: List[Tuple[float, float]] = []
        raw_coords: List[Tuple[str, str]] = []

        try:
            if self.mode == 'point':
                raw_coords = [(self.x_input.text(), self.y_input.text())]
                if not raw_coords[0][0] or not raw_coords[0][1]:
                     raise ValueError("Coordenadas X e Y são obrigatórias.")
            elif self.mode == 'line':
                raw_coords = [
                    (self.x1_input.text(), self.y1_input.text()),
                    (self.x2_input.text(), self.y2_input.text())
                ]
                if not all(raw_coords[0]) or not all(raw_coords[1]):
                     raise ValueError("Todas as 4 coordenadas da linha são obrigatórias.")
            elif self.mode == 'polygon':
                valid_points_count = 0
                for i, (x_input, y_input) in enumerate(self.polygon_point_widgets):
                     x_text = x_input.text().strip()
                     y_text = y_input.text().strip()
                     if x_text and y_text:
                          raw_coords.append((x_text, y_text))
                          valid_points_count += 1
                     elif x_text or y_text:
                          raise ValueError(f"Ponto {i + 1}: Ambas as coordenadas X e Y devem ser preenchidas ou ambas deixadas em branco.")
                if valid_points_count < 3:
                    raise ValueError(f"Polígono requer pelo menos 3 pontos com coordenadas X e Y preenchidas (foram inseridos {valid_points_count}).")

            for i, (x_text, y_text) in enumerate(raw_coords):
                try:
                    x = float(x_text.strip().replace(',', '.'))
                    y = float(y_text.strip().replace(',', '.'))
                    coords.append((x, y))
                except ValueError:
                     point_desc = f"Ponto {i+1}" if self.mode == 'polygon' else ("Ponto Inicial" if i==0 else "Ponto Final") if self.mode == 'line' else "Ponto"
                     raise ValueError(f"{point_desc}: Coordenadas '{x_text}', '{y_text}' inválidas. Use números (ex: 10.5 ou -20).")

            if self.mode in ['point', 'line']:
                return coords, self._selected_color
            elif self.mode == 'polygon':
                is_open = self.open_polygon_checkbox.isChecked()
                return coords, is_open, self._selected_color

            return None

        except ValueError as e:
            QMessageBox.warning(self, "Entrada Inválida", str(e))
            return None