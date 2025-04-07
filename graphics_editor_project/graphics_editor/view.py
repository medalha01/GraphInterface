# graphics_editor/view.py
from PyQt5.QtWidgets import (QGraphicsView, QFrame, QGraphicsScene, QRubberBand,
                             QWidget)
from PyQt5.QtGui import (QPainter, QBrush, QTransform, QMouseEvent, QKeyEvent,
                         QWheelEvent, QCursor) # Adicionado QCursor
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QPoint

from typing import Optional
import math # Importado para cálculos de ângulo e escala

class GraphicsView(QGraphicsView):
    """
    QGraphicsView customizado com navegação (pan/zoom), rotação da "janela"
    e emissão de eventos de interação na cena.
    """

    # Sinais emitidos com coordenadas da CENA
    scene_left_clicked = pyqtSignal(QPointF)
    scene_right_clicked = pyqtSignal(QPointF)
    scene_mouse_moved = pyqtSignal(QPointF)
    delete_requested = pyqtSignal() # Sinal para solicitar exclusão (tecla Del/Backspace)
    rotation_changed = pyqtSignal(float) # Sinal para notificar mudança de rotação
    scale_changed = pyqtSignal() # Sinal para notificar mudança de escala/zoom

    def __init__(self, scene: QGraphicsScene, parent: Optional[QWidget] = None):
        super().__init__(scene, parent)

        # --- Configuração de Navegação ---
        self._min_zoom_factor: float = 0.1  # Zoom mínimo permitido
        self._max_zoom_factor: float = 10.0 # Zoom máximo permitido
        self._zoom_increment: float = 1.15  # Fator de zoom por passo da roda do mouse
        self._pan_step: int = 30            # Pixels para mover com as setas
        self._rotation_step: float = 5.0    # Graus para rotacionar por passo (Shift+Setas)

        # --- Estado da View ---
        self._window_rotation_angle: float = 0.0 # Ângulo atual de rotação da view
        # Removido: self._is_panning_with_mouse: bool = False
        # Removido: self._last_pan_point: QPoint = QPoint()

        self._setup_view_defaults()
        self.setFocusPolicy(Qt.StrongFocus) # Necessário para receber eventos de teclado

    def _setup_view_defaults(self) -> None:
        """Aplica configurações visuais e de comportamento padrão à view."""
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        # O DragMode é controlado pelo Editor (Select/Pan/Draw), aqui definimos apenas o default inicial
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate) # Mais simples, pode ser otimizado depois

        # Âncora de transformação: crucial para rotação e zoom
        # AnchorViewCenter faz rotate() e scale() ocorrerem em torno do centro visível da view.
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter) # Mantém o centro ao redimensionar

        # Desliga as barras de rolagem padrão
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.setBackgroundBrush(QBrush(Qt.lightGray)) # Cor de fundo
        self.setFrameShape(QFrame.NoFrame) # Sem borda
        self.setMouseTracking(True) # Recebe eventos de movimento mesmo sem botão pressionado

    def set_drag_mode(self, mode: QGraphicsView.DragMode) -> None:
        """Define o modo de arrasto da view (controlado pelo Editor)."""
        # Apenas chama o método da classe base. O Editor é responsável por
        # chamar este método e ajustar o cursor se necessário.
        super().setDragMode(mode)

    def _zoom(self, factor: float) -> None:
        """Aplica zoom na view centrado no AnchorViewCenter e emite sinal."""
        current_scale = self.get_scale()

        # Limita o zoom aos fatores mínimo e máximo
        target_scale = current_scale * factor
        clamped_scale = max(self._min_zoom_factor, min(target_scale, self._max_zoom_factor))

        # Calcula o fator de escala real a ser aplicado, evitando divisão por zero
        actual_factor = clamped_scale / current_scale if abs(current_scale) > 1e-9 else 1.0

        # Aplica a escala se houver mudança significativa
        if abs(actual_factor - 1.0) > 1e-6:
            self.scale(actual_factor, actual_factor)
            self.scale_changed.emit() # EMITE O SINAL AQUI!

    def _rotate_view(self, angle_delta: float) -> None:
        """Rotaciona a view em torno do AnchorViewCenter."""
        self.rotate(angle_delta) # QGraphicsView.rotate() usa o transformationAnchor

        # Atualiza o ângulo interno rastreado e emite sinal
        current_transform = self.transform()
        current_rad = math.atan2(current_transform.m21(), current_transform.m11())
        self._window_rotation_angle = math.degrees(current_rad)

        self.rotation_changed.emit(self._window_rotation_angle)

    # --- Event Handlers ---

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Trata eventos da roda do mouse para aplicar zoom."""
        angle = event.angleDelta().y() # Delta vertical da roda
        if angle > 0:
            self._zoom(self._zoom_increment) # Zoom in
        elif angle < 0:
            self._zoom(1.0 / self._zoom_increment) # Zoom out
        event.accept() # Indica que o evento foi tratado

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Trata pressionamentos de tecla para navegação e ações."""
        key = event.key()
        modifiers = event.modifiers()

        # Rotação da View: Shift + Setas Esquerda/Direita
        if modifiers == Qt.ShiftModifier:
            if key == Qt.Key_Left:
                self._rotate_view(self._rotation_step) # Rotaciona anti-horário
                event.accept()
                return
            elif key == Qt.Key_Right:
                self._rotate_view(-self._rotation_step) # Rotaciona horário
                event.accept()
                return

        # Navegação Padrão (Sem Shift)
        elif modifiers == Qt.NoModifier:
            # Pan com Setas: translate() move a "câmera"
            if key == Qt.Key_Left:
                self.translate(self._pan_step, 0); event.accept(); return
            elif key == Qt.Key_Right:
                self.translate(-self._pan_step, 0); event.accept(); return
            elif key == Qt.Key_Up:
                self.translate(0, self._pan_step); event.accept(); return
            elif key == Qt.Key_Down:
                self.translate(0, -self._pan_step); event.accept(); return

            # Zoom com Teclas +/-
            elif key == Qt.Key_Plus or key == Qt.Key_Equal:
                self._zoom(self._zoom_increment); event.accept(); return
            elif key == Qt.Key_Minus:
                self._zoom(1.0 / self._zoom_increment); event.accept(); return

            # Deleção de Itens
            elif key == Qt.Key_Delete or key == Qt.Key_Backspace:
                self.delete_requested.emit(); event.accept(); return

        # Se nenhuma combinação foi tratada, passa para a classe base
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Trata cliques do mouse, emitindo sinais ou iniciando pan."""
        scene_pos = self.mapToScene(event.pos()) # Converte para coordenadas da cena

        if event.button() == Qt.LeftButton:
            # Se estiver no modo Pan (ScrollHandDrag), APENAS muda o cursor.
            # Deixa a classe base QGraphicsView iniciar o pan interno.
            if self.dragMode() == QGraphicsView.ScrollHandDrag:
                self.setCursor(Qt.ClosedHandCursor)
                # NÃO definimos _is_panning_with_mouse = True aqui
                # NÃO chamamos event.accept() aqui para deixar a base processar
                super().mousePressEvent(event) # DEIXA a classe base lidar com o início do pan
            # Se estiver em modo de desenho (NoDrag), emite sinal para o editor
            elif self.dragMode() == QGraphicsView.NoDrag:
                 self.scene_left_clicked.emit(scene_pos)
                 event.accept() # Aceita porque NÓS tratamos isso
            # Se estiver no modo Select (RubberBandDrag), deixa a view base tratar
            else:
                super().mousePressEvent(event) # Deixa a base lidar com seleção

        elif event.button() == Qt.RightButton:
            # Emite sinal para o editor (ex: finalizar polígono)
            self.scene_right_clicked.emit(scene_pos)
            event.accept() # Aceita porque NÓS tratamos isso

        # Passa outros botões (ex: botão do meio) para a classe base
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Trata movimento do mouse para pan ou emissão de posição."""
        scene_pos = self.mapToScene(event.pos()) # Coordenadas da cena

        # Se estiver no modo ScrollHandDrag, deixa a classe base fazer o pan.
        # NÃO precisamos mais do _is_panning_with_mouse ou do cálculo manual de translate.
        if self.dragMode() == QGraphicsView.ScrollHandDrag:
             super().mouseMoveEvent(event) # DEIXA a classe base fazer o pan
             # Não precisa de event.accept() explicitamente aqui, a base deve cuidar disso.
        # Se estiver em modo de desenho, emite a posição do mouse
        elif self.dragMode() == QGraphicsView.NoDrag:
            self.scene_mouse_moved.emit(scene_pos)
            event.accept() # Aceita porque NÓS tratamos isso
        # Outros modos (Select) são tratados pela classe base
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Trata liberação do mouse, finalizando o pan."""
        # Apenas restaura o cursor se o botão esquerdo foi solto no modo Pan.
        # A classe base QGraphicsView cuida da lógica de parada do pan.
        if event.button() == Qt.LeftButton and self.dragMode() == QGraphicsView.ScrollHandDrag:
            self.setCursor(Qt.OpenHandCursor) # Restaura cursor de pan
            super().mouseReleaseEvent(event) # DEIXA a classe base finalizar o pan
        else:
            # Passa outros eventos de release para a classe base
            super().mouseReleaseEvent(event)

    # --- Métodos de Controle da View ---

    def get_rotation_angle(self) -> float:
        """Retorna o ângulo de rotação atual da view em graus."""
        transform = self.transform()
        angle_rad = math.atan2(transform.m21(), transform.m11())
        return math.degrees(angle_rad)

    def set_rotation_angle(self, angle: float) -> None:
        """Define o ângulo de rotação da view para um valor específico."""
        current_angle = self.get_rotation_angle()
        delta = angle - current_angle
        self._rotate_view(delta)

    def get_scale(self) -> float:
        """Retorna o fator de escala atual da view (assume escala uniforme)."""
        return self.transform().m11()

    def set_scale(self, target_scale: float) -> None:
        """Define o fator de escala absoluto da view."""
        current_scale = self.get_scale()
        factor = target_scale / current_scale if abs(current_scale) > 1e-9 else 1.0
        self._zoom(factor)

    def reset_view(self) -> None:
        """Reseta zoom, rotação e posição da view para o estado inicial."""
        initial_scale_was_one = abs(self.get_scale() - 1.0) < 1e-6

        # 1. Reseta a matriz de transformação para identidade
        self.setTransform(QTransform())
        # 2. Centraliza a view na origem da cena (0, 0)
        self.centerOn(0, 0)
        # 3. Reseta o ângulo de rotação interno e emite sinal
        self._window_rotation_angle = 0.0
        self.rotation_changed.emit(0.0)
        # 4. Emite scale_changed APENAS se a escala realmente mudou ao resetar
        if not initial_scale_was_one:
             self.scale_changed.emit()
