from typing import List, Dict, Any

class QAService:
    @staticmethod
    def check_overlap(mask1: Dict[str, Any], mask2: Dict[str, Any]) -> bool:
        """
        Returns true if the two masks overlap significantly.
        """
        # Dummy check
        return False
        
    @staticmethod
    def is_too_small(polygon: List[List[float]], min_area: float = 10.0) -> bool:
        """
        Returns true if polygon area is smaller than min_area.
        """
        # Dummy check
        return False
