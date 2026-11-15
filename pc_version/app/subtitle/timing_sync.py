import math
import re
import subprocess
from typing import List, Optional, Tuple

from app.models.subtitle import SubtitleDocument, SubtitleEvent
from app.subtitle.timecode import format_timecode, parse_timecode_ms


class SubtitleTimingOptimizer:
    """
    Deterministic timing synchronization & Arabic readability optimizer.
    - Extends end_time within available gaps when Arabic text exceeds comfortable
      reading speed (CPS), strictly preserving start_time and inter-cue gaps.
    - Probes initial speech onset via FFmpeg silencedetect to detect fixed audio-subtitle offsets.
    """

    @staticmethod
    def _clean_readable_text(text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"\{[^{}]*\}", "", text)
        cleaned = cleaned.replace(r"\N", " ").replace(r"\n", " ").replace("\n", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @classmethod
    def optimize_arabic_cps(
        cls,
        document: SubtitleDocument,
        max_cps: float = 18.0,
        min_duration_ms: int = 1000,
        min_gap_ms: int = 80,
        max_extend_ms: int = 1200,
    ) -> int:
        """
        Extends end_time (lead-out) for dialogue cues whose reading speed exceeds
        `max_cps` characters/second or duration is below `min_duration_ms`.
        Guarantees:
        - NEVER shifts start_time.
        - NEVER shortens any subtitle duration.
        - NEVER creates overlaps or violates `min_gap_ms` before the next non-overlapping cue.
        - Skips comments, visual effects, and zero-placeholder mock timestamps (0 -> 0).
        """
        if not document or not document.events or max_cps <= 0:
            return 0

        fmt = getattr(getattr(document, "format", None), "value", None)
        timed_items: List[Tuple[int, int, SubtitleEvent]] = []
        for ev in document.events:
            if getattr(ev, "is_comment", False):
                continue
            if hasattr(ev, "is_visual_effect") and ev.is_visual_effect():
                continue
            s_ms = parse_timecode_ms(ev.start_time)
            e_ms = parse_timecode_ms(ev.end_time)
            if s_ms is None or e_ms is None:
                continue
            if s_ms == 0 and e_ms == 0:
                continue
            if e_ms <= s_ms:
                continue
            timed_items.append((s_ms, e_ms, ev))

        if not timed_items:
            return 0

        # Sort chronologically by start time to determine collision-free forward headroom
        timed_items.sort(key=lambda item: (item[0], item[1]))
        extended_count = 0

        for idx, (s_ms, e_ms, ev) in enumerate(timed_items):
            raw_txt = ev.translated_text or ev.original_text or ""
            clean_txt = cls._clean_readable_text(raw_txt)
            if not clean_txt:
                continue

            cur_dur = e_ms - s_ms
            req_dur = max(
                min_duration_ms,
                int(math.ceil((len(clean_txt) / float(max_cps)) * 1000.0)),
            )
            if req_dur <= cur_dur:
                continue

            # Only extend into genuine non-overlapping successor gap
            next_start_ms: Optional[int] = None
            for j in range(idx + 1, len(timed_items)):
                cand_start = timed_items[j][0]
                if cand_start >= e_ms:
                    next_start_ms = cand_start
                    break

            target_end = s_ms + min(req_dur, cur_dur + max(0, max_extend_ms))
            if next_start_ms is not None:
                max_safe_end = next_start_ms - max(0, min_gap_ms)
                if max_safe_end <= e_ms:
                    continue
                target_end = min(target_end, max_safe_end)

            if target_end > e_ms:
                ev.end_time = format_timecode(target_end, template_str=ev.end_time, fmt=fmt)
                setattr(ev, "_cached_cps", None)
                extended_count += 1

        return extended_count

    @staticmethod
    def detect_audio_speech_offset_ms(
        video_path: str,
        subtitle_events: List[SubtitleEvent],
        probe_seconds: int = 90,
        noise_db: str = "-35dB",
        min_silence_dur: float = 0.4,
    ) -> Optional[int]:
        """
        Inspects the first `probe_seconds` of video audio using FFmpeg silencedetect
        and compares initial audio onset (`silence_end`) against the earliest spoken
        subtitle cue start_ms.
        Returns suggested shift in milliseconds (audio_onset_ms - first_cue_ms), or None.
        """
        if not video_path or not subtitle_events:
            return None

        first_cue_ms: Optional[int] = None
        for ev in subtitle_events:
            if getattr(ev, "is_comment", False):
                continue
            if hasattr(ev, "is_visual_effect") and ev.is_visual_effect():
                continue
            s_ms = parse_timecode_ms(ev.start_time)
            e_ms = parse_timecode_ms(ev.end_time)
            if s_ms is None or e_ms is None or e_ms <= s_ms or (s_ms == 0 and e_ms == 0):
                continue
            if first_cue_ms is None or s_ms < first_cue_ms:
                first_cue_ms = s_ms

        if first_cue_ms is None:
            return None

        from app.subtitle.video_extractor import VideoSubtitleExtractor

        ffmpeg_bin = VideoSubtitleExtractor.get_ffmpeg_bin()
        cmd = [
            ffmpeg_bin,
            "-hide_banner",
            "-nostats",
            "-ss", "0",
            "-t", str(max(10, int(probe_seconds))),
            "-i", video_path,
            "-vn",
            "-af", f"silencedetect=noise={noise_db}:d={min_silence_dur}",
            "-f", "null",
            "-",
        ]
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=VideoSubtitleExtractor._get_startupinfo(),
                creationflags=VideoSubtitleExtractor._get_creationflags(),
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=30,
            )
            stderr = getattr(res, "stderr", "") or ""
            if not isinstance(stderr, str) or not stderr:
                return None

            m_start = re.search(r"silence_start:\s*([0-9]+(?:\.[0-9]+)?)", stderr)
            m_end = re.search(r"silence_end:\s*([0-9]+(?:\.[0-9]+)?)", stderr)
            if not m_start or not m_end:
                return None

            silence_start_s = float(m_start.group(1))
            silence_end_s = float(m_end.group(1))
            # Only trust leading silence beginning right near start of stream
            if silence_start_s > 0.25 or silence_end_s <= 0.0:
                return None

            audio_onset_ms = int(round(silence_end_s * 1000))
            delta_ms = audio_onset_ms - first_cue_ms
            if abs(delta_ms) > 15000:
                return None
            return delta_ms
        except Exception:
            return None
