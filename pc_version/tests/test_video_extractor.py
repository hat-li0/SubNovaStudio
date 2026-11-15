import os
import pytest
import subprocess
import tempfile
from pathlib import Path
from app.subtitle.video_extractor import VideoSubtitleExtractor, SubtitleStreamInfo

def test_is_video_file():
    assert VideoSubtitleExtractor.is_video_file("movie.mkv") is True
    assert VideoSubtitleExtractor.is_video_file("video.MP4") is True
    assert VideoSubtitleExtractor.is_video_file("clip.avi") is True
    assert VideoSubtitleExtractor.is_video_file("sub.ass") is False
    assert VideoSubtitleExtractor.is_video_file("sub.srt") is False
    assert VideoSubtitleExtractor.is_video_file("data.json") is False

def test_select_best_stream():
    streams = [
        SubtitleStreamInfo(index=0, global_index=2, codec_name="ass", extension=".ass", language="eng", title="Signs & Songs"),
        SubtitleStreamInfo(index=1, global_index=3, codec_name="ass", extension=".ass", language="eng", title="Full Dialogue", is_default=True),
        SubtitleStreamInfo(index=2, global_index=4, codec_name="subrip", extension=".srt", language="fre", title="French"),
    ]
    best = VideoSubtitleExtractor.select_best_stream(streams, preferred_lang="en")
    assert best is not None
    assert best.index == 1
    assert "Dialogue" in best.title


def test_select_best_stream_songs_and_intro_penalty():
    # Case 1: "Song" singular in title vs generic title
    streams1 = [
        SubtitleStreamInfo(index=0, global_index=2, codec_name="ass", extension=".ass", language="eng", title="English [Song]", frame_count=30),
        SubtitleStreamInfo(index=1, global_index=3, codec_name="ass", extension=".ass", language="eng", title="English", frame_count=350),
    ]
    assert VideoSubtitleExtractor.select_best_stream(streams1, "en").index == 1

    # Case 2: OP/ED vs Episode
    streams2 = [
        SubtitleStreamInfo(index=0, global_index=2, codec_name="ass", extension=".ass", language="eng", title="OP/ED", frame_count=25),
        SubtitleStreamInfo(index=1, global_index=3, codec_name="ass", extension=".ass", language="eng", title="Episode 01", frame_count=420),
    ]
    assert VideoSubtitleExtractor.select_best_stream(streams2, "en").index == 1

    # Case 3: Intro & Outro vs Main Spoken Dialogue
    streams3 = [
        SubtitleStreamInfo(index=0, global_index=2, codec_name="ass", extension=".ass", language="eng", title="Intro & Outro", frame_count=40),
        SubtitleStreamInfo(index=1, global_index=3, codec_name="ass", extension=".ass", language="eng", title="Main Dialogue", frame_count=390),
    ]
    assert VideoSubtitleExtractor.select_best_stream(streams3, "en").index == 1

    # Case 4: Forced signs track with no title vs Full Dialogue track with no title
    streams4 = [
        SubtitleStreamInfo(index=0, global_index=2, codec_name="ass", extension=".ass", language="eng", title="", is_forced=True, frame_count=20),
        SubtitleStreamInfo(index=1, global_index=3, codec_name="ass", extension=".ass", language="eng", title="", is_forced=False, frame_count=480),
    ]
    assert VideoSubtitleExtractor.select_best_stream(streams4, "en").index == 1

    # Case 5: Arabic signs/songs vs Arabic dialogue
    streams5 = [
        SubtitleStreamInfo(index=0, global_index=2, codec_name="ass", extension=".ass", language="ara", title="شارات وأغاني"),
        SubtitleStreamInfo(index=1, global_index=3, codec_name="ass", extension=".ass", language="ara", title="الحوار الكامل"),
    ]
    assert VideoSubtitleExtractor.select_best_stream(streams5, "ar").index == 1

    # Case 6: Real anime case (Fate Extra style): Track 0 is Signs (forced), Track 1 is Dialogue (default)
    streams6 = [
        SubtitleStreamInfo(index=0, global_index=3, codec_name="ass", extension=".ass", language="eng", title="Signs (Chyuu/hchcsen)", is_forced=True, is_default=False, frame_count=1574),
        SubtitleStreamInfo(index=1, global_index=4, codec_name="ass", extension=".ass", language="eng", title="Dialogue (Chyuu/hchcsen)", is_forced=False, is_default=True, frame_count=1789),
    ]
    assert VideoSubtitleExtractor.select_best_stream(streams6, "Auto Detect").index == 1

def test_extract_subtitle_from_real_mkv():
    # Create a temporary MKV video with embedded ASS subtitle using ffmpeg
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir_path = Path(tmpdir)
        ass_path = tmp_dir_path / "sample.ass"
        mkv_path = tmp_dir_path / "test_video.mkv"
        out_sub_path = tmp_dir_path / "extracted.ass"

        sample_ass_content = (
            "[Script Info]\n"
            "Title: Test Subtitle\n"
            "ScriptType: v4.00+\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,28,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{\\an8\\c&H00FFFF&}Hello, this is a test subtitle line!\n"
        )
        ass_path.write_text(sample_ass_content, encoding="utf-8")

        # Generate a 1-second dummy video with embedded ASS subtitle stream
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=160x120:d=1",
            "-i", str(ass_path),
            "-c:v", "libx264",
            "-c:s", "copy",
            str(mkv_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            pytest.skip("ffmpeg video generation not available in test environment")

        # 1. Test probing streams
        streams = VideoSubtitleExtractor.probe_subtitle_streams(str(mkv_path))
        assert len(streams) >= 1
        assert streams[0].codec_name in ("ass", "ssa")

        # 2. Test lossless extraction (-c:s copy)
        ok, extracted_path, err = VideoSubtitleExtractor.extract_subtitle(str(mkv_path), stream_index=0, output_path=str(out_sub_path))
        assert ok is True
        assert os.path.exists(extracted_path)
        
        extracted_content = Path(extracted_path).read_text(encoding="utf-8", errors="ignore")
        assert "ScriptType: v4.00+" in extracted_content
        assert r"{\an8\c&H00FFFF&}Hello, this is a test subtitle line!" in extracted_content
