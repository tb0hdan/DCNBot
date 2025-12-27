all: lint mypy test

lint:
	@pylint -r y -j 0 llmc/

mypy:
	@mypy llmc/

test:
	@pytest llmc/
