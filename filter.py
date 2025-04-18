import requests
import re
import os
import subprocess
from collections import defaultdict

sources_file = "sources.txt"
demo_file = "demo.txt"
output_dir = "output"
min_speed_bytes = 1 * 1024 * 1024  # 2MB/s
min_width = 1920
min_height = 1080
max_links_per_channel = 10

os.makedirs(output_dir, exist_ok=True)

# 读取感兴趣频道关键词
with open(demo_file, 'r', encoding='utf-8') as f:
    keywords = [line.strip().lower() for line in f if line.strip()]

# 是否 IPv4 地址
def is_ipv4(url):
    return '://' in url and not any(ipv6 in url for ipv6 in ['[', '::'])

# 检查分辨率和下载速度
def test_stream(url):
    try:
        ffprobe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0", url
        ]
        result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        output = result.stdout.decode().strip()
        if not output:
            return False
        width, height = map(int, output.split(','))
        if width < min_width or height < min_height:
            return False

        with requests.get(url, stream=True, timeout=5) as r:
            chunk = next(r.iter_content(1024 * 512))
            if len(chunk) < 1024 * 512:
                return False
            return True
    except:
        return False

# 存储符合关键词的候选源
candidates = defaultdict(list)

with open(sources_file, 'r', encoding='utf-8') as f:
    src_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

for src in src_urls:
    print(f"Fetching source: {src}")
    try:
        res = requests.get(src, timeout=10)
        lines = res.text.splitlines()
        for i in range(len(lines)):
            if lines[i].startswith("#EXTINF") and i + 1 < len(lines):
                info_line = lines[i]
                url = lines[i + 1].strip()
                if not url.startswith("http") or not is_ipv4(url):
                    continue
                lower_info = info_line.lower()
                for kw in keywords:
                    if kw in lower_info:
                        if len(candidates[kw]) < max_links_per_channel:
                            candidates[kw].append((info_line, url))
                        break
    except Exception as e:
        print(f"Error fetching from {src}: {e}")

# 过滤有效流并写入输出
filtered = []

for kw, streams in candidates.items():
    print(f"Testing {len(streams)} streams for keyword '{kw}'...")
    count = 0
    for info, url in streams:
        print(f"  → Testing: {url}")
        if test_stream(url):
            filtered.append(f"{info}\n{url}")
            count += 1
        if count >= max_links_per_channel:
            break

with open(os.path.join(output_dir, "filtered.m3u"), "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(filtered))

print(f"✅ Done. Total valid streams: {len(filtered)}")
