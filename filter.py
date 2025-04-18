import requests
import re
import os
import subprocess
from collections import defaultdict

sources_file = "sources.txt"
demo_file = "demo.txt"
output_dir = "output"
min_speed_bytes = 1 * 1024 * 1024  # 1MB/s
min_width = 1280
min_height = 720
max_links_per_channel = 10

os.makedirs(output_dir, exist_ok=True)

# 加载频道关键词，并标准化为简化匹配
def clean(s):
    return re.sub(r'[^a-zA-Z0-9]', '', s.lower())

with open(demo_file, 'r', encoding='utf-8') as f:
    raw_keywords = [line.strip() for line in f if line.strip() and not line.startswith("#") and "genre" not in line]
    keywords = [clean(k) for k in raw_keywords]

# IPv4 判断
def is_ipv4(url):
    return '://' in url and not any(ipv6 in url for ipv6 in ['[', '::'])

# 检测分辨率和下载速度
def test_stream(url):
    try:
        ffprobe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0", url
        ]
        result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        output = result.stdout.decode().strip()
        if not output:
            return "无法获取分辨率"
        width, height = map(int, output.split(','))
        if width < min_width or height < min_height:
            return f"分辨率过低：{width}x{height}"

        with requests.get(url, stream=True, timeout=5) as r:
            chunk = next(r.iter_content(1024 * 512))
            if len(chunk) < 1024 * 512:
                return "速度过慢"
            return True
    except Exception as e:
        return f"异常：{e}"

candidates = defaultdict(list)
filtered = []
skipped = []

# 抓取源并解析频道
with open(sources_file, 'r', encoding='utf-8') as f:
    src_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

for src in src_urls:
    print(f"\n📥 正在抓取源: {src}")
    try:
        res = requests.get(src, timeout=10)
        lines = res.text.splitlines()
        print(f"✅ 获取成功，共 {len(lines)} 行")

        for i in range(len(lines)):
            if lines[i].startswith("#EXTINF") and i + 1 < len(lines):
                info_line = lines[i]
                url = lines[i + 1].strip()
                if not url.startswith("http") or not is_ipv4(url):
                    continue

                cleaned_info = clean(info_line)
                for idx, kw in enumerate(keywords):
                    if kw in cleaned_info:
                        print(f"🎯 命中关键词: {raw_keywords[idx]} → {info_line.strip()}")
                        if len(candidates[kw]) < max_links_per_channel:
                            candidates[kw].append((info_line, url))
                        break
    except Exception as e:
        print(f"⚠️ 抓取失败: {e}")

# 测试每个候选
for kw, streams in candidates.items():
    print(f"\n🔍 测试频道关键词: {kw}（候选 {len(streams)} 个）")
    count = 0
    for info, url in streams:
        print(f"  → 测试: {url}")
        result = test_stream(url)
        if result is True:
            filtered.append(f"{info}\n{url}")
            count += 1
        else:
            skipped.append(f"{info}\n{url}\n# 原因: {result}\n")
        if count >= max_links_per_channel:
            break

# 输出结果
with open(os.path.join(output_dir, "filtered.m3u"), "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(filtered))

with open(os.path.join(output_dir, "skipped.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(skipped))

print(f"\n✅ 合格源数量: {len(filtered)}")
print(f"🚫 被过滤源数量: {len(skipped)}（见 output/skipped.txt）")
