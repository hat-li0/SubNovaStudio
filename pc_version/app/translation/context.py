import re
from typing import List, Dict, Any, Optional
from app.models.subtitle import SubtitleEvent
from app.subtitle.timecode import parse_timecode_ms


class ContextBuilder:
    """Builds scene-coherent context strings for translation prompts with rich dialogue history."""

    MAX_CONTEXT_GAP_MS = 15000

    def __init__(self, prev_count: int = 4, next_count: int = 3):
        self.prev_count = prev_count
        self.next_count = next_count

    def build_context(
        self,
        all_events: List[SubtitleEvent],
        batch_events: List[SubtitleEvent],
        id_map: Optional[Dict[int, int]] = None,
    ) -> Dict[str, str]:
        """Build previous, next, and current text contexts while respecting scene boundaries."""
        if not batch_events or not all_events:
            return {"prev_text": "", "current_text": "", "next_text": ""}

        first_idx = -1
        last_idx = -1

        # Find indices of first and last batch events in all_events
        first_id = batch_events[0].id
        last_id = batch_events[-1].id

        for i, event in enumerate(all_events):
            if event.id == first_id:
                first_idx = i
            if event.id == last_id:
                last_idx = i

        if first_idx == -1 or last_idx == -1:
            first_idx = all_events.index(batch_events[0]) if batch_events[0] in all_events else 0
            last_idx = all_events.index(batch_events[-1]) if batch_events[-1] in all_events else len(all_events) - 1

        # Previous context: walk backward up to prev_count lines, stopping across major scene silences
        prev_collected: List[SubtitleEvent] = []
        anchor = batch_events[0]
        for idx in range(first_idx - 1, max(-1, first_idx - self.prev_count - 1), -1):
            cand = all_events[idx]
            cand_end = parse_timecode_ms(cand.end or "")
            anc_start = parse_timecode_ms(anchor.start or "")
            if (
                cand_end is not None
                and anc_start is not None
                and (cand_end > 0 or anc_start > 0)
                and (anc_start - cand_end) > self.MAX_CONTEXT_GAP_MS
            ):
                break
            prev_collected.append(cand)
            anchor = cand
        prev_collected.reverse()
        prev_lines = []
        for e in prev_collected:
            clean_t = e.get_clean_text()
            if not clean_t:
                continue
            if e.translated_text:
                clean_trans = re.sub(r"\{[^}]*\}", "", e.translated_text).strip()
                if clean_trans and clean_trans != clean_t:
                    prev_lines.append(f"(Context) {clean_t} -> {clean_trans}")
                    continue
            prev_lines.append(f"(Context) {clean_t}")
        prev_text = "\n".join(prev_lines)

        # Next context: walk forward up to next_count lines, stopping across major scene silences
        next_collected: List[SubtitleEvent] = []
        anchor = batch_events[-1]
        for idx in range(last_idx + 1, min(len(all_events), last_idx + 1 + self.next_count)):
            cand = all_events[idx]
            anc_end = parse_timecode_ms(anchor.end or "")
            cand_start = parse_timecode_ms(cand.start or "")
            if (
                anc_end is not None
                and cand_start is not None
                and (anc_end > 0 or cand_start > 0)
                and (cand_start - anc_end) > self.MAX_CONTEXT_GAP_MS
            ):
                break
            next_collected.append(cand)
            anchor = cand
        next_lines = []
        for e in next_collected:
            clean_t = e.get_clean_text()
            if not clean_t:
                continue
            if e.translated_text:
                clean_trans = re.sub(r"\{[^}]*\}", "", e.translated_text).strip()
                if clean_trans and clean_trans != clean_t:
                    next_lines.append(f"(Context) {clean_t} -> {clean_trans}")
                    continue
            next_lines.append(f"(Context) {clean_t}")
        next_text = "\n".join(next_lines)

        # Current text
        current_lines = []
        for event in batch_events:
            mapped_id = id_map.get(event.id, event.id) if id_map else event.id
            event_id_str = f"[{mapped_id:03d}]"
            clean_text = event.get_clean_text()
            current_lines.append(f"{event_id_str} {clean_text}")
        current_text = "\n".join(current_lines)

        return {
            "prev_text": prev_text,
            "current_text": current_text,
            "next_text": next_text
        }
