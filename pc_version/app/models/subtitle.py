import re
from enum import Enum
from typing import List, Optional, Dict, Any, Set, Iterable
from pydantic import BaseModel, Field


class SubtitleFormat(str, Enum):
    SRT = "srt"
    ASS = "ass"
    SSA = "ssa"
    VTT = "vtt"
    SBV = "sbv"
    TXT = "txt"
    JSON = "json"


class SubtitleStyle(BaseModel):
    name: str = "Default"
    fontname: str = "Arial"
    fontsize: float = 20.0
    primary_color: str = "&H00FFFFFF"
    secondary_color: str = "&H00000000"
    outline_color: str = "&H00000000"
    back_color: str = "&H00000000"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikeout: bool = False
    scale_x: float = 100.0
    scale_y: float = 100.0
    spacing: float = 0.0
    angle: float = 0.0
    border_style: int = 1
    outline: float = 2.0
    shadow: float = 0.0
    alignment: int = 2
    margin_l: int = 10
    margin_r: int = 10
    margin_v: int = 10
    encoding: int = 1
    raw_line: str = ""


class SubtitleEvent(BaseModel):
    id: int = 1
    layer: int = 0
    start: str = "00:00:00.00"
    end: str = "00:00:00.00"
    style: str = "Default"
    speaker: str = ""
    text: str = ""  # Clean text without tags
    original_text: str = ""  # Raw text with all tags
    translated_text: Optional[str] = None
    margin_l: int = 0
    margin_r: int = 0
    margin_v: int = 0
    effect: str = ""
    format_type: SubtitleFormat = SubtitleFormat.SRT
    extra: Dict[str, Any] = Field(default_factory=dict)
    is_comment: bool = False

    def __init__(self, **data):
        if "start_time" in data and "start" not in data:
            data["start"] = data.pop("start_time")
        if "end_time" in data and "end" not in data:
            data["end"] = data.pop("end_time")
        if "original_text" in data and ("text" not in data or not data["text"]):
            raw = data["original_text"] or ""
            clean = re.sub(r"\{\\p[1-9]\}[^\\{]*\{\\p0\}", "", raw)
            clean = re.sub(r"\{[^}]*\}", "", clean).replace("\\n", "\\N")
            clean = re.sub(r"\s*\\N\s*", lambda m: r" \N ", clean)
            clean = re.sub(r"\s+", " ", clean).strip()
            data["text"] = clean
        super().__init__(**data)

    @property
    def start_time(self) -> str:
        return self.start

    @start_time.setter
    def start_time(self, val: str):
        self.start = val

    @property
    def end_time(self) -> str:
        return self.end

    @end_time.setter
    def end_time(self, val: str):
        self.end = val

    def extract_tags(self) -> List[str]:
        """Extract all ASS override tags from original_text."""
        if not self.original_text:
            return []
        return re.findall(r"(\{[^}]*\}|\\N|\\n)", self.original_text)

    def get_clean_text(self) -> str:
        """Return clean translatable text, isolating vector drawings, effect tags, and preserving natural dialogue linebreaks (\\N)."""
        raw = self.original_text or self.text or ""
        from app.subtitle.effect_separator import EffectPayloadIsolator
        clean, _ = EffectPayloadIsolator.extract_clean_payload(raw)
        return clean

    def has_translatable_text(self) -> bool:
        """Checks if this event contains readable linguistic words that should be translated."""
        from app.subtitle.effect_separator import EffectPayloadIsolator
        return EffectPayloadIsolator.has_translatable_text(self.original_text or self.text or "")

    def rebuild_text(
        self,
        translated: str,
        target_lang: str = "ar",
        known_names: Optional[Iterable[str]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Reinsert translated text back into original_text with strict multi-layer healing,
        purging corrupt tags, preserving styling, and balancing linebreaks.
        """
        if not translated:
            return ""
        if not self.original_text:
            return translated

        from app.subtitle.effect_separator import EffectPayloadIsolator
        from app.quality.healer import SubtitleHealer
        _, skeleton = EffectPayloadIsolator.extract_clean_payload(self.original_text)
        reconstructed = EffectPayloadIsolator.reconstruct_effect_text(translated, skeleton)
        heal_opts: Dict[str, Any] = dict(options or {})
        heal_opts.setdefault("target_lang", target_lang)
        return SubtitleHealer.heal(
            reconstructed,
            self.original_text,
            options=heal_opts,
            known_names=known_names,
        )

    @classmethod
    def is_style_translatable(cls, style: Optional[str]) -> bool:
        """
        Returns True if the style name indicates human spoken dialogue or English song lyrics
        (e.g. Default, Top, Alt, Main, Dialogue, ED1-En, ED2-En, OP1-En, ED-En, OP-En, etc.).
        """
        if not style:
            return False
        st = style.strip().lower()

        # If it explicitly matches blocked FX/Romaji/Sign patterns, it is NOT translatable
        if cls.is_style_blocked(st):
            return False

        # 1. English Song & Lyric patterns (e.g. ED1-En, ED2-En, OP1-En, ED-En, OP-En, Song-En, Insert-En, Ending-En)
        if re.search(r"[-_](?:en|eng|english)$", st):
            return True
        if re.match(r"^(?:op|ed|in|song|ending|opening)[0-9]*[-_](?:en|eng|english)$", st):
            return True

        # 2. Dialogue & Spoken Line patterns
        dialogue_prefixes = (
            "default", "alt", "top", "main", "dialogue", "narration",
            "flashback", "internal", "thinking", "overlap", "secondary", "sub"
        )
        if any(st.startswith(p) for p in dialogue_prefixes) or "dialogue" in st:
            return True

        return False

    @classmethod
    def is_style_blocked(cls, style: Optional[str]) -> bool:
        """
        Returns True if the style name indicates non-translatable visual effects,
        Karaoke animations, Romaji tracks, Signs, or Staff credits.
        """
        if not style:
            return False
        st = style.strip().lower()

        # 1. Romaji / Japanese song lines (Karaoke tracks)
        if re.search(r"[-_](?:ro|romaji|jap|japanese|kanji|kana|jp)(?:[-_].*)?$", st):
            return True
        if any(k in st for k in ("op-ro", "ed-ro", "in-ro", "song-ro", "op-jap", "ed-jap", "in-jap", "song-jap", "op-kanji", "ed-kanji", "op_ro", "ed_ro", "op-jp", "ed-jp", "in-jp", "song-jp", "op_jp", "ed_jp")):
            return True

        # 2. Karaoke & FX automation
        if any(k in st for k in ("karaoke", "template", "banner", "code", "ruby")):
            return True
        if st.startswith("fx") or "-fx" in st or "_fx" in st:
            return True

        # 3. Signs, Typesetting, Staff, Credits, Titles
        if any(k in st for k in ("sign", "typeset", "staff", "sponsor", "credit", "logo", "title", "next", "osi", "textbox", "box")):
            return True

        return False

    def is_visual_effect(self) -> bool:
        """
        Determines if this event is a visual effect (Karaoke FX, vector drawings, 3D typesetting, signs,
        multi-transform animations, or non-dialogue graphics) that should remain untouched in the subtitle file.
        """
        if self.is_comment:
            return True

        # 1. Explicit effect field set by Aegisub automation (templates, code blocks, karaoke automation, or frame markers)
        eff = (self.effect or "").strip().lower()
        if eff:
            is_automation_fx = (
                eff == "fx"
                or eff.startswith(("fx-", "fx_", "template", "code", "karaoke", "k-fx", "banner", "scroll"))
                or "frame start" in eff
                or "start frame" in eff
            )
            if is_automation_fx:
                return True

        raw = self.original_text or self.text or ""

        # 2. Vector drawing commands ({\p1}, {\p2}, etc.)
        if re.search(r"\{\\p[1-9]\}", raw):
            return True

        # 3. Karaoke timing tags (\k, \K, \kf, \ko) inside the event text
        if re.search(r"\{\\[kK][fo]?\d+", raw):
            return True

        # 4. Clean text check: If there are no readable linguistic letters, it's a graphical/separator effect
        clean = re.sub(r"\{[^{}]*\}", "", raw).replace(r"\N", " ").replace(r"\n", " ").strip()
        if not clean or not re.search(r"[A-Za-zء-ي\u3040-\u30ff\u4e00-\u9faf]", clean):
            return True

        # 5. Raw vector path without {\p1}: e.g. text starting with 'm 163.375 -131.25 b ...'
        if re.match(r"^[mblsc]\s+[-0-9]", clean):
            return True

        # 6. Ultra-short duration frame-by-frame animation (1 to 3 frames: 10ms <= duration <= 120ms)
        # Note: Only applies to actual timed events where timestamps are non-zero,
        # AND which contain override tags or typesetting styles.
        try:
            from app.subtitle.timecode import parse_timecode_ms
            ms1 = parse_timecode_ms(self.start)
            ms2 = parse_timecode_ms(self.end)
            if ms1 is not None and ms2 is not None:
                duration = ms2 - ms1
                if (ms1 > 0 or ms2 > 0) and 0 < duration <= 120:
                    style_l = (self.style or "").lower()
                    if "\\" in raw or any(k in style_l for k in ("typeset", "stat", "anim", "mask", "fx")):
                        return True
        except Exception:
            pass

        # 7. Check style-based classification
        style = (self.style or "").strip().lower()
        if self.is_style_blocked(style):
            return True
        if any(k in style for k in ("statisztika", "typeset", "op typeset", "ed typeset", "insert typeset", "song typeset")):
            return True

        # 8. Pixel-strip clipping masks (e.g. \clip(x1,y1,x2,y2) with narrow strip <= 20px)
        m_clip = re.search(r"\\i?clip\((\d+),(\d+),(\d+),(\d+)\)", raw)
        if m_clip:
            x1, y1, x2, y2 = map(int, m_clip.groups())
            if abs(x2 - x1) <= 20 or abs(y2 - y1) <= 20:
                return True

        # 9. Isolated single or double Latin character from split masks/typesetting (e.g. 'D', 'a', 'r' with clip/pos)
        if len(clean) <= 2 and (r"\clip" in raw or r"\iclip" in raw or r"\pos" in raw or r"\p" in raw or any(k in style for k in ("typeset", "stat", "anim"))):
            if clean.lower() not in (
                "no", "hi", "oh", "ah", "ha", "ok", "we", "me", "us", "up", "he", "so", "it", "is", "in", "on", "at", "to", "go"
            ):
                return True

        # 10. Check effect-segment patterns: SFX, pure signs, titles, chapters, credits, onomatopoeia
        from app.subtitle.effect_separator import EffectSeparator
        if EffectSeparator.is_effect_segment(raw):
            return True

        # 11. If style is explicitly translatable (Default, Top, Alt, ED1-En, ED2-En, OP1-En, etc.),
        # it is translatable dialogue/song lyrics (as long as it wasn't flagged as an effect above)
        if self.is_style_translatable(style):
            return False

        # 12. Undecided styles (e.g. character names like Saber, Rin, or plain subtitles without style):
        # Complex 3D rotation, clipping masks, or multiple chained animated transforms indicate signs
        if re.search(r"\\(fr[xyz]-?[1-9]|org\(|clip\(|iclip\()", raw) or len(re.findall(r"\\t\(", raw)) >= 2:
            return True

        return False

    def is_translatable(self, include_signs: bool = False) -> bool:
        """
        Returns True if this event represents human dialogue/speech eligible for translation.
        When include_signs=True, only genuine readable static signs with real words are included.
        Frame-by-frame animations, clip masks, and vector drawings are strictly excluded.
        """
        if self.is_comment:
            return False
        if not self.is_visual_effect():
            return True
        if include_signs:
            clean = self.get_clean_text().strip()
            if len(clean) <= 2:
                return False
            raw = self.original_text or ""
            if r"\clip(" in raw or r"\iclip(" in raw or re.search(r"\\p[1-9]", raw):
                return False
            style = (self.style or "").strip().lower()
            if any(k in style for k in ("statisztika", "typeset", "karaoke", "template", "code")):
                return False
            from app.subtitle.effect_separator import EffectSeparator
            if not EffectSeparator.has_translatable_text(clean):
                return False
            # Exclude sound effects, audio cues, and asterisks even if include_signs=True
            if re.match(r'^(?:\[|\(|\*|\b)?(?:SFX|سFX|مؤثر|صوت|Sound|Audio|Music|Noise)[\:\s\-\]]', clean, re.IGNORECASE):
                return False
            if re.match(r'^\*[^*]+\*$', clean):
                return False
            words = [w for w in clean.split() if len(w) >= 2]
            return len(words) >= 1
        return False


class SubtitleDocument(BaseModel):
    format: SubtitleFormat = SubtitleFormat.SRT
    file_path: Optional[str] = None
    events: List[SubtitleEvent] = Field(default_factory=list)
    styles: List[SubtitleStyle] = Field(default_factory=list)
    script_info: Dict[str, str] = Field(default_factory=dict)
    raw_header_lines: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_translatable_events(self, skip_effects: bool = True, include_signs: bool = False) -> List[SubtitleEvent]:
        """
        Returns dialogue events eligible for translation.
        When skip_effects=True (default), preserves visual effects, drawings, and karaoke FX untouched,
        while allowing styled signs/titles with translatable words when include_signs=True.
        """
        if skip_effects:
            return [e for e in self.events if e.is_translatable(include_signs=include_signs)]
        return [
            e for e in self.events
            if not e.is_comment and (
                (e.text and e.text.strip()) or 
                (e.original_text and e.original_text.strip()) or
                (e.translated_text and e.translated_text.strip())
            )
        ]

    def get_speakers(self) -> Set[str]:
        """Return unique non-empty speaker names from events."""
        return {e.speaker.strip() for e in self.events if e.speaker and e.speaker.strip()}

    def get_event_by_id(self, event_id: int) -> Optional[SubtitleEvent]:
        """Find an event by its ID."""
        for e in self.events:
            if e.id == event_id:
                return e
        return None

    def separate_mixed_effects(self) -> "SubtitleDocument":
        """
        Separates all lines that combine on-screen effects/signs/drawings with dialogue
        into distinct synchronized events, protecting effects from translation.
        """
        from app.subtitle.effect_separator import EffectSeparator
        return EffectSeparator.separate_document(self)
