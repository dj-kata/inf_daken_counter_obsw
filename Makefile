wuv=/mnt/c/Users/katao/.local/bin/uv.exe
main_file_name=notes_counter
project_name=inf_daken_counter
target=$(project_name)/.built  # timestampファイルにすることで連続でmakeできないように対策
target_zip=$(project_name).zip
prepared=$(project_name)/.prepared
srcs=$(wildcard *.py) $(wildcard *.pyw) $(wildcard src/*.py) $(wildcard misc/*.py)
html_files=$(wildcard template/*.html) $(wildcard template/*.css) $(wildcard template/*.js)
version=$(shell head -n1 version.txt)
ZIP ?= 7z a -tzip -mx=1 -mmt=on
SYNC_DEST ?= /mnt/d/bin/YouTubeLive

.PHONY: all top build-sync sync dist clean test

all: $(target_zip)
top: $(target)

# 共通の準備が完了してから、ZIP作成と同期を並列実行する。
build-sync:
	+$(MAKE) -j2 $(target_zip) sync

sync: $(prepared)
	rsync -av $(project_name) "$(SYNC_DEST)"

$(target_zip): $(prepared)
	@rm -rf $(target_zip)
	$(ZIP) $(target_zip) $(project_name)

$(prepared): $(target) $(html_files) version.txt songinfo.infdc
	@rm -rf $(project_name)/tmp
	@cp version.txt $(project_name)
	@cp -a template $(project_name)
	@mkdir -p $(project_name)/infnotebook
	@cp -a infnotebook/resources $(project_name)/infnotebook/
	@cp songinfo.infdc $(project_name)
	@rm -rf $(project_name)/log
	@rm -rf $(project_name)/*.json
	@touch $(prepared)

$(target): $(srcs) pyproject.toml uv.lock
	@rm -rf $(project_name)
	@$(wuv) run setup.py build
	@cp songinfo.infdc $(project_name)
	@echo "不要なファイルを削除中..."

# 	# Tcl/Tk関連
# 	@rm -rf $(project_name)/share/tcl8.6/tzdata
# 	@rm -rf $(project_name)/share/tcl8.6/msgs
# 	@rm -rf $(project_name)/share/tk8.6/msgs
# 	@rm -rf $(project_name)/share/tcl8.6/encoding  # ASCIIとUTF-8以外不要なら

# 	# Python関連
# 	@find $(project_name) -name "*.pyc" -delete
# 	@find $(project_name) -name "__pycache__" -type d -delete
# 	@find $(project_name) -name "*.pyo" -delete
# 	# テスト/ドキュメント
# 	@find $(project_name) -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
# 	@find $(project_name) -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
	@touch $(target)

dist: 
	@cp -a html to_bin/
	@cp -a version.txt to_bin/
	@cp -a $(project_name)/*.exe to_bin/

clean:
	@rm -rf $(target)
	@rm -rf __pycache__

test:
	@$(wuv) run python $(main_file_name).pyw
