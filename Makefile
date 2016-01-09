pythondir = $(shell python -c "from distutils import sysconfig; print sysconfig.get_python_lib()")

all clean:
	$(MAKE) -C pongc $@

install: all
	./setup.py fix_manifest
	sed -i /^pongc/d MANIFEST
	./setup.py install --prefix=$(DESTDIR)/usr
	for i in __init__.py _pongc.so pongc.py; do \
		install -m 644 -D pongc/$$i $(DESTDIR)/$(pythondir)/pongc/$$i; \
	done
