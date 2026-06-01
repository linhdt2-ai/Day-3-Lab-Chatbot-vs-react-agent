import csv
import json
import os
from typing import Dict, Any, List

class DataLoader:
    _instance = None
    _data = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DataLoader, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, file_path: str = None):
        if self._data is None:
            if not file_path:
                # Find path relative to this file: src/tools/data_loader.py -> project root
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                file_path = os.path.join(base_dir, "VinWonders Nam Hoi An - Noi quy tro choi - JSON.csv")
            
            self.file_path = file_path
            self._load_data()

    def _load_data(self):
        try:
            if not os.path.exists(self.file_path):
                raise FileNotFoundError(f"Data file not found at {self.file_path}")

            with open(self.file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = [row[0] for row in reader if row]
            
            # The first row is 'json_pretty', if so skip it
            if rows and rows[0].strip() == "json_pretty":
                json_str = "\n".join(rows[1:])
            else:
                json_str = "\n".join(rows)

            self._data = json.loads(json_str)
        except Exception as e:
            # Fallback error handling
            self._data = {"park": {}, "general_rules": {}, "rides": [], "sources": []}
            raise RuntimeError(f"Failed to load and parse VinWonders Nam Hoi An dataset: {e}")

    @property
    def park_info(self) -> Dict[str, Any]:
        return self._data.get("park", {})

    @property
    def general_rules(self) -> Dict[str, Any]:
        return self._data.get("general_rules", {})

    @property
    def rides(self) -> List[Dict[str, Any]]:
        return self._data.get("rides", [])

    @property
    def sources(self) -> List[Dict[str, Any]]:
        return self._data.get("sources", [])

    def get_ride_by_name(self, name: str) -> Dict[str, Any]:
        """Finds a ride by its Vietnamese or English name (case-insensitive fuzzy match)."""
        name_lower = name.lower().strip()
        for ride in self.rides:
            if (ride.get("name_vi") and name_lower in ride["name_vi"].lower()) or \
               (ride.get("name_en") and name_lower in ride["name_en"].lower()):
                return ride
        return {}
