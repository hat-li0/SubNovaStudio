import os
import re
from abc import ABC, abstractmethod
from app.models.subtitle import SubtitleDocument

class SubtitleParser(ABC):
    def parse(self, file_path: str) -> SubtitleDocument:
        content = self._read_file(file_path)
        doc = self.parse_text(content)
        doc.file_path = file_path
        return doc

    @abstractmethod
    def parse_text(self, content: str) -> SubtitleDocument:
        pass

    def _read_file(self, file_path: str) -> str:
        """
        Reads subtitle file with resilient multi-encoding detection and clean normalization:
        1. Checks BOM signatures (UTF-8, UTF-16 LE/BE).
        2. Tries standard modern encodings (utf-8-sig, utf-8).
        3. Tries UTF-16 (le & be) and CP1256 (Arabic Windows) / ISO-8859-6.
        4. Tries charset_normalizer / chardet heuristic detection.
        5. Tries Shift_JIS (Japanese) and CP1252.
        6. Cleans null bytes and zero-width artifacts.
        """
        with open(file_path, 'rb') as f:
            raw_bytes = f.read()

        if not raw_bytes:
            return ""

        # 1. Check explicit BOM signatures
        if raw_bytes.startswith(b'\xef\xbb\xbf'):
            text = raw_bytes[3:].decode('utf-8', errors='replace')
            return self._sanitize_content(text)
        elif raw_bytes.startswith(b'\xff\xfe'):
            text = raw_bytes[2:].decode('utf-16le', errors='replace')
            return self._sanitize_content(text)
        elif raw_bytes.startswith(b'\xfe\xff'):
            text = raw_bytes[2:].decode('utf-16be', errors='replace')
            return self._sanitize_content(text)

        # 2. Try explicit common encodings
        candidate_encodings = [
            'utf-8-sig',
            'utf-8',
            'utf-16-le',
            'utf-16-be',
            'cp1256',     # Arabic Windows
            'iso-8859-6', # Arabic ISO
            'shift_jis',  # Japanese
            'cp1252',     # Western European
        ]

        for enc in candidate_encodings:
            try:
                decoded = raw_bytes.decode(enc)
                # If decoded text contains excessive null bytes, it was decoded with wrong 8-bit codec for 16-bit data
                if decoded.count('\x00') > 2:
                    continue
                return self._sanitize_content(decoded)
            except (UnicodeDecodeError, ValueError):
                continue

        # 3. Dynamic charset detection via charset_normalizer or chardet
        try:
            import charset_normalizer
            results = charset_normalizer.from_bytes(raw_bytes)
            best = results.best()
            if best and best.encoding:
                try:
                    decoded = raw_bytes.decode(best.encoding)
                    if decoded.count('\x00') <= 2:
                        return self._sanitize_content(decoded)
                except Exception:
                    pass
        except ImportError:
            try:
                import chardet
                det = chardet.detect(raw_bytes)
                if det and det.get('encoding') and (det.get('confidence', 0) or 0) > 0.6:
                    decoded = raw_bytes.decode(det['encoding'])
                    if decoded.count('\x00') <= 2:
                        return self._sanitize_content(decoded)
            except Exception:
                pass

        # 4. Final resilient fallback
        text = raw_bytes.decode('utf-8', errors='replace')
        return self._sanitize_content(text)

    @staticmethod
    def _sanitize_content(content: str) -> str:
        """Removes null bytes and invisible unicode artifacts."""
        if not content:
            return ""
        # Strip null bytes and non-printable control chars except \t, \n, \r
        content = content.replace('\x00', '')
        # Standardize carriage returns
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        return content
