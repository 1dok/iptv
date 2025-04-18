name: Auto Filter IPTV

on:
  schedule:
    - cron: '0 3 * * *'  # 每天 UTC 3点运行（北京时间11点）
  workflow_dispatch:      # 支持手动触发

jobs:
  filter:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: 3.11

      - name: Install ffmpeg
        run: sudo apt update && sudo apt install -y ffmpeg

      - name: Install Python dependencies
        run: pip install requests

      - name: Run filtering script
        run: python filter.py

      - name: Commit filtered output
        run: |
          git config --global user.name "GitHub Actions"
          git config --global user.email "actions@github.com"
          git add output/filtered.m3u
          git commit -m "daily filtered.m3u update" || echo "No changes to commit"
          git push
