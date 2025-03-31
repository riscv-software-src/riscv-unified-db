RATIFIED_EXTENSIONS := "rv*"
UNRATIFIED_EXTENSIONS := "unratified/rv*"

default: yaml_all

.PHONY: yaml_all
yaml_all: yaml_ratified yaml_unratified

.PHONY: yaml_ratified
yaml_ratified:
	@python3 db.py -yaml $(RATIFIED_EXTENSIONS)

.PHONY: yaml_unratified
yaml_unratified:
	@python3 db.py -yaml $(UNRATIFIED_EXTENSIONS)

.PHONY: clean
clean:
	rm -rf yaml_output
