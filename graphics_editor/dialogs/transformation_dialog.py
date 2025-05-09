"""
Módulo que implementa o diálogo de transformações geométricas 2D.

Este módulo contém:
- TransformationDialog: Diálogo para selecionar e parametrizar transformações 2D
  (translação, escala, rotação)
"""

# graphics_editor/dialogs/transformation_dialog.py
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QComboBox,
    QGroupBox,
    QDoubleSpinBox,
    QWidget,
)
from PyQt5.QtCore import Qt, QLocale
from typing import Optional, Dict, Any


class TransformationDialog(QDialog):
    """
    Diálogo para selecionar e parametrizar transformações geométricas 2D.
    
    Este diálogo permite:
    - Selecionar o tipo de transformação (translação, escala, rotação)
    - Configurar os parâmetros específicos de cada transformação
    - Validar os parâmetros antes de aplicar
    - Suporta transformações relativas a diferentes pontos de referência
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Inicializa o diálogo de transformações.
        
        Args:
            parent: Widget pai do diálogo
        """
        super().__init__(parent)
        self.setWindowTitle("Aplicar Transformação 2D")
        self._parameters: Optional[Dict[str, Any]] = (
            None  # Armazena parâmetros validados
        )
        self._setup_ui()
        self._update_parameter_fields()  # Mostra campos iniciais corretos

    def _setup_ui(self) -> None:
        """
        Configura a interface do diálogo.
        
        Cria e organiza os widgets:
        - ComboBox para seleção do tipo de transformação
        - Campos de parâmetros específicos para cada tipo
        - Botões de ação (Aplicar/Cancelar)
        """
        main_layout = QVBoxLayout(self)
        locale = QLocale()  # Para formatar spinboxes

        # --- Seleção do Tipo ---
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Tipo:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(
            [
                "Translação",
                "Escala (rel. ao Centro)",
                "Rotação (rel. à Origem)",
                "Rotação (rel. ao Centro)",
                "Rotação (rel. a Ponto)",
            ]
        )
        self.type_combo.currentIndexChanged.connect(self._update_parameter_fields)
        type_layout.addWidget(self.type_combo)
        main_layout.addLayout(type_layout)

        # --- Parâmetros (Grupos que são mostrados/ocultos) ---

        # Translação (dx, dy)
        self.translation_group = QGroupBox("Parâmetros de Translação")
        trans_layout = QVBoxLayout()
        self.dx_input = self._create_spinbox(
            trans_layout, locale, "Deslocamento X (dx):", -99999, 99999, 0.0, 1.0
        )
        self.dy_input = self._create_spinbox(
            trans_layout, locale, "Deslocamento Y (dy):", -99999, 99999, 0.0, 1.0
        )
        self.translation_group.setLayout(trans_layout)
        main_layout.addWidget(self.translation_group)

        # Escala (sx, sy)
        self.scaling_group = QGroupBox("Parâmetros de Escala")
        scale_layout = QVBoxLayout()
        # Allow negative for mirroring, but near-zero is handled by transformation matrix func
        self.sx_input = self._create_spinbox(
            scale_layout, locale, "Fator X (sx):", -100.0, 100.0, 1.0, 0.1, 3
        )
        self.sy_input = self._create_spinbox(
            scale_layout, locale, "Fator Y (sy):", -100.0, 100.0, 1.0, 0.1, 3
        )
        scale_layout.addWidget(
            QLabel(
                "<small><i>Valores negativos espelham. Próximo de zero pode colapsar o objeto.</i></small>"
            )
        )
        self.scaling_group.setLayout(scale_layout)
        main_layout.addWidget(self.scaling_group)

        # Rotação (ângulo) - Usado por 3 tipos
        self.rotation_group = QGroupBox("Parâmetros de Rotação")
        rot_layout = QVBoxLayout()
        self.angle_input = self._create_spinbox(
            rot_layout, locale, "Ângulo (graus):", -36000, 36000, 0.0, 5.0, 2
        )
        rot_layout.addWidget(QLabel("<small><i>Positivo: Anti-horário</i></small>"))
        self.rotation_group.setLayout(rot_layout)
        main_layout.addWidget(self.rotation_group)

        # Ponto Arbitrário (px, py) - Usado por "Rotação (rel. Ponto)"
        self.arbitrary_point_group = QGroupBox("Ponto de Rotação")
        arb_layout = QVBoxLayout()
        self.px_input = self._create_spinbox(
            arb_layout, locale, "Coord. X (px):", -99999, 99999, 0.0, 1.0
        )
        self.py_input = self._create_spinbox(
            arb_layout, locale, "Coord. Y (py):", -99999, 99999, 0.0, 1.0
        )
        self.arbitrary_point_group.setLayout(arb_layout)
        main_layout.addWidget(self.arbitrary_point_group)

        # --- Botões ---
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Aplicar")
        ok_btn.setDefault(True)
        cancel_btn = QPushButton("Cancelar")
        ok_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

    def _create_spinbox(
        self,
        layout: QVBoxLayout,
        locale: QLocale,
        label_text: str,
        min_val: float,
        max_val: float,
        default_val: float = 0.0,
        step: float = 0.1,
        decimals: int = 2,
    ) -> QDoubleSpinBox:
        """
        Cria um par QLabel/QDoubleSpinBox para entrada numérica.
        
        Args:
            layout: Layout pai para adicionar os widgets
            locale: Configuração regional para formatação
            label_text: Texto do label
            min_val: Valor mínimo permitido
            max_val: Valor máximo permitido
            default_val: Valor inicial
            step: Incremento/decremento ao usar setas
            decimals: Número de casas decimais
            
        Returns:
            QDoubleSpinBox: Campo de entrada criado
        """
        h_layout = QHBoxLayout()
        label = QLabel(label_text)
        spinbox = QDoubleSpinBox()
        spinbox.setLocale(locale)  # Define locale para formatação
        spinbox.setRange(min_val, max_val)
        spinbox.setSingleStep(step)
        spinbox.setDecimals(decimals)
        spinbox.setValue(default_val)
        spinbox.setMinimumWidth(100)
        spinbox.setAlignment(Qt.AlignRight)  # Align input to the right
        spinbox.setFocusPolicy(Qt.StrongFocus)  # Melhora usabilidade
        # spinbox.setGroupSeparatorShown(True) # Optional: show group separator

        h_layout.addWidget(label)
        h_layout.addStretch()
        h_layout.addWidget(spinbox)
        layout.addLayout(h_layout)
        return spinbox

    def _update_parameter_fields(self) -> None:
        """
        Atualiza a visibilidade dos campos de parâmetros.
        
        Mostra/oculta os grupos de parâmetros de acordo com o tipo
        de transformação selecionado no ComboBox.
        """
        selected_type = self.type_combo.currentText()
        is_translation = selected_type == "Translação"
        is_scaling = "Escala" in selected_type
        is_rotation = "Rotação" in selected_type
        is_arbitrary_point = selected_type == "Rotação (rel. a Ponto)"

        self.translation_group.setVisible(is_translation)
        self.scaling_group.setVisible(is_scaling)
        self.rotation_group.setVisible(is_rotation)
        self.arbitrary_point_group.setVisible(is_arbitrary_point)

        # Adjust dialog size to fit visible widgets
        self.adjustSize()

    def _on_accept(self) -> None:
        """
        Valida e armazena os parâmetros ao clicar OK/Aplicar.
        
        Coleta os valores dos campos visíveis e os armazena em um dicionário
        com o tipo de transformação e seus parâmetros específicos.
        
        Raises:
            ValueError: Se o tipo de transformação for desconhecido
        """
        selected_type = self.type_combo.currentText()
        params: Dict[str, Any] = {}
        epsilon = 1e-9  # Tolerance for near-zero checks (primarily for scale)

        try:
            if selected_type == "Translação":
                params["type"] = "translate"
                params["dx"] = self.dx_input.value()
                params["dy"] = self.dy_input.value()
                # Allow zero translation, it might be intentional
            elif selected_type == "Escala (rel. ao Centro)":
                params["type"] = "scale_center"
                sx = self.sx_input.value()
                sy = self.sy_input.value()
                # Check for near-zero scale factors which cause collapse
                if abs(sx) < epsilon or abs(sy) < epsilon:
                    # Let the transformation function handle this by returning identity, but warn user
                    QMessageBox.warning(
                        self,
                        "Aviso de Escala",
                        f"Fator de escala X ({sx:.3f}) ou Y ({sy:.3f}) está muito próximo de zero. "
                        "A transformação de escala pode não ter efeito visual ou colapsar o objeto.",
                    )
                params["sx"] = sx
                params["sy"] = sy
            elif selected_type == "Rotação (rel. à Origem)":
                params["type"] = "rotate_origin"
                params["angle"] = self.angle_input.value()
                # Allow zero rotation
            elif selected_type == "Rotação (rel. ao Centro)":
                params["type"] = "rotate_center"
                params["angle"] = self.angle_input.value()
            elif selected_type == "Rotação (rel. a Ponto)":
                params["type"] = "rotate_arbitrary"
                params["angle"] = self.angle_input.value()
                params["px"] = self.px_input.value()
                params["py"] = self.py_input.value()
            else:
                # Should not happen if combo box is correctly populated
                raise ValueError(
                    f"Tipo de transformação desconhecido: '{selected_type}'"
                )

            self._parameters = params
            self.accept()  # Fecha com status OK

        except (
            ValueError
        ) as e:  # Catch potential value errors during .value() although unlikely with QDoubleSpinBox
            QMessageBox.warning(self, "Erro de Valor", str(e))
            self._parameters = None
        except Exception as e:  # Catch unexpected errors
            QMessageBox.critical(self, "Erro Inesperado", f"Ocorreu um erro: {e}")
            self._parameters = None

    def get_transformation_parameters(self) -> Optional[Dict[str, Any]]:
        """
        Obtém os parâmetros da transformação validados.
        
        Returns:
            Dicionário com os parâmetros da transformação ou None se cancelado
        """
        return self._parameters if self.result() == QDialog.Accepted else None
