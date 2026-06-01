import re
from typing import Dict, Any, List, Optional
from src.tools.data_loader import DataLoader

# Initialize the global data loader
db = DataLoader()

def _parse_height_to_cm(height_str: Optional[str]) -> Optional[float]:
    """Helper to convert string heights like '1.2m', '<1.4m', '100cm' to float in cm."""
    if not height_str:
        return None
    height_str = height_str.lower().strip()
    # Extract numeric values
    match = re.search(r"([0-9.]+)\s*(m|cm)?", height_str)
    if not match:
        return None
    val = float(match.group(1))
    unit = match.group(2)
    if unit == "m" or (unit is None and val < 5.0):
        # Assumed in meters (e.g. 1.2 or 1.2m)
        return val * 100
    return val

def _parse_weight_limit(weight_str: Optional[str]) -> Dict[str, Optional[float]]:
    """Helper to parse weight limit strings like '50-90kg', '150kg/xe', '1800kg' into min/max weight in kg."""
    limits = {"min": None, "max": None}
    if not weight_str:
        return limits
    weight_str = weight_str.lower().strip()
    
    # Range check e.g., '50-90kg'
    range_match = re.search(r"([0-9.]+)\s*-\s*([0-9.]+)\s*kg", weight_str)
    if range_match:
        limits["min"] = float(range_match.group(1))
        limits["max"] = float(range_match.group(2))
        return limits

    # Single limit check e.g., '1800kg' or '150kg/xe'
    single_match = re.search(r"([0-9.]+)\s*kg", weight_str)
    if single_match:
        limits["max"] = float(single_match.group(1))
        return limits
        
    return limits

# 1. Search Rides Tool
def search_rides(query: str) -> str:
    """
    Tìm kiếm trò chơi theo từ khóa tên tiếng Việt hoặc tiếng Anh.
    Tham số:
      query (str): Tên trò chơi cần tìm (ví dụ: 'thần long', 'desert twister')
    Trả về:
      Danh sách trò chơi khớp dạng văn bản (Markdown).
    """
    query_lower = query.lower().strip()
    matches = []
    for r in db.rides:
        name_vi = r.get("name_vi", "").lower()
        name_en = r.get("name_en", "").lower()
        zone = r.get("zone", "").lower()
        cat = r.get("category", "").lower()
        desc = r.get("description", "").lower()
        
        if query_lower in name_vi or query_lower in name_en or query_lower in zone or query_lower in cat or query_lower in desc:
            matches.append(r)
            
    if not matches:
        return f"Không tìm thấy trò chơi nào phù hợp với từ khóa '{query}'."
    
    res = [f"### Kết quả tìm kiếm cho '{query}':"]
    for r in matches:
        res.append(f"- **{r.get('name_vi')}** ({r.get('name_en')})")
        res.append(f"  * Phân khu: {r.get('zone')} | Loại hình: {r.get('category')}")
        res.append(f"  * Mô tả: {r.get('description')}")
        
    return "\n".join(res)

# 2. Get Ride Details Tool
def get_ride_details(ride_name: str) -> str:
    """
    Lấy thông tin chi tiết đầy đủ của một trò chơi cụ thể.
    Tham số:
      ride_name (str): Tên chính xác hoặc gần đúng của trò chơi.
    Trả về:
      Văn bản chi tiết thông số trò chơi (Markdown).
    """
    ride = db.get_ride_by_name(ride_name)
    if not ride:
        return f"Không tìm thấy trò chơi '{ride_name}'. Bạn có thể sử dụng công cụ 'search_rides' để tìm đúng tên trò chơi."
    
    details = [
        f"## Thông tin chi tiết: {ride.get('name_vi')} ({ride.get('name_en')})",
        f"- **Phân khu**: {ride.get('zone')}",
        f"- **Thể loại**: {ride.get('category')}",
        f"- **Giới hạn chiều cao tối thiểu**: {ride.get('min_height') or 'Không yêu cầu'}",
        f"- **Giới hạn chiều cao tối đa**: {ride.get('max_height') or 'Không yêu cầu'}",
        f"- **Giới hạn cân nặng**: {ride.get('weight_limit') or 'Không yêu cầu'}",
        f"- **Thời gian chơi**: {ride.get('duration') or 'Không rõ'}",
        f"- **Số khách mỗi lượt**: {ride.get('players_per_turn') or 'Không rõ'}",
        f"- **Số ghế ngồi**: {ride.get('seats') or 'Không rõ'}",
        f"- **Thiết bị hỗ trợ**: {ride.get('equipment') or 'Không có'}",
        f"- **Yêu cầu người đi kèm**: {ride.get('escort_requirement') or 'Không yêu cầu'}",
        f"- **Mô tả**: {ride.get('description')}"
    ]
    if ride.get("notes"):
        details.append("- **Lưu ý thêm**:")
        for note in ride["notes"]:
            details.append(f"  * {note}")
            
    return "\n".join(details)

# 3. Check Ride Eligibility Tool
def check_ride_eligibility(ride_name: str, height_cm: float, weight_kg: Optional[float] = None) -> str:
    """
    Kiểm tra xem du khách có đủ điều kiện về chiều cao và cân nặng để chơi một trò chơi cụ thể hay không.
    Tham số:
      ride_name (str): Tên trò chơi.
      height_cm (float): Chiều cao của du khách tính bằng cm (ví dụ: 135).
      weight_kg (float, optional): Cân nặng của du khách tính bằng kg (ví dụ: 55).
    Trả về:
      Kết quả đánh giá đủ điều kiện chơi và lý do cụ thể (Markdown).
    """
    ride = db.get_ride_by_name(ride_name)
    if not ride:
        return f"Không tìm thấy trò chơi '{ride_name}' để kiểm tra điều kiện."
    
    reasons = []
    eligible = True
    
    # 1. Height limits check
    min_h = _parse_height_to_cm(ride.get("min_height"))
    max_h = _parse_height_to_cm(ride.get("max_height"))
    
    if min_h and height_cm < min_h:
        eligible = False
        reasons.append(f"Chiều cao của bạn ({height_cm}cm) thấp hơn mức tối thiểu yêu cầu ({ride.get('min_height')}).")
        
    if max_h:
        # Check if max height notation is like "<1.4m" or "1.9m"
        is_less_than = "<" in str(ride.get("max_height"))
        if is_less_than and height_cm >= max_h:
            eligible = False
            reasons.append(f"Chiều cao của bạn ({height_cm}cm) vượt quá hoặc bằng giới hạn quy định ({ride.get('max_height')}).")
        elif not is_less_than and height_cm > max_h:
            eligible = False
            reasons.append(f"Chiều cao của bạn ({height_cm}cm) vượt quá giới hạn tối đa cho phép ({ride.get('max_height')}).")

    # 2. Weight limits check
    if weight_kg:
        w_limits = _parse_weight_limit(ride.get("weight_limit"))
        if w_limits["min"] and weight_kg < w_limits["min"]:
            eligible = False
            reasons.append(f"Cân nặng của bạn ({weight_kg}kg) thấp hơn giới hạn tối thiểu yêu cầu ({ride.get('weight_limit')}).")
        if w_limits["max"] and weight_kg > w_limits["max"]:
            # Note: handle cases like '1800kg' (which is structure weight, not single player!)
            # Usually single player limit is < 150kg. If max weight limit > 200, it's likely structural.
            if w_limits["max"] < 200:
                eligible = False
                reasons.append(f"Cân nặng của bạn ({weight_kg}kg) vượt quá giới hạn tối đa cho phép của người chơi ({ride.get('weight_limit')}).")
    elif ride.get("weight_limit") and ("50-90kg" in str(ride.get("weight_limit"))):
        reasons.append(f"Trò chơi có yêu cầu cân nặng ({ride.get('weight_limit')}). Vui lòng cân nhắc bổ sung thông tin cân nặng để kiểm tra chính xác.")

    # 3. Special category safety check
    zone = ride.get("zone", "")
    cat = ride.get("category", "")
    if "Thế giới nước" in zone:
        reasons.append("⚠️ Lưu ý phân khu Thế giới nước: Không mang kính mắt, đồng hồ, vật cứng nhọn. Trang phục bơi đúng quy định. Không dành cho phụ nữ mang thai hoặc người bị tim mạch, xương khớp.")
    elif "Cảm giác mạnh" in cat:
        reasons.append("⚠️ Lưu ý trò chơi Cảm giác mạnh: Không dành cho phụ nữ mang thai, người bị bệnh huyết áp, tim mạch, chấn thương lưng/xương khớp.")

    res = [f"### Đánh giá điều kiện chơi: {ride.get('name_vi')}"]
    if eligible:
        res.append(f"🟢 **ĐỦ ĐIỀU KIỆN CHƠI!** Chiều cao {height_cm}cm " + (f"và cân nặng {weight_kg}kg " if weight_kg else "") + "nằm trong giới hạn cho phép.")
    else:
        res.append(f"🔴 **KHÔNG ĐỦ ĐIỀU KIỆN CHƠI.**")
        
    if reasons:
        res.append("**Lý do / Hướng dẫn an toàn:**")
        for reason in reasons:
            res.append(f"- {reason}")
            
    return "\n".join(res)

# 4. Get Ticket Price Rule Tool
def get_ticket_price_rule(height_cm: float) -> str:
    """
    Tra cứu phân loại giá vé dựa trên chiều cao của du khách.
    Tham số:
      height_cm (float): Chiều cao của du khách tính bằng cm (ví dụ: 95, 120, 150).
    Trả về:
      Thông tin phân loại vé quy đổi tương ứng (Markdown).
    """
    park = db.park_info
    rules = park.get("ticket_height_rules", {})
    
    res = [
        f"### Tra cứu giá vé theo chiều cao: {height_cm}cm",
    ]
    
    if height_cm < 100:
        res.append(f"🎟️ Phân loại: **{rules.get('under_1m', 'Miễn phí')}**")
        res.append("- Du khách dưới 100cm được vào cổng miễn phí.")
    elif height_cm < 140:
        res.append(f"🎟️ Phân loại: **{rules.get('from_1m_to_under_1_4m', 'Vé trẻ em')}**")
        res.append("- Du khách cao từ 100cm đến dưới 140cm áp dụng chính sách giá Vé Trẻ Em.")
    else:
        res.append(f"🎟️ Phân loại: **{rules.get('from_1_4m', 'Vé người lớn')}**")
        res.append("- Du khách từ 140cm trở lên áp dụng chính sách giá Vé Người Lớn.")
        
    res.append("\n*Lưu ý: Bảng giá vé chi tiết (VND) vui lòng liên hệ quầy vé chính thức hoặc truy cập trang chủ VinWonders.*")
    return "\n".join(res)

# 5. List Rides by Zone Tool
def list_rides_by_zone(zone_name: str) -> str:
    """
    Liệt kê tất cả các trò chơi trong một phân khu nhất định.
    Tham số:
      zone_name (str): Tên phân khu ('Thế giới nước', 'Vùng đất phiêu lưu', 'Trò chơi trong nhà').
    Trả về:
      Danh sách trò chơi trong phân khu (Markdown).
    """
    zone_lower = zone_name.lower().strip()
    
    # Try fuzzy mapping of zone name
    matched_zone = None
    if "nước" in zone_lower or "water" in zone_lower:
        matched_zone = "Thế giới nước"
    elif "phiêu lưu" in zone_lower or "adventure" in zone_lower:
        matched_zone = "Vùng đất phiêu lưu"
    elif "trong nhà" in zone_lower or "indoor" in zone_lower:
        matched_zone = "Trò chơi trong nhà"
        
    if not matched_zone:
        return f"Không nhận diện được phân khu '{zone_name}'. Phân khu hợp lệ gồm: 'Thế giới nước', 'Vùng đất phiêu lưu', 'Trò chơi trong nhà'."
        
    rides_in_zone = [r for r in db.rides if r.get("zone") == matched_zone]
    
    res = [f"## Danh sách trò chơi tại phân khu: **{matched_zone}** ({len(rides_in_zone)} trò)"]
    
    # Group by category
    cats = {}
    for r in rides_in_zone:
        cat = r.get("category", "Khác")
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(r)
        
    for cat, list_rides in cats.items():
        res.append(f"\n### Thể loại: *{cat}*")
        for r in list_rides:
            limit = ""
            if r.get("min_height") or r.get("max_height"):
                limit = f" (Yêu cầu chiều cao: {r.get('min_height') or 'Không giới hạn'} -> {r.get('max_height') or 'Không giới hạn'})"
            res.append(f"- **{r.get('name_vi')}**{limit} - *{r.get('description')}*")
            
    return "\n".join(res)

# Schema definitions for standard agent import
available_tools = [
    {
        "name": "search_rides",
        "description": "Tìm kiếm trò chơi trong VinWonders theo từ khóa. Dùng khi người dùng hỏi chung chung hoặc muốn tìm tên trò chơi. Tham số: query (str)",
        "func": search_rides
    },
    {
        "name": "get_ride_details",
        "description": "Lấy thông tin chi tiết đầy đủ của một trò chơi như mô tả, thời lượng, sức chứa, nhà sản xuất. Tham số: ride_name (str)",
        "func": get_ride_details
    },
    {
        "name": "check_ride_eligibility",
        "description": "Đánh giá xem chiều cao (cm) và cân nặng (kg) của du khách có đủ điều kiện để chơi trò chơi cụ thể không. Tham số: ride_name (str), height_cm (float), weight_kg (float, optional)",
        "func": check_ride_eligibility
    },
    {
        "name": "get_ticket_price_rule",
        "description": "Tra cứu phân loại giá vé (Miễn phí, Trẻ em, Người lớn) dựa trên chiều cao. Tham số: height_cm (float)",
        "func": get_ticket_price_rule
    },
    {
        "name": "list_rides_by_zone",
        "description": "Liệt kê toàn bộ danh sách trò chơi thuộc phân khu: 'Thế giới nước', 'Vùng đất phiêu lưu', 'Trò chơi trong nhà'. Tham số: zone_name (str)",
        "func": list_rides_by_zone
    }
]
