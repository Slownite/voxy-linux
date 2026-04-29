# Maintainer: Samuel Diop <snfdiop@gmail.com>
pkgname=voxy-linux
pkgver=0.1.0
pkgrel=1
pkgdesc="Local offline voice dictation for Linux (push-to-talk, faster-whisper)"
arch=('x86_64' 'aarch64')
url="https://github.com/Slownite/voxy-linux"
license=('MIT')
depends=('python' 'portaudio' 'python-pip')
optdepends=(
    'xclip: X11 clipboard support'
    'xdotool: X11 paste simulation'
    'wl-clipboard: Wayland clipboard support'
    'ydotool: Wayland paste simulation'
)
makedepends=('python-build' 'python-installer' 'python-wheel')
source=("https://files.pythonhosted.org/packages/source/v/$pkgname/$pkgname-$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
    cd "$srcdir/$pkgname-$pkgver"
    python -m build --wheel --no-isolation
}

package() {
    cd "$srcdir/$pkgname-$pkgver"
    python -m installer --destdir="$pkgdir" dist/*.whl
}
