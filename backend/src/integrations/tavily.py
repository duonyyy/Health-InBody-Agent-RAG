"""Tavily web search tools cho Health/InBody Agent RAG."""
import logging
import os
from typing import Dict, List, Optional

from harness.budget import call_with_supported_kwargs, remaining_for_call

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
TAVILY_TIMEOUT_SECONDS = float(os.environ.get("TAVILY_TIMEOUT_SECONDS", "10"))
TAVILY_MIN_TIMEOUT_SECONDS = max(
    0.05, float(os.environ.get("TAVILY_MIN_TIMEOUT_SECONDS", "0.5"))
)

TRUSTED_HEALTH_DOMAINS = [
    "who.int",
    "cdc.gov",
    "nih.gov",
    "ncbi.nlm.nih.gov",
    "mayoclinic.org",
    "healthline.com",
    "clevelandclinic.org",
    "verywellfit.com",
    "eatright.org",
]

HEALTH_SAFETY_NOTE = (
    "Thông tin web chỉ mang tính tham khảo, không thay thế chẩn đoán hoặc điều trị y khoa. "
    "Nếu có triệu chứng nguy hiểm, đang dùng thuốc hoặc có bệnh nền, người dùng nên hỏi bác sĩ."
)


def tavily_search_health(
    query: str,
    max_results: int = 5,
    prefer_trusted_sources: bool = True,
    timeout: Optional[float] = None,
    deadline_monotonic: Optional[float] = None,
) -> str:
    """
    Mục đích:
        Tìm kiếm thông tin tối ưu riêng cho chủ đề Sức khỏe/InBody bằng cách tối ưu hóa câu hỏi
        và ưu tiên các nguồn tin cậy. Kết quả trả về dạng chuỗi (string) có cấu trúc trực quan.
    """
    enhanced_query = (
        "Health InBody BMI PBF nutrition exercise safety: " + query.strip()
    )
    include_domains = TRUSTED_HEALTH_DOMAINS if prefer_trusted_sources else None
    results = tavily_search(
        enhanced_query,
        max_results=max_results,
        search_depth="advanced",
        include_domains=include_domains,
        timeout=timeout,
        deadline_monotonic=deadline_monotonic,
    )

    if "error" in results:
        return f"Lỗi tìm kiếm: {results['error']}\n\n{HEALTH_SAFETY_NOTE}"

    output = f"Kết quả tìm kiếm sức khỏe/InBody cho: {query}\n\n"
    if results.get("answer"):
        output += f"Tóm tắt Tavily:\n{results['answer']}\n\n"

    output += "Nguồn tham khảo:\n"
    for idx, result in enumerate(results.get("results", []), start=1):
        trusted = "nguồn y tế ưu tiên" if result.get("is_trusted_health_source") else "nguồn web"
        output += f"{idx}. {result['title']} ({trusted})\n"
        output += f"   URL: {result['url']}\n"
        output += f"   {result['content'][:280]}...\n"
        output += f"   Độ liên quan: {result.get('score', 0):.2f}\n\n"

    if not results.get("results"):
        output += "Không tìm thấy kết quả phù hợp.\n\n"

    output += f"Lưu ý an toàn: {HEALTH_SAFETY_NOTE}"
    return output


def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: Optional[List[str]] = None,
    timeout: Optional[float] = None,
    deadline_monotonic: Optional[float] = None,
) -> Dict:
    """
    Mục đích:
        Thực hiện truy vấn tìm kiếm trực tuyến thông qua API của Tavily.
    """
    if not query or not query.strip():
        return {
            "query": query,
            "answer": "",
            "results": [],
            "num_results": 0,
            "safety_note": HEALTH_SAFETY_NOTE,
        }

    effective_timeout = remaining_for_call(
        deadline_monotonic,
        TAVILY_TIMEOUT_SECONDS if timeout is None else timeout,
        default_timeout=TAVILY_TIMEOUT_SECONDS,
        min_timeout=TAVILY_MIN_TIMEOUT_SECONDS,
    )
    if effective_timeout is None:
        return {
            "error": "timeout: web search budget exhausted",
            "query": query,
            "answer": "",
            "results": [],
            "num_results": 0,
            "safety_note": HEALTH_SAFETY_NOTE,
        }

    client = _get_tavily_client()
    if client is None:
        return {
            "error": "TAVILY_API_KEY is not configured or tavily-python is unavailable",
            "query": query,
            "answer": "",
            "results": [],
            "num_results": 0,
            "safety_note": HEALTH_SAFETY_NOTE,
        }

    try:
        request_kwargs = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": True,
            "include_raw_content": False,
            "timeout": effective_timeout,
        }
        if include_domains:
            request_kwargs["include_domains"] = include_domains

        response = call_with_supported_kwargs(client.search, **request_kwargs)
        formatted_results = [
            _format_result(result) for result in response.get("results", [])
        ]

        output = {
            "query": query,
            "answer": response.get("answer", "") or "",
            "results": formatted_results,
            "num_results": len(formatted_results),
            "safety_note": HEALTH_SAFETY_NOTE,
        }
        logger.info(
            "[TAVILY] Health search completed: %s results for '%s'",
            len(formatted_results),
            query,
        )
        return output
    except Exception as e:
        logger.error("[TAVILY] Search error: %s", e)
        return {
            "error": str(e),
            "query": query,
            "answer": "",
            "results": [],
            "num_results": 0,
            "safety_note": HEALTH_SAFETY_NOTE,
        }


def _get_tavily_client():
    """
    Mục đích:
        Khởi tạo và trả về đối tượng TavilyClient để kết nối API.
    """
    if not TAVILY_API_KEY:
        return None

    try:
        from tavily import TavilyClient

        return TavilyClient(api_key=TAVILY_API_KEY)
    except Exception as e:
        logger.warning("Tavily client is not available: %s", e)
        return None


def _format_result(result: Dict) -> Dict:
    """
    Mục đích:
        Định dạng kết quả tìm kiếm thô nhận được từ API Tavily về cấu trúc chuẩn của hệ thống,
        đồng thời xác định nguồn gốc có thuộc danh sách y tế uy tín hay không.
    """
    url = result.get("url", "") or ""
    return {
        "title": result.get("title", "") or "",
        "url": url,
        "content": result.get("content", "") or "",
        "score": result.get("score", 0.0) or 0.0,
        "is_trusted_health_source": any(domain in url for domain in TRUSTED_HEALTH_DOMAINS),
    }
