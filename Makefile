.PHONY: run build test ost

# The project lives in track_2a/ (template layout); every target runs there, in Docker.
run build test ost:
	$(MAKE) -C track_2a $@
