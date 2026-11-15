import pytest
from app.translation.response_parser import ResponseParser
from app.translation.context import ContextBuilder
from app.models.subtitle import SubtitleEvent
from app.translation.prompts import PromptBuilder


def test_response_parser_handles_allam_empty_brackets():
    """Verify that when ALLaM outputs [ ] without IDs, ResponseParser accurately maps them sequentially."""
    parser = ResponseParser()
    expected_ids = [2045, 2046, 2047, 2048, 2049]

    # ALLaM output with empty brackets [ ]
    raw_response = """
    [ ] ضربة نيزك.
    [ ] إنه نيزك صغير،
    [ ] لكن طاقة سقوطه من السماء بسرعة عالية هائلة.
    [ ] أستطيع على الأرجح القضاء عليهم جميعًا.
    [ ] هذا مذهل حقًا.
    """

    res = parser.parse_response(raw_response, expected_ids)
    assert len(res) == 5
    assert res[2045] == "ضربة نيزك."
    assert res[2046] == "إنه نيزك صغير،"
    assert res[2047] == "لكن طاقة سقوطه من السماء بسرعة عالية هائلة."
    assert res[2048] == "أستطيع على الأرجح القضاء عليهم جميعًا."
    assert res[2049] == "هذا مذهل حقًا."


def test_response_parser_handles_empty_brackets_with_extra_context():
    """Verify that when ALLaM translates extra context lines at the end, the target lines are mapped properly."""
    parser = ResponseParser()
    expected_ids = [10, 11, 12]

    # 3 target lines + 2 extra lines that ALLaM translated from upcoming context
    raw_response = """
    [ ] السطر الأول المترجم
    [ ] السطر الثاني المترجم
    [ ] السطر الثالث المترجم
    ### سياق الحوار اللاحق كمرجع:
    (سياق) سياق إضافي لا نريده
    (سياق) سياق آخر
    """

    res = parser.parse_response(raw_response, expected_ids)
    assert len(res) == 3
    assert res[10] == "السطر الأول المترجم"
    assert res[11] == "السطر الثاني المترجم"
    assert res[12] == "السطر الثالث المترجم"


def test_response_parser_handles_partial_empty_bracket_lines():
    """Verify that when ALLaM outputs fewer lines than requested, the available lines are mapped sequentially."""
    parser = ResponseParser()
    expected_ids = [101, 102, 103, 104, 105]

    # Model returned only 3 lines
    raw_response = """
    [ ] ضربة سيف قوية
    [ ] دفاع متين
    [ ] هجوم مضاد
    """

    res = parser.parse_response(raw_response, expected_ids)
    assert len(res) == 3
    assert res[101] == "ضربة سيف قوية"
    assert res[102] == "دفاع متين"
    assert res[103] == "هجوم مضاد"
    assert 104 not in res
    assert 105 not in res


def test_context_builder_formatting():
    """Verify that ContextBuilder formats IDs correctly and consistently."""
    cb = ContextBuilder()
    events = [
        SubtitleEvent(id=1, original_text="One"),
        SubtitleEvent(id=51, original_text="Fifty one"),
        SubtitleEvent(id=2045, original_text="Two thousand forty five"),
    ]

    ctx = cb.build_context(events, events)
    assert "[001] One" in ctx["current_text"]
    assert "[051] Fifty one" in ctx["current_text"]
    assert "[2045] Two thousand forty five" in ctx["current_text"]


def test_prompt_builder_allam_specific_rules():
    """Verify that PromptBuilder for ALLaM contains pure Arabic instructions with no confusing [ID] placeholder."""
    pb = PromptBuilder()
    messages = pb.build_prompt(
        source_lang="English",
        target_lang="Arabic",
        current_subtitles="[51] Hello",
        model_name="allam-7b-arabic-sft"
    )

    sys_content = messages[0].content
    user_content = messages[1].content

    # Should NOT have English [ID] inside Arabic instructions
    assert "[ID]" not in sys_content
    assert "إياك تماماً أن تترك القوسين فارغين هكذا [ ] أو []!" in sys_content
    assert "--- نهاية الأسطر المطلوب ترجمتها (توقف هنا ولا تترجم أي شيء إضافي) ---" in user_content
