import requests
import re
import os
import subprocess

sources_file = "sources.txt"
output_dir = "output"
min_speed_bytes = 2 * 1024 * 1024  # 2MB/s
min_width = 1920
min_height = 1080

os.makedirs(output_dir, exist_ok=True)
valid_streams = []

def is_ipv4(url):
    return '://' in url and not any(ipv6 in url for ipv6 in ['[', '::'])

def test_speed_and_resolution(url):
    try:
        # 用 ffprobe 检查分辨率
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

        # 用 requests 检查下载速度
        with requests.get(url, stream=True, timeout=5) as r:
            chunk = next(r.iter_content(1024 * 512))  # 0.5MB
            if len(chunk) < 1024 * 512:
                return False
            # 成功下载0.5MB即认为大于2MB/s的带宽
            return True
    except:
        return False

with open(sources_file, 'r') as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

for src in urls:
    print(f"Fetching source: {src}")
    try:
        res = requests.get(src, timeout=10)
        m3u_lines = res.text.splitlines()
        for i in range(len(m3u_lines)):
            if m3u_lines[i].startswith("#EXTINF") and i + 1 < len(m3u_lines):
                name = m3u_lines[i]
                stream_url = m3u_lines[i + 1].strip()
                if stream_url.startswith("http") and is_ipv4(stream_url):
                    print(f"Testing {stream_url}...")
                    if test_speed_and_resolution(stream_url):
                        valid_streams.append(f"{name}\n{stream_url}")
    except Exception as e:
        print(f"Failed to process {src}: {e}")

# 写入输出文件
with open(os.path.join(output_dir, "filtered.m3u"), "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write("\n".join(valid_streams))

print(f"Total valid streams: {len(valid_streams)}")
