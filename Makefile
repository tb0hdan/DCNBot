all: lint mypy test

lint:
	@pylint -r y -j 0 dcnbot/

mypy:
	@mypy dcnbot/

test:
	@pytest dcnbot/
