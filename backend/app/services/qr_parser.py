from PIL import Image
from pyzbar.pyzbar import decode
import cv2
import numpy as np
from typing import Optional, Dict, Tuple, List
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available - OCR fallback disabled")

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logger.warning("pdf2image not available - PDF QR extraction disabled")


class PortugueseQRCodeParser:
    """
    Parser for Portuguese AT (Autoridade Tributária) invoice QR codes.
    
    The QR code format follows the structure:
    A:NIF*B:NIF*C:PAÍS*D:TIPO_DOC*E:ESTADO*F:DATA*G:ID_DOC*H:ATCUD*I1:PAÍS*...
    """
    
    @staticmethod
    def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[Image.Image]:
        """Convert PDF pages to images for QR code detection"""
        if not PDF2IMAGE_AVAILABLE:
            logger.warning("pdf2image not available - cannot process PDF")
            return []
        
        try:
            logger.info(f"Converting PDF to images at {dpi} DPI...")
            images = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=3)  # Only first 3 pages
            logger.info(f"Converted {len(images)} pages from PDF")
            return images
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}", exc_info=True)
            return []
    
    @staticmethod
    def extract_qr_from_pil_image(img: Image.Image) -> Optional[str]:
        """Extract QR code from a PIL Image object with advanced preprocessing"""
        try:
            # Convert PIL to OpenCV format
            img_array = np.array(img)
            if len(img_array.shape) == 2:  # Grayscale
                original_cv = img_array
            elif img_array.shape[2] == 4:  # RGBA
                original_cv = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
            else:  # RGB
                original_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            if original_cv is None:
                logger.error("Failed to load image with OpenCV")
                return None
            
            # Try multiple preprocessing strategies with increasing aggressiveness
            preprocessing_strategies = [
                # Strategy 1: Original image
                ("Original PIL", lambda: img, None),
                
                # Strategy 2: RGB conversion
                ("RGB Conversion", lambda: img.convert('RGB'), None),
                
                # Strategy 3: Grayscale
                ("Grayscale", None, lambda img: cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)),
                
                # Strategy 4: High contrast grayscale
                ("High Contrast", None, lambda img: cv2.convertScaleAbs(
                    cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), alpha=2.0, beta=0
                )),
                
                # Strategy 5: Adaptive threshold
                ("Adaptive Threshold", None, lambda img: cv2.adaptiveThreshold(
                    cv2.cvtColor(img, cv2.COLOR_BGR2GRAY),
                    255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
                )),
                
                # Strategy 6: Otsu's thresholding
                ("Otsu Threshold", None, lambda img: cv2.threshold(
                    cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 0, 255, 
                    cv2.THRESH_BINARY + cv2.THRESH_OTSU
                )[1]),
                
                # Strategy 7: Inverted Otsu's thresholding (for white QR on dark background)
                ("Inverted Otsu", None, lambda img: cv2.bitwise_not(cv2.threshold(
                    cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 0, 255, 
                    cv2.THRESH_BINARY + cv2.THRESH_OTSU
                )[1])),
                
                # Strategy 8: Morphological operations
                ("Morphological", None, lambda img: cv2.morphologyEx(
                    cv2.threshold(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 127, 255, cv2.THRESH_BINARY)[1],
                    cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)
                )),
                
                # Strategy 9: Denoising + threshold
                ("Denoised", None, lambda img: cv2.threshold(
                    cv2.fastNlMeansDenoising(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), None, 10, 7, 21),
                    127, 255, cv2.THRESH_BINARY
                )[1]),
                
                # Strategy 10: Sharpen + threshold
                ("Sharpened", None, lambda img: cv2.threshold(
                    cv2.filter2D(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), -1, 
                                 np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])),
                    127, 255, cv2.THRESH_BINARY
                )[1]),
            ]
            
            # Try each strategy with multiple scales
            scales = [1.0, 1.5, 2.0, 0.5]  # Try different image sizes
            
            for scale in scales:
                # Resize if needed
                if scale != 1.0:
                    width = int(original_cv.shape[1] * scale)
                    height = int(original_cv.shape[0] * scale)
                    scaled_cv = cv2.resize(original_cv, (width, height), interpolation=cv2.INTER_CUBIC)
                    scaled_pil = img.resize((width, height), Image.Resampling.LANCZOS)
                else:
                    scaled_cv = original_cv
                    scaled_pil = img
                
                for strategy_name, pil_func, cv_func in preprocessing_strategies:
                    try:
                        if pil_func:
                            # PIL-based processing
                            processed_img = pil_func()
                        elif cv_func:
                            # OpenCV-based processing
                            processed_cv = cv_func(scaled_cv)
                            processed_img = Image.fromarray(processed_cv)
                        else:
                            continue
                        
                        # Try to decode
                        decoded_objects = decode(processed_img)
                        
                        if decoded_objects:
                            qr_data = decoded_objects[0].data.decode('utf-8')
                            logger.info(f"✓ QR found with {strategy_name} at scale {scale}x")
                            return qr_data
                    
                    except Exception as e:
                        logger.debug(f"Strategy {strategy_name} at {scale}x failed: {e}")
                        continue
            
            logger.warning("No QR code found after all preprocessing attempts")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting QR code: {e}", exc_info=True)
            return None
    
    @staticmethod
    def extract_qr_from_image(image_path: str) -> Optional[str]:
        """
        Extract QR code from image file or PDF.
        Handles both image files (PNG, JPG, JPEG) and PDFs.
        """
        path = Path(image_path)
        file_extension = path.suffix.lower()
        
        # Handle PDF files
        if file_extension == '.pdf':
            if not PDF2IMAGE_AVAILABLE:
                logger.error("PDF file provided but pdf2image not available")
                return None
            
            logger.info(f"Processing PDF file: {path.name}")
            images = PortugueseQRCodeParser.pdf_to_images(str(image_path), dpi=300)
            
            if not images:
                logger.warning("No images extracted from PDF")
                return None
            
            # Try to find QR code in each page
            for page_num, img in enumerate(images, 1):
                logger.info(f"Scanning page {page_num}/{len(images)} for QR code...")
                qr_data = PortugueseQRCodeParser.extract_qr_from_pil_image(img)
                if qr_data:
                    logger.info(f"✓ QR code found on page {page_num}")
                    return qr_data
            
            logger.warning(f"No QR code found in any of the {len(images)} pages")
            return None
        
        # Handle image files
        else:
            try:
                img = Image.open(image_path)
                logger.info(f"Processing image file: {path.name}")
                return PortugueseQRCodeParser.extract_qr_from_pil_image(img)
            except Exception as e:
                logger.error(f"Error opening image file: {e}", exc_info=True)
                return None
    
    @staticmethod
    def extract_text_with_ocr(image_path: str) -> Optional[str]:
        """Extract text from image or PDF using OCR as fallback when QR detection fails"""
        if not TESSERACT_AVAILABLE:
            logger.warning("OCR requested but pytesseract not available")
            return None
        
        try:
            path = Path(image_path)
            file_extension = path.suffix.lower()
            
            # Handle PDF files
            if file_extension == '.pdf':
                if not PDF2IMAGE_AVAILABLE:
                    logger.error("PDF file provided but pdf2image not available")
                    return None
                
                logger.info("Extracting text from PDF with OCR...")
                images = PortugueseQRCodeParser.pdf_to_images(str(image_path), dpi=200)  # Lower DPI for OCR
                
                all_text = []
                for page_num, img in enumerate(images, 1):
                    img_array = np.array(img)
                    if len(img_array.shape) == 3:
                        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                    else:
                        gray = img_array
                    
                    # Try multiple preprocessing for OCR
                    preprocessed_images = [
                        gray,
                        cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
                        cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2),
                    ]
                    
                    for processed in preprocessed_images:
                        text = pytesseract.image_to_string(processed, lang='por+eng')
                        if text.strip():
                            all_text.append(f"--- Page {page_num} ---\n{text}")
                            break  # Use first successful OCR result for this page
                
                return "\n".join(all_text) if all_text else None
            
            # Handle image files
            else:
                img = cv2.imread(str(image_path))
                if img is None:
                    return None
                
                # Preprocess for better OCR
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # Try multiple preprocessing for OCR
                preprocessed_images = [
                    gray,
                    cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
                    cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2),
                ]
                
                all_text = []
                for processed in preprocessed_images:
                    text = pytesseract.image_to_string(processed, lang='por+eng')
                    if text.strip():
                        all_text.append(text)
                
                return "\n".join(all_text) if all_text else None
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return None
    
    @staticmethod
    def extract_invoice_data_from_ocr(ocr_text: str) -> Optional[Dict]:
        """
        Extract invoice data from OCR text using pattern matching.
        Looks for common Portuguese invoice fields.
        """
        if not ocr_text:
            return None
        
        data = {}
        
        try:
            # NIF patterns (9 digits)
            nif_pattern = r'NIF[:\s]*(\d{9})'
            nifs = re.findall(nif_pattern, ocr_text, re.IGNORECASE)
            if len(nifs) >= 2:
                data['nif_emitente'] = nifs[0]
                data['nif_adquirente'] = nifs[1]
            elif len(nifs) == 1:
                data['nif_emitente'] = nifs[0]
            
            # Invoice number patterns
            invoice_patterns = [
                r'(?:Fatura|Factura|FT|Invoice)[:\s#]*([A-Z0-9\s/\-]+)',
                r'N[úu]mero[:\s]*([A-Z0-9\s/\-]+)',
                r'Doc[:\s]*([A-Z0-9\s/\-]+)',
            ]
            for pattern in invoice_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data['identificacao_documento'] = match.group(1).strip()
                    break
            
            # Date patterns
            date_patterns = [
                r'Data[:\s]*(\d{2}[-/]\d{2}[-/]\d{4})',
                r'(\d{2}[-/]\d{2}[-/]\d{4})',
                r'(\d{4}[-/]\d{2}[-/]\d{2})',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, ocr_text)
                if match:
                    date_str = match.group(1)
                    # Normalize date format to YYYY-MM-DD
                    if '-' in date_str or '/' in date_str:
                        parts = re.split(r'[-/]', date_str)
                        if len(parts) == 3:
                            if len(parts[0]) == 4:  # YYYY-MM-DD
                                data['data_documento'] = date_str
                            else:  # DD-MM-YYYY
                                data['data_documento'] = f"{parts[2]}-{parts[1]}-{parts[0]}"
                    break
            
            # Total amount patterns (Euro)
            total_patterns = [
                r'Total[:\s]*€?\s*(\d+[.,]\d{2})',
                r'Total Geral[:\s]*€?\s*(\d+[.,]\d{2})',
                r'Total c/ IVA[:\s]*€?\s*(\d+[.,]\d{2})',
                r'TOTAL[:\s]*€?\s*(\d+[.,]\d{2})',
            ]
            for pattern in total_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    amount = match.group(1).replace(',', '.')
                    data['total_documento'] = float(amount)
                    break
            
            # IVA/Tax patterns
            iva_patterns = [
                r'IVA[:\s]*€?\s*(\d+[.,]\d{2})',
                r'Imposto[:\s]*€?\s*(\d+[.,]\d{2})',
                r'Taxa[:\s]*€?\s*(\d+[.,]\d{2})',
            ]
            for pattern in iva_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    amount = match.group(1).replace(',', '.')
                    data['total_impostos'] = float(amount)
                    break
            
            # ATCUD pattern
            atcud_match = re.search(r'ATCUD[:\s]*([A-Z0-9\-]+)', ocr_text, re.IGNORECASE)
            if atcud_match:
                data['atcud'] = atcud_match.group(1)
            
            return data if len(data) >= 2 else None  # At least 2 fields required
            
        except Exception as e:
            logger.error(f"Error extracting data from OCR: {e}")
            return None
    
    @staticmethod
    def validate_atcud_qr(qr_string: str) -> bool:
        """
        Validate that the QR code is an ATCUD-compliant Portuguese fiscal document.
        
        Required fields for ATCUD:
        - A: NIF Emitente (must be present)
        - H: ATCUD code (must be present and in format XXXXXXXX-NNNN)
        
        Returns True if valid ATCUD QR, False otherwise.
        """
        if not qr_string or '*' not in qr_string:
            return False
        
        parts = qr_string.split('*')
        has_nif = False
        has_valid_atcud = False
        
        for part in parts:
            if ':' not in part:
                continue
            
            key, value = part.split(':', 1)
            
            # Check for NIF Emitente (field A)
            if key == 'A':
                # Portuguese NIF should be 9 digits
                if value.isdigit() and len(value) == 9:
                    has_nif = True
            
            # Check for ATCUD (field H)
            elif key == 'H':
                # ATCUD format: 8-character validation code + dash + sequential number
                # Example: JJSDNCJX-615771
                atcud_pattern = r'^[A-Z0-9]{8}-\d+$'
                if re.match(atcud_pattern, value):
                    has_valid_atcud = True
                    logger.info(f"Valid ATCUD format detected: {value}")
                else:
                    logger.warning(f"Invalid ATCUD format: {value}")
        
        is_valid = has_nif and has_valid_atcud
        
        if not is_valid:
            if not has_nif:
                logger.warning("QR code missing valid NIF Emitente (field A)")
            if not has_valid_atcud:
                logger.warning("QR code missing valid ATCUD (field H)")
        
        return is_valid
    
    @staticmethod
    def parse_qr_data(qr_string: str) -> Optional[Dict]:
        """
        Parse Portuguese AT QR code string into structured data.
        
        Official specification format: A:value*B:value*C:value*...
        
        Fields (according to AT specification):
        A - NIF Emitente (Issuer Tax ID) - 9 digits
        B - NIF Adquirente (Buyer Tax ID) - 9 digits or 999999990 for consumer
        C - País Adquirente (Buyer Country) - 2 chars or "Desconhecido"
        D - Tipo Documento (Document Type) - FT, FS, FR, NC, ND, etc.
        E - Estado (Status: N=Normal, T=Transmitted, A=Anulado)
        F - Data (Date YYYYMMDD)
        G - Identificação Documento (Document ID)
        H - ATCUD (Unique Document Code - format: XXXXXXXX-NNNNN)
        I1-I8 - Espaço Fiscal (Tax Region) - PT, PT-AC, PT-MA, etc.
        J1-J8 - Base Tributável por Taxa (Tax Base per rate)
        K1-K8 - Total IVA por Taxa (VAT per rate)
        L - IVA Não Dedutível (Non-deductible VAT)
        M - Imposto do Selo (Stamp Duty)
        N - Total Impostos (IVA+IEC+IS) (Total Taxes)
        O - Total do Documento com Impostos (Document Total with taxes)
        P - Retenção na Fonte (Withholding tax)
        Q - Hash (4 characters)
        R - Nº Certificado (Certificate Number)
        S - Outras Informações (Other Info)
        """
        
        if not qr_string:
            return None
        
        # Validate ATCUD format first
        if not PortugueseQRCodeParser.validate_atcud_qr(qr_string):
            logger.error("QR code validation failed - not a valid ATCUD fiscal document")
            return None
        
        try:
            data = {}
            
            # Log the full QR string for debugging
            logger.info(f"Full QR string: {qr_string}")
            
            # Split by asterisk
            parts = qr_string.split('*')
            
            logger.info(f"QR has {len(parts)} parts: {parts}")
            
            for part in parts:
                if ':' not in part:
                    continue
                
                key, value = part.split(':', 1)
                
                # Map fields according to AT specification
                if key == 'A':
                    data['nif_emitente'] = value
                elif key == 'B':
                    data['nif_adquirente'] = value
                elif key == 'C':
                    data['pais_adquirente'] = value
                elif key == 'D':
                    data['tipo_documento'] = value
                elif key == 'E':
                    data['estado_documento'] = value
                elif key == 'F':
                    # Convert YYYYMMDD to ISO format
                    if len(value) == 8 and value.isdigit():
                        data['data_documento'] = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
                    else:
                        data['data_documento'] = value
                elif key == 'G':
                    data['identificacao_documento'] = value
                elif key == 'H':
                    data['atcud'] = value
                elif key.startswith('I'):
                    # Espaço fiscal - take the first one found
                    if 'espaco_fiscal' not in data:
                        data['espaco_fiscal'] = value
                elif key.startswith('J'):
                    # Tax base amounts per rate
                    if 'base_incidencia_iva' not in data:
                        data['base_incidencia_iva'] = []
                    try:
                        data['base_incidencia_iva'].append(float(value))
                    except ValueError:
                        logger.warning(f"Invalid J value: {value}")
                elif key.startswith('K'):
                    # VAT amounts per rate
                    if 'total_iva' not in data:
                        data['total_iva'] = []
                    try:
                        data['total_iva'].append(float(value))
                    except ValueError:
                        logger.warning(f"Invalid K value: {value}")
                elif key == 'L':
                    # Non-deductible VAT
                    try:
                        data['iva_nao_dedutivel'] = float(value)
                    except ValueError:
                        logger.warning(f"Invalid L value: {value}")
                elif key == 'M':
                    # Stamp duty
                    try:
                        data['imposto_selo'] = float(value)
                    except ValueError:
                        logger.warning(f"Invalid M value: {value}")
                elif key == 'N':
                    # Total taxes (IVA + IEC + IS)
                    try:
                        data['total_impostos'] = float(value)
                    except ValueError:
                        logger.warning(f"Invalid N value: {value}")
                elif key == 'O':
                    # Total document with taxes
                    try:
                        data['total_documento'] = float(value)
                    except ValueError:
                        logger.warning(f"Invalid O value: {value}")
                elif key == 'P':
                    # Withholding tax
                    try:
                        data['retencao_fonte'] = float(value)
                    except ValueError:
                        logger.warning(f"Invalid P value: {value}")
                elif key == 'Q':
                    data['hash'] = value
                elif key == 'R':
                    data['certificado'] = value
                elif key == 'S':
                    data['outras_infos'] = value
                else:
                    logger.debug(f"Unknown QR field: {key}={value}")
            
            logger.info(f"Parsed QR data fields: {list(data.keys())}")
            
            # Calculate subtotal if not explicitly provided
            if 'base_incidencia_iva' in data and data['base_incidencia_iva']:
                data['subtotal'] = sum(data['base_incidencia_iva'])
            
            return data if data else None
            
        except Exception as e:
            logger.error(f"Error parsing QR data: {e}", exc_info=True)
            return None
    
    @staticmethod
    def extract_and_parse(image_path: str, use_ocr_fallback: bool = True) -> Tuple[Optional[Dict], str, Optional[str]]:
        """
        Extract QR code from image and parse it. If QR fails, try OCR.
        
        Returns:
            Tuple of (parsed_data, source, raw_qr_string) where:
            - source is 'qr', 'ocr', or 'none'
            - raw_qr_string is the original QR code content (None if not extracted)
        """
        # Try QR code first
        qr_string = PortugueseQRCodeParser.extract_qr_from_image(image_path)
        if qr_string:
            parsed = PortugueseQRCodeParser.parse_qr_data(qr_string)
            if parsed:
                logger.info("Successfully extracted data from QR code")
                return (parsed, 'qr', qr_string)
        
        # Fallback to OCR if enabled
        if use_ocr_fallback and TESSERACT_AVAILABLE:
            logger.info("QR detection failed, trying OCR fallback...")
            ocr_text = PortugueseQRCodeParser.extract_text_with_ocr(image_path)
            if ocr_text:
                parsed = PortugueseQRCodeParser.extract_invoice_data_from_ocr(ocr_text)
                if parsed:
                    logger.info("Successfully extracted data from OCR")
                    return (parsed, 'ocr', None)
        
        logger.warning("Failed to extract invoice data from both QR and OCR")
        return (None, 'none', None)
