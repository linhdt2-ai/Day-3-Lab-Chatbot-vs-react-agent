import sys
import os

# Add src to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.data_loader import DataLoader
from src.tools.vinwonders_tools import (
    search_rides,
    get_ride_details,
    check_ride_eligibility,
    get_ticket_price_rule,
    list_rides_by_zone
)


def test_data_loader():
    db = DataLoader()
    assert db.park_info["name"] == "VinWonders Nam Hội An"
    assert len(db.rides) > 0
    assert len(db.general_rules) > 0
    print("[OK] test_data_loader passed!")


def test_search_rides():
    res = search_rides("Thần Long")
    assert "Thần Long" in res
    assert "Thế giới nước" in res

    res_empty = search_rides("Trò chơi không tồn tại")
    assert "Không tìm thấy" in res_empty
    print("[OK] test_search_rides passed!")


def test_ride_details():
    res = get_ride_details("Đường trượt Thần Long")
    assert "Đường trượt Thần Long" in res
    assert "1.2m" in res
    assert "Trượt thân" in res
    print("[OK] test_ride_details passed!")


def test_get_ticket_price_rule():
    # Under 1m
    res_under = get_ticket_price_rule(90)
    assert "Miễn phí" in res_under

    # 1.2m
    res_child = get_ticket_price_rule(120)
    assert "Vé trẻ em" in res_child

    # 1.5m
    res_adult = get_ticket_price_rule(150)
    assert "Vé người lớn" in res_adult
    print("[OK] test_get_ticket_price_rule passed!")


def test_list_rides_by_zone():
    res = list_rides_by_zone("Thế giới nước")
    assert "Đường trượt Thần Long" in res
    assert "Sông lười" in res
    print("[OK] test_list_rides_by_zone passed!")


def test_eligibility_checking():
    # Dragon slide requires 1.2m min height
    res = check_ride_eligibility("Đường trượt Thần Long", 130)
    assert "ĐỦ ĐIỀU KIỆN CHƠI" in res

    res_fail = check_ride_eligibility("Đường trượt Thần Long", 110)
    assert "KHÔNG ĐỦ ĐIỀU KIỆN CHƠI" in res_fail

    # Tornado slide requires 1.4m and 50-90kg weight limit
    res_tornado = check_ride_eligibility("Đường trượt Lốc xoáy", 150, 70)
    assert "ĐỦ ĐIỀU KIỆN CHƠI" in res_tornado

    res_tornado_weight_fail = check_ride_eligibility("Đường trượt Lốc xoáy", 150, 45)
    assert "KHÔNG ĐỦ ĐIỀU KIỆN CHƠI" in res_tornado_weight_fail
    print("[OK] test_eligibility_checking passed!")


if __name__ == "__main__":
    print("--- Running VinWonders Nam Hoi An Test Suite ---")
    test_data_loader()
    test_search_rides()
    test_ride_details()
    test_get_ticket_price_rule()
    test_list_rides_by_zone()
    test_eligibility_checking()
    print("\n[SUCCESS] ALL TESTS PASSED SUCCESSFULLY! CODE IS CORRECT!")