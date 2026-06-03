"""HTTP client พร้อม retry/backoff และหน่วงเป็นมารยาทต่อ server ต้นทาง."""
import time
import requests
from config import HEADERS, TIMEOUT, MAX_RETRIES, RETRY_BACKOFF, REQUEST_DELAY

_session = requests.Session()
_session.headers.update(HEADERS)


def get(url: str, params: dict | None = None) -> str:
    """ยิง GET พร้อม retry คืน response text. หน่วงทุกครั้งหลังสำเร็จ."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = _session.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            time.sleep(REQUEST_DELAY)  # มารยาท: หน่วงก่อน request ถัดไป
            return resp.text
        except requests.RequestException as e:
            last_err = e
            wait = RETRY_BACKOFF * attempt
            print(f"  ! request error (attempt {attempt}/{MAX_RETRIES}): {e}")
            print(f"    รอ {wait}s แล้วลองใหม่...")
            time.sleep(wait)
    raise RuntimeError(f"ยิง {url} ไม่สำเร็จหลัง {MAX_RETRIES} ครั้ง: {last_err}")
