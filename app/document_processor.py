"""
Document AI Processor for Project B REST API
Processes documents with Document AI and extracts structured data.
Uses same extraction logic as Project A's DocumentAIService for consistent output.
"""
from google.cloud import documentai
from google.cloud import storage
from app.config import settings
import logging
from typing import Optional, List, Any
import json

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Processes documents with Document AI and extracts form/bank data."""

    def __init__(self):
        self.project_id = settings.GCP_PROJECT_ID
        self.location = settings.DOCUMENT_AI_LOCATION
        self.client = documentai.DocumentProcessorServiceClient()

    def _get_processor_name(self, processor_type: str) -> str:
        if processor_type == "form":
            processor_id = settings.DOCUMENT_AI_FORM_PROCESSOR
        elif processor_type == "bank":
            processor_id = settings.DOCUMENT_AI_BANK_STATEMENT_PROCESSOR
        else:
            raise ValueError(f"Unknown processor type: {processor_type}")
        if not processor_id:
            raise ValueError(f"Processor ID not configured for type: {processor_type}")
        return f"projects/{self.project_id}/locations/{self.location}/processors/{processor_id}"

    def _read_file_content(self, storage_path: str) -> bytes:
        """Read file from GCS path (gs://bucket/path)."""
        storage_path = storage_path.replace("gs://", "")
        bucket_name, blob_path = storage_path.split("/", 1)
        logger.info(f"[DocumentProcessor] Reading from GCS bucket={bucket_name} blob={blob_path}")
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        content = blob.download_as_bytes()
        logger.info(f"[DocumentProcessor] Read {len(content)} bytes from GCS")
        return content

    def process_document(self, content: bytes, processor_type: str, mime_type: str = "application/pdf"):
        """Call Document AI to process document."""
        processor_name = self._get_processor_name(processor_type)
        logger.info(f"[DocumentProcessor] Calling Document AI processor={processor_name} content_size={len(content)} mime={mime_type}")
        request = documentai.ProcessRequest(
            name=processor_name,
            raw_document=documentai.RawDocument(
                content=content,
                mime_type=mime_type
            )
        )
        result = self.client.process_document(request=request)
        logger.info(f"[DocumentProcessor] Document AI returned document with {len(result.document.text) if result.document.text else 0} chars of text")
        return result.document

    def process_form(self, storage_path: str = None, content: bytes = None, mime_type: str = "application/pdf") -> dict:
        """Process application form and return extracted data."""
        if storage_path:
            content = self._read_file_content(storage_path)
        if not content:
            raise ValueError("Either storage_path or content must be provided")
        document = self.process_document(content, "form", mime_type)
        return self._extract_form_data(document)

    def process_bank_statement(self, storage_path: str = None, content: bytes = None, mime_type: str = "application/pdf") -> dict:
        """Process bank statement and return extracted data."""
        if storage_path:
            content = self._read_file_content(storage_path)
        if not content:
            raise ValueError("Either storage_path or content must be provided")
        document = self.process_document(content, "bank", mime_type)
        transactions = self._extract_transactions(document)
        daily_balances = self._extract_daily_balances(document)
        if not transactions and hasattr(document, 'text') and document.text:
            transactions = self._parse_transactions_from_text(document.text)
        return {
            "account_number": self._extract_field(document, "account_number"),
            "routing_number": self._extract_field(document, "routing_number"),
            "bank_name": self._extract_field(document, "bank_name"),
            "statement_period_start": (
                self._extract_field(document, "statement_start_date") or
                self._extract_field(document, "statement_period_start") or
                self._extract_field(document, "period_start")
            ),
            "statement_period_end": (
                self._extract_field(document, "statement_end_date") or
                self._extract_field(document, "statement_period_end") or
                self._extract_field(document, "period_end")
            ),
            "opening_balance": (
                self._extract_field(document, "starting_balance") or
                self._extract_field(document, "opening_balance") or
                self._extract_field(document, "beginning_balance")
            ),
            "closing_balance": (
                self._extract_field(document, "ending_balance") or
                self._extract_field(document, "closing_balance")
            ),
            "transactions": self._serialize_transactions(transactions),
            "daily_balances": self._serialize_balances(daily_balances)
        }

    def _serialize_transactions(self, transactions: list) -> list:
        """Convert transaction dates to ISO strings for JSON."""
        out = []
        for tx in transactions:
            t = dict(tx)
            if "date" in t and t["date"] is not None:
                d = t["date"]
                if hasattr(d, "strftime"):
                    t["date"] = d.strftime("%Y-%m-%d")
                elif not isinstance(d, str):
                    t["date"] = str(d)
            out.append(t)
        return out

    def _serialize_balances(self, balances: list) -> list:
        out = []
        for b in balances:
            t = dict(b)
            if "date" in t and t["date"] is not None:
                d = t["date"]
                if hasattr(d, "strftime"):
                    t["date"] = d.strftime("%Y-%m-%d")
                elif not isinstance(d, str):
                    t["date"] = str(d)
            out.append(t)
        return out

    def _extract_form_data(self, document) -> dict:
        extracted = {
            "business_name": self._extract_field(document, "business_name") or self._extract_field(document, "company_name"),
            "dba": self._extract_field(document, "dba") or self._extract_field(document, "doing_business_as"),
            "ein": self._extract_field(document, "ein") or self._extract_field(document, "tax_id"),
            "owner_name": self._extract_field(document, "owner_name") or self._extract_field(document, "owner"),
            "owner_ssn": self._extract_field(document, "owner_ssn") or self._extract_field(document, "ssn"),
            "address": self._extract_field(document, "address") or self._extract_field(document, "business_address"),
            "phone": self._extract_field(document, "phone") or self._extract_field(document, "phone_number"),
            "email": self._extract_field(document, "email") or self._extract_field(document, "email_address"),
            "industry": self._extract_field(document, "industry") or self._extract_field(document, "business_type"),
            "naics_code": self._extract_field(document, "naics_code") or self._extract_field(document, "naics"),
            "time_in_business_months": None,
            "start_date": self._extract_field(document, "start_date") or self._extract_field(document, "business_start_date"),
            "requested_amount": self._extract_field(document, "requested_amount") or self._extract_field(document, "funding_amount"),
            "business_type": self._extract_field(document, "business_type") or self._extract_field(document, "entity_type")
        }
        if extracted.get("start_date"):
            try:
                from datetime import datetime
                start_date_str = extracted["start_date"].strip()
                date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y", "%d-%m-%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y"]
                start_date = None
                for fmt in date_formats:
                    try:
                        start_date = datetime.strptime(start_date_str, fmt)
                        break
                    except ValueError:
                        continue
                if start_date:
                    months = int((datetime.now() - start_date).days / 30.44)
                    extracted["time_in_business_months"] = months
            except Exception as e:
                logger.warning(f"Error calculating TIB: {e}")
        if not extracted.get("time_in_business_months"):
            tib = self._extract_field(document, "time_in_business") or self._extract_field(document, "time_in_business_months") or self._extract_field(document, "tib")
            if tib:
                import re
                numbers = re.findall(r'\d+\.?\d*', tib)
                if numbers:
                    val = float(numbers[0])
                    if "year" in tib.lower():
                        val *= 12
                    extracted["time_in_business_months"] = int(val)
        return extracted

    def _extract_field(self, document, field_name: str) -> str:
        if not document:
            return ""
        if hasattr(document, 'form_fields') and document.form_fields:
            if field_name in document.form_fields:
                fv = document.form_fields[field_name]
                if hasattr(fv, 'text_anchor') and fv.text_anchor:
                    return self._extract_text_from_anchor(document, fv.text_anchor)
                if hasattr(fv, 'value') and hasattr(fv.value, 'text_content'):
                    return fv.value.text_content
                if hasattr(fv, 'value'):
                    return str(fv.value)
            fn = field_name.lower()
            for k, v in document.form_fields.items():
                if k.lower() == fn:
                    if hasattr(v, 'text_anchor') and v.text_anchor:
                        return self._extract_text_from_anchor(document, v.text_anchor)
                    if hasattr(v, 'value') and hasattr(v.value, 'text_content'):
                        return v.value.text_content
                    if hasattr(v, 'value'):
                        return str(v.value)
        if hasattr(document, 'entities') and document.entities:
            for e in document.entities:
                if hasattr(e, 'type_') and (e.type_ == field_name or e.type_.lower() == field_name.lower()):
                    if hasattr(e, 'mention_text') and e.mention_text:
                        return e.mention_text
                    if hasattr(e, 'text_anchor') and e.text_anchor:
                        t = self._extract_text_from_anchor(document, e.text_anchor)
                        if t:
                            return t
        return ""

    def _extract_text_from_anchor(self, document, text_anchor) -> str:
        if hasattr(text_anchor, 'content') and text_anchor.content:
            return text_anchor.content
        if hasattr(text_anchor, 'text_segments') and text_anchor.text_segments and hasattr(document, 'text'):
            parts = []
            for seg in text_anchor.text_segments:
                if hasattr(seg, 'start_index') and hasattr(seg, 'end_index'):
                    try:
                        s = int(seg.start_index) if hasattr(seg.start_index, '__int__') else seg.start_index
                        e = int(seg.end_index) if hasattr(seg.end_index, '__int__') else seg.end_index
                        parts.append(document.text[s:e])
                    except (ValueError, TypeError, IndexError):
                        pass
            return " ".join(parts)
        return ""

    def _infer_table_section(self, header_cells: list) -> Optional[str]:
        if not header_cells:
            return None
        h = " ".join(header_cells)
        if "deposit" in h and ("addition" in h or "additions" in h):
            return "DEPOSITS_AND_ADDITIONS"
        if "electronic" in h and "withdrawal" in h:
            return "ELECTRONIC_WITHDRAWALS"
        if "checks paid" in h or "check paid" in h:
            return "CHECKS_PAID"
        if ("atm" in h or "debit card" in h) and "withdrawal" in h:
            return "ATM_DEBIT_WITHDRAWALS"
        if "fee" in h:
            return "FEES"
        return None

    def _extract_transactions(self, document) -> list:
        transactions = []
        if not document or not hasattr(document, 'pages') or not document.pages:
            return transactions
        for page in document.pages:
            if not hasattr(page, 'tables') or not page.tables:
                continue
            for table in page.tables:
                header_cells = []
                if hasattr(table, 'header_rows') and table.header_rows:
                    for hr in table.header_rows:
                        for c in hr.cells:
                            if hasattr(c, 'layout') and hasattr(c.layout, 'text_anchor'):
                                header_cells.append(c.layout.text_anchor.content.lower())
                section = self._infer_table_section(header_cells)
                date_col = desc_col = amount_col = type_col = None
                for i, h in enumerate(header_cells):
                    if any(w in h for w in ['date', 'transaction date', 'posted date']):
                        date_col = i
                    elif any(w in h for w in ['description', 'memo', 'details']):
                        desc_col = i
                    elif any(w in h for w in ['amount', 'debit', 'credit', 'withdrawal', 'deposit']):
                        amount_col = i
                    elif any(w in h for w in ['type', 'transaction type']):
                        type_col = i
                if hasattr(table, 'body_rows') and table.body_rows:
                    for row in table.body_rows:
                        if hasattr(row, 'cells') and row.cells:
                            cells = []
                            for c in row.cells:
                                cells.append(c.layout.text_anchor.content.strip() if hasattr(c, 'layout') and hasattr(c.layout, 'text_anchor') else "")
                            tx = {}
                            if date_col is not None and date_col < len(cells):
                                tx["date"] = cells[date_col]
                            if desc_col is not None and desc_col < len(cells):
                                tx["description"] = cells[desc_col]
                            if amount_col is not None and amount_col < len(cells):
                                try:
                                    amt = float(cells[amount_col].replace('$', '').replace(',', '').strip())
                                    tx["amount"] = abs(amt)
                                    if type_col is not None and type_col < len(cells):
                                        tx["type"] = "CREDIT" if "credit" in cells[type_col].lower() or "deposit" in cells[type_col].lower() else "DEBIT"
                                    else:
                                        tx["type"] = "CREDIT" if amt >= 0 else "DEBIT"
                                    tx["section"] = section or ("DEPOSITS_AND_ADDITIONS" if amt >= 0 else "WITHDRAWALS")
                                except ValueError:
                                    pass
                            if tx and "amount" in tx:
                                transactions.append(tx)
        logger.info(f"Extracted {len(transactions)} transactions")
        return transactions

    def _extract_daily_balances(self, document) -> list:
        balances = []
        if not document or not hasattr(document, 'entities') or not document.entities:
            return balances
        for e in document.entities:
            t = e.type_ if hasattr(e, 'type_') else ""
            if "balance" not in t.lower() and "daily" not in t.lower():
                continue
            b = {}
            if hasattr(e, 'mention_text'):
                b["description"] = e.mention_text
            if hasattr(e, 'properties'):
                for p in e.properties:
                    pt = p.type_ if hasattr(p, 'type_') else ""
                    pv = p.mention_text if hasattr(p, 'mention_text') else ""
                    if "date" in pt.lower():
                        b["date"] = pv
                    elif "balance" in pt.lower() or "amount" in pt.lower():
                        try:
                            b["balance"] = float(pv.replace('$', '').replace(',', '').strip())
                        except ValueError:
                            pass
            if b and "balance" in b:
                balances.append(b)
        if not balances and hasattr(document, 'pages') and document.pages:
            for page in document.pages:
                if hasattr(page, 'tables') and page.tables:
                    for table in page.tables:
                        txt = ""
                        if hasattr(table, 'header_rows') and table.header_rows:
                            for hr in table.header_rows:
                                for c in hr.cells:
                                    if hasattr(c, 'layout') and hasattr(c.layout, 'text_anchor'):
                                        txt += c.layout.text_anchor.content.lower() + " "
                        if "balance" in txt or "ending" in txt:
                            if hasattr(table, 'body_rows') and table.body_rows:
                                for row in table.body_rows:
                                    if hasattr(row, 'cells') and len(row.cells) >= 2:
                                        try:
                                            cs = [c.layout.text_anchor.content.strip() for c in row.cells if hasattr(c, 'layout') and hasattr(c.layout, 'text_anchor')]
                                            if len(cs) >= 2:
                                                b = {"date": cs[0], "balance": float(cs[1].replace('$', '').replace(',', '').strip())}
                                                balances.append(b)
                                        except (ValueError, IndexError):
                                            pass
        return balances

    def _parse_transactions_from_text(self, text: str) -> list:
        import re
        from datetime import datetime
        txs = []
        if not text:
            return txs
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if len(line) < 5:
                continue
            dm = re.search(r'\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?', line)
            ams = re.findall(r'\$?([-]?[\d,]+\.?\d*)', line)
            if dm and ams:
                try:
                    valid = [a for a in ams if 10 <= abs(float(a.replace(',', ''))) <= 10_000_000]
                except (ValueError, TypeError):
                    valid = []
                if not valid:
                    continue
                try:
                    amt_str = max(valid, key=lambda x: abs(float(x.replace(',', ''))))
                    amt = abs(float(amt_str.replace(',', '')))
                    desc = line[dm.end():line.rfind(amt_str)].strip() if line.rfind(amt_str) > dm.end() else ""
                    tx_type = "CREDIT" if "deposit" in desc.lower() or "credit" in desc.lower() else "DEBIT"
                    date_str = dm.group(0)
                    for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m/%d']:
                        try:
                            d = datetime.strptime(date_str, fmt)
                            if '%Y' not in fmt and '%y' not in fmt:
                                d = d.replace(year=datetime.now().year)
                            txs.append({"date": d, "description": desc[:200], "amount": amt, "type": tx_type})
                            break
                        except ValueError:
                            continue
                except (ValueError, TypeError):
                    pass
        return txs
