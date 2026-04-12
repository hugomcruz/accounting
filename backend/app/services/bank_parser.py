"""
Bank Statement Parser Service

Parses Portuguese bank CSV statements (CGD format) and Coverflex XLSX statements
"""

import csv
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from io import StringIO, BytesIO


class BankStatementParser:
    """Parser for Portuguese bank statements in CSV format"""
    
    @staticmethod
    def parse_cgd_csv(file_content: str) -> Dict:
        """
        Parse CGD (Caixa Geral de Depósitos) bank statement CSV
        
        Args:
            file_content: CSV file content as string
            
        Returns:
            Dictionary with parsed statement data
        """
        lines = file_content.strip().split('\n')
        
        result = {
            'account_info': {},
            'balances': {},
            'period': {},
            'transactions': []
        }
        
        # Parse header information
        for i, line in enumerate(lines[:15]):  # Header is in first ~15 lines
            line = line.strip()
            
            # Account number
            if 'Consultar saldos' in line and '=' in line:
                match = re.search(r'="(\d+)"', line)
                if match:
                    result['account_info']['account_number'] = match.group(1)
            
            # Company name
            if line.startswith('Nome empresa'):
                parts = line.split(';')
                if len(parts) > 1:
                    result['account_info']['company_name'] = parts[1].strip()
            
            # NIF
            if line.startswith('NIF'):
                parts = line.split(';')
                if len(parts) > 1:
                    result['account_info']['nif'] = parts[1].strip()
            
            # Account details
            if line.startswith('Conta') and 'EUR' in line:
                parts = line.split(';')
                if len(parts) > 1:
                    account_parts = parts[1].split(' - ')
                    if len(account_parts) >= 2:
                        result['account_info']['account_number'] = account_parts[0].strip()
                        result['account_info']['currency'] = account_parts[1].strip()
            
            # Balances
            if 'Saldo contabilístico' in line or 'Saldo contabil' in line:
                parts = line.split(';')
                if len(parts) > 1:
                    balance_str = parts[1].strip().replace('.', '').replace(',', '.').replace(' EUR', '')
                    try:
                        result['balances']['closing_balance'] = float(balance_str)
                    except ValueError:
                        pass
            
            if 'Saldo disponível' in line or 'Saldo dispon' in line:
                parts = line.split(';')
                if len(parts) > 1:
                    balance_str = parts[1].strip().replace('.', '').replace(',', '.').replace(' EUR', '')
                    try:
                        result['balances']['available_balance'] = float(balance_str)
                    except ValueError:
                        pass
            
            # Period
            if line.startswith('Intervalo de'):
                parts = line.split(';')
                if len(parts) > 1:
                    date_range = parts[1].strip()
                    # Format: "01-07-2025 a 31-07-2025"
                    date_match = re.search(r'(\d{2}-\d{2}-\d{4})\s+a\s+(\d{2}-\d{2}-\d{4})', date_range)
                    if date_match:
                        start_str, end_str = date_match.groups()
                        try:
                            result['period']['start'] = datetime.strptime(start_str, '%d-%m-%Y')
                            result['period']['end'] = datetime.strptime(end_str, '%d-%m-%Y')
                        except ValueError:
                            pass
        
        # Find transactions section (starts with "Data mov.")
        transaction_start_idx = None
        header_line = None
        for i, line in enumerate(lines):
            if line.startswith('Data mov.'):
                transaction_start_idx = i + 1
                header_line = line
                break
        
        if transaction_start_idx and header_line:
            # Detect CSV format based on header columns
            header_parts = [p.strip() for p in header_line.split(';')]
            has_origem = 'Origem' in header_parts
            has_estorno = 'Estorno' in header_parts
            
            # Parse transactions
            for line in lines[transaction_start_idx:]:
                line = line.strip()
                if not line:
                    continue
                
                parts = [p.strip() for p in line.split(';')]
                
                try:
                    # Format detection:
                    # Old format (5 cols): Data mov.;Data-valor;Descrição;Montante;Saldo
                    # New format (7 cols): Data mov.;Data valor;Origem;Descrição;Movimento;Estorno;Saldo
                    
                    if has_origem and has_estorno and len(parts) >= 7:
                        # New format with Origem and Estorno columns
                        transaction_date = datetime.strptime(parts[0], '%d-%m-%Y')
                        value_date = datetime.strptime(parts[1], '%d-%m-%Y')
                        origem = parts[2]  # Origin code (LCRT, SIBS, EXCI, etc.)
                        description = parts[3]
                        amount_str = parts[4].replace('.', '').replace(',', '.')
                        estorno = parts[5]  # Reversal indicator
                        balance_str = parts[6].replace('.', '').replace(',', '.')
                    elif len(parts) >= 5:
                        # Old format without Origem and Estorno
                        transaction_date = datetime.strptime(parts[0], '%d-%m-%Y')
                        value_date = datetime.strptime(parts[1], '%d-%m-%Y')
                        description = parts[2]
                        amount_str = parts[3].replace('.', '').replace(',', '.')
                        balance_str = parts[4].replace('.', '').replace(',', '.')
                    else:
                        continue
                    
                    amount = float(amount_str)
                    balance_after = float(balance_str)
                    
                    result['transactions'].append({
                        'transaction_date': transaction_date,
                        'value_date': value_date,
                        'description': description,
                        'amount': amount,
                        'balance_after': balance_after
                    })
                except (ValueError, IndexError) as e:
                    # Skip malformed lines
                    continue
        
        # Calculate opening balance if we have transactions
        if result['transactions'] and result['balances'].get('closing_balance'):
            # Opening balance = closing balance - sum of all transactions
            total_movement = sum(t['amount'] for t in result['transactions'])
            result['balances']['opening_balance'] = result['balances']['closing_balance'] - total_movement
        
        return result
    
    @staticmethod
    def categorize_transaction(description: str) -> str:
        """
        Automatically categorize transaction based on description
        
        Args:
            description: Transaction description
            
        Returns:
            Category string
        """
        description_lower = description.lower()
        
        # Transfer patterns
        if any(word in description_lower for word in ['trf', 'transfer', 'transferencia']):
            return 'transfer'
        
        # Purchase patterns
        if any(word in description_lower for word in ['compra', 'purchase', 'pagamento']):
            return 'purchase'
        
        # Salary/payment received
        if any(word in description_lower for word in ['salario', 'vencimento', 'ordenado']):
            return 'salary'
        
        # Taxes and fees
        if any(word in description_lower for word in ['imposto', 'tsu', 'iva', 'irs', 'seguranca social']):
            return 'tax'
        
        # Insurance
        if any(word in description_lower for word in ['seguro', 'insurance', 'generali']):
            return 'insurance'
        
        # Bank fees
        if any(word in description_lower for word in ['manut', 'comissao', 'fee']):
            return 'bank_fee'
        
        # Utilities
        if any(word in description_lower for word in ['vodafone', 'energia', 'agua', 'gas']):
            return 'utility'
        
        # Default
        return 'other'

    @staticmethod
    def parse_coverflex_xlsx(file_content: bytes) -> Dict:
        """
        Parse Coverflex XLSX bank statement export.

        Expected layout:
          Row 1: "<company_name> <nif>"
          Row 2: "Extrato de conta\\nDe DD-MM-YYYY até DD-MM-YYYY"
          Row 3: format hint (ignored)
          Row 4: "Saldo ... em YYYY-MM-DD: <opening_balance>"
          Row 5: "Saldo ... em YYYY-MM-DD: <closing_balance>"
          Row 6: column headers (Data, Tipo, Categoria, Descrição, NIF, ...)
          Row 7+: transactions
        """
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError("openpyxl is required to parse XLSX files. Install it with: pip install openpyxl")

        wb = openpyxl.load_workbook(BytesIO(file_content))
        ws = wb.active

        rows = [list(row) for row in ws.iter_rows(values_only=True)]

        result = {
            'account_info': {},
            'balances': {},
            'period': {},
            'transactions': [],
        }

        def _parse_pt_number(s: str) -> Optional[float]:
            """Convert Portuguese number format '1.700,00' → 1700.0"""
            if not s or s == '-':
                return None
            try:
                return float(str(s).replace('.', '').replace(',', '.'))
            except (ValueError, AttributeError):
                return None

        # --- Row 1: company name + NIF ---
        if rows:
            cell = str(rows[0][0] or '')
            # Last word is typically the NIF (all digits)
            parts = cell.rsplit(' ', 1)
            if len(parts) == 2 and parts[1].isdigit():
                result['account_info']['company_name'] = parts[0].strip()
                result['account_info']['nif'] = parts[1].strip()
                result['account_info']['account_number'] = parts[1].strip()  # use NIF as account id
            else:
                result['account_info']['company_name'] = cell
                result['account_info']['account_number'] = 'coverflex'

        # --- Row 2: period ---
        if len(rows) > 1:
            cell = str(rows[1][0] or '')
            date_match = re.search(r'(\d{2}-\d{2}-\d{4})\s+até\s+(\d{2}-\d{2}-\d{4})', cell)
            if date_match:
                try:
                    result['period']['start'] = datetime.strptime(date_match.group(1), '%d-%m-%Y')
                    result['period']['end'] = datetime.strptime(date_match.group(2), '%d-%m-%Y')
                except ValueError:
                    pass

        # --- Rows 3-6: balances (skip non-balance rows like format hints) ---
        for row in rows[2:6]:
            cell = str(row[0] or '')
            if 'saldo' not in cell.lower():
                continue
            bal_match = re.search(r':\s*([\d.,]+)\s*$', cell)
            if not bal_match:
                continue
            value = _parse_pt_number(bal_match.group(1))
            # The earlier date row is opening, later is closing
            if 'opening_balance' not in result['balances']:
                result['balances']['opening_balance'] = value
            else:
                result['balances']['closing_balance'] = value

        # --- Find header row ---
        header_idx = None
        for i, row in enumerate(rows):
            if row and str(row[0] or '').strip().lower() == 'data':
                header_idx = i
                break

        if header_idx is None:
            return result

        headers = [str(h or '').strip().lower() for h in rows[header_idx]]

        def _col(name: str) -> Optional[int]:
            for idx, h in enumerate(headers):
                if name in h:
                    return idx
            return None

        col_date = _col('data')
        col_tipo = _col('tipo')
        col_cat = _col('categoria')
        col_desc = _col('descrição') or _col('descricao')
        col_nif = _col('nif')
        col_valor = _col('valor')

        # --- Transactions ---
        running_balance = result['balances'].get('opening_balance') or 0.0
        for row in rows[header_idx + 1:]:
            if not row or all(v is None for v in row):
                continue
            try:
                raw_date = row[col_date] if col_date is not None else None
                raw_amount = row[col_valor] if col_valor is not None else None

                if raw_date is None or raw_amount is None:
                    continue

                # Date may be a string "YYYY-MM-DD" or a datetime object
                if isinstance(raw_date, datetime):
                    tx_date = raw_date
                else:
                    tx_date = datetime.strptime(str(raw_date).strip(), '%Y-%m-%d')

                amount = _parse_pt_number(str(raw_amount))
                if amount is None:
                    continue

                running_balance += amount

                description_parts = []
                if col_tipo is not None and row[col_tipo] and str(row[col_tipo]) != '-':
                    description_parts.append(str(row[col_tipo]))
                if col_cat is not None and row[col_cat] and str(row[col_cat]) != '-':
                    description_parts.append(str(row[col_cat]))
                if col_desc is not None and row[col_desc] and str(row[col_desc]) != '-':
                    description_parts.append(str(row[col_desc]))
                description = ' | '.join(description_parts) if description_parts else 'Coverflex transaction'

                result['transactions'].append({
                    'transaction_date': tx_date,
                    'value_date': tx_date,
                    'description': description,
                    'amount': amount,
                    'balance_after': round(running_balance, 2),
                })
            except (ValueError, IndexError, TypeError):
                continue

        return result
