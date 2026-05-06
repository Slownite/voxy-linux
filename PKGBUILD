# Maintainer: Samuel Diop <snfdiop@gmail.com>
pkgname=voxy-linux
pkgver=0.1.0
pkgrel=1
pkgdesc="Local offline voice dictation for Linux (push-to-talk, faster-whisper)"
arch=('x86_64' 'aarch64')
url="https://github.com/samanddima/voxy-linux"
license=('MIT')
# Python deps bundled in /opt/voxy-linux venv — no AUR packages required.
depends=(
    'python'
    'portaudio'
    'tk'
)
optdepends=(
    'xclip: X11 clipboard support'
    'xdotool: X11 paste simulation'
    'wl-clipboard: Wayland/KDE clipboard support'
    'ydotool: Wayland text insertion (non-KDE; requires input group)'
    'gtk4: cursor overlay (Wayland)'
    'gtk4-layer-shell: cursor overlay (Wayland)'
    'python-gobject: cursor overlay'
    'python-cairo: cursor overlay'
)
makedepends=('uv')
_pyname="${pkgname//-/_}"
_wheel="${_pyname}-${pkgver}-py3-none-any.whl"
noextract=("$_wheel")
source=("$_wheel")
sha256sums=('SKIP')

package() {
    # Isolated venv at final install path — bundles all Python deps.
    python -m venv "$pkgdir/opt/$pkgname"

    uv pip install \
        --python "$pkgdir/opt/$pkgname/bin/python" \
        "$srcdir/$_wheel"

    # Strip $pkgdir prefix from shebangs so scripts work after install.
    find "$pkgdir/opt/$pkgname/bin" -type f -executable \
        -exec sed -i "s|$pkgdir||g" {} \;

    install -dm755 "$pkgdir/usr/bin"
    ln -s "/opt/$pkgname/bin/voxy" "$pkgdir/usr/bin/voxy"
}
