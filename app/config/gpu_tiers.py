"""GPU tier tables used by runtime detection."""

GPU_TIERS = {
    4: ("a5d", "p1d", "高端"),
    3: ("a3d", "a6d", "中端"),
    2: ("a1d", "a3d", "入门"),
    1: ("3k", "1k", "低端"),
}

GPU_TIER_PATTERNS = [
    (r"RTX\s*50[789]0|RTX\s*5090|RTX\s*4090|RTX\s*4080|RTX\s*3090|A100|H100|A6000", 4),
    (r"RTX\s*40[67]0|RTX\s*3080|RTX\s*3070|RTX\s*2080|RTX\s*2070|GTX\s*1080\s*Ti|RTX\s*A[45]000", 4),
    (r"RTX\s*4060|RTX\s*4050|RTX\s*3060|RTX\s*3050|RTX\s*2060|RTX\s*2050|GTX\s*1080(?!\s*Ti)", 3),
    (r"GTX\s*1070|GTX\s*1660|GTX\s*1650|RTX\s*A2000", 3),
    (r"GTX\s*1060|GTX\s*1050|GTX\s*980|GTX\s*970|GTX\s*960|MX\s*[345]\d0", 2),
    (r"GTX\s*950|GTX\s*750|GT\s*1030|GT\s*730|GT\s*710|MX\s*[12]\d0", 1),
]
