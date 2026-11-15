import re
from typing import List, Tuple, Dict, Any, Optional
from app.models.subtitle import SubtitleEvent, SubtitleDocument, SubtitleFormat


class EffectSeparator:
    """
    Intelligent separator for subtitle lines that combine on-screen visual effects,
    signs, drawings, or SFX with human dialogue in the same line.
    
    Provides:
    1. Detection of mixed effect-dialogue lines.
    2. Event-level separation: splits mixed lines into distinct synchronized events
       (FX events for signs/effects, dialogue events for spoken lines).
    3. Document-level processing with sequential ID re-indexing.
    4. Inline vector drawing and SFX delimiter protection.
    """

    @classmethod
    def is_effect_segment(cls, seg: str) -> bool:
        """Determines if a string segment represents an on-screen effect, sign, drawing, or SFX."""
        s = seg.strip()
        if not s:
            return False

        # 1. Vector drawings: {\p1}...
        if re.search(r'\\p[1-9]', s):
            return True

        # 2. Clean text check (strip all ASS override tags)
        clean = re.sub(r'\{[^{}]*\}', '', s).strip()
        if not clean:
            return True

        # 3. No readable linguistic letters (just symbols, coordinates, numbers, or dividers)
        if not re.search(r'[A-Za-zء-ي\u3040-\u30ff\u4e00-\u9faf]', clean):
            return True

        # 4. Karaoke timing tags (\k, \K, \kf, \ko)
        if re.search(r'\{\\[kK][fo]?\d+', s):
            return True

        # 5. Explicit signs or SFX label prefixes (with or without brackets/asterisks)
        if re.match(
            r'^(?:\[|\(|\*|\b)?(?:SFX|سFX|مؤثر|صوت|Sign|لوحة|Sound|Audio|Music|Noise)[\:\s\-\]]',
            clean,
            re.IGNORECASE
        ):
            return True

        # 6. Standalone onomatopoeia / sound effect in asterisks or brackets
        if re.match(r'^\*[^*]+\*$', clean):
            return True
        if re.match(
            r'^\[(?:Sound|Audio|Music|Noise|SFX|Silence|Laughter|Sigh|Gasp|Cough|Footsteps|Applause|Gunfire|Explosion|Door|Phone|Whistle|Chuckle|Scream|Chant)[^\]]*\]$',
            clean,
            re.IGNORECASE
        ):
            return True
        if re.match(
            r'^\((?:Sound|Audio|Music|Noise|SFX|Silence|Laughter|Sigh|Gasp|Cough|Footsteps|Applause|Gunfire|Explosion|Door|Phone|Whistle|Chuckle|Scream|Chant)[^\)]*\)$',
            clean,
            re.IGNORECASE
        ):
            return True

        # 7. Explicit signs, titles, chapters, staff, notes
        if re.match(
            r'^(?:\[|\(|\*|\b)?(?:Title|عنوان|Chapter|فصل|Episode|حلقة|Staff|طاقم|Credits?|حقوق|Typesetting|تايبست|Note|ملاحظة|T/N|TL/N|TN)[\:\s\-\]]',
            clean,
            re.IGNORECASE
        ):
            return True

        # 8. Explicit signs accompanied by positioning / alignment tags (\an[4-9], \pos, \move, \clip, \org, \fad)
        has_pos_or_align = bool(re.search(r'\\(?:an[4-9]|pos|move|clip|iclip|org|fad)', s))
        if has_pos_or_align:
            clean_upper = clean.upper()
            sign_keywords = (
                "SIGN", "TITLE", "CREDIT", "LOGO", "STAFF", "SPONSOR", "NOTE",
                "CHAPTER", "EPISODE", "WARNING", "DANGER", "CAUTION", "HOSPITAL",
                "POLICE", "STATION", "ROOM", "OFFICE", "STORE", "SCHOOL", "LIBRARY",
                "ENTRANCE", "EXIT", "NOTICE", "NEWS", "BREAKING"
            )
            if any(k in clean_upper for k in sign_keywords):
                return True
            # Uppercase English text (signs) with non-dialogue alignment or 3D transform
            if re.match(r'^[A-Z0-9\s\-\:\.\,\!\?\'\"]+$', clean) and len(clean.split()) <= 6:
                if re.search(r'\\an[4-9]', s) or re.search(r'\\(fr[xyz]-?[1-9]|clip\(|iclip\()', s):
                    return True

        # 9. Style resets to a blocked style ({\rSign}, {\rStaff}, etc.)
        r_match = re.search(r'\{\\r([^}]*)\}', s)
        if r_match:
            r_style = r_match.group(1).strip()
            if SubtitleEvent.is_style_blocked(r_style):
                return True

        return False

    @classmethod
    def is_dialogue_segment(cls, seg: str) -> bool:
        """Determines if a string segment represents human speech/dialogue."""
        s = seg.strip()
        if not s:
            return False
        if cls.is_effect_segment(s):
            return False
        clean = re.sub(r'\{[^{}]*\}', '', s).strip()
        return bool(re.search(r'[A-Za-zء-ي\u3040-\u30ff\u4e00-\u9faf]', clean))

    @classmethod
    def split_raw_into_segments(cls, raw: str) -> List[str]:
        """
        Splits a raw subtitle line into its visual component segments based on:
        - Linebreaks (\\N, \\n)
        - Vector drawings ending in {\\p0}
        - Style resets (\\r)
        - Mid-line effect positioning tags (\\pos, \\an4-9, etc.)
        - Inline effect cues at start or end of dialogue
        """
        if not raw:
            return []

        # 1. Primary boundary: \\N or \\n
        if r'\N' in raw or r'\n' in raw or '\n' in raw:
            initial_parts = [p.strip() for p in re.split(r'\\N|\\n|\n', raw)]
        else:
            initial_parts = [raw.strip()]

        segments: List[str] = []
        for part in initial_parts:
            if not part:
                continue

            # Sub-split 2: Vector drawing ending in {\p0} followed by text
            m_p0 = re.search(r'(\{\\p0\})\s*(.+)', part)
            if m_p0:
                segments.append(part[:m_p0.end(1)].strip())
                segments.append(m_p0.group(2).strip())
                continue

            # Sub-split 3: Style reset {\r...} separating two parts
            m_r = re.search(r'([^\\])\s*(\{\\r[^{}]*\}.+)', part)
            if m_r:
                segments.append(part[:m_r.start(2)].strip())
                segments.append(m_r.group(2).strip())
                continue

            # Sub-split 4: Mid-sentence effect positioning tag
            m_pos = re.search(r'([^\\])\s*(\{\\(?:pos|an[4-9]|move|org|clip|fad)[^{}]*\}.+)', part)
            if m_pos:
                segments.append(part[:m_pos.start(2)].strip())
                segments.append(m_pos.group(2).strip())
                continue

            # Sub-split 5: Inline effect cue at START of line followed by dialogue
            # Example: {\pos(100,200)}[SFX: EXPLOSION] هل الجميع بخير؟
            # Or: [SFX: BOOM] - انتبه!
            # Or: *Gasp* What was that?
            # Or: {\fs14}SFX: rumble{\fs20} انتبه يا صديقي
            m_start_fx = re.match(
                r'^((?:\{[^{}]*\}\s*)*)(\[(?:SFX|سFX|مؤثر|صوت|Sound|Audio)[^\]]*\]|\*[^*]+\*|(?:SFX|سFX|مؤثر|صوت|Sign|لوحة)[\:\s\-][A-Za-z0-9_\s\.\!\?\-]+?)(?:\\N|\\n|\s*(\{\\r[^{}]*\}|\{\\fs\d+\})|\s+)([\u0600-\u06FF\-\"].+)$',
                part,
                re.IGNORECASE
            )
            if m_start_fx:
                lead_tags = m_start_fx.group(1) or ""
                fx_text = m_start_fx.group(2)
                mid_tags = m_start_fx.group(3) or ""
                diag_text = m_start_fx.group(4)
                segments.append(f"{lead_tags}{fx_text}".strip())
                segments.append(f"{mid_tags} {diag_text}".strip() if mid_tags else diag_text.strip())
                continue

            # Sub-split 6: Inline effect cue at END of line following dialogue
            # Example: هل الجميع بخير؟ [صوت انفجار]
            # Or: Look out! *Crash*
            m_end_fx = re.match(
                r'^(.+?)(?:\s+|\\N|\\n)(\[(?:SFX|سFX|مؤثر|صوت|Sound|Audio|انفجار|صراخ)[^\]]*\]|\*[^*]+\*)$',
                part,
                re.IGNORECASE
            )
            if m_end_fx and cls.is_effect_segment(m_end_fx.group(2)):
                segments.append(m_end_fx.group(1).strip())
                segments.append(m_end_fx.group(2).strip())
                continue

            segments.append(part)

        return segments

    @classmethod
    def is_mixed_line(cls, event: SubtitleEvent) -> bool:
        """Returns True if the event combines both an effect and spoken dialogue in the same line."""
        if event.is_comment:
            return False

        # If the event is an English song lyric (e.g. ED1-En, ED2-En, OP1-En),
        # it is NOT a mixed line - it's a continuous song subtitle!
        if SubtitleEvent.is_style_translatable(event.style) and any(k in (event.style or "").lower() for k in ("-en", "-eng", "ed", "op", "song")):
            return False

        raw = event.original_text or event.text
        if not raw:
            return False

        segments = cls.split_raw_into_segments(raw)
        if len(segments) <= 1:
            return False

        has_fx = any(cls.is_effect_segment(s) for s in segments)
        has_dialogue = any(cls.is_dialogue_segment(s) for s in segments)
        return has_fx and has_dialogue

    @classmethod
    def separate_event(cls, event: SubtitleEvent) -> List[SubtitleEvent]:
        """
        Splits a mixed event into individual synchronized events:
        - Effect events: Marked with effect="fx" (classified as is_visual_effect()=True).
        - Dialogue events: Grouped dialogue lines with preserved multi-speaker linebreaks.
        Both retain identical start/end timing and layer for perfect on-screen synchronization.
        """
        if not cls.is_mixed_line(event):
            return [event]

        raw = event.original_text or event.text
        segments = cls.split_raw_into_segments(raw)
        result: List[SubtitleEvent] = []

        # Group segments into contiguous blocks, merging consecutive dialogue segments
        blocks: List[Dict[str, Any]] = []
        for seg in segments:
            is_fx = cls.is_effect_segment(seg)
            if blocks and blocks[-1]["is_fx"] is False and is_fx is False:
                blocks[-1]["segments"].append(seg)
            else:
                blocks.append({"is_fx": is_fx, "segments": [seg]})

        for block in blocks:
            is_fx = block["is_fx"]
            segs = block["segments"]

            if is_fx:
                for seg in segs:
                    clean_text = re.sub(r'\{[^{}]*\}', '', seg).strip()
                    seg_style = event.style
                    r_match = re.search(r'\{\\r([^}]*)\}', seg)
                    if r_match:
                        extracted_style = r_match.group(1).strip()
                        if extracted_style:
                            seg_style = extracted_style

                    fx_ev = SubtitleEvent(
                        id=event.id,
                        layer=event.layer,
                        start=event.start,
                        end=event.end,
                        style=seg_style,
                        speaker="",
                        margin_l=event.margin_l,
                        margin_r=event.margin_r,
                        margin_v=event.margin_v,
                        effect=event.effect or "fx",
                        original_text=seg,
                        text=clean_text,
                        is_comment=event.is_comment,
                        format_type=event.format_type
                    )
                    result.append(fx_ev)
            else:
                combined_orig = r"\N".join(segs)
                combined_clean = r"\N".join(
                    re.sub(r'\{[^{}]*\}', '', s).strip() for s in segs
                )
                diag_style = event.style
                for seg in segs:
                    r_match = re.search(r'\{\\r([^}]*)\}', seg)
                    if r_match:
                        extracted_style = r_match.group(1).strip()
                        if extracted_style:
                            diag_style = extracted_style
                            break

                diag_ev = SubtitleEvent(
                    id=event.id,
                    layer=event.layer,
                    start=event.start,
                    end=event.end,
                    style=diag_style,
                    speaker=event.speaker,
                    margin_l=event.margin_l,
                    margin_r=event.margin_r,
                    margin_v=event.margin_v,
                    effect="",
                    original_text=combined_orig,
                    text=combined_clean,
                    is_comment=event.is_comment,
                    format_type=event.format_type
                )
                result.append(diag_ev)

        return result

    @classmethod
    def separate_document(cls, doc: SubtitleDocument) -> SubtitleDocument:
        """
        Separates all mixed events in the document into distinct effect and dialogue events,
        and re-indexes event IDs sequentially.
        """
        if not doc or not doc.events:
            return doc

        new_events: List[SubtitleEvent] = []
        any_split = False

        for ev in doc.events:
            if cls.is_mixed_line(ev):
                split_events = cls.separate_event(ev)
                new_events.extend(split_events)
                any_split = True
            else:
                new_events.append(ev)

        if any_split:
            for i, ev in enumerate(new_events, 1):
                ev.id = i
            doc.events = new_events

        return doc

    @classmethod
    def has_translatable_text(cls, raw: str) -> bool:
        """Determines if a subtitle line/effect contains translatable human words."""
        return EffectPayloadIsolator.has_translatable_text(raw)

    @classmethod
    def extract_clean_payload(cls, raw: str) -> Tuple[str, Dict[str, Any]]:
        """Extracts pure text for LLM without tags, and records effect skeleton."""
        return EffectPayloadIsolator.extract_clean_payload(raw)

    @classmethod
    def reconstruct_effect_text(cls, translated: str, skeleton: Dict[str, Any]) -> str:
        """Re-attaches original visual effects, styling, and positions to translation."""
        return EffectPayloadIsolator.reconstruct_effect_text(translated, skeleton)


class EffectPayloadIsolator:
    """
    Advanced Effect & Styling Payload Isolator.
    
    Extracts pure human dialogue and on-screen sign texts from lines containing
    heavy ASS styling tags, positions, and visual effects. Ensures that:
    1. ZERO effect/styling tags reach the model, cutting context token usage by up to 80%.
    2. Small context models (e.g. ALLaM 4096) are never overwhelmed by coordinate noise.
    3. Re-injects 100% of original ASS positions, fonts, colors, rotations, and animations
       into the translated text upon return.
    """

    @classmethod
    def has_translatable_text(cls, raw: str) -> bool:
        """
        Determines whether a subtitle line or visual effect contains genuine readable linguistic words
        (Latin letters, Arabic, Japanese Kanji/Kana, Cyrillic, etc.) that should be translated.
        Returns False for pure vector drawings, empty shapes, and standalone sound cues (*gasp*, [Music]).
        """
        if not raw or not raw.strip():
            return False

        # 1. Strip vector drawings {\p1}...{\p0}
        clean = re.sub(r'\{\\p[1-9]\}[^\\{]*\{\\p0\}', '', raw)

        # 2. Strip all ASS override tags
        clean = re.sub(r'\{[^}]*\}', '', clean)
        clean = clean.replace(r'\N', ' ').replace(r'\n', ' ').strip()
        if not clean:
            return False

        # 3. Check if raw vector coordinates without tags (e.g. 'm 163.375 -131.25 b ...')
        if re.match(r'^[mblsc]\s+[-0-9]', clean):
            return False

        # 4. Pure sound effects in asterisks or brackets: e.g. *gasp*, [Music], (sigh), SFX: BOOM
        if re.match(r'^\*[^*]+\*$', clean):
            return False
        if re.match(r'^\[(?:Music|Sound|Audio|Noise|SFX|Laughter|Sigh|Gasp|Cough|Chuckle|Footsteps|Applause|Gunfire)[^\]]*\]$', clean, re.IGNORECASE):
            return False
        if re.match(r'^\((?:Music|Sound|Audio|Noise|SFX|Laughter|Sigh|Gasp|Cough|Chuckle|Footsteps|Applause|Gunfire)[^\)]*\)$', clean, re.IGNORECASE):
            return False
        if re.match(r'^(?:SFX|سFX|مؤثر|صوت)[\:\s\-]+[A-Za-z0-9_\s\.\!\?\-]+$', clean, re.IGNORECASE):
            return False

        # 5. Check for genuine readable linguistic letters
        return bool(re.search(r'[A-Za-zء-ي\u3040-\u30ff\u4e00-\u9faf\uac00-\ud7af]', clean))

    @classmethod
    def extract_clean_payload(cls, raw: str) -> Tuple[str, Dict[str, Any]]:
        """
        Separates all visual effect tags and styling from the translatable text payload.
        
        Returns:
            clean_payload: Pure text containing ONLY the dialogue/sign words and natural linebreaks (\\N).
            skeleton: Dictionary storing leading tags, trailing tags, and inline formatting per segment.
        """
        if not raw:
            return "", {"segments": [], "drawings": [], "raw_original": ""}

        # 1. Extract and preserve any vector drawings {\p1}...{\p0}
        drawings = re.findall(r'\{\\p[1-9]\}[^\\{]*\{\\p0\}', raw)
        text_without_drawings = re.sub(r'\{\\p[1-9]\}[^\\{]*\{\\p0\}', '', raw)

        # 2. Split into structural segments by linebreaks to preserve line-specific styling
        raw_segments = re.split(r'\\N|\\n|\n', text_without_drawings)
        clean_segments: List[str] = []
        seg_meta: List[Dict[str, Any]] = []

        for seg in raw_segments:
            # A. Extract leading override tags: e.g. {\pos(100,200)\fad(150,150)\c&HFFFFFF&}
            m_lead = re.match(r'^((?:\{[^{}]*\}\s*)+)(.*)$', seg)
            if m_lead:
                lead_tags = m_lead.group(1).strip()
                rem = m_lead.group(2)
            else:
                lead_tags = ""
                rem = seg

            # B. Extract trailing override tags: e.g. {\i0}
            m_trail = re.search(r'((?:\{[^{}]*\}\s*)+)$', rem)
            if m_trail:
                trail_tags = m_trail.group(1).strip()
                rem = rem[:m_trail.start(1)]
            else:
                trail_tags = ""

            # C. Extract any mid-line internal tags along with proportional positions in clean text
            raw_clean_parts: List[str] = []
            raw_tag_offsets: List[Dict[str, Any]] = []
            clean_pos = 0
            last_idx = 0
            for m_int in re.finditer(r'\{[^{}]*\}', rem):
                chunk = rem[last_idx:m_int.start()]
                raw_clean_parts.append(chunk)
                clean_pos += len(chunk)
                raw_tag_offsets.append({"tag": m_int.group(0), "raw_offset": clean_pos})
                last_idx = m_int.end()
            raw_clean_parts.append(rem[last_idx:])
            untrimmed_clean = "".join(raw_clean_parts)
            lead_ws = len(untrimmed_clean) - len(untrimmed_clean.lstrip())
            clean_text = untrimmed_clean.strip()

            # D. Clean out optional subber note prefixes like 'Sign: ' or '[Sign] ' for pure translation
            m_sign_pref = re.match(r'^(?:\[?Sign\]?|\[?لوحة\]?|\[?Title\]?|\[?عنوان\]?)[\:\s\-]+\s*(.+)$', clean_text, re.IGNORECASE)
            sign_prefix = ""
            prefix_shift = 0
            if m_sign_pref:
                prefix_shift = m_sign_pref.start(1)
                sign_prefix = clean_text[:prefix_shift].strip()
                clean_text = m_sign_pref.group(1).strip()

            total_clean_len = max(1, len(clean_text))
            internal_tags: List[str] = []
            internal_spans: List[Dict[str, Any]] = []
            for tp in raw_tag_offsets:
                tag_str = tp["tag"]
                internal_tags.append(tag_str)
                adj_off = max(0, min(total_clean_len, tp["raw_offset"] - lead_ws - prefix_shift))
                is_closing = bool(re.match(r'^\{\\(?:r|[ibu]0|[cf]s?\s*|\w*0)\}$', tag_str, re.IGNORECASE))
                internal_spans.append({
                    "tag": tag_str,
                    "rel_pos": adj_off / total_clean_len,
                    "is_closing": is_closing,
                })

            clean_segments.append(clean_text)
            seg_meta.append({
                "lead_tags": lead_tags,
                "trail_tags": trail_tags,
                "internal_tags": internal_tags,
                "internal_spans": internal_spans,
                "sign_prefix": sign_prefix,
                "orig_clean": clean_text
            })

        clean_payload = r"\N".join(clean_segments)
        skeleton = {
            "segments": seg_meta,
            "drawings": drawings,
            "raw_original": raw
        }
        return clean_payload, skeleton

    @staticmethod
    def _inject_internal_tags(t_clean: str, seg_meta: Dict[str, Any]) -> str:
        r"""
        Proportionally re-inserts internal override tags (e.g. color highlights {\c&H...&}...{\r},
        inline emphasis {\i1}...{\i0}) at whole-word boundaries in translated text. Idempotent.
        """
        if not t_clean:
            return t_clean

        spans = seg_meta.get("internal_spans")
        if not spans:
            raw_tags = seg_meta.get("internal_tags") or []
            if not raw_tags:
                return t_clean
            n = len(raw_tags)
            spans = [
                {
                    "tag": tag,
                    "rel_pos": (idx + 1) / (n + 1),
                    "is_closing": bool(re.match(r'^\{\\(?:r|[ibu]0)\}$', tag, re.IGNORECASE)) or (n == 2 and idx == 1),
                }
                for idx, tag in enumerate(raw_tags)
            ]

        missing = [sp for sp in spans if sp.get("tag") and sp["tag"] not in t_clean]
        if not missing:
            return t_clean

        words = list(re.finditer(r'\S+', t_clean))
        if not words:
            return t_clean

        text_len = len(t_clean)
        insertions: List[Tuple[int, int, str]] = []
        min_next_offset = 0

        for idx, sp in enumerate(missing):
            tag = sp["tag"]
            rel_pos = float(sp.get("rel_pos", 0.5))
            target_pos = rel_pos * text_len
            is_closing = bool(sp.get("is_closing")) or (len(missing) >= 2 and idx % 2 == 1 and rel_pos > 0.45)

            if is_closing:
                candidates = [w for w in words if w.end() >= min_next_offset]
                chosen = min(candidates or words, key=lambda w: abs(w.end() - target_pos))
                ins_pos = chosen.end()
                min_next_offset = max(min_next_offset, chosen.end())
            else:
                candidates = [w for w in words if w.start() >= min_next_offset]
                chosen = min(candidates or words, key=lambda w: abs(w.start() - target_pos))
                ins_pos = chosen.start()
                min_next_offset = max(min_next_offset, chosen.end())

            insertions.append((ins_pos, idx, tag))

        # Apply insertions cleanly from back to front preserving order for equal positions
        insertions.sort(key=lambda item: (-item[0], -item[1]))
        result = t_clean
        for pos, _, tag in insertions:
            result = result[:pos] + tag + result[pos:]
        return result

    @staticmethod
    def _strip_existing_outer_tags(t_seg: str, lead: str, trail: str) -> str:
        """Strips already-applied outer lead/trail tag sequences so reconstruction is strictly idempotent."""
        res = t_seg.strip()
        if lead and res.startswith(lead):
            res = res[len(lead):].lstrip()
        if trail and res.endswith(trail):
            res = res[:-len(trail)].rstrip()
        return res

    @classmethod
    def reconstruct_effect_text(cls, translated: str, skeleton: Dict[str, Any]) -> str:
        """
        Idempotently reconstructs the full ASS line by re-injecting translated text into
        the original effects skeleton, preserving drawings, outer tags, and mid-line internal tags.
        """
        if not skeleton or "segments" not in skeleton or not skeleton["segments"]:
            return translated

        working_trans = translated or ""
        drawings = [d for d in (skeleton.get("drawings") or []) if d]
        for d in drawings:
            while working_trans.startswith(d):
                working_trans = working_trans[len(d):]
            if d in working_trans:
                working_trans = working_trans.replace(d, "")

        segments = skeleton["segments"]
        trans_segments = re.split(r'\\N|\\n|\n', working_trans)

        rebuilt_segments: List[str] = []

        if len(trans_segments) == len(segments):
            for i, t_seg in enumerate(trans_segments):
                m = segments[i]
                lead = m["lead_tags"]
                trail = m["trail_tags"]
                t_clean = cls._strip_existing_outer_tags(t_seg, lead, trail)
                t_clean = cls._inject_internal_tags(t_clean, m)
                rebuilt_segments.append(f"{lead}{t_clean}{trail}")
        elif len(trans_segments) == 1 and len(segments) > 1:
            # Model collapsed multiple lines into one single line
            lead = segments[0]["lead_tags"]
            trail = segments[-1]["trail_tags"]
            merged_spans: List[Dict[str, Any]] = []
            seg_count = len(segments)
            for si, m in enumerate(segments):
                for sp in (m.get("internal_spans") or []):
                    scaled = dict(sp)
                    scaled["rel_pos"] = (si + float(sp.get("rel_pos", 0.5))) / seg_count
                    merged_spans.append(scaled)
            t_clean = cls._strip_existing_outer_tags(working_trans, lead, trail)
            if merged_spans:
                t_clean = cls._inject_internal_tags(t_clean, {"internal_spans": merged_spans})
            rebuilt_segments.append(f"{lead}{t_clean}{trail}")
        else:
            # Mismatched line count: attach available tags sequentially
            for i, t_seg in enumerate(trans_segments):
                if i < len(segments):
                    m = segments[i]
                    lead = m["lead_tags"]
                    trail = m["trail_tags"]
                    t_clean = cls._strip_existing_outer_tags(t_seg, lead, trail)
                    t_clean = cls._inject_internal_tags(t_clean, m)
                    rebuilt_segments.append(f"{lead}{t_clean}{trail}")
                else:
                    rebuilt_segments.append(t_seg.strip())

        res = r"\N".join(rebuilt_segments)

        # Re-attach each preserved vector drawing block once
        for d in drawings:
            if d not in res:
                res = d + res

        # De-duplicate adjacent identical single or multi-tag clusters (e.g. {\an8}{\an8} -> {\an8})
        res = re.sub(r'(\{\\[^}]+\})\1+', r'\1', res)
        res = re.sub(r'((?:\{\\[^}]+\}){2,})\1+', r'\1', res)

        return res
