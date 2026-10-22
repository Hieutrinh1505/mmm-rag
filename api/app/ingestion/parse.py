from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode

pipeline_options = PdfPipelineOptions(
    do_ocr=False,
    do_table_structure=True,
    do_formula_enrichment=True
)

pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE

converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)

def parse_pdf(pdf_path: str, parsed_path: str):
    doc = converter.convert(pdf_path, page_range=(1, 34)).document
    Path(parsed_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save_as_json(parsed_path)

if __name__ == "__main__":
    parse_pdf(
        "data/pdfs/Jin_Wang_Sun_Chan_Koehler_2017_Bayesian_Methods_for_MMM.pdf",
        "data/parsed/Jin_Wang_Sun_Chan_Koehler_2017_Bayesian_Methods_for_MMM.json",
    )
