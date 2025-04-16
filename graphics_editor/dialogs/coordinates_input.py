# graphics_editor/dialogs/coordinates_input.py
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QCheckBox,
    QWidget,
    QColorDialog,
    QScrollArea,
    QGroupBox,
    QSizePolicy,
)
from PyQt5.QtGui import QColor, QPalette, QDoubleValidator, QIcon, QPixmap
from PyQt5.QtCore import Qt, QSize, QLocale
from typing import List, Tuple, Optional, Union, Any, Dict
import os


class CoordinateInputDialog(QDialog):
    """Diálogo para inserir coordenadas e cor para criar formas."""

    def __init__(self, parent: Optional[QWidget] = None, mode: str = "point"):
        """
        Args:
            mode: 'point', 'line' ou 'polygon'.
        """
        super().__init__(parent)
        self.mode: str = mode.lower()
        if self.mode not in ["point", "line", "polygon"]:
            raise ValueError(
                f"Modo inválido: '{self.mode}'. Use 'point', 'line', 'polygon'."
            )

        self.setWindowTitle(f"Inserir Coordenadas - {self.mode.capitalize()}")
        self.polygon_point_widgets: List[Tuple[QLineEdit, QLineEdit]] = []
        self._selected_color: QColor = QColor(Qt.black)
        # Validador que aceita ponto ou vírgula, dependendo do Locale
        self._double_validator = QDoubleValidator(-99999.99, 99999.99, 6, self)
        self._double_validator.setNotation(QDoubleValidator.StandardNotation)
        # Usa o locale padrão definido em main.py ou do sistema
        self._double_validator.setLocale(QLocale())

        # Ícones
        self._icon_base_path = os.path.join(os.path.dirname(__file__), "..", "icons")

        self._validated_data: Optional[Dict[str, Any]] = (
            None  # Armazena dados validados no OK
        )

        self._setup_ui()
        self.setMinimumWidth(350)

    def set_initial_color(self, color: QColor) -> None:
        """Define a cor inicial."""
        if color.isValid():
            self._selected_color = color
            self._update_color_button_preview()

    def _get_icon(self, name: str) -> QIcon:
        """Carrega ícone ou placeholder."""
        icon_path = os.path.join(self._icon_base_path, name)
        return (
            QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        )  # Retorna ícone vazio se não achar

    def _setup_ui(self) -> None:
        """Configura a interface do diálogo."""
        main_layout = QVBoxLayout(self)

        # --- Entradas de Coordenadas ---
        input_container = QWidget()  # Container para inputs específicos do modo
        self.input_layout = QVBoxLayout(input_container)
        self.input_layout.setContentsMargins(0, 0, 0, 0)

        if self.mode == "point":
            self.x_input = self._create_coord_input(self.input_layout, "X:")
            self.y_input = self._create_coord_input(self.input_layout, "Y:")
        elif self.mode == "line":
            p1_group = QGroupBox("Ponto Inicial")
            p1_layout = QVBoxLayout()
            self.x1_input = self._create_coord_input(p1_layout, "X1:")
            self.y1_input = self._create_coord_input(p1_layout, "Y1:")
            p1_group.setLayout(p1_layout)
            self.input_layout.addWidget(p1_group)

            p2_group = QGroupBox("Ponto Final")
            p2_layout = QVBoxLayout()
            self.x2_input = self._create_coord_input(p2_layout, "X2:")
            self.y2_input = self._create_coord_input(p2_layout, "Y2:")
            p2_group.setLayout(p2_layout)
            self.input_layout.addWidget(p2_group)
        elif self.mode == "polygon":
            self.input_layout.addWidget(
                QLabel("Vértices do Polígono (mínimo 3 para fechado, 2 para aberto):")
            )
            # ScrollArea para os pontos
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setFixedHeight(180)
            scroll_content = QWidget()
            self.polygon_points_layout = QVBoxLayout(
                scroll_content
            )  # Layout dentro da scroll area
            self.polygon_points_layout.setSpacing(4)
            scroll_area.setWidget(scroll_content)
            self.input_layout.addWidget(scroll_area)

            # Controles (aberto/fechado, adicionar ponto)
            poly_options_layout = QHBoxLayout()
            self.open_polygon_checkbox = QCheckBox("Polilinha (Aberta)")
            self.open_polygon_checkbox.setToolTip(
                "Marque para criar uma sequência de linhas abertas."
            )
            poly_options_layout.addWidget(self.open_polygon_checkbox)
            poly_options_layout.addStretch()
            add_point_btn = QPushButton(self._get_icon("add.png"), " Vértice")
            add_point_btn.setToolTip("Adicionar campos para mais um vértice")
            add_point_btn.clicked.connect(self._add_polygon_point_inputs)
            poly_options_layout.addWidget(add_point_btn)
            self.input_layout.addLayout(poly_options_layout)

            # Adiciona os 3 primeiros campos de ponto
            for _ in range(3):
                self._add_polygon_point_inputs()

        main_layout.addWidget(input_container)

        # --- Seleção de Cor ---
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Cor:"))
        self.color_button = QPushButton()
        self.color_button.setToolTip("Clique para selecionar a cor")
        self.color_button.setFixedSize(QSize(40, 24))
        self.color_button.setAutoFillBackground(True)
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button_preview()
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        main_layout.addLayout(color_layout)

        # --- Botões OK/Cancelar ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        cancel_btn = QPushButton("Cancelar")
        ok_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

    def _create_coord_input(
        self, parent_layout: Union[QVBoxLayout, QHBoxLayout], label_text: str
    ) -> QLineEdit:
        """Cria um par QLabel/QLineEdit para uma coordenada."""
        h_layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(50)  # Largura fixa pequena
        input_field = QLineEdit()
        input_field.setValidator(self._double_validator)
        input_field.setPlaceholderText("Valor")
        input_field.setMinimumWidth(80)
        input_field.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )  # Expande horizontalmente
        h_layout.addWidget(label)
        h_layout.addWidget(input_field)
        # Adiciona ao layout pai
        parent_layout.addLayout(h_layout)
        return input_field

    def _add_polygon_point_inputs(self) -> None:
        """Adiciona campos X, Y para um vértice de polígono."""
        if self.mode != "polygon":
            return

        point_index = len(self.polygon_point_widgets) + 1
        point_layout = QHBoxLayout()
        point_layout.setContentsMargins(0, 0, 0, 0)
        x_input = QLineEdit()
        y_input = QLineEdit()
        x_input.setValidator(self._double_validator)
        y_input.setValidator(self._double_validator)
        x_input.setPlaceholderText("X")
        y_input.setPlaceholderText("Y")
        x_input.setMinimumWidth(70)
        y_input.setMinimumWidth(70)
        x_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        y_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        point_layout.addWidget(QLabel(f"{point_index}:"))
        point_layout.addWidget(x_input)
        point_layout.addWidget(y_input)
        # Botão Remover (opcional) - pode adicionar complexidade
        # remove_btn = QPushButton("X") ... connect ... addWidget ...
        # point_layout.addStretch() # Se não houver botão remover

        self.polygon_points_layout.addLayout(point_layout)
        self.polygon_point_widgets.append((x_input, y_input))

    def _choose_color(self) -> None:
        """Abre QColorDialog."""
        color = QColorDialog.getColor(self._selected_color, self, "Selecionar Cor")
        if color.isValid():
            self._selected_color = color
            self._update_color_button_preview()

    def _update_color_button_preview(self) -> None:
        """Atualiza a cor do botão."""
        if self._selected_color.isValid():
            self.color_button.setStyleSheet(
                f"background-color: {self._selected_color.name()}; border: 1px solid gray;"
            )
        else:
            self.color_button.setStyleSheet(
                "background-color: #eeeeee; border: 1px solid gray;"
            )

    def _on_accept(self) -> None:
        """Valida os dados e, se OK, armazena e fecha."""
        try:
            # Chama método de validação interno
            self._validated_data = self._validate_and_get_data()
            self.accept()  # Fecha com status Accepted
        except ValueError as e:
            QMessageBox.warning(self, "Entrada Inválida", str(e))
            self._validated_data = None  # Limpa dados em caso de erro

    def _validate_and_get_data(self) -> Dict[str, Any]:
        """
        Valida as entradas e retorna um dicionário com os dados formatados.
        Levanta ValueError com mensagem de erro se a validação falhar.
        """
        data: Dict[str, Any] = {"coords": []}
        raw_texts: List[Tuple[Optional[str], Optional[str]]] = []

        # 1. Coleta textos crus das entradas relevantes
        if self.mode == "point":
            raw_texts = [(self.x_input.text(), self.y_input.text())]
            if not all(raw_texts[0]):
                raise ValueError("Coordenadas X e Y são obrigatórias.")
        elif self.mode == "line":
            raw_texts = [
                (self.x1_input.text(), self.y1_input.text()),
                (self.x2_input.text(), self.y2_input.text()),
            ]
            if not all(raw_texts[0]) or not all(raw_texts[1]):
                raise ValueError(
                    "Todas as 4 coordenadas são obrigatórias para a linha."
                )
        elif self.mode == "polygon":
            # Coleta apenas de campos preenchidos (X e Y)
            for i, (x_input, y_input) in enumerate(self.polygon_point_widgets):
                x_text, y_text = x_input.text().strip(), y_input.text().strip()
                if x_text and y_text:
                    raw_texts.append((x_text, y_text))
                elif x_text or y_text:  # Apenas um preenchido? Erro.
                    raise ValueError(
                        f"Vértice {i+1}: Preencha X e Y, ou deixe ambos em branco."
                    )
            data["is_open"] = self.open_polygon_checkbox.isChecked()
            min_points = 2 if data["is_open"] else 3
            if len(raw_texts) < min_points:
                tipo = "aberto" if data["is_open"] else "fechado"
                raise ValueError(
                    f"Polígono {tipo} requer pelo menos {min_points} vértices preenchidos ({len(raw_texts)} encontrados)."
                )

        # 2. Converte textos para float
        coords: List[Tuple[float, float]] = []
        locale = self._double_validator.locale()  # Usa o mesmo locale do validador
        for i, (x_text_raw, y_text_raw) in enumerate(raw_texts):
            if x_text_raw is None or y_text_raw is None:
                continue  # Segurança

            x_conv, x_ok = locale.toDouble(x_text_raw)
            y_conv, y_ok = locale.toDouble(y_text_raw)

            if not x_ok or not y_ok:
                p_desc = (
                    f"Vértice {i+1}"
                    if self.mode == "polygon"
                    else (
                        ("Inicial" if i == 0 else "Final")
                        if self.mode == "line"
                        else "Ponto"
                    )
                )
                raise ValueError(
                    f"{p_desc}: Coordenadas '{x_text_raw}', '{y_text_raw}' inválidas. Use números."
                )
            coords.append((x_conv, y_conv))

        # 3. Validações adicionais
        if self.mode == "line" and len(coords) == 2 and coords[0] == coords[1]:
            raise ValueError("Pontos inicial e final da linha não podem ser idênticos.")

        # 4. Preenche dicionário de dados
        data["coords"] = coords
        data["color"] = (
            self._selected_color if self._selected_color.isValid() else QColor(Qt.black)
        )

        return data

    def get_validated_data(self) -> Optional[Dict[str, Any]]:
        """Retorna os dados validados se o diálogo foi aceito, senão None."""
        # Retorna os dados armazenados em _on_accept se o diálogo foi aceito
        return self._validated_data if self.result() == QDialog.Accepted else None
