import pytest
from app.translation.response_parser import ResponseParser
from app.translation.batcher import TokenBatcher
from app.quality.healer import SubtitleHealer
from app.models.subtitle import SubtitleEvent


def test_response_parser_direct_and_relative():
    parser = ResponseParser()

    # 1. Direct ID matching
    raw_direct = "[101] النص الأول\n[102] النص الثاني"
    res_direct = parser.parse_response(raw_direct, [101, 102])
    assert res_direct == {101: "النص الأول", 102: "النص الثاني"}

    # 2. Relative renumbering: LLM renumbers from 1 to N when given non-contiguous or offset IDs
    raw_relative = "[1] النص الأول\n[2] النص الثاني\n[3] النص الثالث"
    res_relative = parser.parse_response(raw_relative, [9, 10, 11])
    assert res_relative == {9: "النص الأول", 10: "النص الثاني", 11: "النص الثالث"}

    # 3. Relative renumbering with non-contiguous IDs (e.g. 28, 1033)
    raw_scattered = "1. مرحباً\n2. إلى اللقاء"
    res_scattered = parser.parse_response(raw_scattered, [28, 1033])
    assert res_scattered == {28: "مرحباً", 1033: "إلى اللقاء"}

    # 4. Zero-based indexing: LLM numbers from 0 to N-1
    raw_zero = "[0] مرحباً\n[1] مع السلامة"
    res_zero = parser.parse_response(raw_zero, [50, 51])
    assert res_zero == {50: "مرحباً", 51: "مع السلامة"}

    # 5. Think tag stripping (DeepSeek / Reasoning models)
    raw_think = "<think>\nThinking about the translation...\n</think>[1] أهلاً بك"
    res_think = parser.parse_response(raw_think, [1])
    assert res_think == {1: "أهلاً بك"}

    # 6. Unclosed think tag (truncated response)
    raw_unclosed = "<think>Still thinking and cut off"
    res_unclosed = parser.parse_response(raw_unclosed, [1])
    assert res_unclosed == {}

    # 7. False positive filtering: timestamps or random numbers shouldn't become IDs
    raw_with_timestamp = "12:05:00 Scene Intro\n[1033] أهلاً\n[1205] وداعاً"
    res_timestamp = parser.parse_response(raw_with_timestamp, [1033, 1205])
    assert res_timestamp == {1033: "أهلاً", 1205: "وداعاً"}
    assert 12 not in res_timestamp


def test_token_batcher_adaptive_local_sizing():
    batcher = TokenBatcher(max_events=30)
    events = [SubtitleEvent(id=i, text=f"Dialogue line {i}") for i in range(1, 41)]

    # Standard (Cloud) batching: max_events up to 30
    cloud_batches = batcher.create_batches(events, is_local=False)
    assert len(cloud_batches[0]) == 30

    # Local model batching: adaptive limit of 12 for translation
    local_batches = batcher.create_batches(events, is_local=True)
    assert len(local_batches[0]) == 12
    assert len(local_batches[1]) == 12

    # Improvement local batching: limit of 8
    improve_batches = batcher.create_batches(events, for_improvement=True, is_local=True)
    assert len(improve_batches[0]) == 8


def test_healer_think_and_notes_purification():
    # 1. Stripping think tags
    with_think = "<think>Analyze context</think>مرحباً بك يا صديقي"
    assert SubtitleHealer.heal(with_think) == "مرحباً بك يا صديقي"

    # 2. Stripping translator notes
    with_note = "أهلاً وسهلاً (ملاحظة: هذا ترحيب تقليدي)"
    assert SubtitleHealer.heal(with_note) == "أهلاً وسهلاً"

    with_en_note = "Welcome to our city! - Note: referring to Tokyo"
    assert SubtitleHealer.heal(with_en_note) == "Welcome to our city!"

    # 3. Stripping markdown headers
    with_header = "### الترجمة:\nمرحباً بالعالم"
    assert "###" not in SubtitleHealer.heal(with_header)

    # 4. Stripping Chinese/Asian hallucinated characters from Arabic dialogue
    with_cjk = "الجوارح真实性 من الغضب"
    assert "真实性" not in SubtitleHealer.heal(with_cjk)
    assert "الجوارح من الغضب" in SubtitleHealer.heal(with_cjk)


def test_validator_detects_chinese_and_foreign_hallucinations():
    from app.translation.validator import PipelineValidator
    val = PipelineValidator()
    events = [SubtitleEvent(id=1, text="Hello"), SubtitleEvent(id=2, text="World")]
    
    # Text contains Chinese characters (like Phi-4 output)
    bad_output = {1: "الجوارح真实性 من الغضب", 2: "العالم"}
    is_valid, blocking = val.validate_batch_output(bad_output, events)
    assert not is_valid
    assert any("Hallucination" in b for b in blocking)
    
    # Text completely untranslated or without Arabic
    non_ar = {1: "Just English text", 2: "مرحبا"}
    is_valid2, blocking2 = val.validate_batch_output(non_ar, events)
    assert not is_valid2
    assert any("Untranslated" in b or "Non-Arabic" in b for b in blocking2)


def test_prefix_and_parentheses_notes_removal():
    parser = ResponseParser()
    
    # 1. Strip translator prefixes
    assert parser.clean_text_item("المترجم: مرحباً بك يا صديقي") == "مرحباً بك يا صديقي"
    assert parser.clean_text_item("المنظر العربي المترجم: مرحباً") == "مرحباً"
    assert parser.clean_text_item("المصقول النهائي: أهلاً وسهلاً") == "أهلاً وسهلاً"
    assert parser.clean_text_item("تقرير التعديلات: شكراً لك") == "شكراً لك"

    # 2. Strip parenthesized commentary / gender notes
    assert parser.clean_text_item("نعم، لا تقلقي (المخاطب فتاة)") == "نعم، لا تقلقي"
    assert parser.clean_text_item("أنا قادم فوراً (المتحدث ذكر)") == "أنا قادم فوراً"
    assert parser.clean_text_item("أنا بخير (تم التصحيح)") == "أنا بخير"

    # 3. Preserve legitimate ASS tags with parentheses like {\pos(960,540)}
    ass_line = r"{\pos(960,540)\i1}انظر إلى هناك!{\i0}"
    assert parser.clean_text_item(ass_line) == ass_line


