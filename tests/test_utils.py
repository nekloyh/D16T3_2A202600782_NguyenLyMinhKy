from src.reflexion_lab.utils import lenient_match, normalize_answer

def test_normalize_answer():
    assert normalize_answer("Oxford University!") == "oxford university"

def test_lenient_match_accepts_harmless_extras():
    # Prediction contains the full gold answer plus a harmless qualifier.
    assert lenient_match("classical", "classical music")
    assert lenient_match("Bab-el-Mandeb", "Bab-el-Mandeb strait")
    assert lenient_match("Mediterranean Sea", "the Mediterranean Sea")
    # Approximators / connectives dropped on either side.
    assert lenient_match("approximately 66000", "66000")
    assert lenient_match("Dutch, French, and German", "Dutch, French, German")

def test_lenient_match_rejects_wrong_or_incomplete():
    # Genuinely different fact.
    assert not lenient_match("Mars", "Jupiter")
    # Prediction drops part of the gold answer (dropped hop) — must stay wrong.
    assert not lenient_match("Dutch, French, and German", "Dutch")
