"""
Label templates for the two supported output languages.
All format-string placeholders use keyword arguments: {n}, {r}, {c}, {s}.
"""

_LABELS = {
    "es": {
        # Word
        "doc_title":       "[TÍTULO DEL DOCUMENTO]",
        "section_title":   "[TÍTULO SECCIÓN {n}]",
        "subtitle":        "[SUBTÍTULO {s}.{n}]",
        "paragraph":       "[CONTENIDO PÁRRAFO {n}]",
        "list_item":       "[ELEMENTO LISTA {n}]",
        "table_cell_word": "[CELDA TABLA FILA-{r} COL-{c}]",
        "text_box":        "[CUADRO DE TEXTO {n}]",
        "header":          "[ENCABEZADO]",
        "footer":          "[PIE DE PÁGINA]",
        # PPTX
        "slide_title":     "[TÍTULO DIAPOSITIVA {n}]",
        "slide_subtitle":  "[SUBTÍTULO DIAPOSITIVA {n}]",
        "body_text":       "[TEXTO CUERPO {n}]",
        "shape_label":     "[ETIQUETA FORMA {n}]",
        "table_cell_pptx": "[CELDA TABLA DIAP-{s} FILA-{r} COL-{c}]",
        "presenter_note":  "[NOTA PRESENTADOR DIAP-{n}]",
        "slide_footer":    "[PIE DIAPOSITIVA]",
        # Excel
        "sheet_name":      "(NOMBRE HOJA {n})",
        "header_col":      "[CABECERA COL-{n}]",
        "data_cell":       "[DATO FILA-{r} COL-{c}]",
        "numeric_value":   "[VALOR NUMÉRICO {n}]",
        "formula":         "[FÓRMULA {n}]",
        "chart_title":     "[TÍTULO GRÁFICO {n}]",
    },
    "en": {
        # Word
        "doc_title":       "[DOCUMENT TITLE]",
        "section_title":   "[SECTION TITLE {n}]",
        "subtitle":        "[SUBTITLE {s}.{n}]",
        "paragraph":       "[PARAGRAPH CONTENT {n}]",
        "list_item":       "[LIST ITEM {n}]",
        "table_cell_word": "[TABLE CELL ROW-{r} COL-{c}]",
        "text_box":        "[TEXT BOX {n}]",
        "header":          "[HEADER]",
        "footer":          "[FOOTER]",
        # PPTX
        "slide_title":     "[SLIDE TITLE {n}]",
        "slide_subtitle":  "[SLIDE SUBTITLE {n}]",
        "body_text":       "[BODY TEXT {n}]",
        "shape_label":     "[SHAPE LABEL {n}]",
        "table_cell_pptx": "[TABLE CELL SLIDE-{s} ROW-{r} COL-{c}]",
        "presenter_note":  "[PRESENTER NOTE SLIDE-{n}]",
        "slide_footer":    "[SLIDE FOOTER]",
        # Excel
        "sheet_name":      "(SHEET NAME {n})",
        "header_col":      "[HEADER COL-{n}]",
        "data_cell":       "[DATA ROW-{r} COL-{c}]",
        "numeric_value":   "[NUMERIC VALUE {n}]",
        "formula":         "[FORMULA {n}]",
        "chart_title":     "[CHART TITLE {n}]",
    },
}

SUPPORTED_LANGS = list(_LABELS.keys())


def get_labels(lang: str = "es") -> dict:
    """Return the label template dict for the given language (falls back to 'es')."""
    return _LABELS.get(lang, _LABELS["es"])
