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

# 读取频道关键词
with open(demo_file, 'r', encoding='utf-8') as f:
    keywords = [line.strip().lower() for line in f if line.strip() and not line.startswith("#") and "genre" not in line]

def is_ipv4(url):
    return '://' in url and not any(ipv6 in url for ipv6 in ['[', '::'])

# 返回 True 表示合格，其他返回字符串表示失败原因
def test_stream(url):
    try:
        # 检查分辨率
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

        # 检查下载速度
        with requests.get(url, stream=True, timeout=5) as r:
            chunk = next(r.iter_content(1024 * 512))
            if len(chunk) < 1024 * 512:
                return "速度过慢"
            return True
    except Exception as e:
        return f"异常：{e}"

# 收集符合频道关键词的候选源
candidates = defaultdict(list)
filtered = []
skipped = []

with open(sources_file, 'r', encoding='utf-8') as f:
    src_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

for src in src_urls:
    print(f"📥 正在抓取源: {src}")
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
        print(f"⚠️ 源获取失败: {e}")

# 测试每个候选流
for kw, streams in candidates.items():
    print(f"🔍 正在测试频道: {kw}（共 {len(streams)} 条）")
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

# 写入结果
with open(os.path.join(output_dir, "filtered.m3u"), "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(filtered))

with open(os.path.join(output_dir, "skipped.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(skipped))

print(f"\n✅ 合格直播源数量: {len(filtered)}")
print(f"🚫 被过滤直播源数量: {len(skipped)}（详情见 output/skipped.txt）")
