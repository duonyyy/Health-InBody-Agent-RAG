"""Unit tests for Vietnamese text parsing helpers in Health/InBody agents."""

import pytest
from agents import graph
from agents.parsing import (
    extract_height_cm,
    extract_pbf,
    extract_sex,
    extract_visceral_fat,
    extract_weight_kg,
    infer_days_per_week,
    infer_goal,
    normalize_match_text,
)


def test_extract_height_cm_handles_vietnamese_notation():
    assert extract_height_cm("Tôi cao 1m70 nặng 72kg") == 170.0
    assert extract_height_cm("Tôi cao 1m7") == 170.0
    assert extract_height_cm("Tôi cao 1m68") == 168.0
    assert extract_height_cm("cao 1 m 75") == 175.0
    assert extract_height_cm("chiều cao 165cm") == 165.0
    assert extract_height_cm("cao 1.70m") == 170.0
    assert extract_height_cm("cao 1,70m") == 170.0
    assert extract_height_cm("cao 170") == 170.0
    assert extract_height_cm("chiều cao 1.75") == 175.0


def test_extract_weight_kg_handles_common_vietnamese_units():
    assert extract_weight_kg("Tôi nặng 72kg") == 72.0
    assert extract_weight_kg("Tôi 65 ký, cao 1m70") == 65.0
    assert extract_weight_kg("nặng 72.5kg") == 72.5
    assert extract_weight_kg("nặng 72,5 kg") == 72.5
    assert extract_weight_kg("60 cân") == 60.0
    assert extract_weight_kg("cân nặng 55") == 55.0
    assert extract_weight_kg("cân nặng là 58") == 58.0


def test_extract_sex_distinguishes_nam_gender_from_nam_year():
    # 'Năm nay' (this year) must NOT be recognized as male
    assert extract_sex("Năm nay tôi 25 tuổi, nữ, PBF 28%") == "female"
    assert extract_sex("Năm nay tôi 25 tuổi, 50kg") is None
    assert extract_sex("nam nay toi 25 tuoi, nu") == "female"
    assert extract_sex("nam nay toi 25 tuoi") is None

    # Punctuation following gender word should not break extraction
    assert extract_sex("Tôi là nam, 25 tuổi") == "male"
    assert extract_sex("Tôi là nữ, 25 tuổi") == "female"
    assert extract_sex("Giới tính: nam") == "male"
    assert extract_sex("Giới tính nữ, pbf 25%") == "female"


def test_extract_pbf_handles_variations():
    assert extract_pbf("PBF là 20.5%") == 20.5
    assert extract_pbf("phần trăm mỡ là 18") == 18.0
    assert extract_pbf("tỷ lệ mỡ 22%") == 22.0
    assert extract_pbf("ti le mo 19.5%") == 19.5
    assert extract_pbf("body fat 15%") == 15.0
    assert extract_pbf("bf 16%") == 16.0
    assert extract_pbf("mỡ cơ thể là 25%") == 25.0


def test_infer_days_per_week():
    assert infer_days_per_week("tập 4 buổi 1 tuần") == 4
    assert infer_days_per_week("3 buổi mỗi tuần") == 3
    assert infer_days_per_week("3 ngày/tuần") == 3
    assert infer_days_per_week("5 buổi/tuần") == 5
    assert infer_days_per_week("2 buoi mot tuan") == 2


def test_infer_goal_and_explicit_goal():
    assert infer_goal("Tôi muốn giảm cân") == "fat_loss"
    assert infer_goal("Tôi muốn giảm mỡ") == "fat_loss"
    assert infer_goal("mục tiêu fat loss") == "fat_loss"
    assert infer_goal("tăng cơ") == "muscle_gain"
    assert infer_goal("tang can") == "muscle_gain"
    assert infer_goal("duy trì") == "maintenance"
    assert infer_goal("giữ cân") == "maintenance"
    assert graph._explicit_goal("Tôi muốn giảm cân") == "fat_loss"


def test_bmi_with_vietnamese_1m70_notation(monkeypatch):
    monkeypatch.setattr(graph, "openai_chat_complete", lambda *args, **kwargs: pytest.fail())
    monkeypatch.setattr(graph, "hybrid_search", lambda *args, **kwargs: pytest.fail())

    res = graph.multi_agent_handle("Tôi cao 1m70, nặng 72kg, tính BMI giúp tôi")
    assert res["status"] == "ok"
    assert res["fast_path"] == "inbody_tools"
    # 72 / (1.70^2) = 24.91
    assert "24.91" in res["content"]
    assert "72.00" not in res["content"]
