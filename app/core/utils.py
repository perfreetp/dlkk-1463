import uuid
import re
import hashlib
import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date, timedelta
from decimal import Decimal
import random
import string


def generate_uuid() -> str:
    return str(uuid.uuid4())


def generate_code(prefix: str = "", length: int = 8) -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{timestamp}{random_str}"


def generate_task_code(task_type: str = "TASK") -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = "".join(random.choices(string.digits, k=4))
    return f"{task_type}-{timestamp}-{random_str}"


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9\s.,;:!?()（）【】《》，。；：？！、]", "", text)
    return text


def extract_keywords(text: str, top_k: int = 20) -> List[str]:
    try:
        import jieba
        import jieba.analyse

        if not text or len(text) < 2:
            return []

        keywords = jieba.analyse.extract_tags(text, topK=top_k, withWeight=False)
        return [kw for kw in keywords if len(kw) >= 2]
    except ImportError:
        words = re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z]{3,}", text)
        from collections import Counter
        return [word for word, _ in Counter(words).most_common(top_k)]


def calculate_text_similarity(text1: str, text2: str, method: str = "cosine") -> float:
    if not text1 or not text2:
        return 0.0

    try:
        import textdistance

        text1_clean = clean_text(text1)
        text2_clean = clean_text(text2)

        if not text1_clean or not text2_clean:
            return 0.0

        if method == "jaccard":
            return textdistance.jaccard.normalized_similarity(text1_clean, text2_clean)
        elif method == "cosine":
            words1 = set(text1_clean.split())
            words2 = set(text2_clean.split())
            if not words1 or not words2:
                return 0.0
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            return intersection / union if union > 0 else 0.0
        elif method == "levenshtein":
            return textdistance.levenshtein.normalized_similarity(text1_clean, text2_clean)
        else:
            return textdistance.cosine.normalized_similarity(text1_clean, text2_clean)
    except ImportError:
        return 0.0


def json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="ignore")
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def to_json(data: Any, indent: int = None) -> str:
    return json.dumps(data, default=json_default, ensure_ascii=False, indent=indent)


def from_json(json_str: str) -> Any:
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def sha256_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mask_string(s: str, start: int = 3, end: int = 3, mask_char: str = "*") -> str:
    if not s or len(s) <= start + end:
        return s
    return s[:start] + mask_char * (len(s) - start - end) + s[-end:]


def mask_phone(phone: str) -> str:
    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + "****" + phone[-4:]


def mask_id_card(id_card: str) -> str:
    if not id_card or len(id_card) < 10:
        return id_card
    return id_card[:6] + "********" + id_card[-4:]


def parse_date(date_str: str, formats: List[str] = None) -> Optional[date]:
    if not date_str:
        return None

    formats = formats or [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y%m%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def parse_datetime(datetime_str: str, formats: List[str] = None) -> Optional[datetime]:
    if not datetime_str:
        return None

    formats = formats or [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y%m%d%H%M%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(datetime_str.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def get_month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def get_date_range(period: str = "month", reference_date: date = None) -> tuple[date, date]:
    reference_date = reference_date or date.today()

    if period == "week":
        start = reference_date - timedelta(days=reference_date.weekday())
        end = start + timedelta(days=6)
    elif period == "quarter":
        quarter = (reference_date.month - 1) // 3
        start = date(reference_date.year, quarter * 3 + 1, 1)
        if quarter == 3:
            end = date(reference_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(reference_date.year, quarter * 3 + 4, 1) - timedelta(days=1)
    elif period == "year":
        start = date(reference_date.year, 1, 1)
        end = date(reference_date.year, 12, 31)
    else:
        start = date(reference_date.year, reference_date.month, 1)
        if reference_date.month == 12:
            end = date(reference_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(reference_date.year, reference_date.month + 1, 1) - timedelta(days=1)

    return start, end


def safe_divide(numerator: Union[int, float], denominator: Union[int, float], default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def calculate_percentage(value: Union[int, float], total: Union[int, float], decimal_places: int = 2) -> float:
    if total == 0:
        return 0.0
    return round((value / total) * 100, decimal_places)


def format_percentage(value: Union[int, float], total: Union[int, float], decimal_places: int = 2) -> str:
    percentage = calculate_percentage(value, total, decimal_places)
    return f"{percentage}%"


def validate_birads_classification(birads: str) -> bool:
    if not birads:
        return False
    valid_codes = ["0", "1", "2", "3", "4", "4a", "4b", "4c", "5", "6"]
    return birads.strip().upper() in [c.upper() for c in valid_codes]


def validate_breast_density(density: str) -> bool:
    if not density:
        return False
    valid_densities = ["A", "B", "C", "D", "a", "b", "c", "d",
                       "1", "2", "3", "4",
                       "脂肪型", "散在纤维腺体型", "不均质致密型", "极度致密型"]
    return density.strip() in valid_densities


def validate_mammo_views(views: str, laterality: str) -> bool:
    if not views:
        return False

    required_views = ["CC", "MLO"]
    if laterality.upper() == "BILATERAL":
        required_views = ["LCC", "RCC", "LMLO", "RMLO"]
    elif laterality.upper() == "LEFT":
        required_views = ["LCC", "LMLO"]
    elif laterality.upper() == "RIGHT":
        required_views = ["RCC", "RMLO"]

    view_list = [v.strip().upper() for v in views.split(",")]
    return all(view in view_list for view in required_views)


def calculate_score(value: float, thresholds: List[tuple]) -> int:
    for min_val, max_val, score in sorted(thresholds, key=lambda x: x[0], reverse=True):
        if min_val <= value <= max_val:
            return score
    return 0


def normalize_birads(birads: str) -> str:
    if not birads:
        return ""
    birads = birads.strip().upper()
    birads = re.sub(r"BI-RADS\s*", "", birads, flags=re.IGNORECASE)
    birads = re.sub(r"[^\dA-Z]", "", birads)
    return birads


def normalize_density(density: str) -> str:
    if not density:
        return ""
    density = density.strip().upper()

    density_map = {
        "A": "A", "1": "A", "脂肪型": "A",
        "B": "B", "2": "B", "散在纤维腺体型": "B",
        "C": "C", "3": "C", "不均质致密型": "C",
        "D": "D", "4": "D", "极度致密型": "D",
    }
    return density_map.get(density, density)


def paginate(items: List[Any], total: int, pagination: Any) -> Dict[str, Any]:
    page = getattr(pagination, "page", 1)
    page_size = getattr(pagination, "page_size", 20)
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
