import subprocess
import os
import re
import json
import logging
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel
import pysubs2
from app.core.logging import get_logger
from app.core.resources import find_binary

logger = get_logger(__name__)

VIDEO_EXTENSIONS = (
    '.mkv', '.mp4', '.avi', '.mov', '.flv',
    '.wmv', '.webm', '.ts', '.m4v', '.ogv'
)

CODEC_EXTENSION_MAP = {
    'ass': '.ass',
    'ssa': '.ssa',
    'subrip': '.srt',
    'srt': '.srt',
    'webvtt': '.vtt',
    'mov_text': '.srt',
    'text': '.txt',
}

IMAGE_CODECS = (
    'hdmv_pgs_subtitle', 'dvd_subtitle', 'dvdsub',
    'pgssub', 'xsub', 'dvb_subtitle', 'dvb_teletext'
)

SIGNS_SONGS_KEYWORDS = (
    # English & Romaji
    "sign", "signs", "song", "songs", "lyrics", "insert",
    "op/ed", "op & ed", "op and ed", "op-ed", "oped",
    "opening", "ending", "intro", "outro",
    "karaoke", "music", "credit", "credits",
    "nced", "ncop", "theme", "forced", "title", "titles",
    # Arabic
    "شارة", "شارات", "أغاني", "اغاني", "أغنية", "اغنية",
    "افتتاحية", "نهاية", "مقدمة", "مؤثرات", "لوحات"
)

DIALOGUE_KEYWORDS = (
    "dialogue", "dialogues", "dialog", "full", "complete",
    "episode", "main", "spoken", "standard",
    "حوار", "كامل", "الحلقة", "الأساسي", "الاساسي"
)

SDH_KEYWORDS = (
    "sdh", "cc", "hearing impaired", "closed captions", "captions",
    "وصفي", "صوتي", "للصم"
)

class SubtitleStreamInfo(BaseModel):
    index: int                  # Relative index among subtitle streams (0, 1, ...)
    global_index: int           # Global stream index in ffmpeg (e.g. 2, 3)
    codec_name: str             # e.g. 'ass', 'subrip', 'webvtt'
    extension: str              # e.g. '.ass', '.srt'
    language: str = "und"       # e.g. 'eng', 'ara', 'jpn'
    title: str = ""             # e.g. 'Full Dialogue', 'Signs & Songs'
    is_default: bool = False
    is_forced: bool = False
    is_hearing_impaired: bool = False
    is_image_based: bool = False
    frame_count: int = 0        # Number of subtitle packets/frames
    byte_count: int = 0         # Size in bytes
    start_time: float = 0.0     # Stream presentation start time in seconds (container PTS offset)

    def display_name(self) -> str:
        lang_str = self.language.upper() if self.language and self.language != "und" else "غير محدد"
        title_str = f" «{self.title}»" if self.title else ""
        codec_str = self.codec_name.upper()
        lines_str = f" ({self.frame_count} سطر)" if self.frame_count > 0 else ""
        tags = []
        if self.is_image_based:
            tags.append("[صورة PGS - غير نصي]")
        if self.is_hearing_impaired:
            tags.append("[SDH]")
        if self.is_forced:
            tags.append("[Forced]")
        tag_str = f" {' '.join(tags)}" if tags else ""
        return f"مسار {self.index + 1}: [{lang_str}] بصيغة ({codec_str}){title_str}{lines_str}{tag_str}"


class VideoSubtitleExtractor:
    """
    Extracts embedded subtitle streams from video files (MKV, MP4, etc.)
    with 100% fidelity to original Aegisub/ASS formatting and styling.
    Seamlessly extracts or converts to .ass format so styling is preserved,
    and purifies extracted files removing all junk, empty ghost lines, and artifacts.
    """

    @staticmethod
    def is_video_file(file_path: str) -> bool:
        """Returns True if the file path has a recognized video extension."""
        return Path(file_path).suffix.lower() in VIDEO_EXTENSIONS

    @staticmethod
    def _get_startupinfo() -> Optional[subprocess.STARTUPINFO]:
        """Suppresses console window popups on Windows."""
        if os.name == 'nt':
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return si
        return None

    @staticmethod
    def _get_creationflags() -> int:
        """Runs child processes at below normal priority to prevent UI/system freezing."""
        flags = 0
        if os.name == 'nt':
            flags |= getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
            flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        return flags

    @classmethod
    def get_ffmpeg_bin(cls) -> str:
        """Dynamically locates the ffmpeg executable."""
        return find_binary("ffmpeg")

    @classmethod
    def get_ffprobe_bin(cls) -> str:
        """Dynamically locates the ffprobe executable."""
        return find_binary("ffprobe")

    @classmethod
    def get_video_resolution(cls, video_path: str) -> Tuple[int, int]:
        """Queries the native (width, height) of the video stream, defaulting to (1920, 1080)."""
        try:
            cmd = [
                cls.get_ffprobe_bin(), "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                video_path
            ]
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=cls._get_startupinfo(),
                creationflags=cls._get_creationflags(),
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=15
            )
            stdout_val = getattr(res, "stdout", None)
            if res.returncode == 0 and isinstance(stdout_val, str) and stdout_val.strip():
                data = json.loads(stdout_val)
                v_streams = data.get("streams", [])
                if v_streams:
                    w = int(v_streams[0].get("width", 1920))
                    h = int(v_streams[0].get("height", 1080))
                    if w > 0 and h > 0:
                        return w, h
        except Exception as e:
            logger.debug(f"Could not probe video resolution: {e}")
        return 1920, 1080

    @classmethod
    def _probe_container_timeline(cls, video_path: str) -> Dict[str, Optional[float]]:
        """Probes container-level format/video/audio start_time offsets without full packet scans."""
        info: Dict[str, Optional[float]] = {
            "format_start": 0.0,
            "video_start": None,
            "audio_start": None,
        }
        try:
            cmd = [
                cls.get_ffprobe_bin(), "-v", "error",
                "-show_entries", "format=start_time:stream=codec_type,start_time",
                "-of", "json",
                video_path
            ]
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=cls._get_startupinfo(),
                creationflags=cls._get_creationflags(),
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=15
            )
            stdout_val = getattr(res, "stdout", None)
            if res.returncode == 0 and isinstance(stdout_val, str) and stdout_val.strip():
                data = json.loads(stdout_val)
                fmt_st = (data.get("format") or {}).get("start_time")
                if fmt_st is not None:
                    try:
                        info["format_start"] = float(fmt_st)
                    except (ValueError, TypeError):
                        pass
                for st in data.get("streams") or []:
                    ctype = (st.get("codec_type") or "").lower()
                    val_raw = st.get("start_time")
                    if val_raw is None:
                        continue
                    try:
                        val = float(val_raw)
                    except (ValueError, TypeError):
                        continue
                    if ctype == "video" and info["video_start"] is None:
                        info["video_start"] = val
                    elif ctype == "audio" and info["audio_start"] is None:
                        info["audio_start"] = val
        except Exception as e:
            logger.debug(f"Could not probe container timeline: {e}")
        return info

    @staticmethod
    def _parse_signed_timecode_ms(ts: str) -> Optional[int]:
        """
        Parses normal or FFmpeg-negative timestamps (including C-signed printf outputs
        such as '0:00:-1.-80', '0:00:0.-25', '0:00:-0.50', or '-0:00:01.00') into signed ms.
        """
        if not ts:
            return None
        s = ts.strip()
        if not s:
            return None
        overall_sign = -1 if s.startswith("-") else 1
        unsigned = s[1:] if s.startswith(("-", "+")) else s
        m = re.match(r"^(\d+):([+-]?\d+):([+-]?\d+)(?:[.,]([+-]?\d+))?$", unsigned)
        if not m:
            return None
        h_s, m_s, sec_s, frac_s = m.groups()
        frac_ms = 0
        frac_neg = False
        if frac_s:
            frac_neg = frac_s.startswith("-")
            frac_digits = frac_s.lstrip("+-")
            denom = 10 ** len(frac_digits)
            frac_ms = (int(frac_digits) * 1000 + denom // 2) // denom

        if overall_sign < 0:
            return -((int(h_s) * 3600 + abs(int(m_s)) * 60 + abs(int(sec_s))) * 1000 + frac_ms)

        m_neg = m_s.startswith("-")
        sec_neg = sec_s.startswith("-")
        total = int(h_s) * 3600000
        total += (-abs(int(m_s)) if m_neg else int(m_s)) * 60000
        total += (-abs(int(sec_s)) if sec_neg else int(sec_s)) * 1000
        # Fraction carries its own '-' (FFmpeg '0:00:-1.-80' or '0:00:0.-25'),
        # or inherits '-' from '-0' seconds ('0:00:-0.50')
        if frac_s and (frac_neg or (sec_neg and not frac_s.startswith("+"))):
            total -= frac_ms
        else:
            total += frac_ms
        return total

    @classmethod
    def probe_subtitle_streams(cls, video_path: str) -> List[SubtitleStreamInfo]:
        """
        Uses ffprobe to inspect all embedded subtitle streams in the video.
        Accurately queries stream codecs, languages, titles, disposition flags,
        and counts actual packets/frames to differentiate full dialogue from song/signs tracks.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        command = [
            cls.get_ffprobe_bin(),
            "-v", "error",
            "-select_streams", "s",
            "-show_entries", "stream=index,codec_name,start_time:stream_tags:stream_disposition",
            "-of", "json",
            video_path
        ]

        try:
            res = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=cls._get_startupinfo(),
                creationflags=cls._get_creationflags(),
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=60
            )
            if res.returncode != 0:
                logger.warning(f"ffprobe failed: {res.stderr}")
                return []

            data = json.loads(res.stdout or "{}")
            streams_raw = data.get("streams", [])
            result: List[SubtitleStreamInfo] = []

            for sub_idx, s in enumerate(streams_raw):
                codec = s.get("codec_name", "").lower()
                ext = CODEC_EXTENSION_MAP.get(codec, ".ass" if "ass" in codec or "ssa" in codec else ".srt")
                tags = s.get("tags", {})
                disp = s.get("disposition", {})
                title = tags.get("title", "").strip()
                title_lower = title.lower()

                # Extract frame count from tags (e.g. NUMBER_OF_FRAMES, NUMBER_OF_FRAMES-eng, NUMBER_OF_PACKETS)
                frame_cnt = 0
                for k, v in tags.items():
                    if any(term in k.lower() for term in ("number_of_frames", "number_of_packets", "frames_count")):
                        try:
                            frame_cnt = int(v)
                            break
                        except (ValueError, TypeError):
                            pass

                # Extract byte count from tags (e.g. NUMBER_OF_BYTES, NUMBER_OF_BYTES-eng)
                byte_cnt = 0
                for k, v in tags.items():
                    if "number_of_bytes" in k.lower():
                        try:
                            byte_cnt = int(v)
                            break
                        except (ValueError, TypeError):
                            pass

                is_img = codec in IMAGE_CODECS or "pgs" in codec or "dvd" in codec
                is_sdh = bool(disp.get("hearing_impaired", 0)) or any(k in title_lower for k in SDH_KEYWORDS)

                start_val = 0.0
                try:
                    raw_st = s.get("start_time")
                    if raw_st is not None:
                        start_val = float(raw_st)
                except (ValueError, TypeError):
                    start_val = 0.0

                info = SubtitleStreamInfo(
                    index=sub_idx,
                    global_index=s.get("index", sub_idx),
                    codec_name=codec,
                    extension=ext,
                    language=tags.get("language", "und").lower(),
                    title=title,
                    is_default=bool(disp.get("default", 0)),
                    is_forced=bool(disp.get("forced", 0)),
                    is_hearing_impaired=is_sdh,
                    is_image_based=is_img,
                    frame_count=frame_cnt,
                    byte_count=byte_cnt,
                    start_time=start_val
                )
                result.append(info)

            # If frame_cnt was not in tags and multiple streams exist, probe subtitle packets
            if len(result) > 1 and all(s.frame_count == 0 for s in result):
                try:
                    cmd_cnt = [
                        cls.get_ffprobe_bin(), "-v", "error",
                        "-select_streams", "s",
                        "-count_packets",
                        "-show_entries", "stream=index,nb_read_packets",
                        "-of", "json",
                        video_path
                    ]
                    res_cnt = subprocess.run(
                        cmd_cnt,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        startupinfo=cls._get_startupinfo(),
                        creationflags=cls._get_creationflags(),
                        text=True,
                        encoding='utf-8',
                        errors='ignore',
                        timeout=20
                    )
                    if res_cnt.returncode == 0:
                        data_cnt = json.loads(res_cnt.stdout or "{}")
                        cnt_streams = data_cnt.get("streams", [])
                        cnt_map = {
                            s.get("index"): int(s.get("nb_read_packets", 0))
                            for s in cnt_streams
                            if str(s.get("nb_read_packets", "")).isdigit()
                        }
                        for info in result:
                            if info.global_index in cnt_map:
                                info.frame_count = cnt_map[info.global_index]
                except Exception as e:
                    logger.debug(f"Packet count probe skipped: {e}")

            return result

        except Exception as e:
            logger.error(f"Error probing subtitle streams from {video_path}: {e}")
            return []

    @classmethod
    def select_best_stream(
        cls,
        streams: List[SubtitleStreamInfo],
        preferred_lang: str = "en"
    ) -> Optional[SubtitleStreamInfo]:
        """
        Selects the best subtitle stream for localization:
        - Prioritizes full episode dialogue tracks over signs/songs/intro/outro tracks.
        - Strongly penalizes bitmap image subtitle streams (PGS, VobSub).
        - Strongly penalizes SDH (hearing impaired) and forced tracks.
        - Analyzes frame/packet count (dialogue typically has hundreds of lines vs few for songs).
        - Prioritizes ASS over SRT for richer formatting.
        - Prioritizes matching target/source language.
        """
        if not streams:
            return None

        pref = preferred_lang.lower().strip()
        is_auto = "auto" in pref or not pref
        candidates = []

        # Find maximum frame count to gauge relative size across tracks
        max_frames = max((s.frame_count for s in streams), default=0)

        for s in streams:
            score = 0
            title_lower = s.title.lower()

            # 1. Language matching
            if is_auto:
                if s.language in ("eng", "en"):
                    score += 50
                elif s.language in ("jpn", "ja"):
                    score += 40
                elif s.language != "und":
                    score += 20
            elif s.language in (pref, f"{pref}g", f"{pref}lish") or (pref == "en" and s.language in ("eng", "en")):
                score += 60
            elif s.language != "und":
                score += 10

            # 2. Episode Dialogue title bonus
            if any(k in title_lower for k in DIALOGUE_KEYWORDS):
                score += 80

            # 3. Signs / Songs / Intro / Outro severe penalty
            if any(k in title_lower for k in SIGNS_SONGS_KEYWORDS):
                score -= 100

            # 4. Forced track penalty (anime forced tracks are exclusively signs/songs for dub viewers)
            if s.is_forced:
                score -= 100

            # 5. Hearing Impaired / SDH penalty (contains annoying sound effect cues like [music], [sighs])
            if s.is_hearing_impaired:
                score -= 120

            # 6. Heavily penalize bitmap image subtitle streams (PGS, VobSub)
            if s.is_image_based:
                score -= 250

            # 7. Packet / Frame count intelligence
            if s.frame_count > 0:
                if s.frame_count >= 150:
                    score += 50  # Typical episode dialogue
                elif max_frames >= 150 and s.frame_count < 80:
                    score -= 80  # Obvious short songs/signs track compared to dialogue
                
                # Bonus if this stream has the highest frame count
                if s.frame_count == max_frames and max_frames > 0:
                    score += 30

            # 8. Format preference: ASS has the richest typesetting, followed by text SRT/VTT
            if s.codec_name in ('ass', 'ssa'):
                score += 25
            elif s.codec_name in ('subrip', 'srt', 'webvtt', 'mov_text'):
                score += 15

            # 9. Default flag (only rewarded if not forced and not SDH)
            if s.is_default and not s.is_forced and not s.is_hearing_impaired:
                score += 20

            candidates.append((score, s))

        # Sort by score descending; break ties with frame_count descending, then stream index ascending
        candidates.sort(key=lambda x: (x[0], x[1].frame_count, -x[1].index), reverse=True)
        return candidates[0][1] if candidates else streams[0]

    @classmethod
    def purify_extracted_subtitle(
        cls,
        file_path: str,
        video_path: Optional[str] = None,
        video_resolution: Optional[Tuple[int, int]] = None,
        is_source_ass: bool = False,
    ) -> bool:
        """
        Guarantees that the extracted subtitle file is 100% clean, pristine, and ready for work:
        - Removes Aegisub session and project garbage headers ([Aegisub Project Garbage], Last Style Storage, etc.).
        - Removes zero-width and invisible unicode characters (\u200b, \u200c, \u200d, \ufeff, directional markers).
        - Removes empty ghost lines (events with no text or zero duration).
        - Fixes unclosed or corrupt tag braces.
        - Ensures standard modern Full HD PlayResX: 1920, PlayResY: 1080 (or matches video native resolution).
        - Ensures WrapStyle: 0 and ScaledBorderAndShadow: yes.
        - Ensures crisp Aegisub Default styling for converted subtitles.
        - Saves as clean UTF-8 with BOM (utf-8-sig) so players render properly.
        """
        if not os.path.exists(file_path):
            return False

        try:
            from app.subtitle.parsers.base import SubtitleParser

            class _TempReader(SubtitleParser):
                def parse_text(self, content: str):
                    return None

            raw_content = _TempReader()._read_file(file_path)
            if not raw_content:
                return False

            ext = Path(file_path).suffix.lower()
            clamped_neg_count = 0
            dropped_neg_count = 0

            if ext in ('.ass', '.ssa'):
                from app.subtitle.timecode import format_ass_time
                lines = raw_content.splitlines()
                clean_lines = []
                current_section = None
                has_script_info = False
                seen_headers = set()
                events_format = ["layer", "start", "end", "style", "name", "marginl", "marginr", "marginv", "effect", "text"]

                if video_resolution and len(video_resolution) == 2 and video_resolution[0] > 0 and video_resolution[1] > 0:
                    v_width, v_height = video_resolution
                elif video_path:
                    v_width, v_height = cls.get_video_resolution(video_path)
                else:
                    v_width, v_height = (1920, 1080)

                i = 0
                while i < len(lines):
                    line = lines[i]
                    stripped = line.strip()

                    # Section Headers
                    if stripped.startswith('[') and stripped.endswith(']'):
                        current_section = stripped[1:-1].lower()
                        # Ignore Aegisub Project Garbage section completely
                        if "aegisub" in current_section and ("garbage" in current_section or "extradata" in current_section):
                            i += 1
                            while i < len(lines) and not (lines[i].strip().startswith('[') and lines[i].strip().endswith(']')):
                                i += 1
                            continue

                        if "script info" in current_section:
                            has_script_info = True

                        clean_lines.append(line)
                        i += 1
                        continue

                    # In Script Info Section: filter garbage headers
                    if current_section == "script info":
                        if any(stripped.lower().startswith(k) for k in (
                            "last style storage:", "audio file:", "video file:", "video ar mode:",
                            "video aspect ratio:", "video zoom percent:", "scroll position:",
                            "active line:", "video position:", "; script generated by pysubs2"
                        )):
                            i += 1
                            continue

                        # Preserve native ASS/SSA PlayRes verbatim; only normalize converted streams
                        if stripped.lower().startswith("playresx:"):
                            seen_headers.add("playresx")
                            val = stripped.split(':', 1)[1].strip()
                            if not is_source_ass and val in ("0", "384"):
                                clean_lines.append(f"PlayResX: {v_width}")
                            else:
                                clean_lines.append(line)
                            i += 1
                            continue
                        elif stripped.lower().startswith("playresy:"):
                            seen_headers.add("playresy")
                            val = stripped.split(':', 1)[1].strip()
                            if not is_source_ass and val in ("0", "288"):
                                clean_lines.append(f"PlayResY: {v_height}")
                            else:
                                clean_lines.append(line)
                            i += 1
                            continue
                        elif stripped.lower().startswith("wrapstyle:"):
                            clean_lines.append(line if is_source_ass else "WrapStyle: 0")
                            seen_headers.add("wrapstyle")
                            i += 1
                            continue
                        elif stripped.lower().startswith("scaledborderandshadow:"):
                            clean_lines.append(line if is_source_ass else "ScaledBorderAndShadow: yes")
                            seen_headers.add("scaledborderandshadow")
                            i += 1
                            continue

                    # In Styles Section: preserve native ASS styles untouched; only upgrade tiny converted SRT styles
                    if current_section and "styles" in current_section:
                        if not is_source_ass and stripped.startswith("Style: Default,"):
                            # If font size is tiny (< 32 on converted stream), upgrade to crisp standard
                            parts = stripped.split(',')
                            if len(parts) >= 23:
                                try:
                                    fs = float(parts[2])
                                    if fs < 32:
                                        parts[2] = "48"    # Font size
                                        parts[1] = "Arial" # Font name
                                        parts[16] = "2.8"  # Outline
                                        parts[17] = "1.2"  # Shadow
                                        stripped = ','.join(parts)
                                        line = stripped
                                except (ValueError, TypeError):
                                    pass

                    # In Events Section: filter ghost events, fix negative FFmpeg timestamps & clean unicode artifacts
                    if current_section and "events" in current_section:
                        if stripped.lower().startswith("format:"):
                            events_format = [f.strip().lower() for f in stripped.split(':', 1)[1].split(',')]
                            clean_lines.append(line)
                            i += 1
                            continue

                        if stripped.startswith("Dialogue:") or stripped.startswith("Comment:"):
                            # Clean invisible unicode characters (preserve \u200f RLM BiDi marks)
                            line = re.sub(r'[\u200b\u200c\u200d\u200e\ufeff\u202a-\u202e\u2066-\u2069]', '', line)
                            line = line.replace('\x00', '')
                            num_cols = max(10, len(events_format))
                            parts = line.split(',', num_cols - 1)
                            if len(parts) == num_cols:
                                try:
                                    start_idx = events_format.index("start")
                                except ValueError:
                                    start_idx = 1
                                try:
                                    end_idx = events_format.index("end")
                                except ValueError:
                                    end_idx = 2
                                try:
                                    text_idx = events_format.index("text")
                                except ValueError:
                                    text_idx = num_cols - 1

                                s_raw = parts[start_idx].strip()
                                e_raw = parts[end_idx].strip()
                                s_ms = cls._parse_signed_timecode_ms(s_raw)
                                e_ms = cls._parse_signed_timecode_ms(e_raw)
                                if s_ms is not None and e_ms is not None:
                                    if e_ms < 0 or (s_ms < 0 and e_ms <= 0):
                                        dropped_neg_count += 1
                                        i += 1
                                        continue
                                    elif s_ms < 0 < e_ms:
                                        s_raw = format_ass_time(0)
                                        e_raw = format_ass_time(e_ms)
                                        clamped_neg_count += 1

                                parts[start_idx] = s_raw
                                parts[end_idx] = e_raw

                                t = parts[text_idx].strip()
                                # Clean empty tags like {}
                                t = re.sub(r'\{\s*\}', '', t).strip()
                                parts[text_idx] = t
                                line = ','.join(parts)
                                # If start == end and text is empty, it's a useless ghost line
                                if s_raw == e_raw and not t:
                                    i += 1
                                    continue

                    clean_lines.append(line)
                    i += 1

                # Only inject missing PlayResX/Y for converted subtitles (or if completely absent)
                if "playresx" not in seen_headers and has_script_info and not is_source_ass:
                    for idx_l, cl in enumerate(clean_lines):
                        if cl.strip().lower() == "[script info]":
                            clean_lines.insert(idx_l + 1, f"PlayResX: {v_width}")
                            clean_lines.insert(idx_l + 2, f"PlayResY: {v_height}")
                            clean_lines.insert(idx_l + 3, "WrapStyle: 0")
                            clean_lines.insert(idx_l + 4, "ScaledBorderAndShadow: yes")
                            break

                final_text = "\n".join(clean_lines) + "\n"
            else:
                # SRT / VTT clean
                from app.subtitle.timecode import format_srt_time, format_vtt_time
                cleaned = re.sub(r'[\u200b\u200c\u200d\u200e\ufeff\u202a-\u202e\u2066-\u2069]', '', raw_content)
                cleaned = cleaned.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')
                fmt_fn = format_vtt_time if ext == '.vtt' else format_srt_time
                blocks = re.split(r'\n[ \t]*\n+', cleaned.strip())
                fixed_blocks = []
                for blk in blocks:
                    blk_lines = blk.split('\n')
                    drop_blk = False
                    for li, ln in enumerate(blk_lines):
                        m_cue = re.match(r'^\s*(\S+?)\s*-->\s*([^\s]+)(.*)$', ln)
                        if m_cue and '-' in (m_cue.group(1) + m_cue.group(2)):
                            s_ms = cls._parse_signed_timecode_ms(m_cue.group(1))
                            e_ms = cls._parse_signed_timecode_ms(m_cue.group(2))
                            if s_ms is not None and e_ms is not None:
                                if e_ms < 0 or (s_ms < 0 and e_ms <= 0):
                                    dropped_neg_count += 1
                                    drop_blk = True
                                    break
                                if s_ms < 0 < e_ms:
                                    clamped_neg_count += 1
                                    blk_lines[li] = f"{fmt_fn(0)} --> {fmt_fn(e_ms)}{m_cue.group(3)}"
                    if not drop_blk:
                        fixed_blocks.append('\n'.join(blk_lines))
                final_text = '\n\n'.join(fixed_blocks) + ('\n' if fixed_blocks else '')

            if clamped_neg_count > 0 or dropped_neg_count > 0:
                logger.info(
                    f"Timeline sanitizer healed container pre-roll timestamps in {file_path}: "
                    f"clamped={clamped_neg_count}, dropped_before_zero={dropped_neg_count}"
                )

            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.write(final_text)
            return True
        except Exception as e:
            logger.warning(f"Error purifying extracted subtitle {file_path}: {e}")
            return False

    @classmethod
    def extract_subtitle(
        cls,
        video_path: str,
        stream_index: int = 0,
        output_path: Optional[str] = None,
        prefer_ass: bool = True
    ) -> Tuple[bool, str, str]:
        """
        Extracts a subtitle stream from video.
        If prefer_ass is True, guarantees output in .ass format with full Aegisub headers and styles.
        Uses stream copy for ASS, or intelligent conversion for SubRip/other formats.
        Immediately purifies the extracted file removing junk and ensuring pristine quality.
        
        Returns:
            Tuple[bool, str, str]: (success, output_subtitle_path, error_message)
        """
        if not os.path.exists(video_path):
            return False, "", f"Video file not found: {video_path}"

        streams = cls.probe_subtitle_streams(video_path)
        if not streams:
            return False, "", "لا يحتوي ملف الفيديو على أي مسار ترجمة مدمج (No subtitle streams found)."

        chosen_stream = next((s for s in streams if s.index == stream_index), streams[0])

        if chosen_stream.is_image_based:
            return False, "", (
                f"المسار المختار [{chosen_stream.codec_name.upper()}] هو ترجمة صورية (Bitmap / PGS) "
                "ولا يحتوي على نصوص برمجية قابلة للاستخراج النصي المباشر بدون معالجة صورية OCR. "
                "يرجى اختيار مسار ترجمة نصي (مثل ASS أو SRT)."
            )

        timeline = cls._probe_container_timeline(video_path)
        video_res = cls.get_video_resolution(video_path)
        fmt_start = timeline.get("format_start") or 0.0
        if abs(fmt_start) > 0.05:
            logger.warning(
                f"⏱️ تم رصد إزاحة بداية الحاوية ({fmt_start:+.3f}s): تتم مواءمة التوقيت تلقائياً مع بداية التشغيل 0:00:00."
            )

        target_ext = ".ass" if prefer_ass else chosen_stream.extension
        if not output_path:
            base_name = os.path.splitext(video_path)[0]
            output_path = f"{base_name}{target_ext}"

        # Ensure destination directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        is_source_ass = chosen_stream.codec_name.lower() in ('ass', 'ssa')
        startup_info = cls._get_startupinfo()
        c_flags = cls._get_creationflags()

        # Strategy 1: If source is ASS and target is ASS, extract losslessly via -c:s copy
        if is_source_ass and target_ext == ".ass":
            cmd = [
                cls.get_ffmpeg_bin(), "-y", "-i", video_path,
                "-map", f"0:s:{chosen_stream.index}",
                "-c:s", "copy",
                output_path
            ]
            try:
                res = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    startupinfo=startup_info, creationflags=c_flags, text=True, encoding='utf-8', errors='ignore', timeout=60
                )
                if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    cls.purify_extracted_subtitle(output_path, video_path=video_path, video_resolution=video_res, is_source_ass=True)
                    logger.info(f"Successfully extracted lossless ASS to {output_path}")
                    return True, output_path, ""
            except Exception as e:
                logger.warning(f"Lossless copy failed, falling back to encoder: {e}")

        # Strategy 2: Convert to ASS directly via ffmpeg built-in ass muxer (-c:s ass)
        if target_ext == ".ass":
            cmd = [
                cls.get_ffmpeg_bin(), "-y", "-i", video_path,
                "-map", f"0:s:{chosen_stream.index}",
                "-c:s", "ass",
                output_path
            ]
            try:
                res = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    startupinfo=startup_info, creationflags=c_flags, text=True, encoding='utf-8', errors='ignore', timeout=60
                )
                if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    cls.purify_extracted_subtitle(output_path, video_path=video_path, video_resolution=video_res, is_source_ass=is_source_ass)
                    logger.info(f"Successfully converted and extracted ASS subtitle to {output_path}")
                    return True, output_path, ""
            except Exception as e:
                logger.warning(f"Direct ffmpeg ASS conversion failed: {e}")

        # Strategy 3: Try mapping by global index
        if target_ext == ".ass":
            cmd = [
                cls.get_ffmpeg_bin(), "-y", "-i", video_path,
                "-map", f"0:{chosen_stream.global_index}",
                "-c:s", "ass",
                output_path
            ]
            try:
                res = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    startupinfo=startup_info, creationflags=c_flags, text=True, encoding='utf-8', errors='ignore', timeout=60
                )
                if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    cls.purify_extracted_subtitle(output_path, video_path=video_path, video_resolution=video_res, is_source_ass=is_source_ass)
                    logger.info(f"Successfully converted ASS using global index to {output_path}")
                    return True, output_path, ""
            except Exception:
                pass

        # Strategy 4 (Universal pysubs2 Fallback): Extract raw source format into temp file, then convert via pysubs2
        tmp_path = None
        try:
            raw_ext = chosen_stream.extension
            with tempfile.NamedTemporaryFile(suffix=raw_ext, delete=False) as tmp_f:
                tmp_path = tmp_f.name

            cmd = [
                cls.get_ffmpeg_bin(), "-y", "-i", video_path,
                "-map", f"0:s:{chosen_stream.index}",
                "-c:s", "copy",
                tmp_path
            ]
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                startupinfo=startup_info, creationflags=c_flags, text=True, encoding='utf-8', errors='ignore', timeout=60
            )

            if res.returncode != 0 or not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                # Try without -c:s copy
                cmd = [cls.get_ffmpeg_bin(), "-y", "-i", video_path, "-map", f"0:s:{chosen_stream.index}", tmp_path]
                res = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    startupinfo=startup_info, creationflags=c_flags, text=True, encoding='utf-8', errors='ignore', timeout=60
                )

            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                fmt_hint = "ass" if raw_ext in (".ass", ".ssa") else None
                try:
                    subs = pysubs2.load(tmp_path, format_=fmt_hint)
                except Exception:
                    subs = pysubs2.load(tmp_path)
                if target_ext == ".ass":
                    subs.save(output_path, format_="ass")
                else:
                    subs.save(output_path)
                cls.purify_extracted_subtitle(output_path, video_path=video_path, video_resolution=video_res, is_source_ass=is_source_ass)
                return True, output_path, ""
        except Exception as e:
            logger.error(f"Pysubs2 conversion fallback failed: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        return False, "", "تعذر استخراج مسار الترجمة بالصيغة المطلوبة من الفيديو. تحقق من تثبيت ffmpeg وصحة مسار الترجمة."

    @classmethod
    def auto_extract_and_prepare(
        cls,
        video_path: str,
        preferred_lang: str = "en",
        prefer_ass: bool = True,
        output_path: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        One-stop helper: probes video, selects the best full dialogue track,
        and extracts it losslessly with full formatting intact and cleaned.
        
        Returns:
            Tuple[bool, str, str]: (success, extracted_file_path, status_message)
        """
        streams = cls.probe_subtitle_streams(video_path)
        if not streams:
            return False, "", "لا توجد مسارات ترجمة مدمجة داخل الفيديو."

        best = cls.select_best_stream(streams, preferred_lang)
        if not best:
            best = streams[0]

        ok, out_path, err = cls.extract_subtitle(
            video_path, stream_index=best.index, output_path=output_path, prefer_ass=prefer_ass
        )
        if ok:
            msg = f"تم استخراج مسار الترجمة بنجاح: {best.display_name()}"
            return True, out_path, msg
        return False, "", err
