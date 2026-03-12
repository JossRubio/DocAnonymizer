from pptx import Presentation
from pptx.util import Pt
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
import copy


def _replace_text_in_frame(tf, new_text: str):
    """Replace all text in a text frame with new_text, preserving formatting of first run."""
    paragraphs = tf.paragraphs
    if not paragraphs:
        return
    # Keep first paragraph, clear others
    first_para = paragraphs[0]
    for para in paragraphs[1:]:
        p_elem = para._p
        p_elem.getparent().remove(p_elem)

    runs = first_para.runs
    if runs:
        runs[0].text = new_text
        for run in runs[1:]:
            run.text = ""
    else:
        first_para.add_run().text = new_text


def _process_shape(shape, slide_num, counters, labels_used):
    def label(tag):
        labels_used.append(tag)
        return tag

    shape_type = shape.shape_type

    # Tables
    if shape.has_table:
        for r_idx, row in enumerate(shape.table.rows):
            for c_idx, cell in enumerate(row.cells):
                if cell.text.strip():
                    lbl = label(f"[CELDA TABLA DIAP-{slide_num} FILA-{r_idx+1} COL-{c_idx+1}]")
                    _replace_text_in_frame(cell.text_frame, lbl)
        return

    if not shape.has_text_frame:
        return

    tf = shape.text_frame
    text = tf.text.strip()
    if not text:
        return

    ph = shape.placeholder_format if shape.is_placeholder else None

    if ph is not None:
        ph_type = ph.type
        ph_idx = ph.idx
        from pptx.util import Emu
        from pptx.enum.text import PP_ALIGN

        # idx 0 = title, idx 1 = body/subtitle
        if ph_idx == 0:
            counters["slide_title"] += 1
            lbl = label(f"[TÍTULO DIAPOSITIVA {slide_num}]")
        elif ph_idx == 1:
            # Could be subtitle (slide 1) or body
            counters["body"] += 1
            lbl = label(f"[SUBTÍTULO DIAPOSITIVA {slide_num}]")
        else:
            counters["body"] += 1
            lbl = label(f"[TEXTO CUERPO {counters['body']}]")
    else:
        # Non-placeholder text box or shape
        # Check if it looks like a footer
        name_lower = shape.name.lower()
        if "footer" in name_lower or "pie" in name_lower:
            lbl = label(f"[PIE DIAPOSITIVA]")
        else:
            counters["shape"] += 1
            lbl = label(f"[ETIQUETA FORMA {counters['shape']}]")

    _replace_text_in_frame(tf, lbl)


def process_pptx(input_path: str, output_path: str) -> dict:
    prs = Presentation(input_path)
    labels_used = []
    counters = {
        "slide_title": 0,
        "body": 0,
        "shape": 0,
        "smartart": 0,
        "note": 0,
    }

    for slide_num, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            _process_shape(shape, slide_num, counters, labels_used)

        # Presenter notes
        if slide.has_notes_slide:
            notes_tf = slide.notes_slide.notes_text_frame
            if notes_tf and notes_tf.text.strip():
                counters["note"] += 1
                lbl = f"[NOTA PRESENTADOR DIAP-{slide_num}]"
                labels_used.append(lbl)
                _replace_text_in_frame(notes_tf, lbl)

    prs.save(output_path)
    unique_labels = list(dict.fromkeys(labels_used))
    return {"total": len(labels_used), "labels": unique_labels}
