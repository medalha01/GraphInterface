# dialogs/transformation_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QMessageBox, QComboBox, QGroupBox, QDoubleSpinBox,
                             QWidget)
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtCore import Qt
from typing import Optional, Dict, Any

class TransformationDialog(QDialog):
    """Diálogo para selecionar tipo de transformação e inserir parâmetros."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Aplicar Transformação 2D")
        self.parameters: Optional[Dict[str, Any]] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        validator = QDoubleValidator(-9999.99, 9999.99, 2)

        # --- Seleção do Tipo de Transformação ---
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Tipo de Transformação:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Translação",
            "Escala (Centro)",
            "Rotação (Origem)",
            "Rotação (Centro)",
            "Rotação (Ponto Arbitrário)"
        ])
        self.type_combo.currentIndexChanged.connect(self._update_parameter_fields)
        type_layout.addWidget(self.type_combo)
        main_layout.addLayout(type_layout)

        # --- GroupBoxes de Parâmetros ---
        self.translation_group = QGroupBox("Parâmetros de Translação")
        trans_layout = QVBoxLayout()
        self.dx_input = self._create_spinbox(trans_layout, "dx:", validator)
        self.dy_input = self._create_spinbox(trans_layout, "dy:", validator)
        self.translation_group.setLayout(trans_layout)
        main_layout.addWidget(self.translation_group)

        self.scaling_group = QGroupBox("Parâmetros de Escala")
        scale_layout = QVBoxLayout()
        self.sx_input = self._create_spinbox(scale_layout, "sx:", validator, 1.0, 0.01)
        self.sy_input = self._create_spinbox(scale_layout, "sy:", validator, 1.0, 0.01)
        self.scaling_group.setLayout(scale_layout)
        main_layout.addWidget(self.scaling_group)

        self.rotation_group = QGroupBox("Parâmetros de Rotação")
        rot_layout = QVBoxLayout()
        self.angle_input = self._create_spinbox(rot_layout, "Ângulo (graus):", validator,
                                                 default_val=0.0, step=5.0,
                                                 min_val=-360.0, max_val=360.0)
        self.rotation_group.setLayout(rot_layout)
        main_layout.addWidget(self.rotation_group)

        self.arbitrary_point_group = QGroupBox("Ponto de Rotação Arbitrário")
        arb_layout = QVBoxLayout()
        self.px_input = self._create_spinbox(arb_layout, "px:", validator)
        self.py_input = self._create_spinbox(arb_layout, "py:", validator)
        self.arbitrary_point_group.setLayout(arb_layout)
        main_layout.addWidget(self.arbitrary_point_group)

        # --- Botões ---
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancelar")
        ok_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        self._update_parameter_fields()

    def _create_spinbox(self, layout: QVBoxLayout, label_text: str, validator: QDoubleValidator,
                         default_val: float = 0.0, step: float = 0.1, min_val=-9999.99, max_val=9999.99) -> QDoubleSpinBox:
        """Auxiliar para criar um rótulo e QDoubleSpinBox."""
        h_layout = QHBoxLayout()
        label = QLabel(label_text)
        spinbox = QDoubleSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setSingleStep(step)
        spinbox.setDecimals(2)
        spinbox.setValue(default_val)
        h_layout.addWidget(label)
        h_layout.addWidget(spinbox)
        layout.addLayout(h_layout)
        return spinbox

    def _update_parameter_fields(self) -> None:
        """Mostra/oculta campos de entrada de parâmetros com base no tipo de transformação selecionado."""
        selected_type = self.type_combo.currentText()

        self.translation_group.setVisible(selected_type == "Translação")
        self.scaling_group.setVisible(selected_type == "Escala (Centro)")
        self.rotation_group.setVisible("Rotação" in selected_type)
        self.arbitrary_point_group.setVisible(selected_type == "Rotação (Ponto Arbitrário)")
        self.adjustSize()

    def _on_accept(self) -> None:
        """Valida a entrada e armazena os parâmetros antes de aceitar."""
        selected_type = self.type_combo.currentText()
        params = {}
        try:
            if selected_type == "Translação":
                params = {'type': 'translate', 'dx': self.dx_input.value(), 'dy': self.dy_input.value()}
            elif selected_type == "Escala (Centro)":
                sx = self.sx_input.value()
                sy = self.sy_input.value()
                if abs(sx) < 1e-6 or abs(sy) < 1e-6:
                     raise ValueError("Fatores de escala (sx, sy) não podem ser zero.")
                params = {'type': 'scale_center', 'sx': sx, 'sy': sy}
            elif selected_type == "Rotação (Origem)":
                params = {'type': 'rotate_origin', 'angle': self.angle_input.value()}
            elif selected_type == "Rotação (Centro)":
                params = {'type': 'rotate_center', 'angle': self.angle_input.value()}
            elif selected_type == "Rotação (Ponto Arbitrário)":
                params = {
                    'type': 'rotate_arbitrary',
                    'angle': self.angle_input.value(),
                    'px': self.px_input.value(),
                    'py': self.py_input.value()
                }
            else:
                 raise ValueError("Tipo de transformação desconhecido.")

            self.parameters = params
            self.accept()

        except ValueError as e:
            QMessageBox.warning(self, "Entrada Inválida", str(e))
            self.parameters = None

    def get_transformation_parameters(self) -> Optional[Dict[str, Any]]:
        """Retorna os parâmetros validados após o diálogo ser aceito."""
        return self.parameters