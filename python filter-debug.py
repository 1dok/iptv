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

def clean(s):
    return re.sub(r'[^a-zA-Z0-9]', '', s.lower())

with open(demo_file, 'r', encoding='utf-8') as f:
    raw_keywords = [line.strip() for line in f if line.strip() and not line.startswith("#") and "genre" not in line]
    keywords = [clean(k) for k in raw_keywords]

def is_ipv4(url):
    return '://' in url and not any(ipv6 in url for ipv6 in ['[', '::'])

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
match_count = defaultdict(int)
filtered = []
skipped = []

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
                        match_count[kw] += 1
                        if len(candidates[kw]) < max_links_per_channel:
                            candidates[kw].append((info_line, url))
                        break
    except Exception as e:
        print(f"⚠️ 源抓取失败: {e}")

# 测试流
for kw, streams in candidates.items():
    print(f"\n🔍 测试频道关键词: {kw}（候选 {len(streams)} 条）")
    count = 0
    for info, url in streams:
        print(f"  → 测试链接: {url}")
        print(f"    标题: {info}")
        result = test_stream(url)
        print(f"    测试结果: {result} ({type(result)})")
        if result is True:
            filtered.append(f"{info}\n{url}")
            count += 1
        else:
            skipped.append(f"{info}\n{url}\n# 原因: {result}\n")
        if count >= max_links_per_channel:
            break

# 写入文件
filtered_file = os.path.join(output_dir, "filtered.m3u")
skipped_file = os.path.join(output_dir, "skipped.txt")

with open(filtered_file, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    if filtered:
        f.write("\n".join(filtered))
    else:
        f.write("# 无符合条件的直播源\n")

with open(skipped_file, "w", encoding="utf-8") as f:
    if skipped:
        f.write("\n".join(skipped))
    else:
        f.write("# 所有频道检测均未命中或测速失败\n")

# 总结输出
print("\n📊 匹配频道统计：")
for raw, kw in zip(raw_keywords, keywords):
    print(f"  - {raw} 匹配流数: {match_count[kw]}")

print(f"\n✅ 合格源写入: {len(filtered)} 条")
print(f"🚫 不合格写入: {len(skipped)} 条")
print("📁 已写入 output/filtered.m3u 和 output/skipped.txt")
