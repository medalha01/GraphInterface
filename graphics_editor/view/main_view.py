# graphics_editor/view/main_view.py
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from PyQt5.QtCore import Qt, QPoint, QPointF, pyqtSignal, QRectF, QSize
from PyQt5.QtGui import (
    QMouseEvent,
    QWheelEvent,
    QPainter,
    QTransform,
    QKeyEvent,
    QCursor,
)


class GraphicsView(QGraphicsView):
    """
    View customizada para exibir a cena gráfica.
    Para 2D: suporta zoom, pan e rotação da vista 2D.
    Para 3D: encaminha eventos de mouse para navegação da câmera 3D e
             eventos de teclado para deleção.
    """

    VIEW_SCALE_MIN = 0.02  # Limite mínimo de zoom para vista 2D
    VIEW_SCALE_MAX = 50.0  # Limite máximo de zoom para vista 2D

    # Sinais para desenho e interação 2D
    scene_left_clicked = pyqtSignal(QPointF)
    scene_right_clicked = pyqtSignal(QPointF)
    scene_mouse_moved = pyqtSignal(QPointF)
    delete_requested = pyqtSignal()  # Para deleção via teclado (genérico)

    # Sinais para notificar UI sobre mudanças na vista 2D
    scale_changed = pyqtSignal()
    rotation_changed = pyqtSignal()

    # Sinais para navegação 3D
    # (prev_pos_viewport, current_pos_viewport, botoes_mouse, modificadores_teclado)
    mouse_drag_event_3d = pyqtSignal(
        QPoint, QPoint, Qt.MouseButtons, Qt.KeyboardModifiers
    )
    # (delta_roda, modificadores_teclado)
    mouse_wheel_event_3d = pyqtSignal(int, Qt.KeyboardModifiers)

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self._current_scale: float = 1.0  # Para zoom da vista 2D
        self._current_rotation: float = 0.0  # Rotação da vista 2D em graus

        self._is_panning_2d: bool = False  # Flag para pan 2D
        self._is_dragging_3d: bool = (
            False  # Flag para arrastar do mouse para navegação 3D
        )
        self._last_mouse_pos: QPoint = QPoint()  # Última posição do mouse na viewport

        self._zoom_sensitivity: float = 0.1  # Sensibilidade do zoom 2D
        self._rotation_step: float = 5.0  # Graus por passo para rotação da vista 2D

        self.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )
        self.setTransformationAnchor(
            QGraphicsView.AnchorUnderMouse
        )  # Zoom 2D centraliza no mouse
        self.setResizeAnchor(
            QGraphicsView.AnchorViewCenter
        )  # Redimensionar centraliza na vista
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.RubberBandDrag)  # Modo padrão: seleção 2D
        self.setViewportUpdateMode(
            QGraphicsView.FullViewportUpdate
        )  # Para rotação/zoom suaves
        self.setFocusPolicy(
            Qt.StrongFocus
        )  # Para receber eventos de teclado para navegação 3D (futuro) ou deleção

    # --- Getters (específicos da Vista 2D) ---
    def get_scale(self) -> float:
        return self._current_scale

    def get_rotation_angle(self) -> float:
        return self._current_rotation

    # --- Setters Controlados (específicos da Vista 2D) ---
    def set_scale(self, scale: float, center_on_mouse: bool = True):
        """Define a escala da vista 2D, com limites."""
        clamped_scale = max(self.VIEW_SCALE_MIN, min(scale, self.VIEW_SCALE_MAX))
        if abs(self._current_scale - clamped_scale) < 1e-6:
            return

        scale_factor = clamped_scale / self._current_scale
        self._current_scale = clamped_scale

        anchor = (
            QGraphicsView.AnchorUnderMouse
            if center_on_mouse
            else QGraphicsView.AnchorViewCenter
        )
        current_anchor = self.transformationAnchor()
        self.setTransformationAnchor(anchor)
        super().scale(scale_factor, scale_factor)  # Chama o scale da QGraphicsView
        self.setTransformationAnchor(current_anchor)
        self.scale_changed.emit()

    def set_rotation_angle(self, angle: float):
        """Define o ângulo de rotação da vista 2D em graus."""
        if abs(self._current_rotation - angle) < 1e-6:
            return

        delta_angle = angle - self._current_rotation
        self._current_rotation = angle

        anchor = QGraphicsView.AnchorViewCenter
        current_anchor = self.transformationAnchor()
        self.setTransformationAnchor(anchor)
        super().rotate(delta_angle)  # Chama o rotate da QGraphicsView
        self.setTransformationAnchor(current_anchor)
        self.rotation_changed.emit()

    def set_drag_mode(self, mode: QGraphicsView.DragMode):
        """Define o modo de arrasto (para 2D) e ajusta o cursor."""
        super().setDragMode(mode)
        if mode == QGraphicsView.ScrollHandDrag:
            self.setCursor(Qt.OpenHandCursor)  # Pan 2D
        elif mode == QGraphicsView.RubberBandDrag:
            self.setCursor(Qt.ArrowCursor)  # Seleção 2D
        elif mode == QGraphicsView.NoDrag:
            self.setCursor(Qt.CrossCursor)  # Desenho 2D
        else:
            self.setCursor(Qt.ArrowCursor)  # Padrão

    # --- Manipuladores de Eventos ---
    def mousePressEvent(self, event: QMouseEvent):
        self._last_mouse_pos = event.pos()  # Salva posição na viewport
        scene_pos = self.mapToScene(event.pos())  # Converte para coords da cena

        # Navegação 3D com botão do meio
        if event.button() == Qt.MiddleButton:
            self._is_dragging_3d = True
            self.setCursor(Qt.ClosedHandCursor)  # Indica arrastar 3D
            event.accept()
            return

        # Interação 2D com botão esquerdo
        if event.button() == Qt.LeftButton:
            if self.dragMode() == QGraphicsView.ScrollHandDrag:  # Pan 2D
                self._is_panning_2d = True
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
            elif self.dragMode() == QGraphicsView.NoDrag:  # Desenho 2D
                self.scene_left_clicked.emit(scene_pos)
                event.accept()
            else:  # RubberBandDrag (seleção 2D)
                self.scene_left_clicked.emit(scene_pos)  # Para iniciar seleção
                super().mousePressEvent(
                    event
                )  # Passa para QGraphicsView tratar seleção

        elif event.button() == Qt.RightButton:  # Para completar desenho 2D
            self.scene_right_clicked.emit(scene_pos)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        current_pos_viewport = event.pos()
        scene_pos = self.mapToScene(current_pos_viewport)
        self.scene_mouse_moved.emit(scene_pos)  # Sempre emite para status bar 2D

        if self._is_dragging_3d:  # Arrastando para navegação 3D
            self.mouse_drag_event_3d.emit(
                self._last_mouse_pos,
                current_pos_viewport,
                event.buttons(),
                event.modifiers(),
            )
            self._last_mouse_pos = current_pos_viewport
            event.accept()
            return

        if self._is_panning_2d:  # Pan 2D
            delta_viewport = current_pos_viewport - self._last_mouse_pos
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta_viewport.x())
            v_bar.setValue(v_bar.value() - delta_viewport.y())
            # self._last_mouse_pos já é atualizado abaixo
            event.accept()

        self._last_mouse_pos = current_pos_viewport  # Atualiza para o próximo evento
        super().mouseMoveEvent(event)  # Para seleção 2D, etc.

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_dragging_3d and event.button() == Qt.MiddleButton:
            self._is_dragging_3d = False
            self.set_drag_mode(self.dragMode())  # Restaura cursor com base no modo 2D
            event.accept()
            return

        if self._is_panning_2d and event.button() == Qt.LeftButton:  # Pan 2D
            self._is_panning_2d = False
            self.set_drag_mode(self.dragMode())  # Restaura cursor
            event.accept()

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return

        # Zoom 3D com Alt + Roda
        if event.modifiers() & Qt.AltModifier:
            self.mouse_wheel_event_3d.emit(delta, event.modifiers())
            event.accept()
        else:  # Padrão para zoom 2D
            zoom_factor = 1.0 + (self._zoom_sensitivity * (delta / 120.0))
            self.set_scale(self._current_scale * zoom_factor, center_on_mouse=True)
            event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        # Rotação da Vista 2D com Shift + Setas
        if event.modifiers() == Qt.ShiftModifier:  # Apenas Shift
            angle_delta = 0.0
            if event.key() == Qt.Key_Left:
                angle_delta = -self._rotation_step
            elif event.key() == Qt.Key_Right:
                angle_delta = self._rotation_step

            if angle_delta != 0.0:
                self.set_rotation_angle(self._current_rotation + angle_delta)
                event.accept()
                return

        # Deleção (genérico para itens selecionados)
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            self.delete_requested.emit()
            event.accept()
            return

        super().keyPressEvent(event)  # Passa para itens ou cena

    # --- Métodos de Controle (específicos da Vista 2D) ---
    def reset_view(self):
        """Reseta zoom, pan e rotação da vista 2D para o padrão."""
        old_scale = self._current_scale
        old_rotation = self._current_rotation
        self.setTransform(QTransform())  # Reseta transformação da vista 2D

        self._current_scale = 1.0
        self._current_rotation = 0.0
        self._is_panning_2d = False
        self._is_dragging_3d = False
        self.set_drag_mode(self.dragMode())

        if abs(old_scale - 1.0) > 1e-6:
            self.scale_changed.emit()
        if abs(old_rotation - 0.0) > 1e-6:
            self.rotation_changed.emit()
        self.viewport().update()
