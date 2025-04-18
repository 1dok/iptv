import requests
import os
import subprocess

# ✅ 设置是否启用分辨率 + 下载速度过滤
enable_filter = False  # False：只判断能否访问；True：加上画质和带宽检测

min_speed_bytes = 1 * 1024 * 1024  # 1MB/s
min_width = 1280
min_height = 720
max_links_total = 1000  # 最多处理多少条流（防止超时）

sources_file = "sources.txt"
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

def is_ipv4(url):
    return '://' in url and not any(ipv6 in url for ipv6 in ['[', '::'])

# ✅ 检测函数：根据设置判断是否检测画质和速度
def test_stream(url):
    try:
        if not enable_filter:
            with requests.get(url, stream=True, timeout=5) as r:
                chunk = next(r.iter_content(1024))
                if len(chunk) > 0:
                    return True
                return "链接无响应"

        # ffprobe 检查分辨率
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

# ✅ 主流程：读取 M3U 并处理所有流
filtered = []
skipped = []
stream_count = 0

with open(sources_file, 'r', encoding='utf-8') as f:
    lines = f.read().splitlines()

for i in range(len(lines)):
    if lines[i].startswith("#EXTINF") and i + 1 < len(lines):
        info = lines[i]
        url = lines[i + 1].strip()
        if not url.startswith("http") or not is_ipv4(url):
            continue

        print(f"\n🎯 检测流: {url}")
        result = test_stream(url)
        print(f"  → 结果: {result}")

        if result is True:
            filtered.append(f"{info}\n{url}")
        else:
            skipped.append(f"{info}\n{url}\n# 原因: {result}\n")

        stream_count += 1
        if stream_count >= max_links_total:
            print("🚫 达到最大检测数量限制，提前结束。")
            break

# ✅ 写入结果
with open(os.path.join(output_dir, "filtered.m3u"), "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(filtered) if filtered else "# 无符合条件的直播源\n")

with open(os.path.join(output_dir, "skipped.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(skipped) if skipped else "# 所有直播源检测失败\n")

# ✅ 最终输出
print(f"\n✅ 合格源写入: {len(filtered)} 条")
print(f"🚫 被跳过源: {len(skipped)} 条")
print("📁 已写入 output/filtered.m3u 和 output/skipped.txt")
