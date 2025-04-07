# graphics_editor/editor.py
import sys
import os
from enum import Enum, auto
from typing import List, Optional, Tuple, Dict, Union

from PyQt5.QtWidgets import (
    QMainWindow,
    QGraphicsScene,
    QToolBar,
    QAction,
    QActionGroup,
    QDialog,
    QMessageBox,
    QGraphicsView,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QInputDialog,
    QGraphicsEllipseItem,
    QGraphicsPolygonItem,
    QColorDialog,
    QPushButton,
    QGraphicsItem,
    QFileDialog,
    QMenu,
    QMenuBar,
    QLabel,
    QStatusBar,
    QSlider,  # Import QSlider
)
from PyQt5.QtCore import (
    QPointF,
    Qt,
    pyqtSignal,
    QSize,
    QLineF,
    QRectF,
    QTimer,
)  # Import QTimer
from PyQt5.QtGui import (
    QPainterPath,
    QPen,
    QColor,
    QPolygonF,
    QIcon,
    QPixmap,
    QCloseEvent,
    QBrush,
    QTransform,
    QPainter,  # Added QPainter here
)

# Use relative imports for modules within the package
from .view import GraphicsView
from .models.point import Point
from .models.line import Line
from .models.polygon import Polygon
from .dialogs.coordinates_input import CoordinateInputDialog
from .controllers.transformation_controller import TransformationController
from .io_handler import IOHandler
from .object_manager import ObjectManager

# Define the DataObject type alias relative to models
DataObject = Union[Point, Line, Polygon]


class DrawingMode(Enum):
    """Modos de interação disponíveis no editor."""

    POINT = auto()
    LINE = auto()
    POLYGON = auto()
    SELECT = auto()
    PAN = auto()


class GraphicsEditor(QMainWindow):
    """Janela principal da aplicação para o editor gráfico."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editor Gráfico 2D")
        self.resize(1000, 750)

        # --- Caminho Base para Ícones ---
        self._icon_base_path = os.path.join(os.path.dirname(__file__), "icons")

        # --- Constantes para Zoom Slider ---
        self.SLIDER_RANGE_MIN = 0
        self.SLIDER_RANGE_MAX = 200  # Maior range para mais granularidade
        self.VIEW_SCALE_MIN = 0.1
        self.VIEW_SCALE_MAX = 10.0

        # --- Estado Interno ---
        self._drawing_mode: DrawingMode = DrawingMode.SELECT
        self._current_line_start: Optional[Point] = None
        self._current_polygon_points: List[Point] = []
        self._current_polygon_is_open: bool = False
        self._current_draw_color: QColor = QColor(Qt.black)

        # --- Itens de Pré-visualização ---
        self._temp_line_item: Optional[QGraphicsLineItem] = None
        self._temp_polygon_path: Optional[QGraphicsPathItem] = None
        self._temp_item_pen = QPen(Qt.gray, 1, Qt.DashLine)

        # --- Componentes Principais ---
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(
            -5000, -5000, 10000, 10000
        )  # Define uma área grande para a cena
        self._view = GraphicsView(self._scene, self)
        self.setCentralWidget(self._view)

        # --- Controller e Handlers ---
        self._transformation_controller = TransformationController(self)
        self._io_handler = IOHandler(self)
        self._object_manager = ObjectManager()

        # --- Configuração da UI ---
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()  # Configura a status bar (incluindo slider e rotação agora)
        self._connect_signals()
        self._update_view_interaction()  # Define o modo inicial da view
        self._update_status_bar()  # Define o texto inicial da status bar
        # Atualiza os controles de zoom (slider/label) para o estado inicial da view
        # Usar QTimer.singleShot para garantir que a view esteja pronta
        QTimer.singleShot(0, self._update_zoom_controls)

    def _get_icon(self, name: str) -> QIcon:
        """Carrega um QIcon do diretório de ícones."""
        path = os.path.join(self._icon_base_path, name)
        if not os.path.exists(path):
            print(f"Aviso: Ícone não encontrado em {path}")
            # Retorna um QIcon vazio para evitar crash, mas a UI ficará sem o ícone
            return QIcon()
        return QIcon(path)

    def _setup_menu_bar(self) -> None:
        """Configura a barra de menus."""
        menubar = self.menuBar()

        # --- Menu Arquivo ---
        file_menu = menubar.addMenu("&Arquivo")
        load_obj_action = QAction(self._get_icon("open.png"), "Carregar &OBJ...", self)
        load_obj_action.setToolTip("Carregar geometria de um arquivo Wavefront OBJ")
        load_obj_action.triggered.connect(self._prompt_load_obj)
        file_menu.addAction(load_obj_action)

        save_obj_action = QAction(
            self._get_icon("save.png"), "&Salvar como OBJ...", self
        )
        save_obj_action.setToolTip("Salvar a cena atual em um arquivo Wavefront OBJ")
        save_obj_action.triggered.connect(self._prompt_save_obj)
        file_menu.addAction(save_obj_action)

        file_menu.addSeparator()

        clear_action = QAction(self._get_icon("clear.png"), "&Limpar Cena", self)
        clear_action.setToolTip("Limpar todos os objetos da cena")
        clear_action.triggered.connect(self._clear_scene)
        file_menu.addAction(clear_action)

        file_menu.addSeparator()

        exit_action = QAction(self._get_icon("exit.png"), "&Sair", self)
        exit_action.setToolTip("Fechar a aplicação")
        exit_action.triggered.connect(self.close)  # Chama o closeEvent da QMainWindow
        file_menu.addAction(exit_action)

        # --- Menu Vista ---
        view_menu = menubar.addMenu("&Vista")
        reset_view_action = QAction("Resetar Vista", self)
        reset_view_action.setToolTip(
            "Resetar zoom, pan e rotação da vista (Shift+Setas para rotacionar)"
        )
        reset_view_action.triggered.connect(self._reset_view)
        view_menu.addAction(reset_view_action)

    def _setup_toolbar(self) -> None:
        """Configura a barra de ferramentas principal."""
        toolbar = QToolBar("Ferramentas")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.LeftToolBarArea, toolbar)

        self._mode_action_group = QActionGroup(self)
        self._mode_action_group.setExclusive(True)

        # --- Ações de Modo ---
        modes = [
            (
                "Selecionar",
                DrawingMode.SELECT,
                "Selecionar itens (Padrão)",
                "select.png",
            ),
            (
                "Mover Vista",
                DrawingMode.PAN,
                "Mover a vista (Ferramenta Mão)",
                "pan.png",
            ),
            ("Ponto", DrawingMode.POINT, "Desenhar um ponto único", "point.png"),
            ("Linha", DrawingMode.LINE, "Desenhar uma linha (2 cliques)", "line.png"),
            (
                "Polígono",
                DrawingMode.POLYGON,
                "Desenhar um polígono (cliques, botão direito finaliza)",
                "polygon.png",
            ),
        ]
        for name, mode, tip, icon_name in modes:
            action = QAction(self._get_icon(icon_name), name, self)
            action.setToolTip(f"{tip}\nRotação: Shift+Setas")  # Add rotation hint
            action.setCheckable(True)
            action.setData(mode)  # Armazena o enum DrawingMode na ação
            action.triggered.connect(self._on_mode_action_triggered)
            toolbar.addAction(action)
            self._mode_action_group.addAction(action)
            if mode == self._drawing_mode:  # Marca a ação do modo inicial
                action.setChecked(True)

        toolbar.addSeparator()

        # --- Ação de Cor ---
        self.color_action = QAction(
            self._create_color_icon(self._current_draw_color), "Cor Desenho", self
        )
        self.color_action.setToolTip("Selecionar cor para novos objetos")
        self.color_action.triggered.connect(self._select_drawing_color)
        toolbar.addAction(self.color_action)

        toolbar.addSeparator()

        # --- Ação de Coordenadas Manuais ---
        manual_coord_action = QAction(self._get_icon("coords.png"), "Coordenadas", self)
        manual_coord_action.setToolTip("Adicionar forma via diálogo de coordenadas")
        manual_coord_action.triggered.connect(self._open_coordinate_input_dialog)
        toolbar.addAction(manual_coord_action)

        toolbar.addSeparator()

        # --- Ação de Transformação ---
        transform_action = QAction(self._get_icon("transform.png"), "Transformar", self)
        transform_action.setToolTip("Aplicar transformação ao objeto selecionado")
        transform_action.triggered.connect(self._open_transformation_dialog)
        toolbar.addAction(transform_action)

    def _setup_status_bar(self) -> None:
        """Configura a barra de status, incluindo controles de zoom e rotação."""
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)

        # --- Widgets Permanentes (à direita) ---
        # Ordem: Modo, Rotação, Zoom Label, Zoom Slider

        self._status_mode_label = QLabel("Modo: -")
        self._status_bar.addPermanentWidget(self._status_mode_label)

        # Label para mostrar o ângulo de rotação
        self._status_rotation_label = QLabel("Rotação View: 0.0°")
        self._status_bar.addPermanentWidget(self._status_rotation_label)

        # --- Controles de Zoom (à direita, antes dos permanentes) ---
        self._zoom_label = QLabel("Zoom: 100%")
        self._status_bar.addPermanentWidget(self._zoom_label)

        self._zoom_slider = QSlider(Qt.Horizontal)
        self._zoom_slider.setRange(self.SLIDER_RANGE_MIN, self.SLIDER_RANGE_MAX)
        self._zoom_slider.setToolTip("Controlar o nível de zoom")
        self._zoom_slider.setMinimumWidth(150)  # Define um tamanho mínimo
        # Valor inicial será definido em _update_zoom_controls
        self._status_bar.addPermanentWidget(self._zoom_slider)

    def _update_status_bar(self) -> None:
        """Atualiza as informações exibidas na barra de status (modo, rotação, zoom é separado)."""
        mode_text = f"Modo: {self._drawing_mode.name.capitalize()}"
        self._status_mode_label.setText(mode_text)

        # Pega o ângulo de rotação da view e atualiza o label
        rotation_angle = self._view.get_rotation_angle()
        rotation_text = f"Rotação View: {rotation_angle:.1f}°"
        self._status_rotation_label.setText(rotation_text)
        # Nota: A atualização do zoom (label e slider) é feita por _update_zoom_controls

    def _connect_signals(self) -> None:
        """Conecta sinais e slots entre os componentes."""
        # --- Sinais da View -> Editor ---
        self._view.scene_left_clicked.connect(self._handle_scene_left_click)
        self._view.scene_right_clicked.connect(self._handle_scene_right_click)
        self._view.scene_mouse_moved.connect(self._handle_scene_mouse_move)
        self._view.delete_requested.connect(self._delete_selected_items)

        # Conecta mudança de ROTAÇÃO da view à atualização da status bar
        self._view.rotation_changed.connect(
            self._update_status_bar
        )  # Atualiza label de rotação
        # Conecta mudança de ESCALA da view à atualização dos controles de zoom
        self._view.scale_changed.connect(self._update_zoom_controls)

        # --- Sinais do Controller -> Editor ---
        self._transformation_controller.object_transformed.connect(
            self._handle_object_transformed
        )

        # --- Sinais dos Controles de Zoom -> Editor ---
        # Conecta mudança no slider à ação de zoom na view
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)

        # Conexão opcional para coordenadas do mouse na status bar
        # self._view.scene_mouse_moved.connect(self._update_mouse_coords_status)

    # --- Slots para Controles de Zoom ---

    def _on_zoom_slider_changed(self, value: int) -> None:
        """Chamado quando o valor do slider de zoom muda."""
        # Mapeia o valor inteiro do slider (0-200) para a escala da view (0.1-10.0)
        # Usar mapeamento linear
        if self.SLIDER_RANGE_MAX == self.SLIDER_RANGE_MIN:
            return  # Avoid division by zero
        factor = (value - self.SLIDER_RANGE_MIN) / (
            self.SLIDER_RANGE_MAX - self.SLIDER_RANGE_MIN
        )  # Normaliza para 0.0 - 1.0
        target_scale = self.VIEW_SCALE_MIN + factor * (
            self.VIEW_SCALE_MAX - self.VIEW_SCALE_MIN
        )

        # Define a escala na view (que emitirá scale_changed, atualizando o label e slider)
        self._view.set_scale(target_scale)  # set_scale agora lida com a lógica de zoom

    def _update_zoom_controls(self) -> None:
        """Atualiza o slider e o label de zoom com base na escala atual da view."""
        current_scale = self._view.get_scale()

        # Atualiza o Label
        self._zoom_label.setText(f"Zoom: {current_scale * 100:.0f}%")

        # Mapeia a escala da view (0.1-10.0) de volta para o valor do slider (0-200)
        if (self.VIEW_SCALE_MAX - self.VIEW_SCALE_MIN) == 0:
            return  # Avoid division by zero
        clamped_scale = max(
            self.VIEW_SCALE_MIN, min(current_scale, self.VIEW_SCALE_MAX)
        )
        factor = (clamped_scale - self.VIEW_SCALE_MIN) / (
            self.VIEW_SCALE_MAX - self.VIEW_SCALE_MIN
        )
        slider_value = int(
            round(
                self.SLIDER_RANGE_MIN
                + factor * (self.SLIDER_RANGE_MAX - self.SLIDER_RANGE_MIN)
            )
        )

        # Define o valor no slider SEM emitir o sinal valueChanged novamente
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(slider_value)
        self._zoom_slider.blockSignals(False)

    # --- Métodos Utilitários de UI ---

    def _create_color_icon(self, color: QColor, size: int = 16) -> QIcon:
        """Cria um ícone quadrado preenchido com a cor especificada."""
        pixmap = QPixmap(size, size)
        pixmap.fill(color)
        border_pen = QPen(Qt.gray)
        painter = QPainter(pixmap)  # Necessário importar QPainter
        painter.setPen(border_pen)
        painter.drawRect(0, 0, size - 1, size - 1)
        painter.end()
        return QIcon(pixmap)

    def _select_drawing_color(self):
        """Abre um diálogo para o usuário selecionar a cor de desenho atual."""
        new_color = QColorDialog.getColor(
            self._current_draw_color, self, "Selecionar Cor de Desenho"
        )
        if new_color.isValid():
            self._current_draw_color = new_color
            self.color_action.setIcon(self._create_color_icon(self._current_draw_color))

    # --- Gerenciamento de Modo ---

    def _on_mode_action_triggered(self) -> None:
        """Chamado quando uma ação de modo na toolbar é clicada."""
        checked_action = self._mode_action_group.checkedAction()
        if checked_action:
            new_mode = checked_action.data()  # Obtém o DrawingMode armazenado
            if isinstance(new_mode, DrawingMode):
                self._set_drawing_mode(new_mode)

    def _set_drawing_mode(self, mode: DrawingMode) -> None:
        """Define o modo de desenho atual e atualiza a UI."""
        if mode == self._drawing_mode:
            return  # Não faz nada se o modo já for o atual

        self._finish_current_drawing(commit=False)  # Cancela desenho em progresso
        self._drawing_mode = mode
        self._update_view_interaction()  # Ajusta cursor e modo de arrasto da view
        self._update_status_bar()  # Atualiza texto na status bar (modo e rotação)

        # Garante que a ação correta na toolbar esteja marcada
        for action in self._mode_action_group.actions():
            if action.data() == mode:
                action.setChecked(True)
                break

    def _update_view_interaction(self) -> None:
        """Atualiza o cursor e o modo de arrasto da QGraphicsView com base no modo."""
        if self._drawing_mode == DrawingMode.SELECT:
            self._view.set_drag_mode(QGraphicsView.RubberBandDrag)
            # self._view.setCursor(Qt.ArrowCursor) # View.set_drag_mode agora faz isso
        elif self._drawing_mode == DrawingMode.PAN:
            self._view.set_drag_mode(QGraphicsView.ScrollHandDrag)
            # O cursor (OpenHand/ClosedHand) é gerenciado pela view/Qt neste modo
        else:  # Modos de desenho (POINT, LINE, POLYGON)
            self._view.set_drag_mode(QGraphicsView.NoDrag)
            # self._view.setCursor(Qt.CrossCursor) # View.set_drag_mode agora faz isso

        # Força a view a atualizar seu cursor com base no novo drag mode
        self._view.set_drag_mode(self._view.dragMode())

    # --- Lógica de Desenho ---

    def _handle_scene_left_click(self, scene_pos: QPointF) -> None:
        """
        Processa um clique esquerdo na cena, dependendo do modo atual.
        A `scene_pos` recebida já está em coordenadas do mundo (cena),
        independentemente da rotação/zoom/pan da view.
        """
        x, y = scene_pos.x(), scene_pos.y()
        current_point_data = Point(x, y, color=self._current_draw_color)

        if self._drawing_mode == DrawingMode.POINT:
            self._add_data_object_to_scene(current_point_data)

        elif self._drawing_mode == DrawingMode.LINE:
            if self._current_line_start is None:
                # Inicia a linha, armazena o primeiro ponto (em WC)
                self._current_line_start = current_point_data
                # Atualiza a pré-visualização inicial (ponto inicial para posição atual)
                self._update_line_preview(scene_pos)
            else:
                # Finaliza a linha, criando o objeto Line com pontos em WC
                line_data = Line(
                    self._current_line_start,
                    current_point_data,
                    color=self._current_draw_color,
                )
                self._add_data_object_to_scene(line_data)
                # Reseta o estado de desenho da linha
                self._current_line_start = None
                self._remove_temp_items()

        elif self._drawing_mode == DrawingMode.POLYGON:
            # Adiciona o ponto clicado (em WC) à lista de pontos do polígono atual
            if not self._current_polygon_points:  # Primeiro ponto do polígono
                # Pergunta sobre polígono aberto/fechado
                reply = QMessageBox.question(
                    self,
                    "Tipo de Polígono",
                    "Deseja criar um polígono aberto (linha tracejada/polilinha)?\n"
                    "('Não' para polígono fechado padrão)",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                self._current_polygon_is_open = reply == QMessageBox.Yes

            self._current_polygon_points.append(current_point_data)
            # Atualiza a pré-visualização do polígono
            self._update_polygon_preview(scene_pos)

    def _handle_scene_right_click(self, scene_pos: QPointF) -> None:
        """Processa um clique direito na cena, usado para finalizar polígonos."""
        if self._drawing_mode == DrawingMode.POLYGON:
            # Finaliza o polígono se tiver pontos suficientes
            self._finish_current_drawing(commit=True)

    def _handle_scene_mouse_move(self, scene_pos: QPointF) -> None:
        """
        Processa o movimento do mouse na cena, atualizando pré-visualizações.
        A `scene_pos` recebida já está em coordenadas do mundo (cena).
        """
        if self._drawing_mode == DrawingMode.LINE and self._current_line_start:
            # Atualiza a pré-visualização da linha (de _current_line_start até scene_pos)
            self._update_line_preview(scene_pos)
        elif self._drawing_mode == DrawingMode.POLYGON and self._current_polygon_points:
            # Atualiza a pré-visualização do polígono (do último ponto até scene_pos)
            self._update_polygon_preview(scene_pos)

    def _update_line_preview(self, current_pos: QPointF):
        """Atualiza ou cria a linha de pré-visualização (em coordenadas de cena)."""
        if not self._current_line_start:
            return

        start_qpos = self._current_line_start.to_qpointf()  # Ponto inicial (WC)
        # Posição atual do mouse (WC)
        end_qpos = current_pos

        if self._temp_line_item is None:
            # Cria o item temporário na cena
            self._temp_line_item = QGraphicsLineItem(QLineF(start_qpos, end_qpos))
            self._temp_line_item.setPen(self._temp_item_pen)
            self._temp_line_item.setZValue(1000)  # Garante que fique por cima
            self._scene.addItem(self._temp_line_item)
        else:
            # Atualiza a linha do item existente
            self._temp_line_item.setLine(QLineF(start_qpos, end_qpos))

    def _update_polygon_preview(self, current_pos: QPointF):
        """Atualiza ou cria o caminho de pré-visualização do polígono (em coordenadas de cena)."""
        if not self._current_polygon_points:
            return

        path = QPainterPath()
        # Pega o primeiro ponto (WC)
        start_qpos = self._current_polygon_points[0].to_qpointf()
        path.moveTo(start_qpos)
        # Adiciona linhas para os pontos subsequentes (WC)
        for point_data in self._current_polygon_points[1:]:
            path.lineTo(point_data.to_qpointf())
        # Adiciona linha até a posição atual do mouse (WC)
        path.lineTo(current_pos)
        # Se for fechado e tivermos pelo menos 1 ponto, adiciona linha de volta ao início
        if not self._current_polygon_is_open and len(self._current_polygon_points) >= 1:
            # path.lineTo(start_qpos) # PainterPath fecha automaticamente com closeSubpath se necessário
            # Mas para preview visual, desenhar a linha explicitamente é melhor
            path.lineTo(start_qpos)  # Conecta o cursor ao ponto inicial

        if self._temp_polygon_path is None:
            # Cria o item temporário na cena
            self._temp_polygon_path = QGraphicsPathItem()
            self._temp_polygon_path.setPen(self._temp_item_pen)
            self._temp_polygon_path.setZValue(1000)
            self._scene.addItem(self._temp_polygon_path)

        # Atualiza o caminho do item existente
        self._temp_polygon_path.setPath(path)

    def _finish_current_drawing(self, commit: bool = True) -> None:
        """Finaliza ou cancela a operação de desenho atual."""
        drawing_finished = False
        if self._drawing_mode == DrawingMode.LINE and self._current_line_start:
            # Se estava desenhando linha, apenas reseta o estado
            self._current_line_start = None
            drawing_finished = True  # Marca que uma operação foi cancelada/finalizada

        if self._drawing_mode == DrawingMode.POLYGON and self._current_polygon_points:
            # Se estava desenhando polígono...
            min_points_needed = 2 if self._current_polygon_is_open else 3
            if commit and len(self._current_polygon_points) >= min_points_needed:
                # Se commit=True e tem pontos suficientes, cria o objeto Polygon
                polygon_data = Polygon(
                    self._current_polygon_points.copy(),  # Copia a lista
                    self._current_polygon_is_open,
                    color=self._current_draw_color,
                )
                self._add_data_object_to_scene(polygon_data)

            # Reseta o estado do desenho do polígono independentemente de ter criado ou não
            self._current_polygon_points = []
            self._current_polygon_is_open = False
            drawing_finished = True  # Marca que uma operação foi cancelada/finalizada

        if drawing_finished:
            # Remove quaisquer itens de pré-visualização da cena
            self._remove_temp_items()

    def _remove_temp_items(self) -> None:
        """Remove os itens gráficos temporários (pré-visualização) da cena."""
        if self._temp_line_item and self._temp_line_item.scene():
            self._scene.removeItem(self._temp_line_item)
            self._temp_line_item = None
        if self._temp_polygon_path and self._temp_polygon_path.scene():
            self._scene.removeItem(self._temp_polygon_path)
            self._temp_polygon_path = None

    # --- Gerenciamento de Objetos e Cena ---

    def _add_data_object_to_scene(self, data_object: DataObject):
        """Cria o QGraphicsItem para um DataObject e o adiciona à cena."""
        try:
            # O DataObject cria seu próprio item gráfico em World Coordinates
            graphics_item = data_object.create_graphics_item()
            # Associa o objeto de dados ao item gráfico para referência futura
            graphics_item.setData(0, data_object)
            # Aplica estilo (cor, preenchimento) com base nos dados
            self._apply_style_to_item(graphics_item, data_object)
            self._scene.addItem(graphics_item)
            # A view se encarregará de exibir este item corretamente,
            # aplicando sua transformação (incluindo rotação) no momento do desenho.
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro ao Adicionar Item",
                f"Não foi possível criar o item gráfico para {type(data_object).__name__}: {e}",
            )

    def _delete_selected_items(self) -> None:
        """Remove os itens atualmente selecionados da cena, após confirmação."""
        selected = self._scene.selectedItems()
        if not selected:
            return

        reply = QMessageBox.question(
            self,
            "Confirmar Exclusão",
            f"Tem certeza que deseja excluir {len(selected)} item(ns) selecionado(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            for item in selected:
                if item.scene():
                    # Remove o item gráfico da cena
                    self._scene.removeItem(item)
                    # Opcional: remover o objeto de dados associado de alguma lista,
                    # mas como não temos uma lista centralizada aqui, apenas remover
                    # da cena é suficiente por enquanto.
            self._scene.update()  # Solicita redesenho da cena

    def _clear_scene(self) -> None:
        """Limpa todos os itens da cena e reseta a visualização, após confirmação."""
        reply = QMessageBox.question(
            self,
            "Confirmar Limpeza",
            "Tem certeza que deseja limpar toda a cena?\nEsta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self._finish_current_drawing(
                commit=False
            )  # Cancela qualquer desenho pendente
            self._scene.clearSelection()  # Limpa seleção atual
            # self._scene.clear() # Remove todos os itens gráficos da cena
            # É mais seguro iterar e remover, especialmente se houver itens com lógica especial
            items_to_remove = list(self._scene.items())  # Cria cópia da lista de itens
            for item in items_to_remove:
                if item.scene():  # Verifica se ainda está na cena
                    self._scene.removeItem(item)

            # Opcional: Limpar a lista de DataObjects se houver uma centralizada.
            # self._object_manager.clear_all_objects() # Exemplo se tivéssemos essa gestão

            self._scene.update()  # Solicita redesenho
            self._reset_view()  # Reseta zoom, pan e ROTAÇÃO da view

    def _reset_view(self) -> None:
        """Reseta a transformação da QGraphicsView (zoom, pan, rotação)."""
        # Chama o método reset_view da nossa classe GraphicsView customizada
        self._view.reset_view()
        # Os sinais scale_changed e rotation_changed (emitidos por reset_view se necessário)
        # já estão conectados para atualizar a UI (slider, labels, status bar).

    # --- Diálogos e Interações Externas ---

    def _open_coordinate_input_dialog(self) -> None:
        """Abre um diálogo para adicionar formas usando coordenadas manuais."""
        dialog_mode_map = {
            DrawingMode.POINT: "point",
            DrawingMode.LINE: "line",
            DrawingMode.POLYGON: "polygon",
        }
        # Tenta usar o modo atual, senão pergunta ao usuário
        dialog_mode_str = dialog_mode_map.get(self._drawing_mode)

        if dialog_mode_str is None:
            items = ("Ponto", "Linha", "Polígono")
            item, ok = QInputDialog.getItem(
                self,
                "Selecionar Forma",
                "Qual forma deseja adicionar manualmente?",
                items,
                0,
                False,
            )
            if ok and item:
                dialog_mode_str = {
                    "Ponto": "point",
                    "Linha": "line",
                    "Polígono": "polygon",
                }.get(item)
            else:
                return  # Usuário cancelou

        if not dialog_mode_str:
            return  # Segurança

        self._finish_current_drawing(commit=False)  # Cancela desenho atual

        dialog = CoordinateInputDialog(self, mode=dialog_mode_str)
        dialog.set_initial_color(self._current_draw_color)

        if dialog.exec_() == QDialog.Accepted:
            # O diálogo get_coordinates faz a validação interna
            result_data = dialog.get_coordinates()
            if result_data:
                try:
                    # Desempacota o resultado com base no modo
                    if dialog_mode_str == "polygon":
                        coords, is_open, color = result_data
                    elif dialog_mode_str in ["point", "line"]:
                        coords, color = result_data
                        is_open = False  # Não aplicável, mas define para consistência
                    else:
                        raise ValueError(
                            f"Modo de diálogo inesperado ao processar resultado: {dialog_mode_str}"
                        )

                    # Garante uma cor válida
                    if not color or not color.isValid():
                        color = QColor(Qt.black)

                    # Cria o objeto de dados a partir das coordenadas (que estão em WC)
                    self._add_item_from_coordinates(
                        coords, is_open, color, dialog_mode_str
                    )

                except (ValueError, TypeError, IndexError) as e:
                    QMessageBox.warning(
                        self,
                        "Erro ao Processar Coordenadas",
                        f"Dados do diálogo inválidos ou formato inesperado: {e}",
                    )

    def _add_item_from_coordinates(
        self,
        coords: List[Tuple[float, float]],
        is_open: bool,
        color: QColor,
        dialog_mode_str: str,
    ) -> None:
        """Cria e adiciona um objeto de dados à cena a partir de coordenadas (WC)."""
        try:
            data_object: Optional[DataObject] = None
            # Cria o objeto de dados apropriado (Point, Line, Polygon)
            if dialog_mode_str == "point":
                if not coords:
                    raise ValueError("Coordenadas do ponto ausentes.")
                data_object = Point(coords[0][0], coords[0][1], color=color)
            elif dialog_mode_str == "line":
                if len(coords) < 2:
                    raise ValueError("Coordenadas da linha insuficientes.")
                start_pt = Point(
                    coords[0][0], coords[0][1], color=color
                )  # Ponto inicial em WC
                end_pt = Point(
                    coords[1][0], coords[1][1], color=color
                )  # Ponto final em WC
                data_object = Line(start_pt, end_pt, color=color)
            elif dialog_mode_str == "polygon":
                min_pts = 2 if is_open else 3
                if len(coords) < min_pts:
                    raise ValueError(
                        f"Coordenadas insuficientes para polígono {('aberto' if is_open else 'fechado')} ({len(coords)}/{min_pts})."
                    )
                # Cria lista de objetos Point a partir das coordenadas WC
                poly_pts = [Point(x, y, color=color) for x, y in coords]
                data_object = Polygon(poly_pts, is_open, color=color)
            else:
                raise ValueError(f"Modo de criação desconhecido: {dialog_mode_str}")

            if data_object:
                # Adiciona o objeto de dados (e seu item gráfico) à cena
                self._add_data_object_to_scene(data_object)

        except (IndexError, ValueError, TypeError) as e:
            QMessageBox.warning(
                self,
                "Erro ao Adicionar Item",
                f"Não foi possível criar o item a partir das coordenadas: {e}",
            )

    def _open_transformation_dialog(self) -> None:
        """Abre o diálogo para aplicar transformações ao item selecionado."""
        selected_items = self._scene.selectedItems()
        if len(selected_items) != 1:
            QMessageBox.warning(
                self,
                "Seleção Inválida",
                "Selecione exatamente UM objeto para transformar.",
            )
            return

        graphics_item = selected_items[0]
        # Recupera o objeto de dados associado ao item gráfico
        data_object = graphics_item.data(0)  # Assume que associamos em _add_data...

        # Verifica se o objeto de dados é transformável
        if not isinstance(data_object, (Point, Line, Polygon)):
            # Tenta obter o tipo, se possível
            type_name = type(data_object).__name__ if data_object else "Nenhum"
            QMessageBox.critical(
                self,
                "Erro Interno",
                f"Item selecionado não possui dados válidos associados ({type_name}) ou tipo não suportado para transformação.",
            )
            return

        # Passa o objeto de DADOS para o controlador de transformação
        self._transformation_controller.request_transformation(data_object)

    def _handle_object_transformed(self, data_object: DataObject) -> None:
        """
        Atualiza o item gráfico correspondente após a transformação do objeto de dados.
        O `data_object` recebido já teve suas coordenadas (WC) modificadas pelo controller.
        """
        # Encontra o item gráfico na cena que corresponde a este objeto de dados
        graphics_item = self._find_graphics_item_for_object(data_object)
        if not graphics_item:
            print(
                f"Aviso: Item gráfico não encontrado para atualizar após transformação: {data_object}"
            )
            # Tenta recriar? Ou apenas logar? Por enquanto, apenas loga.
            return

        try:
            # 1. Atualiza a geometria do item gráfico com as novas coordenadas WC do data_object
            self._update_graphics_item_geometry(graphics_item, data_object)
            # 2. Reaplica o estilo (cor, etc.) caso a transformação possa afetá-lo (raro, mas seguro)
            self._apply_style_to_item(graphics_item, data_object)
            # 3. Força o redesenho do item e da cena
            graphics_item.update()
            self._scene.update()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro ao Atualizar Gráfico",
                f"Falha ao atualizar item gráfico ({type(graphics_item).__name__}) após transformação: {e}",
            )

    def _find_graphics_item_for_object(
        self, data_obj: DataObject
    ) -> Optional[QGraphicsItem]:
        """Encontra o QGraphicsItem na cena que corresponde ao DataObject fornecido."""
        if data_obj is None:
            return None
        # Itera sobre todos os itens na cena
        for item in self._scene.items():
            # Compara a identidade do objeto de dados associado ao item com o objeto alvo
            if item.data(0) is data_obj:
                return item
        return None  # Não encontrado

    def _update_graphics_item_geometry(self, item: QGraphicsItem, data: DataObject):
        """Atualiza a geometria de um QGraphicsItem com base nas coordenadas WC do DataObject."""
        if isinstance(data, Point) and isinstance(item, QGraphicsEllipseItem):
            # Ponto: Reposiciona a elipse
            size, offset = 6.0, 3.0
            item.setRect(data.x - offset, data.y - offset, size, size)
        elif isinstance(data, Line) and isinstance(item, QGraphicsLineItem):
            # Linha: Atualiza os pontos inicial e final da linha gráfica
            item.setLine(data.start.x, data.start.y, data.end.x, data.end.y)
        elif isinstance(data, Polygon) and isinstance(item, QGraphicsPolygonItem):
            # Polígono: Reconstrói o QPolygonF com os novos pontos
            polygon_qf = QPolygonF()
            for p in data.points:
                polygon_qf.append(p.to_qpointf())
            item.setPolygon(polygon_qf)
        # Adicionar mais tipos se necessário
        else:
            # Log ou erro se o tipo de item/dado não corresponder
            print(
                f"Aviso: Não foi possível atualizar geometria para item {type(item).__name__} com dados {type(data).__name__}"
            )

    def _apply_style_to_item(self, item: QGraphicsItem, data: DataObject):
        """Aplica a caneta e o pincel corretos a um QGraphicsItem baseado no DataObject."""
        # Verifica se o objeto de dados tem um atributo 'color'
        if not hasattr(data, "color"):
            return

        # Garante que a cor é válida, senão usa preto
        color = (
            data.color
            if isinstance(data.color, QColor) and data.color.isValid()
            else QColor(Qt.black)
        )

        if isinstance(data, Point) and isinstance(item, QGraphicsEllipseItem):
            item.setPen(QPen(color, 1))
            item.setBrush(QBrush(color))
        elif isinstance(data, Line) and isinstance(item, QGraphicsLineItem):
            item.setPen(QPen(color, 2))
        elif isinstance(data, Polygon) and isinstance(item, QGraphicsPolygonItem):
            pen = QPen(color, 2)
            brush = QBrush()
            if data.is_open:  # Polilinha
                pen.setStyle(Qt.DashLine)
                brush.setStyle(Qt.NoBrush)
            else:  # Polígono fechado
                pen.setStyle(Qt.SolidLine)
                brush.setStyle(Qt.SolidPattern)
                # Cria cor de preenchimento semi-transparente
                fill_color = QColor(color)
                fill_color.setAlphaF(0.35)
                brush.setColor(fill_color)
            item.setPen(pen)
            item.setBrush(brush)
        # Adicionar mais tipos se necessário

    # --- Importação/Exportação OBJ ---

    def _prompt_load_obj(self) -> None:
        """Abre diálogo para carregar um arquivo OBJ e processa os dados."""
        obj_filepath = self._io_handler.prompt_load_obj()
        if not obj_filepath:
            return

        # Confirma se deseja limpar a cena antes de carregar
        reply = QMessageBox.question(
            self,
            "Confirmar Carregamento",
            "Limpar a cena atual antes de carregar o arquivo OBJ?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,  # Adiciona Cancelar
            QMessageBox.Yes,
        )

        if reply == QMessageBox.Cancel:
            return
        elif reply == QMessageBox.Yes:
            clear_before_load = True
        else:  # QMessageBox.No
            clear_before_load = False

        # Lê as linhas do OBJ e a referência MTL
        read_result = self._io_handler.read_obj_lines(obj_filepath)
        if read_result is None:
            return  # Erro na leitura (já mostrou mensagem)
        obj_lines, mtl_filename_relative = read_result

        # Processa o arquivo MTL se existir
        material_colors: Dict[str, QColor] = {}
        mtl_warnings: List[str] = []
        if mtl_filename_relative:
            obj_dir = os.path.dirname(obj_filepath)
            mtl_filepath = os.path.normpath(
                os.path.join(obj_dir, mtl_filename_relative)
            )
            if os.path.exists(mtl_filepath):
                # Lê as cores do MTL
                material_colors, mtl_warnings = self._io_handler.read_mtl_file(
                    mtl_filepath
                )
            else:
                mtl_warnings.append(
                    f"Arquivo MTL '{mtl_filename_relative}' referenciado não encontrado em '{mtl_filepath}'. Cores padrão serão usadas."
                )

        # Analisa os dados OBJ usando o ObjectManager para criar DataObjects
        parsed_objects, obj_warnings = self._object_manager.parse_obj_data(
            obj_lines, material_colors, self._current_draw_color  # Passa cor padrão
        )

        # Se deve limpar, faz isso agora
        if clear_before_load:
            self._finish_current_drawing(commit=False)
            self._scene.clearSelection()
            items_to_remove = list(self._scene.items())
            for item in items_to_remove:
                if item.scene():
                    self._scene.removeItem(item)

        # Adiciona os objetos parseados à cena
        creation_errors = []
        if not parsed_objects and not mtl_warnings and not obj_warnings:
            QMessageBox.information(
                self,
                "Arquivo Vazio ou Sem Geometria",
                f"Nenhum objeto geométrico suportado (v, l, f, p) ou material encontrado em '{os.path.basename(obj_filepath)}' e seu MTL associado (se houver).",
            )
            if clear_before_load:
                self._reset_view()  # Reseta view mesmo se vazio
            return

        for data_obj in parsed_objects:
            try:
                # Adiciona cada objeto de dados (e seu item gráfico) à cena
                self._add_data_object_to_scene(data_obj)
            except Exception as e:
                creation_errors.append(
                    f"Erro ao criar item gráfico para {type(data_obj).__name__}: {e}"
                )

        self._scene.update()  # Atualiza a cena após adicionar tudo
        # Reseta a visualização APENAS se limpou antes
        if clear_before_load:
            self._reset_view()

        # Mostra relatório final (avisos e erros)
        all_warnings = mtl_warnings + obj_warnings + creation_errors
        if all_warnings:
            formatted_warnings = "- " + "\n- ".join(all_warnings)
            QMessageBox.warning(
                self,
                "Carregado com Avisos",
                f"Arquivo '{os.path.basename(obj_filepath)}' carregado.\n\nAvisos:\n{formatted_warnings}",
            )
        else:
            QMessageBox.information(
                self,
                "Carregamento Concluído",
                f"Arquivo OBJ '{os.path.basename(obj_filepath)}' carregado com sucesso.",
            )

    def _prompt_save_obj(self) -> None:
        """Coleta objetos da cena, gera dados OBJ/MTL e solicita local para salvar."""
        # Coleta todos os DataObjects válidos da cena atual
        scene_data_objects: List[DataObject] = []
        for item in self._scene.items():
            data = item.data(0)  # Obtém o DataObject associado
            if isinstance(data, (Point, Line, Polygon)):
                scene_data_objects.append(data)

        if not scene_data_objects:
            QMessageBox.information(
                self,
                "Nada para Salvar",
                "A cena está vazia. Não há objetos para salvar.",
            )
            return

        # Pede ao usuário o caminho BASE para salvar (ex: 'minha_cena')
        base_filepath = self._io_handler.prompt_save_obj(
            "cena"
        )  # Sugere 'cena' como base
        if not base_filepath:
            return  # Usuário cancelou

        # Define o nome do arquivo MTL baseado no nome do OBJ
        mtl_filename = os.path.basename(base_filepath) + ".mtl"

        # Gera as linhas de texto para os arquivos OBJ e MTL
        obj_lines, mtl_lines, warnings_gen = self._object_manager.generate_obj_data(
            scene_data_objects, mtl_filename
        )

        # Verifica se a geração falhou
        if obj_lines is None:
            msg = "Falha ao gerar dados OBJ para salvar."
            if warnings_gen:
                msg += "\n\nAvisos durante a geração:\n- " + "\n- ".join(warnings_gen)
            QMessageBox.critical(self, "Erro na Geração OBJ", msg)
            return

        # Escreve os arquivos OBJ e MTL no disco
        success = self._io_handler.write_obj_and_mtl(
            base_filepath,
            obj_lines,
            mtl_lines or [],  # Passa lista vazia se mtl_lines for None
        )

        # Informa o usuário sobre o resultado
        if success:
            obj_filename_saved = os.path.basename(base_filepath + ".obj")
            msg = f"Cena salva como '{obj_filename_saved}'"
            if mtl_lines:  # Se um arquivo MTL foi gerado e salvo
                mtl_filename_saved = os.path.basename(base_filepath + ".mtl")
                msg += f" e '{mtl_filename_saved}'"
            msg += "."

            if warnings_gen:
                formatted_warnings = "\n\nAvisos durante a geração:\n- " + "\n- ".join(
                    warnings_gen
                )
                QMessageBox.warning(
                    self, "Salvo com Avisos", f"{msg}{formatted_warnings}"
                )
            else:
                QMessageBox.information(self, "Salvo com Sucesso", msg)
        # Se !success, o IOHandler já mostrou a mensagem de erro crítica.

    # --- Evento de Fechamento ---

    def closeEvent(self, event: QCloseEvent) -> None:
        """Chamado quando o usuário tenta fechar a janela."""
        # Cancela qualquer operação de desenho em andamento
        self._finish_current_drawing(commit=False)
        # Poderia adicionar verificação "salvar antes de sair" aqui, se desejado.
        # Exemplo:
        # if self.is_modified(): # (Precisaria implementar uma flag de modificação)
        #     reply = QMessageBox.question(self, "Sair sem Salvar?",
        #                                  "A cena foi modificada. Deseja salvar as alterações?",
        #                                  QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        #     if reply == QMessageBox.Save:
        #         self._prompt_save_obj()
        #         # Verificar se o save foi cancelado? Se sim, event.ignore()
        #         event.accept() # Assume save OK ou falhou mas usuário quer fechar
        #     elif reply == QMessageBox.Discard:
        #         event.accept()
        #     else: # Cancel
        #         event.ignore()
        #         return
        # else:
        #     event.accept()

        super().closeEvent(event)  # Permite que o evento de fechamento continue
