import re
from typing import Dict, List, Optional


class ResponseParser:
    """Parses and cleans the LLM response to extract translations, stripping all prompt echoes and metadata."""

    # Common prefix noise to strip
    PREFIX_CLEANER = re.compile(
        r"^(?:(?:Original|Current Arabic|Improved Arabic|Improved|Corrected|Arabic|Revision|Refined|Result|Translation|Translated|Translated text|Target|Draft|Translator|"
        r"المنظر العربي المترجم|المنظر العربي|المترجم|المترجمة|المدقق|المراجع|تقرير التعديلات|تقرير التحسين|تقرير المراجعة|التعديلات|التصحيحات|التصحيح|"
        r"النص العربي المصقول النهائي مباشرة|النص العربي المصقول النهائي|النص المصقول النهائي|المصقول النهائي مباشرة|المصقول النهائي|النص المصقول|السطر المصقول|"
        r"الترجمة المحسنة|الترجمة المقترحة|الترجمة النهائية|الترجمة العربية|الترجمة|المسودة|النتيجة|المصححة|الصياغة الجديدة|الصياغة الفصيحة|الأصل|النص الأصلي|"
        r"النص العربي|التحسين|التعديل|ترجمة|إليك الترجمة|الترجمة هي|نص الترجمة)[\s:\-–—]*)+",
        re.IGNORECASE
    )

    @classmethod
    def clean_text_item(cls, text: str) -> str:
        """Cleans prompt echoes, formatting tokens, prefixes, and quotation marks from a translation string."""
        if not text:
            return ""

        # Remove zero-width & invisible unicode characters (preserve \u200f RLM BiDi marks)
        text = re.sub(r'[\u200b\u200c\u200d\u200e\ufeff\u202a-\u202e\u2066-\u2069]', '', text)

        # If text contains a pipe '|' separating original and translation (prompt leak echo)
        if "|" in text:
            parts = text.split("|")
            text = parts[-1].strip()

        # Remove leading/trailing formatting like **, ``, --
        text = re.sub(r"^[\*\:\s\-–—\.]+", "", text).strip()
        text = re.sub(r"\*+$", "", text).strip()

        # Check for inline markdown like **Translated Text**
        if text.startswith("**") and text.endswith("**"):
            text = text[2:-2].strip()

        if text.startswith("`") and text.endswith("`"):
            text = text.strip("`").strip()

        # Iteratively strip out common conversational and prompt prefixes inside the translation
        for _ in range(3):
            prev = text
            text = cls.PREFIX_CLEANER.sub("", text).strip()
            text = re.sub(r"^[\*\:\s\-–—\.]+", "", text).strip()
            if text == prev:
                break

        # Strip quotes if wrapped or orphan outer quote
        for q_open, q_close in (('"', '"'), ("'", "'"), ('“', '”'), ('«', '»'), ('"', '”'), ('“', '"')):
            if text.startswith(q_open) and text.endswith(q_close) and len(text) >= 2:
                text = text[len(q_open):-len(q_close)].strip()
                break
        else:
            if text.startswith(('"', "'", "“", "«")):
                text = text[1:].strip()
            if text.endswith(('"', "'", "”", "»")):
                text = text[:-1].strip()

        # Strip empty or stray brackets at beginning like [] or [ ] (common in ALLaM outputs)
        text = re.sub(r"^[\[\(]\s*[\]\)]\s*[:\-\–\—\.]*", "", text).strip()

        # Strip trailing notes or context leaks e.g. (سياق الحوار اللاحق) ... or \n### ...
        text = re.sub(r"\n\s*(?:###|\(سياق|\(Context|ملاحظة:|Note:).*$", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r"\s*\(سياق[^\)]*\)$", "", text).strip()
        text = re.sub(r"\s*\(Context[^\)]*\)$", "", text, flags=re.IGNORECASE).strip()

        if text.startswith("`") and text.endswith("`"):
            text = text.strip("`").strip()
        elif text.startswith("`") and text.count("`") % 2 == 1:
            text = text[1:].strip()
        elif text.endswith("`") and text.count("`") % 2 == 1:
            text = text[:-1].strip()

        # Strip out translation notes aggressively
        text = re.sub(r"[\(\[]?(Note|ملاحظة|ملاحظه|Translation Note)[\s:]+.*$", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*[-|–|—]\s*(Note|ملاحظة|ملاحظه)[\s:]+.*$", "", text, flags=re.IGNORECASE).strip()

        # Strip commentary, gender, or explanation notes inside parentheses (e.g. (المخاطب فتاة), (المتحدث غاضب), (تم التصحيح))
        text = re.sub(
            r"\s*[\(\[«](?:المخاطب|المتحدث|المتكلم|ملاحظة|ملاحظه|تعديل|تصحيح|توضيح|شرح|حذف|إضافة|مذكر|مؤنث|أنثى|فتاة|صبي|رجل|note|tone|speaker|context)[\s:،,-][^\)\]»]*[\)\]»]",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()
        text = re.sub(
            r"\s*[\(\[](?:المخاطب\s+(?:فتاة|ذكر|أنثى|مذكر|مؤنث)|المتحدث\s+(?:فتاة|ذكر|أنثى|مذكر|مؤنث)|تم\s+التصحيح|تم\s+التعديل|بصوت\s+عالي|بهمس)[\)\]]\s*$",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()

        return text.strip()

    def parse_response(self, raw_response: str, expected_ids: List[int]) -> Dict[int, str]:
        """Extract translations mapped by ID from raw LLM output, supporting inline and multiline ID blocks."""
        if not raw_response:
            return {}

        # 1. Strip think blocks (both closed <think>...</think> and unclosed <think>...)
        cleaned = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL)
        if "<think>" in cleaned:
            cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL)
        if "</think>" in cleaned:
            cleaned = cleaned.split("</think>")[-1]

        # 2. Strip markdown code fences
        cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\n```$", "", cleaned, flags=re.MULTILINE)

        lines = [line.strip() for line in cleaned.split("\n") if line.strip()]

        raw_parsed: List[tuple[int, str]] = []

        # Pattern 1: [1] Text or **[1]**: Text or - [1] Text or [ 001 ] Text or (1) Text
        pat_bracket = re.compile(r"^[^\w\[\(]*[\[\(]\s*(\d+)\s*[\]\)]\s*[:\-\–\—\.]*\s*(.*)$")
        # Pattern 1b: [] Text or [ ] Text (Empty brackets without digits, e.g. from ALLaM SFT)
        pat_empty_bracket = re.compile(r"^[^\w\[\(]*[\[\(]\s*[\]\)]\s*[:\-\–\—\.]*\s*(.*)$")
        # Pattern 2: 1. Text or 1: Text or 1 - Text or **1:** Text
        pat_dot = re.compile(r"^[^\w]*(\d+)[\.\:\-][\s:\-\–\—\.]*\s*(.*)$")

        i = 0
        n_expected = len(expected_ids)
        expected_set = set(expected_ids)
        expected_min = min(expected_ids) if expected_ids else 0

        IGNORE_TRIGGERS = (
            "here is", "here are", "sure,", "sure!", "translation:", "الترجمة التالية:",
            "###", "---", "(سياق)", "(context)", "(سياق الحوار", "ملاحظة:", "note:"
        )

        while i < len(lines):
            line = lines[i]
            line_lower = line.lower()
            if any(trig in line_lower for trig in IGNORE_TRIGGERS):
                i += 1
                continue

            # Ignore raw timestamp lines (e.g. '12:05:00 Scene Intro') before pat_dot matching
            if re.match(r"^\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?\b", line):
                i += 1
                continue

            match = pat_bracket.match(line) or pat_dot.match(line)
            empty_match = pat_empty_bracket.match(line) if not match else None

            if match:
                parsed_num = int(match.group(1))
                inline_text = self.clean_text_item(match.group(2))

                # Avoid false positives where pat_dot matched arbitrary numbers
                is_valid_id = (
                    parsed_num in expected_set or
                    (1 <= parsed_num <= n_expected) or
                    (parsed_num == 0 and n_expected > 0) or
                    (n_expected > 1 and expected_min <= parsed_num <= expected_min + n_expected - 1)
                )

                if not is_valid_id:
                    i += 1
                    continue

                if inline_text:
                    raw_parsed.append((parsed_num, inline_text))
                    i += 1
                    continue

                # Text is on the following line(s) (multiline ID block format)
                i += 1
                block_lines = []
                while i < len(lines):
                    next_line = lines[i]
                    if pat_bracket.match(next_line) or pat_dot.match(next_line) or pat_empty_bracket.match(next_line):
                        break
                    block_lines.append(next_line)
                    i += 1

                chosen = ""
                for bl in block_lines:
                    if any(k in bl for k in ("الترجمة المحسنة", "الترجمة:", "الصياغة", "Improved:", "Translation:")):
                        chosen = self.clean_text_item(bl)
                        if chosen:
                            break
                if not chosen:
                    for bl in reversed(block_lines):
                        if not any(k in bl for k in ("النص الأصلي", "الترجمة الحالية", "Original:", "Current:")):
                            cand = self.clean_text_item(bl)
                            if cand:
                                chosen = cand
                                break
                if chosen:
                    raw_parsed.append((parsed_num, chosen))
            elif empty_match:
                inline_text = self.clean_text_item(empty_match.group(1))
                if inline_text:
                    raw_parsed.append((-1, inline_text))
                i += 1
            else:
                i += 1

        translations: Dict[int, str] = {}

        # Strategy 1 (Preflight Guard): Detect sequential renumbering slippage before partial Direct ID matching
        # Example: expected=[10, 12, 14, 18], LLM renumbers sequentially as [10, 11, 12, 13] or [1, 2, 3, 4]
        direct_matches = {pid: text for pid, text in raw_parsed if pid in expected_set}
        numbered_entries = [(pid, text) for pid, text in raw_parsed if pid != -1 and text]
        numbered_pids = [pid for pid, _ in numbered_entries]
        if (
            len(numbered_pids) >= 2
            and len(direct_matches) < len(expected_ids)
            and numbered_pids != expected_ids[:len(numbered_pids)]
            and numbered_pids == list(range(numbered_pids[0], numbered_pids[0] + len(numbered_pids)))
            and numbered_pids[0] in (0, 1, expected_ids[0])
        ):
            remapped = {}
            for idx in range(min(len(numbered_entries), len(expected_ids))):
                remapped[expected_ids[idx]] = numbered_entries[idx][1]
            if len(remapped) >= len(direct_matches):
                return remapped

        # Strategy 1: Direct ID Match
        if len(direct_matches) == len(expected_ids) or (len(expected_ids) > 1 and len(direct_matches) >= len(expected_ids) // 2):
            translations.update(direct_matches)
            # Fill remaining unmatched expected slots with unnumbered (-1) lines ONLY if counts match exactly
            unmatched_expected = [eid for eid in expected_ids if eid not in translations]
            unmatched_raw = [text for pid, text in raw_parsed if pid == -1 and text]
            if unmatched_expected and unmatched_raw and len(unmatched_expected) == len(unmatched_raw):
                for idx, text in enumerate(unmatched_raw):
                    translations[unmatched_expected[idx]] = text
            return translations

        # Strategy 2: Relative Renumbering Match (1..N or 0..N-1)
        # When LLMs renumber items sequentially from 1 (or 0) instead of retaining original IDs (e.g. [9..16] -> [1..8])
        if len(raw_parsed) > 0 and len(direct_matches) < len(expected_ids):
            valid_pids = [pid for pid, _ in raw_parsed if pid != -1]
            if valid_pids:
                is_1_based = all(1 <= pid <= len(expected_ids) for pid in valid_pids)
                is_0_based = all(0 <= pid < len(expected_ids) for pid in valid_pids)

                if is_1_based and len(expected_set.intersection(valid_pids)) < len(valid_pids):
                    remapped = {}
                    for pid, text in raw_parsed:
                        if 1 <= pid <= len(expected_ids):
                            target_id = expected_ids[pid - 1]
                            remapped[target_id] = text
                    if len(remapped) >= len(direct_matches):
                        return remapped

                elif is_0_based and len(expected_set.intersection(valid_pids)) < len(valid_pids):
                    remapped = {}
                    for pid, text in raw_parsed:
                        if 0 <= pid < len(expected_ids):
                            target_id = expected_ids[pid]
                            remapped[target_id] = text
                    if len(remapped) >= len(direct_matches):
                        return remapped

        # Strategy 3: Sequential / Positional Mapping (Handles [ ] and un-numbered lines from ALLaM and local LLMs)
        if len(raw_parsed) > 0:
            # If no direct matches were found (e.g. all lines used [ ] or []), map sequentially
            if len(direct_matches) == 0:
                remapped = {}
                limit = min(len(expected_ids), len(raw_parsed))
                for idx in range(limit):
                    remapped[expected_ids[idx]] = raw_parsed[idx][1]
                return remapped

        # Return whatever direct matches we found
        if direct_matches:
            return direct_matches

        # Strategy 4: Fallback to non-empty clean lines matching expected_ids
        clean_lines = [
            l for l in lines 
            if not any(trig in l.lower() for trig in IGNORE_TRIGGERS)
        ]
        if len(clean_lines) > 0:
            limit = min(len(expected_ids), len(clean_lines))
            for idx in range(limit):
                fallback_text = self.clean_text_item(clean_lines[idx])
                translations[expected_ids[idx]] = fallback_text

        return translations
