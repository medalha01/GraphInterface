# graphics_editor/ui_manager.py
import os
from PyQt5.QtCore import (
    QSize,
    Qt,
    QLocale,
    QRectF,
    QPointF,
    QSignalBlocker,
)  # Import QSignalBlocker
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
    QMenu,
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from typing import Callable, Dict, Any, Optional

from .state_manager import DrawingMode, LineClippingAlgorithm


class UIManager:
    """
    Gerenciador da interface do usuário do editor gráfico.

    Responsável por:
    - Configurar e gerenciar a barra de menu, barra de ferramentas e barra de status.
    - Gerenciar ícones e recursos visuais.
    - Atualizar elementos da interface baseado no estado da aplicação.
    """

    SLIDER_RANGE_MIN = 0  # Para zoom 2D
    SLIDER_RANGE_MAX = 400  # Para zoom 2D

    def __init__(self, main_window: QMainWindow, state_manager):
        """
        Inicializa o gerenciador de interface.

        Args:
            main_window: Janela principal da aplicação
            state_manager: Gerenciador de estado da aplicação
        """
        self.window = main_window
        self.state_manager = state_manager
        self._icon_base_path = os.path.join(
            os.path.dirname(__file__), "resources", "icons"
        )

        self.toolbar: Optional[QToolBar] = None
        self.mode_action_group: Optional[QActionGroup] = None
        self.color_action: Optional[QAction] = None
        self.cs_radio: Optional[QRadioButton] = None  # Para clipping 2D
        self.lb_radio: Optional[QRadioButton] = None  # Para clipping 2D

        self.status_bar: Optional[QStatusBar] = None
        self.status_message_label: Optional[QLabel] = None
        self.status_coords_label: Optional[QLabel] = None  # Coords do mouse 2D
        self.status_3d_coords_label: Optional[QLabel] = None  # Coords 3D (e.g., VRP)
        self.status_mode_label: Optional[QLabel] = None
        self.status_rotation_label: Optional[QLabel] = None  # Rotação da vista 2D
        self.zoom_label: Optional[QLabel] = None  # Zoom da vista 2D
        self.zoom_slider: Optional[QSlider] = None  # Zoom da vista 2D
        self.viewport_toggle_action: Optional[QAction] = None  # Viewport 2D

    def _get_icon(self, name: str) -> QIcon:
        """
        Obtém um ícone do diretório de recursos.

        Args:
            name: Nome do arquivo de ícone

        Returns:
            QIcon: Ícone carregado ou um ícone de fallback se não encontrado
        """
        path = os.path.join(self._icon_base_path, name)
        if not os.path.exists(path):
            # Cria um ícone de fallback simples
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
        """
        Cria um ícone representando uma cor.

        Args:
            color: Cor a ser representada
            size: Tamanho do ícone em pixels

        Returns:
            QIcon: Ícone representando a cor
        """
        pixmap = QPixmap(size, size)
        valid_color = color if color.isValid() else QColor(Qt.black)
        pixmap.fill(valid_color)
        painter = QPainter(pixmap)
        painter.setPen(QPen(Qt.gray, 1))
        painter.drawRect(0, 0, size - 1, size - 1)
        painter.end()
        return QIcon(pixmap)

    def setup_menu_bar(
        self,
        menu_callbacks: Dict[str, Callable],
        get_initial_viewport_visible: Callable[[], bool],
    ) -> None:
        """
        Configura a barra de menus da aplicação.

        Args:
            menu_callbacks: Dicionário de callbacks para ações do menu.
            get_initial_viewport_visible: Função que retorna o estado inicial de visibilidade do viewport 2D.
        """
        menubar = self.window.menuBar()

        # --- Menu Arquivo ---
        file_menu = menubar.addMenu("&Arquivo")
        new_action = QAction(self._get_icon("clear.png"), "&Nova Cena", self.window)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(menu_callbacks["new_scene"])
        file_menu.addAction(new_action)
        file_menu.addSeparator()
        load_obj_action = QAction(
            self._get_icon("open.png"), "&Abrir OBJ (2D)...", self.window
        )
        load_obj_action.setShortcut("Ctrl+O")
        load_obj_action.triggered.connect(menu_callbacks["load_obj"])
        file_menu.addAction(load_obj_action)
        save_as_action = QAction(
            self._get_icon("save.png"), "Salvar &Como OBJ (2D)...", self.window
        )
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(menu_callbacks["save_as_obj"])
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        exit_action = QAction(self._get_icon("exit.png"), "&Sair", self.window)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(menu_callbacks["exit"])
        file_menu.addAction(exit_action)

        # --- Menu Editar ---
        edit_menu = menubar.addMenu("&Editar")
        delete_action = QAction(
            QIcon.fromTheme("edit-delete", self._get_icon("delete.png")),
            "&Excluir Selecionado(s)",
            self.window,
        )
        delete_action.setShortcuts([Qt.Key_Delete, Qt.Key_Backspace])
        delete_action.triggered.connect(menu_callbacks["delete_selected"])
        edit_menu.addAction(delete_action)
        edit_menu.addSeparator()
        transform_action = QAction(
            self._get_icon("transform.png"), "&Transformar Objeto...", self.window
        )
        transform_action.setShortcut("Ctrl+T")
        transform_action.triggered.connect(menu_callbacks["transform_object"])
        edit_menu.addAction(transform_action)

        # --- Menu Exibir (para 2D) ---
        view_menu_2d = menubar.addMenu("Exibir (&2D)")
        reset_view_action_2d = QAction("Resetar &Vista 2D", self.window)
        reset_view_action_2d.setShortcut("Ctrl+R")
        reset_view_action_2d.triggered.connect(menu_callbacks["reset_view"])
        view_menu_2d.addAction(reset_view_action_2d)
        view_menu_2d.addSeparator()
        self.viewport_toggle_action = QAction(
            "Mostrar/Ocultar Viewport 2D", self.window, checkable=True
        )
        self.viewport_toggle_action.setChecked(get_initial_viewport_visible())
        self.viewport_toggle_action.triggered.connect(menu_callbacks["toggle_viewport"])
        view_menu_2d.addAction(self.viewport_toggle_action)

        # --- Menu 3D ---
        view_menu_3d = menubar.addMenu("&3D")
        create_cube_action = QAction(
            self._get_icon("cube.png"), "Criar Cubo 3D", self.window
        )
        create_cube_action.triggered.connect(menu_callbacks["create_cube_3d"])
        view_menu_3d.addAction(create_cube_action)
        create_pyramid_action = QAction(
            self._get_icon("pyramid.png"), "Criar Pirâmide 3D", self.window
        )
        create_pyramid_action.triggered.connect(menu_callbacks["create_pyramid_3d"])
        view_menu_3d.addAction(create_pyramid_action)
        view_menu_3d.addSeparator()
        set_camera_action = QAction(
            self._get_icon("camera.png"), "Configurar Câmera 3D...", self.window
        )
        set_camera_action.triggered.connect(menu_callbacks["set_camera_3d"])
        view_menu_3d.addAction(set_camera_action)
        reset_camera_action = QAction("Resetar Câmera 3D", self.window)
        reset_camera_action.triggered.connect(menu_callbacks["reset_camera_3d"])
        view_menu_3d.addAction(reset_camera_action)

    def setup_toolbar(
        self,
        mode_callback: Callable[[DrawingMode], None],
        color_callback: Callable[[], None],
        coord_callback: Callable[[], None],  # Para entrada de coords 2D
        transform_callback: Callable[[], None],  # Genérico
        clipper_callback: Callable[[LineClippingAlgorithm], None],  # Para clipping 2D
    ) -> QToolBar:
        """
        Configura a barra de ferramentas da aplicação.

        Args:
            mode_callback: Callback para mudança de modo de desenho.
            color_callback: Callback para seleção de cor.
            coord_callback: Callback para entrada de coordenadas 2D.
            transform_callback: Callback para transformações (2D e 3D).
            clipper_callback: Callback para seleção de algoritmo de recorte de linha 2D.

        Returns:
            QToolBar: Barra de ferramentas configurada.
        """
        toolbar = QToolBar("Ferramentas")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.window.addToolBar(Qt.LeftToolBarArea, toolbar)
        self.toolbar = toolbar

        self.mode_action_group = QActionGroup(self.window)
        self.mode_action_group.setExclusive(True)

        # Modos de desenho são primariamente para 2D. 3D é via menu.
        modes = [
            (
                DrawingMode.SELECT,
                "Selecionar",
                "Selecionar e mover itens (S)",
                "select.png",
                "S",
            ),
            (
                DrawingMode.PAN,
                "Mover Vista 2D",
                "Mover a vista 2D (Pan) (H)",
                "pan.png",
                "H",
            ),
            (
                DrawingMode.POINT,
                "Ponto (2D)",
                "Desenhar pontos 2D (P)",
                "point.png",
                "P",
            ),
            (DrawingMode.LINE, "Linha (2D)", "Desenhar linhas 2D (L)", "line.png", "L"),
            (
                DrawingMode.POLYGON,
                "Polígono (2D)",
                "Desenhar polígonos/polilinhas 2D (G)",
                "polygon.png",
                "G",
            ),
            (
                DrawingMode.BEZIER,
                "Bézier (2D)",
                "Desenhar curvas de Bézier 2D (B)",
                "bezier.png",
                "B",
            ),
            (
                DrawingMode.BSPLINE,
                "B-spline (2D)",
                "Desenhar curvas B-spline 2D (N)",
                "bspline.png",
                "N",
            ),
        ]
        initial_mode = self.state_manager.drawing_mode()
        for mode, name, tip, icon_name, shortcut in modes:
            action = QAction(self._get_icon(icon_name), name, self.window)
            action.setToolTip(tip)
            action.setShortcut(shortcut)
            action.setCheckable(True)
            action.setData(mode)
            action.triggered.connect(
                lambda checked, m=mode: mode_callback(m) if checked else None
            )
            toolbar.addAction(action)
            self.mode_action_group.addAction(action)
            if mode == initial_mode:
                action.setChecked(True)

        toolbar.addSeparator()
        initial_color = self.state_manager.draw_color()
        self.color_action = QAction(
            self._create_color_icon(initial_color, 24), "Cor", self.window
        )
        self.color_action.setToolTip("Selecionar cor para novos objetos (C)")
        self.color_action.setShortcut("C")
        self.color_action.triggered.connect(color_callback)
        toolbar.addAction(self.color_action)
        toolbar.addSeparator()

        manual_coord_action = QAction(
            self._get_icon("coords.png"), "Coords (2D)", self.window
        )
        manual_coord_action.setToolTip("Adicionar forma 2D via coordenadas (M)")
        manual_coord_action.setShortcut("M")
        manual_coord_action.triggered.connect(coord_callback)
        toolbar.addAction(manual_coord_action)

        transform_action_tb = QAction(
            self._get_icon("transform.png"), "Transf.", self.window
        )
        transform_action_tb.setToolTip("Aplicar transformação (Ctrl+T)")  # Genérico
        transform_action_tb.triggered.connect(transform_callback)
        toolbar.addAction(transform_action_tb)
        toolbar.addSeparator()

        # Controles de Clipping de Linha (2D)
        clipping_group_box = QGroupBox("Clipping Linha (2D)")
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
        """
        Configura a barra de status da aplicação.

        Args:
            zoom_callback: Callback para mudanças no zoom (da vista 2D).

        Returns:
            QStatusBar: Barra de status configurada.
        """
        status_bar = QStatusBar(self.window)
        self.window.setStatusBar(status_bar)
        self.status_bar = status_bar

        # Controles de Zoom 2D
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(self.SLIDER_RANGE_MIN, self.SLIDER_RANGE_MAX)
        self.zoom_slider.setToolTip("Controlar o nível de zoom (Vista 2D)")
        self.zoom_slider.setMinimumWidth(100)
        self.zoom_slider.setMaximumWidth(150)
        self.zoom_slider.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.zoom_slider.valueChanged.connect(zoom_callback)
        status_bar.addPermanentWidget(self.zoom_slider)

        self.zoom_label = QLabel("Zoom 2D: 100%")
        self.zoom_label.setMinimumWidth(110)
        # Aumentado para "Zoom 2D: "
        self.zoom_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        status_bar.addPermanentWidget(self.zoom_label)

        # Rotação da Vista 2D
        self.status_rotation_label = QLabel("Rot 2D: 0.0°")
        self.status_rotation_label.setToolTip("Rotação da vista 2D (Shift+Setas)")
        self.status_rotation_label.setMinimumWidth(90)
        self.status_rotation_label.setAlignment(Qt.AlignCenter)
        status_bar.addPermanentWidget(self.status_rotation_label)

        # Modo de Desenho/Interação
        self.status_mode_label = QLabel("Modo: Select")
        self.status_mode_label.setToolTip("Modo de interação atual")
        self.status_mode_label.setMinimumWidth(120)
        # Aumentado para nomes mais longos
        self.status_mode_label.setAlignment(Qt.AlignCenter)
        status_bar.addPermanentWidget(self.status_mode_label)

        # Coordenadas do Mouse 2D
        self.status_coords_label = QLabel("Mouse XY: ---, ---")
        self.status_coords_label.setToolTip("Coordenadas do mouse na cena 2D")
        self.status_coords_label.setMinimumWidth(160)
        self.status_coords_label.setAlignment(Qt.AlignCenter)
        status_bar.addPermanentWidget(self.status_coords_label)

        # Coordenadas 3D (e.g. VRP)
        self.status_3d_coords_label = QLabel(
            "VRP XYZ: ---, ---, ---"
        )  # Exemplo inicial
        self.status_3d_coords_label.setToolTip(
            "Coordenadas 3D relevantes (e.g. VRP da câmera)"
        )
        self.status_3d_coords_label.setMinimumWidth(200)
        # Espaço para "Label XYZ: x, y, z"
        self.status_3d_coords_label.setAlignment(Qt.AlignCenter)
        status_bar.addPermanentWidget(self.status_3d_coords_label)

        self.status_message_label = QLabel("Pronto.")
        status_bar.addWidget(self.status_message_label, 1)  # Widget que se estica

        self.update_status_bar_mode(self.state_manager.drawing_mode())
        return status_bar

    def update_color_button(self, color: QColor):
        """Atualiza o ícone do botão de cor."""
        if self.color_action:
            self.color_action.setIcon(self._create_color_icon(color, 24))

    def update_toolbar_mode_selection(self, mode: DrawingMode):
        """Atualiza a seleção de modo na barra de ferramentas."""
        if self.mode_action_group:
            for action in self.mode_action_group.actions():
                if action.data() == mode:
                    if not action.isChecked():
                        action.setChecked(True)
                    break

    def update_clipper_selection(
        self, algorithm: LineClippingAlgorithm
    ):  # Para clipping 2D
        """Atualiza a seleção do algoritmo de recorte."""
        if self.cs_radio and self.lb_radio:
            is_cs = algorithm == LineClippingAlgorithm.COHEN_SUTHERLAND
            if self.cs_radio.isChecked() != is_cs:
                self.cs_radio.setChecked(is_cs)
            if self.lb_radio.isChecked() == is_cs:
                self.lb_radio.setChecked(not is_cs)

    def update_status_bar_message(self, message: str):
        """Atualiza a mensagem na barra de status."""
        if self.status_message_label:
            self.status_message_label.setText(message)

    def update_status_bar_coords(self, scene_pos: QPointF):  # Coordenadas do mouse 2D
        """Atualiza as coordenadas 2D do mouse exibidas na barra de status."""
        if self.status_coords_label:
            locale = QLocale()
            # Formata com uma casa decimal
            coord_text = f"Mouse XY: {locale.toString(scene_pos.x(), 'f', 1)}, {locale.toString(scene_pos.y(), 'f', 1)}"
            self.status_coords_label.setText(coord_text)

    def update_status_bar_3d_coords(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        label: str = "VRP",
    ):
        """
        Atualiza as coordenadas 3D exibidas na barra de status.

        Args:
            x, y, z: Coordenadas 3D. Se None, exibirá "---".
            label: Rótulo para as coordenadas (e.g., "VRP", "Alvo").
        """
        if self.status_3d_coords_label:
            locale = QLocale()
            if x is None or y is None or z is None:
                coord_text = f"{label} XYZ: ---, ---, ---"
            else:
                coord_text = f"{label} XYZ: {locale.toString(x, 'f', 1)}, {locale.toString(y, 'f', 1)}, {locale.toString(z, 'f', 1)}"
            self.status_3d_coords_label.setText(coord_text)

    def update_status_bar_mode(self, mode: DrawingMode):
        """Atualiza o modo de desenho/interação exibido na barra de status."""
        if self.status_mode_label:
            # Mapeia apenas modos de desenho 2D aqui; SELEÇÃO/PAN são genéricos
            mode_map = {
                DrawingMode.SELECT: "Seleção",
                DrawingMode.PAN: "Mover Vista 2D",
                DrawingMode.POINT: "Ponto 2D",
                DrawingMode.LINE: "Linha 2D",
                DrawingMode.POLYGON: "Polígono 2D",
                DrawingMode.BEZIER: "Bézier 2D",
                DrawingMode.BSPLINE: "B-spline 2D",
            }
            mode_text = f"Modo: {mode_map.get(mode, 'N/A')}"  # N/A para modos 3D específicos via menu
            self.status_mode_label.setText(mode_text)

    def update_status_bar_rotation(self, angle: float):  # Rotação da vista 2D
        """Atualiza o ângulo de rotação da vista 2D exibido na barra de status."""
        if self.status_rotation_label:
            rotation_text = f"Rot 2D: {QLocale().toString(angle, 'f', 1)}°"
            self.status_rotation_label.setText(rotation_text)

    def update_status_bar_zoom(
        self, scale: float, slider_value: int
    ):  # Zoom da vista 2D
        """
        Atualiza o nível de zoom da vista 2D exibido na barra de status.

        Args:
            scale: Nova escala de zoom.
            slider_value: Novo valor do controle deslizante de zoom.
        """
        if self.zoom_label:
            zoom_percent = scale * 100
            self.zoom_label.setText(
                f"Zoom 2D: {QLocale().toString(zoom_percent, 'f', 0)}%"
            )

        if self.zoom_slider:  # <<< ADICIONADA VERIFICAÇÃO
            # Bloqueia sinais para evitar que setValue dispare valueChanged recursivamente
            with QSignalBlocker(self.zoom_slider):
                self.zoom_slider.setValue(slider_value)
        # else:
        #     print("Aviso UIManager: Tentativa de atualizar zoom_slider antes de ser inicializado.")

    def update_viewport_action_state(self, is_visible: bool):  # Viewport 2D
        """Atualiza o estado da ação de visibilidade do viewport 2D no menu."""
        if self.viewport_toggle_action:
            if self.viewport_toggle_action.isChecked() != is_visible:
                self.viewport_toggle_action.setChecked(is_visible)
