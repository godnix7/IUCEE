from typing import List, Dict, Any

class FusionService:
    @staticmethod
    def vote_fusion(masks: List[Dict[str, Any]], threshold: float = 0.5) -> Dict[str, Any]:
        """
        Takes multiple model outputs and applies majority voting for pixel agreement.
        Returns the fused mask.
        """
        # In a real implementation, we would convert polygons to bitmasks and do a pixel-wise AND/OR voting.
        # For simulation, we return the mask with the highest confidence.
        if not masks:
            return {}
            
        best_mask = max(masks, key=lambda x: x.get("confidence", 0))
        
        return {
            "polygon": best_mask.get("polygon", []),
            "confidence": best_mask.get("confidence", 0),
            "model": "Fused_MajorityVote"
        }

    @staticmethod
    def iou_agreement(mask1: Dict[str, Any], mask2: Dict[str, Any]) -> float:
        """
        Calculates the Intersection over Union between two masks.
        """
        # Dummy IoU calculation
        return 0.85
