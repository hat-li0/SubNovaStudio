import pytest
from app.quality.healer import SubtitleHealer

def test_protect_and_restore_ass_tags():
    text = r"{\an8}مرحباً بك يا صديقي!{\i1} كيف حالك؟{\i0}"
    protected, tags = SubtitleHealer.protect_ass_tags(text)
    assert r"{\an8}" in tags
    assert r"{\i1}" in tags
    assert r"{\i0}" in tags
    assert "___ASS_TAG_0___" in protected
    
    restored = SubtitleHealer.restore_ass_tags(protected, tags)
    assert restored == text

def test_dropped_ass_tag_restored():
    orig_text = r"{\an8}مرحباً بك"
    # LLM dropped the tag completely
    raw_translated = "مرحباً بك"
    healed = SubtitleHealer.heal(raw_translated, original_text=orig_text)
    assert r"{\an8}" in healed

def test_clean_stray_latin():
    dirty = r"{\an8}مرحباً \N I يا صديقي {Hmm.} a"
    cleaned = SubtitleHealer.clean_stray_latin(dirty)
    assert "{Hmm.}" not in cleaned
    assert r"\N I" not in cleaned
    assert "a" not in cleaned.split()

def test_normalize_arabic_punctuation():
    text = "مرحباً, كيف حالك? أنا بخير; شكراً لك."
    normalized = SubtitleHealer.normalize_arabic_punctuation(text)
    assert "،" in normalized
    assert "؟" in normalized
    assert "؛" in normalized
    assert "," not in normalized
    assert "?" not in normalized
    assert ";" not in normalized

def test_fix_orphan_quotes():
    text = '"هذا نص غير مغلق'
    fixed = SubtitleHealer.fix_orphan_quotes(text)
    assert '"' not in fixed

    balanced = '"هذا نص مغلق تماماً"'
    assert SubtitleHealer.fix_orphan_quotes(balanced) == balanced

def test_full_heal_pipeline():
    orig = r"{\an8\pos(192,20)}Wait, are you sure? {Sigh}"
    raw = r"انتظر, هل أنت متأكد? \N I {Sigh}"
    healed = SubtitleHealer.heal(raw, original_text=orig)
    assert r"{\an8\pos(192,20)}" in healed
    assert "،" in healed
    assert "؟" in healed
    assert "{Sigh}" not in healed
    assert r"\N I" not in healed

def test_empty_tags_purged():
    dirty = r"{\i1}{\i0}منذ ذلك اليوم، لم يعد يحاول شيئاً.{\b1}{\b0}"
    cleaned = SubtitleHealer.purge_corrupt_tags(dirty)
    assert r"{\i1}{\i0}" not in cleaned
    assert r"{\b1}{\b0}" not in cleaned
    assert "منذ ذلك اليوم" in cleaned

def test_italics_wrapped_properly_no_i1i0():
    orig = r"{\i1}Depuis ce jour,\NYoshioka n'a plus rien tenté.{\i0}"
    raw = "منذ ذلك اليوم، لم يعد يوشيوكا يحاول شيئاً."
    healed = SubtitleHealer.heal(raw, original_text=orig)
    assert r"{\i1}{\i0}" not in healed
    assert healed.startswith(r"{\i1}")
    assert healed.endswith(r"{\i0}")
    assert r"\N" in healed

def test_stray_latin_fused_prefix():
    raw = "رائع، سأختار قميصاً لامعاً جداً لتakeru!"
    cleaned = SubtitleHealer.clean_stray_latin_and_fillers(raw)
    assert "akeru" not in cleaned
    assert "لتاكيرو" in cleaned

def test_balance_ass_linebreaks():
    orig = r"Il fait beau !\NJe peux aller chez Takeru, aujourd'hui !"
    raw = "الجو جميل! يمكنني الذهاب إلى منزل تاكيرو اليوم!"
    balanced = SubtitleHealer.balance_ass_linebreaks(raw, orig)
    assert r"\N" in balanced
    assert balanced == r"الجو جميل!\Nيمكنني الذهاب إلى منزل تاكيرو اليوم!"

def test_transliterate_name_to_arabic():
    assert SubtitleHealer.transliterate_name_to_arabic("Takeru") == "تاكيرو"
    assert SubtitleHealer.transliterate_name_to_arabic("Hidaka") == "هيداكا"
    assert SubtitleHealer.transliterate_name_to_arabic("Kaori") == "كاوري"
    assert SubtitleHealer.transliterate_name_to_arabic("Tomoko") == "توموكو"
    assert SubtitleHealer.transliterate_name_to_arabic("Yoshioka") == "يوشيوكا"

