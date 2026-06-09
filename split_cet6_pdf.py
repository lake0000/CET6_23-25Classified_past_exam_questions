from __future__ import annotations

import re
from pathlib import Path

import fitz


SRC = next(Path(".").glob("*.pdf"))
OUT = Path("切分结果")


TOPIC_DIRS = {
    "listening": "听力",
    "cloze": "选词填空",
    "matching": "长篇阅读（段落匹配）",
    "careful": "仔细阅读",
    "writing_translation": "翻译作文",
}


EXAMS = [
    ("2023年3月_第一套", 1, 9, "text_full"),
    ("2023年3月_第二套", 10, 10, "text_wt_only"),
    ("2023年3月_第三套", 11, 11, "text_wt_only"),
    ("2023年6月_第一套", 12, 19, "scan_full8"),
    ("2023年6月_第二套", 20, 27, "scan_full8"),
    ("2023年6月_第三套", 28, 33, "scan_no_listening6"),
    ("2023年12月_第一套", 34, 42, "text_full"),
    ("2023年12月_第二套", 43, 51, "text_full"),
    ("2023年12月_第三套", 52, 57, "text_no_listening6"),
    ("2024年6月_第一套", 58, 66, "scan_full9"),
    ("2024年6月_第二套", 67, 75, "scan_full9"),
    ("2024年6月_第三套", 76, 80, "scan_no_listening5"),
    ("2024年12月_第一套", 82, 89, "text_full8"),
    ("2024年12月_第二套", 90, 97, "text_full8"),
    ("2024年12月_第三套", 98, 103, "text_no_listening6"),
    ("2025年6月_第一套", 104, 112, "text_full"),
    ("2025年6月_第二套", 113, 121, "text_full"),
    ("2025年6月_第三套", 122, 127, "text_no_listening6"),
]


def rect(page: fitz.Page, x0: float, y0: float, x1: float, y1: float) -> fitz.Rect:
    w, h = page.rect.width, page.rect.height
    return fitz.Rect(max(0, x0), max(0, y0), min(w, x1), min(h, y1))


def clip_rel(page: fitz.Page, y0: float, y1: float, x0: float = 0.07, x1: float = 0.93) -> fitz.Rect:
    w, h = page.rect.width, page.rect.height
    return fitz.Rect(w * x0, h * y0, w * x1, h * y1)


def add_clip(out_doc: fitz.Document, src_doc: fitz.Document, page_no_1based: int, clip: fitz.Rect) -> None:
    if clip.height < 12 or clip.width < 12:
        return
    new_page = out_doc.new_page(width=clip.width, height=clip.height)
    new_page.show_pdf_page(new_page.rect, src_doc, page_no_1based - 1, clip=clip)


def first_y(page: fitz.Page, needle: str, default: float | None = None) -> float | None:
    hits = page.search_for(needle)
    if not hits:
        return default
    return min(r.y0 for r in hits)


def after_last_y(page: fitz.Page, needle: str, default: float) -> float:
    hits = page.search_for(needle)
    if not hits:
        return default
    return max(r.y1 for r in hits) + 10


def text_full_clips(doc: fitz.Document, start: int, end: int, full8: bool = False) -> dict[str, list[tuple[int, fitz.Rect]]]:
    pages = [doc.load_page(i - 1) for i in range(start, end + 1)]
    last = end
    p1 = pages[0]
    p3 = pages[2]
    p4 = pages[3]
    p6 = pages[5]
    plast = pages[-1]

    part2 = first_y(p1, "Part II", p1.rect.height * 0.27) - 8
    q1 = first_y(p1, "Questions 1 to 4", part2 + 95) - 8
    part3 = first_y(p3, "Part III", p3.rect.height * 0.38) - 8
    sec_b = first_y(p4, "Section B", p4.rect.height * 0.27) - 8
    sec_c = first_y(p6, "Section C", p6.rect.height * 0.56) - 8
    passage_one = first_y(p6, "Passage One", sec_c + 65) - 6
    part4 = first_y(plast, "Part IV", plast.rect.height * 0.36) - 8
    cloze_body = after_last_y(p3, "more than once.", part3 + 80)
    matching_body = after_last_y(p4, "Answer Sheet 2.", sec_b + 80)

    content_x0, content_x1 = 45, p1.rect.width - 35
    top, bottom = 50, p1.rect.height - 45

    clips: dict[str, list[tuple[int, fitz.Rect]]] = {
        "writing_translation": [(start, rect(p1, content_x0, 70, content_x1, part2))],
        "listening": [
            (start, rect(p1, content_x0, q1, content_x1, bottom)),
            (start + 1, rect(pages[1], content_x0, top, content_x1, bottom)),
            (start + 2, rect(p3, content_x0, top, content_x1, part3)),
        ],
        "cloze": [
            (start + 2, rect(p3, content_x0, cloze_body, content_x1, bottom)),
            (start + 3, rect(p4, content_x0, top, content_x1, sec_b)),
        ],
        "matching": [
            (start + 3, rect(p4, content_x0, matching_body, content_x1, bottom)),
            (start + 4, rect(pages[4], content_x0, top, content_x1, bottom)),
            (start + 5, rect(p6, content_x0, top, content_x1, sec_c)),
        ],
        "careful": [
            (start + 5, rect(p6, content_x0, passage_one, content_x1, bottom)),
        ],
    }
    for pno in range(start + 6, last):
        clips["careful"].append((pno, rect(doc.load_page(pno - 1), content_x0, top, content_x1, bottom)))
    clips["careful"].append((last, rect(plast, content_x0, top, content_x1, part4)))
    clips["writing_translation"].append((last, rect(plast, content_x0, part4, content_x1, bottom)))

    if full8:
        # Same layout compressed into eight physical pages: the formula above still
        # works because section headings are read from actual page coordinates.
        pass
    return clips


def text_wt_only_clips(doc: fitz.Document, start: int) -> dict[str, list[tuple[int, fitz.Rect]]]:
    page = doc.load_page(start - 1)
    part4 = first_y(page, "Part IV", page.rect.height * 0.45) - 8
    return {"writing_translation": [(start, rect(page, 45, 70, page.rect.width - 35, page.rect.height - 45))]}


def text_no_listening6_clips(doc: fitz.Document, start: int, end: int) -> dict[str, list[tuple[int, fitz.Rect]]]:
    pages = [doc.load_page(i - 1) for i in range(start, end + 1)]
    p1, p2, p4, plast = pages[0], pages[1], pages[3], pages[-1]
    part3 = first_y(p1, "Part III", p1.rect.height * 0.28) - 8
    sec_b = first_y(p2, "Section B", p2.rect.height * 0.10) - 8
    sec_c = first_y(p4, "Section C", p4.rect.height * 0.55) - 8
    passage_one = first_y(p4, "Passage One", sec_c + 65) - 6
    part4 = first_y(plast, "Part IV", plast.rect.height * 0.70) - 8
    cloze_body = after_last_y(p1, "more than once.", part3 + 80)
    matching_body = after_last_y(p2, "Answer Sheet 2.", sec_b + 80)
    x0, x1 = 45, p1.rect.width - 35
    top, bottom = 50, p1.rect.height - 45
    clips = {
        "writing_translation": [(start, rect(p1, x0, 70, x1, part3))],
        "cloze": [
            (start, rect(p1, x0, cloze_body, x1, bottom)),
            (start + 1, rect(p2, x0, top, x1, sec_b)),
        ],
        "matching": [
            (start + 1, rect(p2, x0, matching_body, x1, bottom)),
            (start + 2, rect(pages[2], x0, top, x1, bottom)),
            (start + 3, rect(p4, x0, top, x1, sec_c)),
        ],
        "careful": [(start + 3, rect(p4, x0, passage_one, x1, bottom))],
    }
    for pno in range(start + 4, end):
        clips["careful"].append((pno, rect(doc.load_page(pno - 1), x0, top, x1, bottom)))
    clips["careful"].append((end, rect(plast, x0, top, x1, part4)))
    clips["writing_translation"].append((end, rect(plast, x0, part4, x1, bottom)))
    return clips


SCAN_FULL9 = {
    "writing_translation": [(0, 0.10, 0.30), (8, 0.33, 0.78)],
    "listening": [(0, 0.43, 0.92), (1, 0.08, 0.92), (2, 0.08, 0.56)],
    "cloze": [(2, 0.70, 0.92), (3, 0.08, 0.47)],
    "matching": [(3, 0.57, 0.92), (4, 0.08, 0.92), (5, 0.08, 0.60)],
    "careful": [(5, 0.66, 0.92), (6, 0.08, 0.92), (7, 0.08, 0.92), (8, 0.08, 0.33)],
}

SCAN_FULL8 = {
    "writing_translation": [(0, 0.08, 0.27), (7, 0.55, 0.88)],
    "listening": [(0, 0.40, 0.92), (1, 0.08, 0.92), (2, 0.08, 0.40)],
    "cloze": [(2, 0.54, 0.92), (3, 0.08, 0.28)],
    "matching": [(3, 0.38, 0.92), (4, 0.08, 0.92), (5, 0.08, 0.45)],
    "careful": [(5, 0.53, 0.92), (6, 0.08, 0.92), (7, 0.08, 0.55)],
}

SCAN_NO_LISTENING6 = {
    "writing_translation": [(0, 0.08, 0.28), (5, 0.62, 0.88)],
    "cloze": [(0, 0.42, 0.92), (1, 0.08, 0.28)],
    "matching": [(1, 0.38, 0.92), (2, 0.08, 0.92), (3, 0.08, 0.40)],
    "careful": [(3, 0.50, 0.92), (4, 0.08, 0.92), (5, 0.08, 0.62)],
}

SCAN_NO_LISTENING5 = {
    "writing_translation": [(0, 0.10, 0.32), (4, 0.65, 0.88)],
    "cloze": [(0, 0.50, 0.92)],
    "matching": [(1, 0.18, 0.92), (2, 0.08, 0.45)],
    "careful": [(2, 0.55, 0.92), (3, 0.08, 0.92), (4, 0.08, 0.65)],
}


def scan_clips(doc: fitz.Document, start: int, spec: dict[str, list[tuple[int, float, float]]]) -> dict[str, list[tuple[int, fitz.Rect]]]:
    clips: dict[str, list[tuple[int, fitz.Rect]]] = {}
    for topic, entries in spec.items():
        clips[topic] = []
        for offset, y0, y1 in entries:
            pno = start + offset
            page = doc.load_page(pno - 1)
            clips[topic].append((pno, clip_rel(page, y0, y1)))
    return clips


def build() -> None:
    doc = fitz.open(SRC)
    OUT.mkdir(exist_ok=True)
    for name in TOPIC_DIRS.values():
        (OUT / name).mkdir(exist_ok=True)

    for exam_name, start, end, kind in EXAMS:
        if kind == "text_full":
            clips = text_full_clips(doc, start, end)
        elif kind == "text_full8":
            clips = text_full_clips(doc, start, end, full8=True)
        elif kind == "text_wt_only":
            clips = text_wt_only_clips(doc, start)
        elif kind == "text_no_listening6":
            clips = text_no_listening6_clips(doc, start, end)
        elif kind == "scan_full9":
            clips = scan_clips(doc, start, SCAN_FULL9)
        elif kind == "scan_full8":
            clips = scan_clips(doc, start, SCAN_FULL8)
        elif kind == "scan_no_listening6":
            clips = scan_clips(doc, start, SCAN_NO_LISTENING6)
        elif kind == "scan_no_listening5":
            clips = scan_clips(doc, start, SCAN_NO_LISTENING5)
        else:
            raise ValueError(kind)

        for topic, topic_clips in clips.items():
            out_doc = fitz.open()
            for pno, clip in topic_clips:
                add_clip(out_doc, doc, pno, clip)
            if out_doc.page_count:
                filename = f"{exam_name}_{TOPIC_DIRS[topic]}.pdf"
                out_path = OUT / TOPIC_DIRS[topic] / filename
                if out_path.exists():
                    out_path.unlink()
                out_doc.save(out_path, deflate=True, garbage=4)
            out_doc.close()

    doc.close()


if __name__ == "__main__":
    build()
