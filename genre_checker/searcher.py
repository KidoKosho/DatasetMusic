"""
Module tìm kiếm genre đa nguồn theo cơ chế xếp tầng (Source Search Cascade),
thu thập chứng cứ (Evidence Model), giải quyết thực thể (Entity Resolution),
xác thực thể loại (Genre Validation) và hợp nhất đa nguồn (Evidence Aggregation).
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import concurrent.futures
import threading
from config import (
    USER_AGENT,
    TIMEOUT,
    MAX_RETRIES,
    BACKOFF_FACTOR,
    REQUEST_DELAY,
    LASTFM_DELAY,
    WEB_SEARCH_DELAY,
    GENRE_SYNONYMS,
    CHANNEL_NOISE_WORDS,
)
from normalizer import (
    normalize_title,
    normalize_artist,
    clean_for_search_query,
    normalize_genre,
    normalize_single_label,
    validate_genre,
    validate_genre_label,
    get_genre_tokens,
)

load_dotenv()

logger = logging.getLogger("GenreChecker.Searcher")


@dataclass
class Evidence:
    """Mô hình chứng cứ cho từng kết quả thu thập từ một nguồn."""
    source: str
    query: str
    genre: str
    evidence_type: str  # "track_level", "album_level", "artist_level", "search_snippet"
    url: str = ""
    snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GenreSearcher:
    """Bộ điều phối tìm kiếm đa nguồn với khả năng kiểm định chứng cứ và phân giải xung đột."""

    def __init__(self, lastfm_api_key: Optional[str] = None):
        self.lastfm_api_key = lastfm_api_key or os.getenv("LASTFM_API_KEY")
        if not self.lastfm_api_key:
            logger.info("Không có LASTFM_API_KEY. Sẽ bỏ qua Last.fm và dùng MusicBrainz/Web Platforms.")

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Khóa điều phối Rate Limit chống HTTP 429/503 khi chạy đa luồng
        self._discogs_lock = threading.Lock()
        self._last_discogs_time = 0.0

        self._mb_lock = threading.Lock()
        self._last_mb_time = 0.0

    def _request_with_retry(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        delay_after: float = 0.0,
    ) -> Optional[requests.Response]:
        """Thực hiện HTTP GET với Exponential Backoff (2s, 4s, 8s). Không crash."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=TIMEOUT,
                )

                if resp.status_code in {429, 500, 502, 503, 504}:
                    wait_time = BACKOFF_FACTOR ** attempt
                    logger.warning(
                        "Gặp HTTP %d từ %s. Thử lại lần %d/%d sau %ds...",
                        resp.status_code,
                        url,
                        attempt,
                        MAX_RETRIES,
                        wait_time,
                    )
                    time.sleep(wait_time)
                    continue

                if delay_after > 0:
                    time.sleep(delay_after)

                return resp

            except (requests.Timeout, requests.ConnectionError) as net_err:
                wait_time = BACKOFF_FACTOR ** attempt
                logger.warning(
                    "Lỗi kết nối/timeout (%s) tại %s. Thử lại lần %d/%d sau %ds...",
                    net_err.__class__.__name__,
                    url,
                    attempt,
                    MAX_RETRIES,
                    wait_time,
                )
                time.sleep(wait_time)
            except Exception as ex:
                logger.error("Ngoại lệ khi gọi %s: %s", url, ex)
                break

        return None

    # ==========================================
    # 1. LAST.FM API
    # ==========================================
    def search_lastfm(self, title: str, singer: str) -> Optional[Evidence]:
        if not self.lastfm_api_key:
            return None

        clean_t, clean_s = clean_for_search_query(title, singer)
        if not clean_t or not clean_s:
            return None

        url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "track.getInfo",
            "api_key": self.lastfm_api_key,
            "artist": clean_s,
            "track": clean_t,
            "autocorrect": 1,
            "format": "json",
        }

        resp = self._request_with_retry(url, params=params, delay_after=LASTFM_DELAY)
        if not resp or resp.status_code != 200:
            return None

        try:
            data = resp.json()
            track_info = data.get("track")
            if not track_info:
                return None

            toptags = track_info.get("toptags", {}).get("tag", [])
            if isinstance(toptags, dict):
                toptags = [toptags]

            raw_tags = [t.get("name", "") for t in toptags if isinstance(t, dict)]
            # Lọc bỏ tag trùng với tên nghệ sĩ hoặc tiêu đề bài hát
            filtered_tags = [
                tag for tag in raw_tags
                if tag.lower().strip() != clean_s.lower().strip()
                and tag.lower().strip() != clean_t.lower().strip()
            ]

            norm = normalize_genre(", ".join(filtered_tags))
            if norm and validate_genre(norm):
                return Evidence(
                    source="lastfm",
                    query=f"artist={clean_s}&track={clean_t}",
                    genre=norm,
                    evidence_type="track_level",
                    url=url,
                    snippet=f"tags: {', '.join(filtered_tags[:5])}",
                )
        except Exception as e:
            logger.debug("Lỗi Last.fm: %s", e)

        return None

    # ==========================================
    # 2. MUSICBRAINZ API
    # ==========================================
    def search_musicbrainz(self, title: str, singer: str) -> Optional[Evidence]:
        clean_t, clean_s = clean_for_search_query(title, singer)
        if not clean_t:
            return None

        search_url = "https://musicbrainz.org/ws/2/recording"
        safe_t = re.sub(r'["\+\-\!\(\)\{\}\[\]\^~\*\?:\\]', " ", clean_t).strip()
        safe_s = re.sub(r'["\+\-\!\(\)\{\}\[\]\^~\*\?:\\]', " ", clean_s).strip()

        query = f'recording:"{safe_t}" AND artist:"{safe_s}"' if safe_s else f'recording:"{safe_t}"'
        params = {"query": query, "fmt": "json"}

        with self._mb_lock:
            elapsed = time.time() - self._last_mb_time
            if elapsed < 1.1:
                time.sleep(1.1 - elapsed)
            self._last_mb_time = time.time()
            resp = self._request_with_retry(search_url, params=params, delay_after=0.2)

        if not resp or resp.status_code != 200:
            return None

        try:
            data = resp.json()
            recs = data.get("recordings", [])
            if not recs:
                return None

            top_rec = recs[0]
            rec_id = top_rec.get("id")
            if not rec_id:
                return None

            # Lookup chi tiết recording
            lookup_url = f"https://musicbrainz.org/ws/2/recording/{rec_id}"
            l_resp = self._request_with_retry(
                lookup_url,
                params={"inc": "genres+tags+artist-credits", "fmt": "json"},
                delay_after=REQUEST_DELAY,
            )

            if l_resp and l_resp.status_code == 200:
                l_data = l_resp.json()
                tags = [g.get("name", "") for g in l_data.get("genres", [])]
                tags += [t.get("name", "") for t in l_data.get("tags", [])]

                norm = normalize_genre(", ".join(tags))
                if norm and validate_genre(norm):
                    return Evidence(
                        source="musicbrainz",
                        query=query,
                        genre=norm,
                        evidence_type="track_level",
                        url=lookup_url,
                        snippet=f"recording tags: {', '.join(tags[:5])}",
                    )

                # Fallback tra cứu tags của nghệ sĩ chính
                artists = l_data.get("artist-credit", [])
                if artists and isinstance(artists[0], dict):
                    art_id = artists[0].get("artist", {}).get("id")
                    if art_id:
                        art_url = f"https://musicbrainz.org/ws/2/artist/{art_id}"
                        art_resp = self._request_with_retry(
                            art_url,
                            params={"inc": "genres+tags", "fmt": "json"},
                            delay_after=REQUEST_DELAY,
                        )
                        if art_resp and art_resp.status_code == 200:
                            art_data = art_resp.json()
                            art_tags = [g.get("name", "") for g in art_data.get("genres", [])]
                            art_tags += [t.get("name", "") for t in art_data.get("tags", [])]
                            art_norm = normalize_genre(", ".join(art_tags))
                            if art_norm and validate_genre(art_norm):
                                return Evidence(
                                    source="musicbrainz",
                                    query=f"artist:{art_id}",
                                    genre=art_norm,
                                    evidence_type="artist_level",
                                    url=art_url,
                                    snippet=f"artist tags: {', '.join(art_tags[:5])}",
                                )
        except Exception as e:
            logger.debug("Lỗi MusicBrainz: %s", e)

        return None

    # ==========================================
    # 3. APPLE MUSIC / ITUNES SEARCH API
    # ==========================================
    def search_apple_music(self, title: str, singer: str) -> Optional[Evidence]:
        """Tra cứu Apple Music qua iTunes Search API chính thức (track-level)."""
        clean_t, clean_s = clean_for_search_query(title, singer)
        if not clean_t:
            return None

        url = "https://itunes.apple.com/search"
        params = {"term": f"{clean_t} {clean_s}".strip(), "entity": "song", "limit": 3}
        resp = self._request_with_retry(url, params=params, delay_after=0.2)

        if not resp or resp.status_code != 200:
            return None

        try:
            results = resp.json().get("results", [])
            for item in results:
                raw_genre = item.get("primaryGenreName", "")
                norm = normalize_genre(raw_genre)
                if norm and validate_genre(norm):
                    track_name = item.get("trackName", "")
                    artist_name = item.get("artistName", "")
                    return Evidence(
                        source="apple_music",
                        query=f"{clean_t} {clean_s}",
                        genre=norm,
                        evidence_type="track_level",
                        url=item.get("trackViewUrl", url),
                        snippet=f"Apple Music track '{track_name}' by '{artist_name}', genre: {raw_genre}",
                    )
        except Exception as e:
            logger.debug("Lỗi Apple Music API: %s", e)

        return None

    # ==========================================
    # 4. DISCOGS DATABASE SEARCH API
    # ==========================================
    def search_discogs(self, title: str, singer: str) -> Optional[Evidence]:
        """Tra cứu qua Discogs API chính thức (genre & style)."""
        clean_t, clean_s = clean_for_search_query(title, singer)
        if not clean_t:
            return None

        url = "https://api.discogs.com/database/search"
        params = {"q": f"{clean_t} {clean_s}".strip(), "type": "release"}
        headers = {"User-Agent": USER_AGENT}

        with self._discogs_lock:
            elapsed = time.time() - self._last_discogs_time
            if elapsed < 1.1:
                time.sleep(1.1 - elapsed)
            self._last_discogs_time = time.time()
            resp = self._request_with_retry(url, params=params, headers=headers, delay_after=0.1)

        if not resp or resp.status_code != 200:
            return None

        try:
            results = resp.json().get("results", [])
            for item in results[:3]:
                genres = item.get("genre", [])
                styles = item.get("style", [])
                all_tags = (genres if isinstance(genres, list) else [genres]) + (styles if isinstance(styles, list) else [styles])
                combined = ", ".join(str(t) for t in all_tags if t)
                norm = normalize_genre(combined)
                if norm and validate_genre(norm):
                    release_title = item.get("title", "")
                    return Evidence(
                        source="discogs",
                        query=f"{clean_t} {clean_s}",
                        genre=norm,
                        evidence_type="track_level",
                        url=f"https://www.discogs.com{item.get('uri', '')}",
                        snippet=f"Discogs release '{release_title}', tags: {combined}",
                    )
        except Exception as e:
            logger.debug("Lỗi Discogs API: %s", e)

        return None

    # ==========================================
    # 3. VIETNAMESE PLATFORMS: ZING MP3
    # ==========================================
    def search_zingmp3(self, title: str, singer: str, zing_id: Optional[str] = None) -> Optional[Evidence]:
        clean_t, clean_s = clean_for_search_query(title, singer)
        target_song_id = str(zing_id).strip() if zing_id and str(zing_id).strip() and str(zing_id).lower() != "nan" else None

        if not target_song_id and clean_t:
            candidate_queries = [f"{clean_t} {clean_s}".strip()]
            if " - " in clean_t:
                parts = clean_t.split(" - ")
                if len(parts[0].strip()) > 1:
                    candidate_queries.append(f"{parts[0].strip()} {clean_s}".strip())
                if len(parts[1].strip()) > 1:
                    candidate_queries.append(f"{parts[1].strip()} {clean_s}".strip())
            candidate_queries.append(clean_t)

            ac_url = "http://ac.mp3.zing.vn/complete"
            for q in candidate_queries:
                ac_params = {"type": "artist,song,key,hub", "num": "5", "query": q}
                ac_resp = self._request_with_retry(ac_url, params=ac_params, delay_after=WEB_SEARCH_DELAY)

                if ac_resp and ac_resp.status_code == 200:
                    try:
                        ac_data = ac_resp.json()
                        for group in ac_data.get("data", []):
                            songs = group.get("song", [])
                            if songs and isinstance(songs, list):
                                target_song_id = songs[0].get("id")
                                break
                    except Exception:
                        pass
                if target_song_id:
                    break

        if target_song_id:
            song_page_url = f"https://zingmp3.vn/bai-hat/{target_song_id}.html"
            page_resp = self._request_with_retry(song_page_url, delay_after=WEB_SEARCH_DELAY)
            if page_resp and page_resp.status_code == 200:
                try:
                    soup = BeautifulSoup(page_resp.text, "html.parser")
                    for script in soup.find_all("script", type="application/ld+json"):
                        try:
                            ld_json = json.loads(script.string or "{}")
                            genre_raw = ld_json.get("genre")
                            if genre_raw:
                                norm = normalize_genre(genre_raw)
                                if norm and validate_genre(norm):
                                    return Evidence(
                                        source="zingmp3",
                                        query=f"id={target_song_id}",
                                        genre=norm,
                                        evidence_type="track_level",
                                        url=song_page_url,
                                        snippet=f"JSON-LD genre: {genre_raw}",
                                    )
                                else:
                                    logger.debug("[INVALID_GENRE] ZingMP3 genre='%s' -> reject", genre_raw)
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug("Lỗi parse ZingMP3: %s", e)

        return None

    # ==========================================
    # 4. VIETNAMESE & INTERNATIONAL PLATFORM WEB SEARCH
    # ==========================================
    def search_platform_via_web(
        self,
        domain: str,
        source_name: str,
        title: str,
        singer: str,
    ) -> Optional[Evidence]:
        """
        Tìm kiếm metadata trên domain mục tiêu qua Bing Search HTML:
        site:{domain} "{TITLE}" "{SINGER}"
        """
        clean_t, clean_s = clean_for_search_query(title, singer)
        if not clean_t:
            return None

        query = f'site:{domain} "{clean_t}" "{clean_s}"'
        search_url = "https://www.bing.com/search"
        headers = {
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }

        resp = self._request_with_retry(search_url, params={"q": query}, headers=headers, delay_after=WEB_SEARCH_DELAY)
        if not resp or resp.status_code != 200:
            return None

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            snippets: List[str] = []
            target_url = ""
            for li in soup.select("li.b_algo"):
                a_tag = li.select_one("h2 a")
                if a_tag and not target_url:
                    target_url = a_tag.get("href", "")
                p = li.select_one("p")
                if p:
                    snippets.append(p.get_text(strip=True))

            full_text = " ".join(snippets).lower()
            matched = self._extract_genres_from_text(full_text)
            if matched and validate_genre(matched):
                return Evidence(
                    source=source_name,
                    query=query,
                    genre=matched,
                    evidence_type="search_snippet",
                    url=target_url,
                    snippet=" ".join(snippets[:2]),
                )
        except Exception as e:
            logger.debug("Lỗi search %s: %s", source_name, e)

        return None

    # ==========================================
    # 5. GENERAL WEB SEARCH
    # ==========================================
    def search_general_web(self, title: str, singer: str) -> Optional[Evidence]:
        clean_t, clean_s = clean_for_search_query(title, singer)
        if not clean_t:
            return None

        queries = [
            f'"{clean_t}" "{clean_s}" thể loại',
            f'"{clean_t}" "{clean_s}" genre',
        ]
        search_url = "https://www.bing.com/search"
        headers = {
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }

        for q in queries:
            resp = self._request_with_retry(search_url, params={"q": q}, headers=headers, delay_after=WEB_SEARCH_DELAY)
            if not resp or resp.status_code != 200:
                continue

            try:
                soup = BeautifulSoup(resp.text, "html.parser")
                snippets: List[str] = []
                for li in soup.select("li.b_algo"):
                    p = li.select_one("p")
                    if p:
                        snippets.append(p.get_text(strip=True))

                full_text = " ".join(snippets).lower()
                matched = self._extract_genres_from_text(full_text)
                if matched and validate_genre(matched):
                    return Evidence(
                        source="web_search",
                        query=q,
                        genre=matched,
                        evidence_type="search_snippet",
                        snippet=" ".join(snippets[:2]),
                    )
            except Exception as e:
                logger.debug("Lỗi web search general: %s", e)

        return None

    def _extract_genres_from_text(self, text: str) -> str:
        """Trích xuất các nhãn thể loại hợp lệ từ văn bản snippet một cách chính xác."""
        if not text:
            return ""

        # Sắp xếp các từ khóa theo độ dài giảm dần (từ dài, đặc thù trước: e.g. 'indie pop' trước 'pop')
        sorted_kws = sorted(GENRE_SYNONYMS.keys(), key=len, reverse=True)

        matched_genres = []
        # Ưu tiên tìm trong ngữ cảnh rõ ràng: thể loại / dòng nhạc / genre
        ctx_match = re.search(r"(?:thể loại|dòng nhạc|genre|category)\s*[:\-]\s*([^,\.\n\|;]+)", text)
        if ctx_match:
            ctx_text = ctx_match.group(1).lower()
            for kw in sorted_kws:
                if re.search(rf"\b{re.escape(kw)}\b", ctx_text):
                    norm_val = GENRE_SYNONYMS[kw]
                    if validate_genre(norm_val) and norm_val not in matched_genres:
                        matched_genres.append(norm_val)

        # Nếu chưa tìm thấy từ ngữ cảnh, quét trên toàn văn bản
        if not matched_genres:
            for kw in sorted_kws:
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, text):
                    norm_val = GENRE_SYNONYMS[kw]
                    if validate_genre(norm_val) and norm_val not in matched_genres:
                        matched_genres.append(norm_val)

        if matched_genres:
            res = "|".join(matched_genres[:2])
            return normalize_genre(res)
        return ""

    # ==========================================
    # HỢP NHẤT CHỨNG CỨ & PHÂN GIẢI XUNG ĐỘT (EVIDENCE AGGREGATION)
    # ==========================================
    # ==========================================
    # HỢP NHẤT CHỨNG CỨ & TỔNG HỢP ĐA THỂ LOẠI (MULTI-GENRE AGGREGATION)
    # ==========================================
    def aggregate_evidence(self, evidences: List[Evidence]) -> Tuple[str, str, str, str]:
        """
        Hợp nhất các chứng cứ thu thập được từ tất cả các nguồn:
        1. Lọc bỏ chứng cứ không hợp lệ (validate_genre == False).
        2. Tổng hợp tất cả các thể loại hợp lệ độc nhất (Union of valid genres).
           Một bài hát có thể có nhiều thể loại (ví dụ: pop|v-pop|dance|remix).
        3. Tổng hợp danh sách nguồn đã cung cấp thể loại (ví dụ: apple_music|zingmp3|discogs).
        4. Tính toán độ tin cậy (HIGH, MEDIUM, LOW, 0):
           - HIGH: Nếu có >= 2 nguồn độc lập, hoặc có track-level từ nguồn uy tín (Apple Music, Zing MP3, Discogs, Last.fm).
           - MEDIUM: Nếu có 1 nguồn track-level.
           - LOW: Nếu chỉ có web search snippet.
           - 0: Nếu không tìm thấy.
        Trả về tuple: (genre, source, status, confidence)
        """
        valid_evidences = [ev for ev in evidences if ev and ev.genre and validate_genre(ev.genre)]
        if not valid_evidences:
            return "", "", "NOT_FOUND", "0"

        # Định nghĩa thứ tự ưu tiên của các nguồn uy tín
        source_priority = {
            "apple_music": 1,
            "discogs": 1,
            "lastfm": 1,
            "zingmp3": 1,
            "musicbrainz": 2,
            "nhaccuatui": 2,
            "nhac_vn": 2,
            "shazam": 2,
            "allmusic": 2,
            "qobuz": 2,
            "youtube": 3,
            "general_web": 4,
            "web_search": 4,
        }

        # Sắp xếp các chứng cứ theo độ ưu tiên nguồn và loại chứng cứ
        def ev_sort_key(ev: Evidence):
            prio = source_priority.get(ev.source, 5)
            type_prio = 0 if ev.evidence_type == "track_level" else 1
            return (type_prio, prio)

        sorted_evs = sorted(valid_evidences, key=ev_sort_key)

        collected_genres: List[str] = []
        source_names: List[str] = []

        for ev in sorted_evs:
            if ev.source not in source_names:
                source_names.append(ev.source)

            # Phân tách và chuẩn hóa từng nhãn con
            raw_parts = re.split(r"[,;/\|\+&]+", ev.genre)
            for part in raw_parts:
                norm_part = normalize_single_label(part)
                if norm_part and validate_genre_label(norm_part):
                    if norm_part not in collected_genres:
                        collected_genres.append(norm_part)

        if not collected_genres:
            return "", "", "NOT_FOUND", "0"

        combined_genre = "|".join(collected_genres)
        combined_sources = "|".join(source_names)

        # Tính toán độ tin cậy (Confidence)
        num_sources = len(source_names)
        has_top_source = any(
            ev.evidence_type == "track_level" and ev.source in {"apple_music", "discogs", "lastfm", "zingmp3"}
            for ev in valid_evidences
        )
        has_track_level = any(ev.evidence_type == "track_level" for ev in valid_evidences)

        if num_sources >= 2 or has_top_source:
            confidence = "HIGH"
        elif has_track_level:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return combined_genre, combined_sources, "FOUND", confidence

    # ==========================================
    # TÌM KIẾM ĐỒNG THỜI TOÀN BỘ CÁC NGUỒN (CONCURRENT MULTI-SOURCE SEARCH)
    # ==========================================
    def search_all_concurrent(
        self,
        title: str,
        singer: str,
        zing_id: Optional[str] = None,
        max_workers: int = 8,
    ) -> Tuple[str, str, str, str, List[Dict[str, Any]]]:
        """
        Tìm kiếm đồng thời (concurrent) trên TẤT CẢ các nguồn:
        - Last.fm API
        - Apple Music (iTunes Search API)
        - Discogs Database Search API
        - Zing MP3 (Autocomplete API + LD-JSON)
        - MusicBrainz API
        - NhacCuaTui, Nhac.vn (Targeted Web Search)
        - Shazam, AllMusic, Qobuz, YouTube (Targeted Web Search)
        Và tổng hợp đa thể loại (multi-genre aggregation) cho bài hát.
        """
        tasks = {
            "apple_music": lambda: self.search_apple_music(title, singer),
            "discogs": lambda: self.search_discogs(title, singer),
            "lastfm": lambda: self.search_lastfm(title, singer),
            "zingmp3": lambda: self.search_zingmp3(title, singer, zing_id=zing_id),
            "musicbrainz": lambda: self.search_musicbrainz(title, singer),
            "nhaccuatui": lambda: self.search_platform_via_web("nhaccuatui.com", "nhaccuatui", title, singer),
            "nhac_vn": lambda: self.search_platform_via_web("nhac.vn", "nhac_vn", title, singer),
            "shazam": lambda: self.search_platform_via_web("shazam.com", "shazam", title, singer),
            "allmusic": lambda: self.search_platform_via_web("allmusic.com", "allmusic", title, singer),
            "qobuz": lambda: self.search_platform_via_web("qobuz.com", "qobuz", title, singer),
            "youtube": lambda: self.search_platform_via_web("youtube.com", "youtube", title, singer),
        }

        evidences: List[Evidence] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_source = {executor.submit(fn): name for name, fn in tasks.items()}
            for future in concurrent.futures.as_completed(future_to_source):
                src_name = future_to_source[future]
                try:
                    ev = future.result()
                    if ev and ev.genre and validate_genre(ev.genre):
                        evidences.append(ev)
                        logger.info("[WEB] source=%s genre=%s confidence=%s", ev.source, ev.genre, ev.evidence_type)
                except Exception as e:
                    logger.debug("[CONCURRENT_ERR] %s: %s", src_name, e)

        # Nếu các nguồn chuyên biệt chưa tìm thấy, fallback sang general web search
        if not evidences:
            ev_gen = self.search_general_web(title, singer)
            if ev_gen and validate_genre(ev_gen.genre):
                evidences.append(ev_gen)
                logger.info("[WEB] source=web_search genre=%s confidence=LOW", ev_gen.genre)

        genre, source, status, confidence = self.aggregate_evidence(evidences)
        evidence_dicts = [ev.to_dict() for ev in evidences]

        return genre, source, status, confidence, evidence_dicts

    # ==========================================
    # TIẾN TRÌNH TÌM KIẾM THEO CASCADE
    # ==========================================
    def search_cascade(
        self,
        title: str,
        singer: str,
        zing_id: Optional[str] = None,
        source_mode: str = "all",
    ) -> Tuple[str, str, str, str, List[Dict[str, Any]]]:
        """
        Nếu source_mode == 'all', thực hiện tìm kiếm đồng thời (concurrent) tất cả các nguồn
        và tổng hợp đa thể loại. Nếu chọn một nguồn cụ thể, chỉ truy vấn nguồn đó.
        """
        if source_mode == "all":
            return self.search_all_concurrent(title, singer, zing_id=zing_id)

        evidences: List[Evidence] = []

        if source_mode in {"lastfm"}:
            ev = self.search_lastfm(title, singer)
            if ev:
                evidences.append(ev)
        elif source_mode in {"apple"}:
            ev = self.search_apple_music(title, singer)
            if ev:
                evidences.append(ev)
        elif source_mode in {"discogs"}:
            ev = self.search_discogs(title, singer)
            if ev:
                evidences.append(ev)
        elif source_mode in {"musicbrainz"}:
            ev = self.search_musicbrainz(title, singer)
            if ev:
                evidences.append(ev)
        elif source_mode in {"vietnam"}:
            ev_zing = self.search_zingmp3(title, singer, zing_id=zing_id)
            if ev_zing:
                evidences.append(ev_zing)
            ev_nct = self.search_platform_via_web("nhaccuatui.com", "nhaccuatui", title, singer)
            if ev_nct:
                evidences.append(ev_nct)
            ev_nhacvn = self.search_platform_via_web("nhac.vn", "nhac_vn", title, singer)
            if ev_nhacvn:
                evidences.append(ev_nhacvn)
        elif source_mode in {"web"}:
            ev_gen = self.search_general_web(title, singer)
            if ev_gen:
                evidences.append(ev_gen)

        genre, source, status, confidence = self.aggregate_evidence(evidences)
        evidence_dicts = [ev.to_dict() for ev in evidences]

        return genre, source, status, confidence, evidence_dicts
