.PHONY: install test inspect discover run validate report clean

install:
	python -m pip install -e .

test:
	python -m pytest tests/ -v

inspect:
	python -m music_dataset inspect

discover:
	python -m music_dataset discover --dry-run

run:
	python -m music_dataset run --dry-run

validate:
	python -m music_dataset validate

report:
	python -m music_dataset report

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
