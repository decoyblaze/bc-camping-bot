#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python3 -m bc_camping_bot.gui
