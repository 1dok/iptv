import requests
import os
import subprocess

# ✅ 设置是否开启分辨率/速度过滤
enable_filter = False  # True 启用严格过滤，False 只判断链接能访问

min_speed_bytes = 1 * 1024 * 1024  # 1MB/s
min_width = 1280
min_height = 720
max_links_total = 1000

sources_file = "sources.txt"
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

def is_ipv4(url):
    return '://' in url and not any(ipv6 in url for ipv6 in ['[', '::'])

# ✅ 检测直播流是否可用/合格
def test_stream(url):
    try:
        if not enable_filter:
            with requests.get(url, stream=True, timeout=5) as r:
                chunk = next(r.iter_content(1024))
                if len(chunk) > 0:
                    return True
                return "链接无响应"

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

# ✅ 自动处理源内容，支持标准 M3U 或 URL-only
def load_sources():
    streams = []
    with open(sources_file, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("#EXTM3U"):
            i += 1
            continue

        if line.startswith("#EXTINF"):
            info = line
            i += 1
            if i < len(lines):
                url = lines[i].strip()
                if url.startswith("http") and is_ipv4(url):
                    streams.append((info, url))
        elif line.startswith("http") and is_ipv4(line):
            # 非 M3U 格式 → 自动补 EXTINF
            info = "#EXTINF:-1, Unknown"
            streams.append((info, line))
        i += 1
    return streams

# ✅ 主逻辑处理
filtered = []
skipped = []
streams = load_sources()
print(f"\n📦 总共检测流数: {len(streams)} 条")

for idx, (info, url) in enumerate(streams):
    print(f"\n🔍 测试 {idx+1}/{len(streams)}: {url}")
    result = test_stream(url)
    print(f"  → 结果: {result}")
    if result is True:
        filtered.append(f"{info}\n{url}")
    else:
        skipped.append(f"{info}\n{url}\n# 原因: {result}\n")

    if len(filtered) + len(skipped) >= max_links_total:
        print("🚫 达到最大检测数量限制，提前结束")
        break

# ✅ 输出结果
filtered_file = os.path.join(output_dir, "filtered.m3u")
skipped_file = os.path.join(output_dir, "skipped.txt")

with open(filtered_file, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(filtered) if filtered else "# 无合格源")

with open(skipped_file, "w", encoding="utf-8") as f:
    f.write("\n".join(skipped) if skipped else "# 所有源都检测失败")

print(f"\n✅ 合格源数: {len(filtered)}")
print(f"🚫 跳过源数: {len(skipped)}")
print("📁 输出至 output/filtered.m3u 和 output/skipped.txt")
