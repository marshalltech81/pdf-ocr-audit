from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def create_pdf(path: Path, page_texts: list[str]) -> None:
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)  # noqa: SLF001

    for text in page_texts:
        page = writer.add_blank_page(width=612, height=792)
        if text:
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
                }
            )
            content = DecodedStreamObject()
            content.set_data(f"BT /F1 12 Tf 72 720 Td ({escape_pdf_text(text)}) Tj ET".encode())
            content_ref = writer._add_object(content)  # noqa: SLF001
            page[NameObject("/Contents")] = content_ref

    with path.open("wb") as handle:
        writer.write(handle)


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
