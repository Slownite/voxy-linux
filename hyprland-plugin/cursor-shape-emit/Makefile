PLUGIN_NAME = cursor-shape-emit

CXX      ?= g++
CXXFLAGS  = -std=c++26 -shared -fPIC -O2 \
            $(shell pkg-config --cflags hyprland 2>/dev/null || echo "-I/usr/include/hyprland") \
            -I/usr/include/hyprland/src \
            -Wno-deprecated-declarations
LDFLAGS   =

SRC = main.cpp
OUT = $(PLUGIN_NAME).so

all: $(OUT)

$(OUT): $(SRC)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $<

install: $(OUT)
	install -Dm755 $(OUT) "$(HOME)/.local/share/hyprland/plugins/$(OUT)"

clean:
	rm -f $(OUT)

.PHONY: all install clean
