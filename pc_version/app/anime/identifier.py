import re
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

class MediaIdentifier:
    """Identifies media title, episode, season, year, and type from file paths."""
    
    def identify_media_info(self, file_path: str) -> Dict[str, Any]:
        """Extract detailed media info from filename."""
        raw_name = Path(file_path).stem
        
        # 1. Strip ReleaseGroup [XXX] at start
        cleaned = re.sub(r'^\[.*?\]\s*', '', raw_name)
        
        # 2. TV Series: S01E05 or S1E5
        s_e_match = re.search(r'(?i)\b[sS](\d+)[eE](\d+)\b', cleaned)
        if s_e_match:
            title = cleaned[:s_e_match.start()]
            return {
                "title": self.clean_title(title),
                "episode": s_e_match.group(2),
                "season": s_e_match.group(1),
                "media_type": "tv",
                "year": None
            }
            
        # 3. TV Series: 1x05 or 01x05
        x_match = re.search(r'(?i)\b(\d{1,2})x(\d{1,2})\b', cleaned)
        if x_match:
            title = cleaned[:x_match.start()]
            return {
                "title": self.clean_title(title),
                "episode": x_match.group(2),
                "season": x_match.group(1),
                "media_type": "tv",
                "year": None
            }
            
        # 4. Anime style _E05 or - E05
        e_match = re.search(r'(?i)[_ -]E(\d+)\b', cleaned)
        if e_match:
            title = cleaned[:e_match.start()]
            return {
                "title": self.clean_title(title),
                "episode": e_match.group(1),
                "season": None,
                "media_type": "anime",
                "year": None
            }
            
        # 5. Anime dash style: ' - 05'
        dash_match = re.search(r'\s+-\s+(\d+)\b', cleaned)
        if dash_match:
            title = cleaned[:dash_match.start()]
            return {
                "title": self.clean_title(title),
                "episode": dash_match.group(1),
                "season": None,
                "media_type": "anime",
                "year": None
            }

        # 6. Movie: Year in title (1920-2099)
        year_match = re.search(r'[\s\.\(\[\-_](19\d\d|20\d\d)[\s\.\)\]\-_]', cleaned)
        if year_match:
            title = cleaned[:year_match.start()]
            return {
                "title": self.clean_title(title),
                "episode": "",
                "season": None,
                "media_type": "movie",
                "year": year_match.group(1)
            }
            
        # 7. Fallback
        return {
            "title": self.clean_title(cleaned),
            "episode": "",
            "season": None,
            "media_type": "unknown",
            "year": None
        }

    def identify_from_path(self, file_path: str) -> Tuple[str, str]:
        """Extract clean title and episode string from filename (backwards compatibility)."""
        info = self.identify_media_info(file_path)
        return info["title"], info["episode"]

    def clean_title(self, title: str) -> str:
        """Removes brackets, resolution tags, codecs, scene tags, clean delimiters."""
        # Replace dots and underscores with spaces if it looks like a scene release
        if "." in title and " " not in title:
            title = title.replace(".", " ")
        title = title.replace("_", " ")

        # Remove trailing resolution tags like (1080p), [720p], 2160p, 4k
        title = re.sub(r'(?i)[\[\(]?\b(2160p|1080p|720p|480p|4k|uhd)\b[\]\)]?', '', title)
        
        # Remove audio and video format tags
        title = re.sub(r'(?i)\b(bluray|bdrip|brrip|web-?dl|webrip|hdtv|dvdrip|x264|x265|hevc|h\.?264|h\.?265|10bit|aac|ddp5\.1|ac3|dts)\b.*', '', title)
        
        # Remove any remaining brackets and parentheses
        title = re.sub(r'[\[\(].*?[\]\)]', '', title)
        
        # Remove trailing scene release group tags e.g. -YTS, -PSA, -EVO
        title = re.sub(r'-[a-zA-Z0-9]+$', '', title)
        
        # Collapse multiple spaces and strip trailing hyphens
        title = re.sub(r'\s+', ' ', title)
        title = re.sub(r'[-\s]+$', '', title).strip()
        return title

# Backward compatibility alias
AnimeIdentifier = MediaIdentifier

