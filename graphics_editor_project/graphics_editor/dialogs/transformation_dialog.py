# graphics_editor/dialogs/transformation_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QMessageBox, QComboBox, QGroupBox, QDoubleSpinBox,
                             QWidget)
from PyQt5.QtGui import QDoubleValidator # Usado para QLineEdit, mas QDoubleSpinBox tem o seu próprio
from PyQt5.QtCore import Qt
from typing import Optional, Dict, Any

class TransformationDialog(QDialog):
    """
    Diálogo modal para permitir ao usuário selecionar o tipo de transformação 2D
    (Translação, Escala, Rotação) e inserir os parâmetros necessários.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Aplicar Transformação 2D")
        self.parameters: Optional[Dict[str, Any]] = None # Armazena os parâmetros validados
        self._setup_ui()
        self._update_parameter_fields() # Garante que apenas os campos relevantes são mostrados inicialmente

    def _setup_ui(self) -> None:
        """Configura a interface do usuário do diálogo."""
        main_layout = QVBoxLayout(self)

        # --- Seleção do Tipo de Transformação ---
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Tipo de Transformação:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Translação",           # Mover dx, dy
            "Escala (rel. Centro)", # Escalar sx, sy em torno do centro do objeto
            "Rotação (rel. Origem)",# Rotacionar em torno de (0,0)
            "Rotação (rel. Centro)",# Rotacionar em torno do centro do objeto
            "Rotação (rel. Ponto)"  # Rotacionar em torno de um ponto (px, py)
        ])
        # Conecta a mudança de seleção à atualização dos campos visíveis
        self.type_combo.currentIndexChanged.connect(self._update_parameter_fields)
        type_layout.addWidget(self.type_combo)
        main_layout.addLayout(type_layout)

        # --- GroupBoxes para Parâmetros (um para cada tipo/conjunto) ---
        # Usar QDoubleSpinBox é geralmente melhor para entrada numérica que QLineEdit + QValidator

        # Parâmetros de Translação (dx, dy)
        self.translation_group = QGroupBox("Parâmetros de Translação")
        trans_layout = QVBoxLayout()
        self.dx_input = self._create_spinbox(trans_layout, "Deslocamento X (dx):", -9999.99, 9999.99)
        self.dy_input = self._create_spinbox(trans_layout, "Deslocamento Y (dy):", -9999.99, 9999.99)
        self.translation_group.setLayout(trans_layout)
        main_layout.addWidget(self.translation_group)

        # Parâmetros de Escala (sx, sy)
        self.scaling_group = QGroupBox("Parâmetros de Escala")
        scale_layout = QVBoxLayout()
        # Escala geralmente é positiva, mas permite negativa para espelhamento. Mínimo pequeno > 0.
        self.sx_input = self._create_spinbox(scale_layout, "Fator X (sx):", -100.0, 100.0, default_val=1.0, step=0.1)
        self.sy_input = self._create_spinbox(scale_layout, "Fator Y (sy):", -100.0, 100.0, default_val=1.0, step=0.1)
        self.scaling_group.setLayout(scale_layout)
        main_layout.addWidget(self.scaling_group)

        # Parâmetros de Rotação (ângulo) - Usado por 3 tipos de rotação
        self.rotation_group = QGroupBox("Parâmetros de Rotação")
        rot_layout = QVBoxLayout()
        self.angle_input = self._create_spinbox(rot_layout, "Ângulo (graus):", -3600.0, 3600.0, default_val=0.0, step=5.0)
        self.rotation_group.setLayout(rot_layout)
        main_layout.addWidget(self.rotation_group)

        # Ponto de Rotação Arbitrário (px, py) - Usado apenas por "Rotação (rel. Ponto)"
        self.arbitrary_point_group = QGroupBox("Ponto de Rotação")
        arb_layout = QVBoxLayout()
        self.px_input = self._create_spinbox(arb_layout, "Coord. X do Ponto (px):", -9999.99, 9999.99)
        self.py_input = self._create_spinbox(arb_layout, "Coord. Y do Ponto (py):", -9999.99, 9999.99)
        self.arbitrary_point_group.setLayout(arb_layout)
        main_layout.addWidget(self.arbitrary_point_group)

        # --- Botões OK/Cancelar ---
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Aplicar")
        cancel_btn = QPushButton("Cancelar")
        ok_btn.clicked.connect(self._on_accept)    # Valida e aceita
        cancel_btn.clicked.connect(self.reject) # Rejeita (fecha) o diálogo
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

    def _create_spinbox(self, layout: QVBoxLayout, label_text: str,
                        min_val: float, max_val: float,
                        default_val: float = 0.0, step: float = 0.1, decimals: int = 2) -> QDoubleSpinBox:
        """
        Cria um layout horizontal com um QLabel e um QDoubleSpinBox e o adiciona
        ao layout vertical fornecido.

        Args:
            layout: O QVBoxLayout onde adicionar o novo QHBoxLayout.
            label_text: Texto do QLabel.
            min_val: Valor mínimo do spinbox.
            max_val: Valor máximo do spinbox.
            default_val: Valor inicial do spinbox.
            step: Incremento/decremento por clique nas setas.
            decimals: Número de casas decimais a serem exibidas.

        Returns:
            A instância QDoubleSpinBox criada.
        """
        h_layout = QHBoxLayout()
        label = QLabel(label_text)
        spinbox = QDoubleSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setSingleStep(step)
        spinbox.setDecimals(decimals)
        spinbox.setValue(default_val)
        # Define um tamanho mínimo razoável para o spinbox
        spinbox.setMinimumWidth(100)
        h_layout.addWidget(label)
        h_layout.addWidget(spinbox)
        layout.addLayout(h_layout)
        return spinbox

    def _update_parameter_fields(self) -> None:
        """Mostra ou oculta os QGroupBoxes de parâmetros com base no tipo selecionado."""
        selected_type = self.type_combo.currentText()

        # Define a visibilidade de cada grupo
        self.translation_group.setVisible(selected_type == "Translação")
        self.scaling_group.setVisible(selected_type == "Escala (rel. Centro)")
        # O grupo de rotação é visível para todos os tipos de rotação
        self.rotation_group.setVisible("Rotação" in selected_type)
        # O grupo de ponto arbitrário só é visível para esse tipo específico
        self.arbitrary_point_group.setVisible(selected_type == "Rotação (rel. Ponto)")

        # Ajusta o tamanho do diálogo para acomodar os campos visíveis
        self.adjustSize()

    def _on_accept(self) -> None:
        """Chamado quando o botão OK/Aplicar é clicado. Valida e armazena os parâmetros."""
        selected_type = self.type_combo.currentText()
        params: Dict[str, Any] = {'type': ''} # Inicializa o dicionário de parâmetros

        try:
            # Coleta os valores dos spinboxes relevantes para o tipo selecionado
            if selected_type == "Translação":
                params['type'] = 'translate'
                params['dx'] = self.dx_input.value()
                params['dy'] = self.dy_input.value()
            elif selected_type == "Escala (rel. Centro)":
                params['type'] = 'scale_center'
                sx = self.sx_input.value()
                sy = self.sy_input.value()
                # Validação específica para escala: não pode ser zero
                if abs(sx) < 1e-6 or abs(sy) < 1e-6:
                     raise ValueError("Fatores de escala (sx, sy) não podem ser zero.")
                params['sx'] = sx
                params['sy'] = sy
            elif selected_type == "Rotação (rel. Origem)":
                params['type'] = 'rotate_origin'
                params['angle'] = self.angle_input.value()
            elif selected_type == "Rotação (rel. Centro)":
                params['type'] = 'rotate_center'
                params['angle'] = self.angle_input.value()
            elif selected_type == "Rotação (rel. Ponto)":
                params['type'] = 'rotate_arbitrary'
                params['angle'] = self.angle_input.value()
                params['px'] = self.px_input.value()
                params['py'] = self.py_input.value()
            else:
                 # Segurança: caso um tipo inválido seja adicionado futuramente
                 raise ValueError(f"Tipo de transformação selecionado ('{selected_type}') é desconhecido.")

            # Armazena os parâmetros validados e aceita o diálogo
            self.parameters = params
            self.accept() # Fecha o diálogo com status QDialog.Accepted

        except ValueError as e:
            # Exibe mensagem de erro se a validação falhar
            QMessageBox.warning(self, "Entrada Inválida", str(e))
            self.parameters = None # Garante que parâmetros inválidos não sejam retornados

    def get_transformation_parameters(self) -> Optional[Dict[str, Any]]:
        """
        Retorna o dicionário de parâmetros de transformação validados após o
        diálogo ter sido aceito. Retorna None se o diálogo foi cancelado ou
        se a validação falhou no momento de aceitar.
        """
        return self.parameters
