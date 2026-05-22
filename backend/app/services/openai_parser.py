"""
OpenAI GPT-4o vision-based invoice parser.

Extracts structured invoice data from uploaded files (PDF or image).
When ATCUD/QR data is available it is passed as context so the model
can focus on filling in the human-readable fields (supplier name, line
items, etc.) rather than re-deriving the authoritative fiscal numbers.
"""

import base64
import io
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


_EXTRACTION_PROMPT = """You are an expert at reading Portuguese invoices (faturas / faturas-recibo / notas de crédito).

Extract the following fields from the invoice shown in the image and return them as a single valid JSON object.
Use null for any field that is not visible or cannot be determined.

Fields to extract:
{{
  "nome_emitente":           "full name of the issuing company (string)",
  "nif_emitente":            "issuer NIF – 9 digits, no spaces (string)",
  "nome_adquirente":         "full name of the buying company or person (string)",
  "nif_adquirente":          "buyer NIF – 9 digits (string)",
  "identificacao_documento": "invoice number / document ID (string)",
  "tipo_documento":          "document type code: FT=Fatura, FR=Fatura-Recibo, FS=Fatura Simplificada, NC=Nota de Crédito, ND=Nota de Débito (string)",
  "data_documento":          "invoice date in YYYY-MM-DD format (string)",
  "atcud":                   "ATCUD code if visible, format XXXXXXXX-NNNNN (string)",
  "total_documento":         "grand total amount including taxes (number)",
  "total_impostos":          "total IVA / tax amount (number)",
  "subtotal":                "subtotal before tax (number)",
  "tax_rate":                "primary VAT/IVA rate as a percentage number e.g. 23.0 (number)",
  "currency":                "ISO currency code, default EUR (string)",
  "notes":                   "any relevant notes, payment terms, or IBAN visible on the invoice (string)"
}}

<additional_context>
{context}
</additional_context>

Return ONLY the raw JSON object – no markdown fences, no explanation."""


# Fields where QR/ATCUD data is authoritative and must not be overridden by AI.
_QR_PRIORITY_FIELDS = frozenset({
    'nif_emitente', 'nif_adquirente', 'pais_adquirente', 'tipo_documento',
    'estado_documento', 'data_documento', 'identificacao_documento', 'atcud',
    'espaco_fiscal', 'base_incidencia_iva', 'total_iva', 'total_impostos',
    'total_documento', 'hash', 'certificado', 'subtotal',
})


class OpenAIInvoiceParser:
    """Uses OpenAI GPT-4o vision to extract invoice details."""

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _encode_file(file_path: str) -> Optional[Tuple[str, str]]:
        """
        Return (base64_data, media_type) for *file_path*.

        PDFs are converted to a PNG of the first page so the vision API
        can process them.  Returns None on failure.
        """
        ext = Path(file_path).suffix.lower()

        if ext == '.pdf':
            try:
                from pdf2image import convert_from_path  # already in requirements
                images = convert_from_path(file_path, dpi=200, first_page=1, last_page=1)
                if not images:
                    logger.warning("pdf2image returned no pages for %s", file_path)
                    return None
                buf = io.BytesIO()
                images[0].save(buf, format='PNG')
                buf.seek(0)
                return base64.b64encode(buf.read()).decode('utf-8'), 'image/png'
            except Exception as exc:
                logger.error("PDF→image conversion failed for %s: %s", file_path, exc)
                return None

        media_type_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
        }
        media_type = media_type_map.get(ext, 'image/jpeg')
        try:
            with open(file_path, 'rb') as fh:
                return base64.b64encode(fh.read()).decode('utf-8'), media_type
        except OSError as exc:
            logger.error("Cannot read file %s: %s", file_path, exc)
            return None

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def parse(
        file_path: str,
        qr_data: Optional[Dict] = None,
        api_key: str = '',
    ) -> Optional[Dict]:
        """
        Extract invoice fields from *file_path* using OpenAI GPT-4o vision.

        Parameters
        ----------
        file_path:
            Absolute path to the invoice file (PDF, PNG, JPG, JPEG).
        qr_data:
            Pre-parsed QR / ATCUD data for this invoice.  When provided
            it is included in the prompt as context.
        api_key:
            OpenAI API key.  If empty the method returns None immediately.

        Returns
        -------
        dict with extracted fields, or None on failure / no API key.
        """
        if not api_key:
            logger.debug("OPENAI_API_KEY not configured – skipping AI extraction")
            return None

        try:
            from openai import OpenAI
        except ImportError:
            logger.warning("openai package not installed – skipping AI extraction")
            return None

        encoded = OpenAIInvoiceParser._encode_file(file_path)
        if encoded is None:
            logger.warning("Could not encode file for AI parsing: %s", file_path)
            return None

        image_b64, media_type = encoded

        if qr_data:
            context = (
                "The following data was already parsed from the ATCUD/QR code embedded in "
                "this invoice – treat it as authoritative for fiscal fields:\n"
                + json.dumps(qr_data, ensure_ascii=False, indent=2)
            )
        else:
            context = "No ATCUD/QR code was detected in this invoice."

        prompt = _EXTRACTION_PROMPT.format(context=context)

        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_b64}",
                                    "detail": "high",
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                max_tokens=1000,
                temperature=0,
            )
        except Exception as exc:
            logger.error("OpenAI API call failed: %s", exc)
            return None

        raw = response.choices[0].message.content.strip()

        # Strip optional markdown code fences (``` or ```json … ```)
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1]
            if raw.endswith('```'):
                raw = raw[: raw.rfind('```')]
            raw = raw.strip()

        try:
            extracted: Dict = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("OpenAI returned non-JSON content (%s): %r", exc, raw[:200])
            return None

        logger.info(
            "OpenAI extracted fields: %s",
            [k for k, v in extracted.items() if v is not None],
        )
        return extracted

    @staticmethod
    def merge(ai_data: Optional[Dict], qr_data: Optional[Dict]) -> Dict:
        """
        Merge AI-extracted data with QR/ATCUD data.

        QR fields are authoritative for all fiscal/tax values.
        AI fills in human-readable fields (supplier name, buyer name, etc.)
        and any gaps not covered by the QR code.
        """
        merged: Dict = {}

        # Start with AI data (lower priority)
        if ai_data:
            merged.update({k: v for k, v in ai_data.items() if v is not None})

        # Overlay QR priority fields unconditionally, add remaining QR fields
        # only where not already set
        if qr_data:
            for key, value in qr_data.items():
                if value is None:
                    continue
                if key in _QR_PRIORITY_FIELDS:
                    merged[key] = value       # QR always wins for fiscal fields
                elif key not in merged:
                    merged[key] = value       # fill gaps with QR data

        return merged
