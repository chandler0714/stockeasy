#!/bin/zsh
cd "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print "请先按 README.md 中的快速开始步骤安装依赖。"
  read -k 1 "?按任意键关闭…"
  exit 1
fi
exec .venv/bin/python -m streamlit run app.py
