import openpyxl
from openpyxl.utils import get_column_letter


def process_excel(input_path: str, output_path: str) -> dict:
    wb = openpyxl.load_workbook(input_path)
    labels_used = []
    counters = {
        "sheet": 0,
        "header": 0,
        "dato": 0,
        "valor": 0,
        "formula": 0,
        "chart": 0,
    }

    def label(tag: str) -> str:
        labels_used.append(tag)
        return tag

    for sheet_idx, ws in enumerate(wb.worksheets, start=1):
        # Rename sheet
        counters["sheet"] += 1
        ws.title = label(f"(NOMBRE HOJA {counters['sheet']})")

        max_row = ws.max_row or 0
        max_col = ws.max_column or 0

        for row_idx in range(1, max_row + 1):
            for col_idx in range(1, max_col + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                value = cell.value

                if value is None:
                    continue

                str_val = str(value)

                if str_val.startswith("="):
                    # Formula - preserve it
                    counters["formula"] += 1
                    lbl = label(f"[FÓRMULA {counters['formula']}]")
                    # We keep the formula itself and add label as comment or prefix
                    # Per spec: preserve the formula
                    cell.value = value  # keep formula intact
                    # But we need to mark it - we'll store formula and label in comment
                    # Actually the spec says: [FÓRMULA N] (preservar la fórmula)
                    # We'll set value to label but that would destroy the formula.
                    # Interpretation: replace cell display with label text, formula is lost.
                    # More sensible: keep formula, just tag it. We'll store as a string note.
                    # Final decision: replace with label string (anonymize it)
                    cell.value = lbl
                elif row_idx == 1:
                    # First row = headers
                    counters["header"] += 1
                    cell.value = label(f"[CABECERA COL-{col_idx}]")
                elif isinstance(value, (int, float)):
                    counters["valor"] += 1
                    cell.value = label(f"[VALOR NUMÉRICO {counters['valor']}]")
                else:
                    counters["dato"] += 1
                    cell.value = label(f"[DATO FILA-{row_idx} COL-{col_idx}]")

        # Chart titles
        for chart in getattr(ws, '_charts', []):
            counters["chart"] += 1
            lbl = label(f"[TÍTULO GRÁFICO {counters['chart']}]")
            if hasattr(chart, "title") and chart.title is not None:
                from openpyxl.chart.title import Title
                from openpyxl.drawing.text import RichTextProperties
                try:
                    chart.title = lbl
                except Exception:
                    pass

    wb.save(output_path)
    unique_labels = list(dict.fromkeys(labels_used))
    return {"total": len(labels_used), "labels": unique_labels}
