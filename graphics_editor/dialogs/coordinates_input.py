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
    """
    Diálogo para inserir coordenadas e propriedades de objetos gráficos 2D.

    Permite:
    - Inserir coordenadas para Ponto, Linha, Polígono, Curva de Bézier, B-spline (todos 2D).
    - Selecionar a cor do objeto.
    - Configurar propriedades específicas (ex: polígono aberto/fechado, preenchido).
    - Validar as entradas antes de aceitar.
    """

    def __init__(self, parent: Optional[QWidget] = None, mode: str = "point"):
        """
        Inicializa o diálogo de entrada de coordenadas.

        Args:
            parent: Widget pai do diálogo.
            mode: Modo de operação ('point', 'line', 'polygon', 'bezier', 'bspline').
                  Todos se referem a objetos 2D.

        Raises:
            ValueError: Se o modo for inválido.
        """
        super().__init__(parent)
        self.mode: str = mode.lower()
        if self.mode not in ["point", "line", "polygon", "bezier", "bspline"]:
            raise ValueError(
                f"Modo inválido: '{self.mode}'. Use 'point', 'line', 'polygon', 'bezier' ou 'bspline'."
            )

        self.setWindowTitle(f"Inserir Coordenadas 2D - {self.mode.capitalize()}")
        self.point_widgets: List[Tuple[QLineEdit, QLineEdit]] = (
            []
        )  # Para polígono/curvas
        self._selected_color: QColor = QColor(Qt.black)

        self._double_validator = QDoubleValidator(-99999.99, 99999.99, 6, self)
        self._double_validator.setNotation(QDoubleValidator.StandardNotation)
        self._double_validator.setLocale(QLocale())  # Usa locale do sistema

        self._icon_base_path = os.path.join(
            os.path.dirname(__file__), "..", "resources", "icons"
        )
        self._validated_data: Optional[Dict[str, Any]] = None

        # Campos de entrada (opcionais dependendo do modo)
        self.x_input: Optional[QLineEdit] = None
        self.y_input: Optional[QLineEdit] = None
        self.x1_input: Optional[QLineEdit] = None
        self.y1_input: Optional[QLineEdit] = None
        self.x2_input: Optional[QLineEdit] = None
        self.y2_input: Optional[QLineEdit] = None
        self.open_polygon_checkbox: Optional[QCheckBox] = None
        self.filled_polygon_checkbox: Optional[QCheckBox] = None
        self.add_point_button: Optional[QPushButton] = None
        self.scroll_area: Optional[QScrollArea] = None
        self.point_list_layout: Optional[QVBoxLayout] = None

        self._setup_ui()
        self.setMinimumWidth(350)

    def set_initial_color(self, color: QColor) -> None:
        if color.isValid():
            self._selected_color = color
            self._update_color_button_preview()

    def _get_icon(self, name: str) -> QIcon:
        icon_path = os.path.join(self._icon_base_path, name)
        return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        input_container = QWidget()
        self.input_layout = QVBoxLayout(input_container)
        self.input_layout.setContentsMargins(0, 0, 0, 0)

        if self.mode == "point":
            self.x_input = self._create_coord_input_row(self.input_layout, "X:")
            self.y_input = self._create_coord_input_row(self.input_layout, "Y:")
        elif self.mode == "line":
            p1_group = QGroupBox("Ponto Inicial (2D)")
            p1_layout = QVBoxLayout(p1_group)
            self.x1_input = self._create_coord_input_row(p1_layout, "X1:")
            self.y1_input = self._create_coord_input_row(p1_layout, "Y1:")
            self.input_layout.addWidget(p1_group)

            p2_group = QGroupBox("Ponto Final (2D)")
            p2_layout = QVBoxLayout(p2_group)
            self.x2_input = self._create_coord_input_row(p2_layout, "X2:")
            self.y2_input = self._create_coord_input_row(p2_layout, "Y2:")
            self.input_layout.addWidget(p2_group)
        elif self.mode in ["polygon", "bezier", "bspline"]:
            label_text, initial_points = "", 0
            if self.mode == "polygon":
                label_text = "Vértices do Polígono 2D (mín. 3 fechado, 2 aberto):"
                initial_points = 3
            elif self.mode == "bezier":
                label_text = (
                    "Pontos de Controle Bézier 2D (mín. 4, depois +3 por segmento):"
                )
                initial_points = 4
            elif self.mode == "bspline":
                label_text = "Pontos de Controle B-spline 2D (mín. 2, grau padrão 3):"
                initial_points = 2  # Para grau 1. Para grau 3, precisa de 4 pontos.
                # Ajuste initial_points se o grau mínimo for maior.
                if (
                    BSplineCurve.DEFAULT_DEGREE + 1 > initial_points
                ):  # e.g. grau 3 -> 4 pontos
                    initial_points = BSplineCurve.DEFAULT_DEGREE + 1

            self.input_layout.addWidget(QLabel(label_text))
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setFixedHeight(180)
            scroll_content = QWidget()
            self.point_list_layout = QVBoxLayout(scroll_content)
            self.point_list_layout.setSpacing(4)
            self.scroll_area.setWidget(scroll_content)
            self.input_layout.addWidget(self.scroll_area)

            options_layout = QHBoxLayout()
            if self.mode == "polygon":
                self.open_polygon_checkbox = QCheckBox("Polilinha (Aberta)")
                self.open_polygon_checkbox.setToolTip(
                    "Marque para criar uma polilinha aberta."
                )
                self.filled_polygon_checkbox = QCheckBox("Preenchido")
                self.filled_polygon_checkbox.setToolTip(
                    "Marque para preencher o polígono (apenas se fechado)."
                )
                self.open_polygon_checkbox.toggled.connect(
                    self._on_polygon_open_toggled
                )
                options_layout.addWidget(self.open_polygon_checkbox)
                options_layout.addWidget(self.filled_polygon_checkbox)

            options_layout.addStretch()
            self.add_point_button = QPushButton(self._get_icon("add.png"), " Ponto")
            self.add_point_button.setToolTip("Adicionar campos para mais um ponto")
            self.add_point_button.clicked.connect(self._add_list_point_inputs_row)
            options_layout.addWidget(self.add_point_button)
            self.input_layout.addLayout(options_layout)
            for _ in range(initial_points):
                self._add_list_point_inputs_row()

        main_layout.addWidget(input_container)
        self._add_color_selector(main_layout)
        self._add_ok_cancel_buttons(main_layout)

    def _on_polygon_open_toggled(self, checked: bool):
        if self.filled_polygon_checkbox:
            self.filled_polygon_checkbox.setDisabled(checked)
            if checked:
                self.filled_polygon_checkbox.setChecked(False)

    def _create_coord_input_row(
        self, parent_layout: QVBoxLayout, label_text: str
    ) -> QLineEdit:
        """Cria uma linha com QLabel e QLineEdit para uma coordenada."""
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

    def _add_list_point_inputs_row(self) -> None:
        """Adiciona uma linha com campos X, Y para um ponto na lista (polígono/curvas)."""
        if self.point_list_layout is None:
            return

        point_index = len(self.point_widgets) + 1
        point_row_layout = QHBoxLayout()
        point_row_layout.setContentsMargins(0, 0, 0, 0)

        x_input = QLineEdit()
        y_input = QLineEdit()
        for inp, placeholder in [(x_input, "X"), (y_input, "Y")]:
            inp.setValidator(self._double_validator)
            inp.setPlaceholderText(placeholder)
            inp.setMinimumWidth(70)
            inp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        point_row_layout.addWidget(QLabel(f"{point_index}:"))
        point_row_layout.addWidget(x_input)
        point_row_layout.addWidget(y_input)

        # Botão de remover (opcional, adiciona complexidade de reindexar)
        # remove_btn = QPushButton(self._get_icon("delete.png")); remove_btn.setFixedSize(24,24)
        # remove_btn.clicked.connect(lambda _, r=point_row_layout: self._remove_list_point_row(r))
        # point_row_layout.addWidget(remove_btn)

        self.point_list_layout.addLayout(point_row_layout)
        self.point_widgets.append((x_input, y_input))

    def _add_color_selector(self, main_layout: QVBoxLayout):
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Cor:"))
        self.color_button = QPushButton()
        self.color_button.setToolTip("Clique para selecionar a cor")
        self.color_button.setFixedSize(QSize(40, 24))
        self.color_button.setAutoFillBackground(
            True
        )  # Necessário para stylesheet de fundo
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button_preview()
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        main_layout.addLayout(color_layout)

    def _add_ok_cancel_buttons(self, main_layout: QVBoxLayout):
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

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(self._selected_color, self, "Selecionar Cor")
        if color.isValid():
            self._selected_color = color
            self._update_color_button_preview()

    def _update_color_button_preview(self) -> None:
        color_name = (
            self._selected_color.name() if self._selected_color.isValid() else "#eeeeee"
        )
        self.color_button.setStyleSheet(
            f"background-color: {color_name}; border: 1px solid gray;"
        )

    def _on_accept(self) -> None:
        try:
            self._validated_data = self._validate_and_get_data()
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Entrada Inválida", str(e))
            self._validated_data = None

    def _validate_and_get_data(self) -> Dict[str, Any]:
        """Valida entradas e retorna dados formatados para objetos 2D."""
        data: Dict[str, Any] = {"coords": []}
        raw_texts: List[Tuple[Optional[str], Optional[str]]] = []
        locale = self._double_validator.locale()
        coords: List[Tuple[float, float]] = []

        if self.mode == "point":
            if not self.x_input or not self.y_input:
                raise ValueError("Campos de ponto ausentes.")
            raw_texts = [(self.x_input.text(), self.y_input.text())]
            if not all(raw_texts[0]):
                raise ValueError("Coordenadas X e Y são obrigatórias.")
        elif self.mode == "line":
            if (
                not self.x1_input
                or not self.y1_input
                or not self.x2_input
                or not self.y2_input
            ):
                raise ValueError("Campos de linha ausentes.")
            raw_texts = [
                (self.x1_input.text(), self.y1_input.text()),
                (self.x2_input.text(), self.y2_input.text()),
            ]
            if not all(raw_texts[0]) or not all(raw_texts[1]):
                raise ValueError("Todas as 4 coordenadas são obrigatórias para linha.")
        elif self.mode in ["polygon", "bezier", "bspline"]:
            for i, (x_inp, y_inp) in enumerate(self.point_widgets):
                x_txt, y_txt = x_inp.text().strip(), y_inp.text().strip()
                if x_txt and y_txt:
                    raw_texts.append((x_txt, y_txt))
                elif x_txt or y_txt:
                    raise ValueError(
                        f"Ponto {i+1}: Preencha X e Y, ou deixe ambos em branco."
                    )

            num_pts = len(raw_texts)
            if self.mode == "polygon":
                if not self.open_polygon_checkbox or not self.filled_polygon_checkbox:
                    raise ValueError("Controles de polígono ausentes.")
                data["is_open"] = self.open_polygon_checkbox.isChecked()
                data["is_filled"] = (
                    self.filled_polygon_checkbox.isChecked() and not data["is_open"]
                )
                min_req = 2 if data["is_open"] else 3
                if num_pts < min_req:
                    raise ValueError(
                        f"Polígono {'aberto' if data['is_open'] else 'fechado'} requer {min_req} pts ({num_pts} fornecidos)."
                    )
            elif self.mode == "bezier":
                if num_pts < 4:
                    raise ValueError(f"Bézier requer >= 4 pts ({num_pts} fornecidos).")
                if (num_pts - 1) % 3 != 0:
                    raise ValueError(
                        f"Bézier: {num_pts} pts inválido. Use 4, 7, 10,..."
                    )
            elif self.mode == "bspline":
                # Grau p precisa de p+1 pontos no mínimo. Padrão grau 3 -> 4 pontos.
                # Se grau for menor, menos pontos. Ex: grau 1 (polilinha) -> 2 pontos.
                min_req = BSplineCurve.DEFAULT_DEGREE + 1  # Assumindo grau padrão
                if num_pts < min_req:
                    raise ValueError(
                        f"B-spline (grau {BSplineCurve.DEFAULT_DEGREE}) requer >= {min_req} pts ({num_pts} fornecidos)."
                    )

        for i, (x_raw, y_raw) in enumerate(raw_texts):
            if x_raw is None or y_raw is None:
                continue
            x_val, x_ok = locale.toDouble(x_raw)
            y_val, y_ok = locale.toDouble(y_raw)
            if not x_ok or not y_ok:
                p_desc = f"Ponto {i+1}"
                if self.mode == "line":
                    p_desc = "Inicial" if i == 0 else "Final"
                elif self.mode == "point":
                    p_desc = "Ponto"
                raise ValueError(
                    f"{p_desc}: Coordenadas '{x_raw}', '{y_raw}' inválidas."
                )
            coords.append((x_val, y_val))

        if self.mode == "line" and len(coords) == 2 and coords[0] == coords[1]:
            raise ValueError("Pontos inicial e final da linha não podem ser idênticos.")

        data["coords"] = coords
        data["color"] = (
            self._selected_color if self._selected_color.isValid() else QColor(Qt.black)
        )
        return data

    def get_validated_data(self) -> Optional[Dict[str, Any]]:
        return self._validated_data if self.result() == QDialog.Accepted else None
