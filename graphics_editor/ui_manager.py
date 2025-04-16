# graphics_editor/ui_manager.py
import os
from PyQt5.QtCore import QSize, Qt, QLocale, QRectF, QPointF
from PyQt5.QtWidgets import (
    QMainWindow,
    QToolBar,
    QAction,
    QActionGroup,
    QGroupBox,
    QVBoxLayout,
    QRadioButton,
    QWidgetAction,
    QLabel,
    QStatusBar,
    QSlider,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from typing import Callable, Dict, Any

from .state_manager import DrawingMode, LineClippingAlgorithm


class UIManager:
    """Gerencia a criação e atualização de elementos da UI (Toolbar, Statusbar)."""

    # Constantes para o slider de zoom (poderiam vir do state_manager ou config)
    SLIDER_RANGE_MIN = 0
    SLIDER_RANGE_MAX = 400

    def __init__(self, main_window: QMainWindow, state_manager):
        self.window = main_window
        self.state_manager = state_manager
        self._icon_base_path = os.path.join(os.path.dirname(__file__), "icons")

        # Referências aos widgets da UI que precisam ser atualizados
        self.toolbar: Optional[QToolBar] = None
        self.mode_action_group: Optional[QActionGroup] = None
        self.color_action: Optional[QAction] = None
        self.cs_radio: Optional[QRadioButton] = None
        self.lb_radio: Optional[QRadioButton] = None

        self.status_bar: Optional[QStatusBar] = None
        self.status_message_label: Optional[QLabel] = None
        self.status_coords_label: Optional[QLabel] = None
        self.status_mode_label: Optional[QLabel] = None
        self.status_rotation_label: Optional[QLabel] = None
        self.zoom_label: Optional[QLabel] = None
        self.zoom_slider: Optional[QSlider] = None
        self.viewport_toggle_action: Optional[QAction] = (
            None  # Referência à ação do menu
        )

    def _get_icon(self, name: str) -> QIcon:
        """Carrega um QIcon ou retorna placeholder."""
        path = os.path.join(self._icon_base_path, name)
        if not os.path.exists(path):
            pixmap = QPixmap(24, 24)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setPen(Qt.red)
            painter.drawRect(0, 0, 23, 23)
            painter.drawText(QRectF(0, 0, 24, 24), Qt.AlignCenter, "?")
            painter.end()
            return QIcon(pixmap)
        return QIcon(path)

    def _create_color_icon(self, color: QColor, size: int = 16) -> QIcon:
        """Cria um ícone quadrado com a cor especificada."""
        pixmap = QPixmap(size, size)
        valid_color = color if color.isValid() else QColor(Qt.black)
        pixmap.fill(valid_color)
        painter = QPainter(pixmap)
        painter.setPen(QPen(Qt.gray, 1))
        painter.drawRect(0, 0, size - 1, size - 1)
        painter.end()
        return QIcon(pixmap)

    def setup_toolbar(
        self,
        mode_callback: Callable[[DrawingMode], None],
        color_callback: Callable[[], None],
        coord_callback: Callable[[], None],
        transform_callback: Callable[[], None],
        clipper_callback: Callable[[LineClippingAlgorithm], None],
    ) -> QToolBar:
        """Configura e retorna a barra de ferramentas principal."""
        toolbar = QToolBar("Ferramentas")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.window.addToolBar(Qt.LeftToolBarArea, toolbar)
        self.toolbar = toolbar

        self.mode_action_group = QActionGroup(self.window)
        self.mode_action_group.setExclusive(True)

        modes = [
            (
                DrawingMode.SELECT,
                "Selecionar",
                "Selecionar e mover itens (S)",
                "select.png",
                "S",
            ),
            (DrawingMode.PAN, "Mover Vista", "Mover a vista (Pan) (H)", "pan.png", "H"),
            (DrawingMode.POINT, "Ponto", "Desenhar pontos (P)", "point.png", "P"),
            (DrawingMode.LINE, "Linha", "Desenhar linhas (L)", "line.png", "L"),
            (
                DrawingMode.POLYGON,
                "Polígono",
                "Desenhar polígonos/polilinhas (G)",
                "polygon.png",
                "G",
            ),
        ]
        initial_mode = self.state_manager.drawing_mode()
        for mode, name, tip, icon_name, shortcut in modes:
            action = QAction(self._get_icon(icon_name), name, self.window)
            action.setToolTip(tip)
            action.setShortcut(shortcut)
            action.setCheckable(True)
            action.setData(mode)
            # Conecta ao callback INTERNO que chama o setter do state_manager
            action.triggered.connect(
                lambda checked, m=mode: mode_callback(m) if checked else None
            )
            toolbar.addAction(action)
            self.mode_action_group.addAction(action)
            if mode == initial_mode:
                action.setChecked(True)

        toolbar.addSeparator()

        # Ação de Cor
        initial_color = self.state_manager.draw_color()
        self.color_action = QAction(
            self._create_color_icon(initial_color, 24), "Cor", self.window
        )
        self.color_action.setToolTip("Selecionar cor para novos objetos (C)")
        self.color_action.setShortcut("C")
        self.color_action.triggered.connect(color_callback)
        toolbar.addAction(self.color_action)

        toolbar.addSeparator()

        # Ações adicionais
        manual_coord_action = QAction(
            self._get_icon("coords.png"), "Coords", self.window
        )
        manual_coord_action.setToolTip("Adicionar forma via coordenadas (M)")
        manual_coord_action.setShortcut("M")
        manual_coord_action.triggered.connect(coord_callback)
        toolbar.addAction(manual_coord_action)

        transform_action_tb = QAction(
            self._get_icon("transform.png"), "Transf.", self.window
        )
        transform_action_tb.setToolTip("Aplicar transformação (Ctrl+T)")
        transform_action_tb.triggered.connect(transform_callback)
        toolbar.addAction(transform_action_tb)

        toolbar.addSeparator()

        # Grupo de Clipping
        clipping_group_box = QGroupBox("Clipping Linha")
        clipping_layout = QVBoxLayout()
        clipping_layout.setContentsMargins(2, 2, 2, 2)
        clipping_layout.setSpacing(2)
        self.cs_radio = QRadioButton("Cohen-Suth.")
        self.lb_radio = QRadioButton("Liang-Barsky")
        initial_clipper = self.state_manager.selected_line_clipper()
        self.cs_radio.setChecked(
            initial_clipper == LineClippingAlgorithm.COHEN_SUTHERLAND
        )
        self.lb_radio.setChecked(initial_clipper == LineClippingAlgorithm.LIANG_BARSKY)
        self.cs_radio.toggled.connect(
            lambda checked: (
                clipper_callback(LineClippingAlgorithm.COHEN_SUTHERLAND)
                if checked
                else None
            )
        )
        self.lb_radio.toggled.connect(
            lambda checked: (
                clipper_callback(LineClippingAlgorithm.LIANG_BARSKY)
                if checked
                else None
            )
        )
        clipping_layout.addWidget(self.cs_radio)
        clipping_layout.addWidget(self.lb_radio)
        clipping_group_box.setLayout(clipping_layout)
        clipping_action = QWidgetAction(self.window)
        clipping_action.setDefaultWidget(clipping_group_box)
        toolbar.addAction(clipping_action)

        return toolbar

    def setup_status_bar(self, zoom_callback: Callable[[int], None]) -> QStatusBar:
        """Configura e retorna a barra de status."""
        status_bar = QStatusBar(self.window)
        self.window.setStatusBar(status_bar)
        self.status_bar = status_bar

        self.status_message_label = QLabel("Pronto.")
        status_bar.addWidget(self.status_message_label, 1)

        self.status_coords_label = QLabel("X: --- Y: ---")
        self.status_coords_label.setToolTip("Coordenadas do mouse na cena")
        self.status_coords_label.setMinimumWidth(160)
        self.status_coords_label.setAlignment(Qt.AlignCenter)
        status_bar.addPermanentWidget(self.status_coords_label)

        self.status_mode_label = QLabel("Modo: Select")
        self.status_mode_label.setToolTip("Modo de interação atual")
        self.status_mode_label.setMinimumWidth(100)
        self.status_mode_label.setAlignment(Qt.AlignCenter)
        status_bar.addPermanentWidget(self.status_mode_label)

        self.status_rotation_label = QLabel("Rot: 0.0°")
        self.status_rotation_label.setToolTip("Rotação da vista (Shift+Setas)")
        self.status_rotation_label.setMinimumWidth(80)
        self.status_rotation_label.setAlignment(Qt.AlignCenter)
        status_bar.addPermanentWidget(self.status_rotation_label)

        self.zoom_label = QLabel("Zoom: 100%")
        self.zoom_label.setMinimumWidth(90)
        self.zoom_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        status_bar.addPermanentWidget(self.zoom_label)

        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(self.SLIDER_RANGE_MIN, self.SLIDER_RANGE_MAX)
        self.zoom_slider.setToolTip("Controlar o nível de zoom")
        self.zoom_slider.setMinimumWidth(100)
        self.zoom_slider.setMaximumWidth(150)
        self.zoom_slider.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.zoom_slider.valueChanged.connect(
            zoom_callback
        )  # Conecta ao callback do Editor
        status_bar.addPermanentWidget(self.zoom_slider)

        # Inicializa com valores corretos
        self.update_status_bar_mode(self.state_manager.drawing_mode())
        # Outros (zoom, rotação) serão atualizados pelo editor via view

        return status_bar

    # --- Métodos de Atualização da UI ---

    def update_color_button(self, color: QColor):
        """Atualiza o ícone do botão de cor."""
        if self.color_action:
            self.color_action.setIcon(self._create_color_icon(color, 24))

    def update_toolbar_mode_selection(self, mode: DrawingMode):
        """Marca a ação correta na toolbar."""
        if self.mode_action_group:
            for action in self.mode_action_group.actions():
                if action.data() == mode:
                    if not action.isChecked():
                        action.setChecked(True)
                    break

    def update_clipper_selection(self, algorithm: LineClippingAlgorithm):
        """Marca o radio button correto."""
        if self.cs_radio and self.lb_radio:
            if algorithm == LineClippingAlgorithm.COHEN_SUTHERLAND:
                if not self.cs_radio.isChecked():
                    self.cs_radio.setChecked(True)
            else:
                if not self.lb_radio.isChecked():
                    self.lb_radio.setChecked(True)

    def update_status_bar_message(self, message: str):
        """Define a mensagem principal na status bar."""
        if self.status_message_label:
            self.status_message_label.setText(message)

    def update_status_bar_coords(self, scene_pos: QPointF):
        """Atualiza as coordenadas na status bar."""
        if self.status_coords_label:
            locale = QLocale()
            coord_text = f"X: {locale.toString(scene_pos.x(), 'f', 2)}  Y: {locale.toString(scene_pos.y(), 'f', 2)}"
            self.status_coords_label.setText(coord_text)

    def update_status_bar_mode(self, mode: DrawingMode):
        """Atualiza o modo na status bar."""
        if self.status_mode_label:
            mode_map = {
                DrawingMode.SELECT: "Seleção",
                DrawingMode.PAN: "Mover Vista",
                DrawingMode.POINT: "Ponto",
                DrawingMode.LINE: "Linha",
                DrawingMode.POLYGON: "Polígono",
            }
            mode_text = f"Modo: {mode_map.get(mode, 'N/D')}"
            self.status_mode_label.setText(mode_text)

    def update_status_bar_rotation(self, angle: float):
        """Atualiza a rotação na status bar."""
        if self.status_rotation_label:
            rotation_text = f"Rot: {QLocale().toString(angle, 'f', 1)}°"
            self.status_rotation_label.setText(rotation_text)

    def update_status_bar_zoom(self, scale: float, slider_value: int):
        """Atualiza o zoom (label e slider) na status bar."""
        if self.zoom_label:
            zoom_percent = scale * 100
            self.zoom_label.setText(
                f"Zoom: {QLocale().toString(zoom_percent, 'f', 0)}%"
            )
        if self.zoom_slider:
            # Evita loop de sinais
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(slider_value)
            self.zoom_slider.blockSignals(False)

    def update_viewport_action_state(self, is_visible: bool):
        """Atualiza o estado 'checked' da ação de mostrar/ocultar viewport."""
        if self.viewport_toggle_action:
            self.viewport_toggle_action.setChecked(is_visible)
