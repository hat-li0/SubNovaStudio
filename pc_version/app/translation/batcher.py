import math
from typing import List
from app.models.subtitle import SubtitleEvent
from app.subtitle.timecode import parse_timecode_ms


class TokenBatcher:
    """Token-aware, scene-aware, and context-length-adaptive batcher for subtitle events."""

    MAX_ID_GAP = 5
    MAX_SCENE_GAP_MS = 4000

    def __init__(
        self,
        max_tokens: int = 6000,
        max_events: int = 30,
        local_max_events: int = 12,
        max_context: int = 4096,
        max_id_gap: int = MAX_ID_GAP,
        max_scene_gap_ms: int = MAX_SCENE_GAP_MS,
    ):
        self.max_tokens = max_tokens
        self.max_events = max_events
        self.local_max_events = local_max_events
        self.max_context = max_context
        self.max_id_gap = max_id_gap
        self.max_scene_gap_ms = max_scene_gap_ms
        self.prompt_overhead_tokens = 500

    @staticmethod
    def estimate_tokens_static(text: str) -> int:
        """
        Script-aware BPE token estimate:
        - Non-Latin scripts (Arabic, Japanese, CJK, Cyrillic, Korean) cost ~1.0 token/char.
        - ASCII / Latin text averages ~1 token per 3.5 characters.
        """
        if not text:
            return 1
        non_ascii = sum(1 for ch in text if ord(ch) > 127)
        ascii_len = len(text) - non_ascii
        return max(1, math.ceil(non_ascii * 1.0 + (ascii_len / 3.5)))

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens for the given text based on script density."""
        return self.estimate_tokens_static(text)

    def _should_break_scene_or_gap(self, prev_event: SubtitleEvent, curr_event: SubtitleEvent) -> bool:
        """Determines whether an ID discontinuity (> max_id_gap) or silence gap (> max_scene_gap_ms) requires a batch boundary."""
        try:
            if abs(int(curr_event.id) - int(prev_event.id)) > self.max_id_gap:
                return True
        except (TypeError, ValueError):
            pass

        prev_end_ms = parse_timecode_ms(prev_event.end or "")
        curr_start_ms = parse_timecode_ms(curr_event.start or "")
        if (
            prev_end_ms is not None
            and curr_start_ms is not None
            and (prev_end_ms > 0 or curr_start_ms > 0)
        ):
            if (curr_start_ms - prev_end_ms) > self.max_scene_gap_ms:
                return True

        return False

    def create_batches(
        self,
        events: List[SubtitleEvent],
        for_improvement: bool = False,
        is_local: bool = False
    ) -> List[List[SubtitleEvent]]:
        """Group events into cohesive batches respecting tokens, context size, ID continuity, and scene breaks."""
        batches: List[List[SubtitleEvent]] = []
        current_batch: List[SubtitleEvent] = []
        overhead = 800 if for_improvement else self.prompt_overhead_tokens

        # Adaptive context limits based on the model's max_context
        # Reserve generous tokens for prompt instruction overhead and output tokens
        reserve_output = 1200 if for_improvement else 1500
        budget_from_context = max(400, self.max_context - overhead - reserve_output)

        if is_local:
            limit_events = min(self.max_events, 8 if for_improvement else self.local_max_events)
            effective_max_tokens = min(self.max_tokens, budget_from_context)
        else:
            limit_events = min(self.max_events, 8) if for_improvement else self.max_events
            effective_max_tokens = min(self.max_tokens, budget_from_context if self.max_context < 16000 else self.max_tokens)

        current_tokens = overhead

        for event in events:
            if for_improvement:
                comb = f"{event.get_clean_text()} {event.translated_text or ''}"
                event_tokens = self.estimate_tokens(comb) + 15
            else:
                text = event.get_clean_text()
                event_tokens = self.estimate_tokens(text)

            # Break batch at scene transitions (time gap > 4s) or ID jumps (> 5, e.g. from checkpoints/TM hits)
            if current_batch and self._should_break_scene_or_gap(current_batch[-1], event):
                batches.append(current_batch)
                current_batch = []
                current_tokens = overhead

            # If a single event exceeds max tokens, put it in its own batch anyway
            if event_tokens + overhead > effective_max_tokens:
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = overhead
                batches.append([event])
                continue

            # Check if adding this event exceeds limits
            if len(current_batch) >= limit_events or current_tokens + event_tokens > effective_max_tokens:
                batches.append(current_batch)
                current_batch = [event]
                current_tokens = overhead + event_tokens
            else:
                current_batch.append(event)
                current_tokens += event_tokens

        if current_batch:
            batches.append(current_batch)

        return batches
