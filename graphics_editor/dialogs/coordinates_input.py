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
            mode: 'point', 'line', 'polygon', or 'bezier'.
        """
        super().__init__(parent)
        self.mode: str = mode.lower()
        if self.mode not in ["point", "line", "polygon", "bezier"]: # Add bezier
            raise ValueError(
                f"Modo inválido: '{self.mode}'. Use 'point', 'line', 'polygon', 'bezier'."
            )

        self.setWindowTitle(f"Inserir Coordenadas - {self.mode.capitalize()}")
        # Renamed polygon_point_widgets to generic name
        self.point_widgets: List[Tuple[QLineEdit, QLineEdit]] = []
        self._selected_color: QColor = QColor(Qt.black)
        # Validador que aceita ponto ou vírgula, dependendo do Locale
        self._double_validator = QDoubleValidator(-99999.99, 99999.99, 6, self)
        self._double_validator.setNotation(QDoubleValidator.StandardNotation)
        # Usa o locale padrão definido em main.py ou do sistema
        self._double_validator.setLocale(QLocale())

        # Ícones
        self._icon_base_path = os.path.join(os.path.dirname(__file__), "..","resources", "icons")

        self._validated_data: Optional[Dict[str, Any]] = (
            None  # Armazena dados validados no OK
        )

        # Input fields (optional based on mode)
        self.x_input: Optional[QLineEdit] = None
        self.y_input: Optional[QLineEdit] = None
        self.x1_input: Optional[QLineEdit] = None
        self.y1_input: Optional[QLineEdit] = None
        self.x2_input: Optional[QLineEdit] = None
        self.y2_input: Optional[QLineEdit] = None
        # Polygon/Bezier specific controls
        self.open_polygon_checkbox: Optional[QCheckBox] = None
        self.filled_polygon_checkbox: Optional[QCheckBox] = None
        self.add_point_button: Optional[QPushButton] = None
        self.scroll_area: Optional[QScrollArea] = None
        self.point_list_layout: Optional[QVBoxLayout] = None # Layout inside scroll area

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
        input_container = QWidget()
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

        elif self.mode == "polygon" or self.mode == "bezier":
            # Shared UI for Polygon and Bezier point lists
            if self.mode == "polygon":
                label_text = "Vértices do Polígono (mín. 3 fechado, 2 aberto):"
                initial_points = 3
            else: # Bezier
                label_text = "Pontos de Controle Bézier (mín. 4, depois +3 por segmento):"
                initial_points = 4

            self.input_layout.addWidget(QLabel(label_text))

            # ScrollArea for the points
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setFixedHeight(180)
            scroll_content = QWidget()
            self.point_list_layout = QVBoxLayout(scroll_content)
            self.point_list_layout.setSpacing(4)
            self.scroll_area.setWidget(scroll_content)
            self.input_layout.addWidget(self.scroll_area)

            # Options Layout
            options_layout = QHBoxLayout()

            # Polygon specific options
            if self.mode == "polygon":
                self.open_polygon_checkbox = QCheckBox("Polilinha (Aberta)")
                self.open_polygon_checkbox.setToolTip("Marque para criar uma sequência de linhas abertas.")
                self.filled_polygon_checkbox = QCheckBox("Preenchido")
                self.filled_polygon_checkbox.setToolTip("Marque para preencher o polígono (somente se fechado).")
                self.open_polygon_checkbox.toggled.connect(self._on_polygon_open_toggled)
                options_layout.addWidget(self.open_polygon_checkbox)
                options_layout.addWidget(self.filled_polygon_checkbox)

            options_layout.addStretch()
            self.add_point_button = QPushButton(self._get_icon("add.png"), " Ponto")
            self.add_point_button.setToolTip("Adicionar campos para mais um ponto de controle/vértice")
            self.add_point_button.clicked.connect(self._add_list_point_inputs)
            options_layout.addWidget(self.add_point_button)
            self.input_layout.addLayout(options_layout)

            # Add initial point fields
            for _ in range(initial_points):
                self._add_list_point_inputs()

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

    def _on_polygon_open_toggled(self, checked: bool):
         """Callback when the 'open polygon' checkbox changes state."""
         if self.filled_polygon_checkbox:
              self.filled_polygon_checkbox.setDisabled(checked)
              if checked:
                   self.filled_polygon_checkbox.setChecked(False)


    def _create_coord_input(
        self, parent_layout: Union[QVBoxLayout, QHBoxLayout], label_text: str
    ) -> QLineEdit:
        """Cria um par QLabel/QLineEdit para uma coordenada."""
        h_layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(50)
        input_field = QLineEdit()
        input_field.setValidator(self._double_validator)
        input_field.setPlaceholderText("Valor")
        input_field.setMinimumWidth(80)
        input_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h_layout.addWidget(label)
        h_layout.addWidget(input_field)
        parent_layout.addLayout(h_layout)
        return input_field

    def _add_list_point_inputs(self) -> None:
        """Adiciona campos X, Y para um ponto na lista (polígono/bezier)."""
        if self.point_list_layout is None: return

        point_index = len(self.point_widgets) + 1
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

        self.point_list_layout.addLayout(point_layout)
        self.point_widgets.append((x_input, y_input))

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
            self._validated_data = self._validate_and_get_data()
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Entrada Inválida", str(e))
            self._validated_data = None

    def _validate_and_get_data(self) -> Dict[str, Any]:
        """
        Valida as entradas e retorna um dicionário com os dados formatados.
        Levanta ValueError com mensagem de erro se a validação falhar.
        """
        data: Dict[str, Any] = {"coords": []}
        raw_texts: List[Tuple[Optional[str], Optional[str]]] = []
        locale = self._double_validator.locale()
        coords: List[Tuple[float, float]] = []

        if self.mode == "point":
            if not self.x_input or not self.y_input: raise ValueError("Campos de ponto ausentes.")
            raw_texts = [(self.x_input.text(), self.y_input.text())]
            if not all(raw_texts[0]): raise ValueError("Coordenadas X e Y são obrigatórias.")

        elif self.mode == "line":
            if not self.x1_input or not self.y1_input or not self.x2_input or not self.y2_input:
                raise ValueError("Campos de linha ausentes.")
            raw_texts = [
                (self.x1_input.text(), self.y1_input.text()),
                (self.x2_input.text(), self.y2_input.text()),
            ]
            if not all(raw_texts[0]) or not all(raw_texts[1]):
                raise ValueError("Todas as 4 coordenadas são obrigatórias para a linha.")

        elif self.mode == "polygon" or self.mode == "bezier":
            # Collect non-empty pairs from the list
            for i, (x_input, y_input) in enumerate(self.point_widgets):
                x_text, y_text = x_input.text().strip(), y_input.text().strip()
                if x_text and y_text:
                    raw_texts.append((x_text, y_text))
                elif x_text or y_text:
                    raise ValueError(f"Ponto {i+1}: Preencha X e Y, ou deixe ambos em branco.")

            num_points_collected = len(raw_texts)

            if self.mode == "polygon":
                if not self.open_polygon_checkbox or not self.filled_polygon_checkbox:
                     raise ValueError("Controles de polígono ausentes.")
                data["is_open"] = self.open_polygon_checkbox.isChecked()
                data["is_filled"] = (
                    self.filled_polygon_checkbox.isChecked() and not data["is_open"]
                )
                min_points = 2 if data["is_open"] else 3
                if num_points_collected < min_points:
                    tipo = "aberto" if data["is_open"] else "fechado"
                    raise ValueError(
                        f"Polígono {tipo} requer pelo menos {min_points} vértices preenchidos ({num_points_collected} encontrados)."
                    )
            else: # Bezier validation
                min_points = 4
                if num_points_collected < min_points:
                    raise ValueError(f"Curva de Bézier requer pelo menos {min_points} pontos ({num_points_collected} encontrados).")
                if num_points_collected > min_points and (num_points_collected - min_points) % 3 != 0:
                    raise ValueError(
                       f"Número inválido de pontos ({num_points_collected}) para curva Bézier composta. "
                       "Deve ser 4 ou 7 ou 10 etc. (4 + 3*N)."
                    )

        # Convert texts to float using locale
        for i, (x_text_raw, y_text_raw) in enumerate(raw_texts):
            if x_text_raw is None or y_text_raw is None: continue # Should not happen

            x_conv, x_ok = locale.toDouble(x_text_raw)
            y_conv, y_ok = locale.toDouble(y_text_raw)

            if not x_ok or not y_ok:
                p_desc = f"Ponto {i+1}" # Default description
                if self.mode == "line": p_desc = "Inicial" if i == 0 else "Final"
                elif self.mode == "point": p_desc = "Ponto"
                raise ValueError(f"{p_desc}: Coordenadas '{x_text_raw}', '{y_text_raw}' inválidas.")
            coords.append((x_conv, y_conv))

        # Additional validations
        if self.mode == "line" and len(coords) == 2 and coords[0] == coords[1]:
            raise ValueError("Pontos inicial e final da linha não podem ser idênticos.")

        # Fill data dictionary
        data["coords"] = coords
        data["color"] = self._selected_color if self._selected_color.isValid() else QColor(Qt.black)

        return data

    def get_validated_data(self) -> Optional[Dict[str, Any]]:
        """Retorna os dados validados se o diálogo foi aceito, senão None."""
        return self._validated_data if self.result() == QDialog.Accepted else None
