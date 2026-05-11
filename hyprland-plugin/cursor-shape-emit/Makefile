PLUGIN_NAME = cursor-shape-emit

CXX      ?= g++
CXXFLAGS  = -std=c++26 -fPIC -O2 \
            $(shell pkg-config --cflags hyprland 2>/dev/null || echo "-I/usr/include/hyprland") \
            -I/usr/include/hyprland/src \
            -Wno-deprecated-declarations
LDFLAGS   =

OUT = $(PLUGIN_NAME).so
OBJ = main.o outline.o

all: $(OUT)

$(OUT): $(OBJ)
	$(CXX) $(CXXFLAGS) -shared $(LDFLAGS) -o $@ $^

main.o: main.cpp outline.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

outline.o: outline.cpp outline.hpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

install: $(OUT)
	install -Dm755 $(OUT) "$(HOME)/.local/share/hyprland/plugins/$(OUT)"

clean:
	rm -f $(OUT) $(OBJ) tests/test_outline tests/test_outline_asan

# --- Tests ------------------------------------------------------------------

TEST_CXXFLAGS = -std=c++26 -O2 -fno-omit-frame-pointer -Wall -Wextra \
                $(shell pkg-config --cflags cairo)
TEST_LDFLAGS  = $(shell pkg-config --libs cairo)

tests/test_outline: tests/test_outline.cpp outline.cpp outline.hpp
	$(CXX) $(TEST_CXXFLAGS) tests/test_outline.cpp outline.cpp \
	    -o $@ $(TEST_LDFLAGS)

test: tests/test_outline
	@./tests/test_outline

regen-golden: tests/test_outline
	@./tests/test_outline --regen-golden

# AddressSanitizer + UndefinedBehaviorSanitizer build of the unit tests.
# Catches OOB reads, leaks, UB. ~2x slower runtime; small input sizes so trivial.
tests/test_outline_asan: tests/test_outline.cpp outline.cpp outline.hpp
	$(CXX) $(TEST_CXXFLAGS) -fsanitize=address,undefined -g \
	    tests/test_outline.cpp outline.cpp \
	    -o $@ $(TEST_LDFLAGS) -fsanitize=address,undefined

test-asan: tests/test_outline_asan
	@ASAN_OPTIONS=detect_leaks=1 ./tests/test_outline_asan

# Integration smoke test against a live Hyprland.
smoke: $(OUT)
	@bash tests/integration_smoke.sh

# Lint the smoke script if shellcheck is installed.
smoke-lint:
	@if command -v shellcheck >/dev/null 2>&1; then \
	    shellcheck tests/integration_smoke.sh; \
	else \
	    echo "shellcheck not installed — skipping"; \
	fi

# Run every check: unit, sanitized, smoke, lint.
check: test test-asan smoke-lint smoke

.PHONY: all install clean test regen-golden test-asan smoke smoke-lint check
