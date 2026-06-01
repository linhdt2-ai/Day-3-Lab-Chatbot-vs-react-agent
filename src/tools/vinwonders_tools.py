import os
import json
import re
from typing import Dict, Any, List, Optional

# Path to the data file
DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "data.json")

def _load_data() -> Dict[str, Any]:
    """Helper function to load the VinWonders data."""
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Data file not found at {DATA_PATH}")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_ticket_rules() -> str:
    """
    Retrieves the ticket height rules for VinWonders Nam Hội An.
    Returns:
        A formatted string describing the rules.
    """
    try:
        data = _load_data()
        park_info = data.get("park", {})
        rules = park_info.get("ticket_height_rules", {})
        notes = park_info.get("notes", [])
        
        output = [
            f"=== QUY ĐỊNH CHIỀU CAO VÀ GIÁ VÉ - {park_info.get('name', 'VinWonders')} ==="
        ]
        for key, value in rules.items():
            friendly_name = key.replace("_", " ")
            output.append(f"- {friendly_name.capitalize()}: {value}")
        
        if notes:
            output.append("\nGhi chú:")
            for note in notes:
                output.append(f"- {note}")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error loading ticket rules: {str(e)}"

def get_general_rules(category: str) -> str:
    """
    Retrieves general park rules for a specific category.
    Args:
        category: 'water_park' or 'thrill_rides'
    Returns:
        A formatted string listing the general rules.
    """
    try:
        data = _load_data()
        rules_dict = data.get("general_rules", {})
        
        if category not in rules_dict:
            available = list(rules_dict.keys())
            return f"Error: Category '{category}' not found. Available categories: {available}"
            
        rules = rules_dict[category]
        title = "CÔNG VIÊN NƯỚC" if category == "water_park" else "TRÒ CHƠI CẢM GIÁC MẠNH"
        
        output = [f"=== NỘI QUY CHUNG KHI CHƠI CÁC TRÒ {title} ==="]
        for rule in rules:
            output.append(f"- {rule}")
            
        return "\n".join(output)
    except Exception as e:
        return f"Error loading general rules: {str(e)}"

def search_rides(zone: Optional[str] = None, category: Optional[str] = None, name_query: Optional[str] = None) -> str:
    """
    Searches and filters VinWonders rides by zone, category, or name.
    Args:
        zone: Zone name (e.g., 'Thế giới nước', 'Vùng đất phiêu lưu', 'Trò chơi trong nhà')
        category: Category of ride (e.g., 'Đường trượt', 'Sông hồ', 'Cảm giác mạnh', 'Thiếu nhi', 'Gia đình')
        name_query: Partial name match (e.g., 'Thần Long', 'Swiss Tower')
    Returns:
        A formatted string listing matching rides and their key parameters.
    """
    try:
        data = _load_data()
        rides = data.get("rides", [])
        filtered = []
        
        for ride in rides:
            # Filter by zone
            if zone and zone.strip().lower() not in ride.get("zone", "").strip().lower():
                continue
            # Filter by category
            if category and category.strip().lower() not in ride.get("category", "").strip().lower():
                continue
            # Filter by name (English or Vietnamese)
            if name_query:
                q = name_query.strip().lower()
                name_vi = ride.get("name_vi", "").lower()
                name_en = ride.get("name_en", "").lower()
                if q not in name_vi and q not in name_en:
                    continue
            filtered.append(ride)
            
        if not filtered:
            return f"Không tìm thấy trò chơi nào khớp với yêu cầu (zone={zone}, category={category}, name_query={name_query})."
            
        output = [f"Tìm thấy {len(filtered)} trò chơi phù hợp:"]
        for r in filtered:
            min_h = r.get("min_height") or "Không giới hạn"
            max_h = r.get("max_height") or "Không giới hạn"
            weight = r.get("weight_limit") or "Không quy định cá nhân"
            equip = r.get("equipment") or "Tự thân"
            
            output.append(
                f"- **{r.get('name_vi')}** ({r.get('name_en')})\n"
                f"  + Khu vực: {r.get('zone')} | Thể loại: {r.get('category')}\n"
                f"  + Chiều cao tối thiểu: {min_h} | Chiều cao tối đa: {max_h}\n"
                f"  + Giới hạn cân nặng: {weight} | Thiết bị: {equip}\n"
                f"  + Số lượng khách/lượt: {r.get('players_per_turn') or 'N/A'} | Thời lượng: {r.get('duration') or 'N/A'}"
            )
            if r.get("escort_requirement"):
                output.append(f"  + Yêu cầu đi kèm: {r.get('escort_requirement')}")
            if r.get("notes"):
                output.append(f"  + Lưu ý: {', '.join(r.get('notes'))}")
                
        return "\n\n".join(output)
    except Exception as e:
        return f"Error searching rides: {str(e)}"

def check_ride_suitability(ride_name: str, height_m: float, weight_kg: Optional[float] = None) -> str:
    """
    Evaluates if a visitor of a given height and weight is permitted to participate in a specific ride.
    Args:
        ride_name: Name of the ride (Vietnamese or English)
        height_m: Height of visitor in meters (e.g. 1.35)
        weight_kg: Weight of visitor in kg (optional)
    Returns:
        A detailed suitability evaluation report.
    """
    try:
        data = _load_data()
        rides = data.get("rides", [])
        target_ride = None
        
        for r in rides:
            if (ride_name.strip().lower() in r.get("name_vi", "").strip().lower() or
                ride_name.strip().lower() in r.get("name_en", "").strip().lower()):
                target_ride = r
                break
                
        if not target_ride:
            return f"Không tìm thấy trò chơi nào có tên '{ride_name}' trong dữ liệu."
            
        name = target_ride.get("name_vi")
        min_h_str = target_ride.get("min_height")
        max_h_str = target_ride.get("max_height")
        weight_limit_str = target_ride.get("weight_limit")
        
        errors = []
        warnings = []
        
        # Check height limits
        # Parse min_height (e.g. "1.2m" or "Không giới hạn" or "1m")
        if min_h_str and min_h_str != "Không giới hạn":
            try:
                min_h_match = re.findall(r"([0-9.]+)", min_h_str)
                if min_h_match:
                    min_h_val = float(min_h_match[0])
                    if height_m < min_h_val:
                        errors.append(f"Chiều cao của bạn là {height_m}m, nhỏ hơn chiều cao tối thiểu yêu cầu là {min_h_str}.")
            except Exception:
                warnings.append(f"Không thể phân tích chiều cao tối thiểu '{min_h_str}' để so sánh tự động.")
                
        # Parse max_height (e.g. "<1.4m" or "2m" or "1.9m")
        if max_h_str:
            try:
                max_h_match = re.findall(r"([0-9.]+)", max_h_str)
                if max_h_match:
                    max_h_val = float(max_h_match[0])
                    if "<" in max_h_str or "under" in max_h_str.lower():
                        if height_m >= max_h_val:
                            errors.append(f"Chiều cao của bạn là {height_m}m, không thỏa mãn yêu cầu dưới {max_h_str}.")
                    else:
                        if height_m > max_h_val:
                            errors.append(f"Chiều cao của bạn là {height_m}m, vượt quá chiều cao tối đa cho phép là {max_h_str}.")
            except Exception:
                warnings.append(f"Không thể phân tích chiều cao tối đa '{max_h_str}' để so sánh tự động.")
                
        # Check weight limits (e.g. "50-90kg" or "1800kg")
        if weight_limit_str and weight_kg is not None:
            try:
                if "-" in weight_limit_str: # Range, e.g. "50-90kg"
                    weight_match = re.findall(r"([0-9.]+)-([0-9.]+)", weight_limit_str)
                    if weight_match:
                        min_w_val = float(weight_match[0][0])
                        max_w_val = float(weight_match[0][1])
                        if weight_kg < min_w_val or weight_kg > max_w_val:
                            errors.append(f"Cân nặng của bạn là {weight_kg}kg, nằm ngoài giới hạn an toàn {weight_limit_str}.")
                else: # Singular value like "1800kg" (usually total ride load)
                    weight_match = re.findall(r"([0-9.]+)", weight_limit_str)
                    if weight_match:
                        max_w_val = float(weight_match[0])
                        # If the limit is very large (e.g. >= 500kg), it's a total load capacity, not individual weight
                        if max_w_val < 200:
                            if weight_kg > max_w_val:
                                errors.append(f"Cân nặng của bạn là {weight_kg}kg, vượt quá giới hạn an toàn cá nhân {weight_limit_str}.")
                        else:
                            warnings.append(f"Giới hạn '{weight_limit_str}' là tổng tải trọng của xe/lượt chơi, hãy tuân thủ hướng dẫn tại chỗ.")
            except Exception:
                warnings.append(f"Không thể phân tích giới hạn cân nặng '{weight_limit_str}' để so sánh tự động.")
                
        # Format the result
        if errors:
            status = "❌ KHÔNG PHÙ HỢP / BỊ TỪ CHỐI THAM GIA"
            reason = "\n".join([f"- {err}" for err in errors])
        else:
            status = "✅ PHÙ HỢP / ĐỦ ĐIỀU KIỆN THAM GIA"
            reason = "- Bạn thỏa mãn tất cả các điều kiện an toàn về chiều cao và cân nặng."
            
        output = [
            f"=== ĐÁNH GIÁ SỰ PHÙ HỢP CHO TRÒ CHƠI: {name} ===",
            f"Độ tuổi/thông số của bạn: Chiều cao: {height_m}m | Cân nặng: {weight_kg or 'Không cung cấp'}kg",
            f"Trạng thái: {status}",
            f"Chi tiết lý do:\n{reason}"
        ]
        
        if warnings:
            output.append("\nCảnh báo/Lưu ý thêm:")
            for warn in warnings:
                output.append(f"- {warn}")
                
        if target_ride.get("escort_requirement"):
            output.append(f"\nYêu cầu người đi kèm: {target_ride.get('escort_requirement')}")
            
        return "\n".join(output)
    except Exception as e:
        return f"Error checking ride suitability: {str(e)}"
